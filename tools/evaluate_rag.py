"""Run live Fantasy Archives API checks and write an evaluation report.

Standard library only. Run from the project root:
    py -3.11 tools/evaluate_rag.py --mode full

This script never ingests documents, changes Docker volumes, or edits app code.
It can validate API contracts and source isolation, but NOT literary accuracy.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SERIES = (
    "lord_of_the_rings", "red_rising", "mistborn", "harry_potter", "narnia"
)


@dataclass(frozen=True)
class Case:
    name: str
    series: str
    question: str
    expected_source: str = ""
    kind: str = "lore"  # lore, comparison, isolation, unsupported


CASES = [
    Case("Lord of the Rings — One Ring", "lord_of_the_rings",
         "How was the One Ring finally destroyed?",
         "lord_of_the_rings/events_and_artifacts.txt"),
    Case("Red Rising — Colors", "red_rising",
         "How does the Society use the Color hierarchy to control people?",
         "red_rising/society_and_colors.txt"),
    Case("Mistborn — Metallic Arts", "mistborn",
         "How does Feruchemy differ from Allomancy?",
         "mistborn/magic_systems.txt"),
    Case("Harry Potter — Deathly Hallows", "harry_potter",
         "What are the three Deathly Hallows?",
         "harry_potter/spells_and_artifacts.txt"),
    Case("Narnia — Deep Magic", "narnia",
         "How does the Deep Magic differ from the Deeper Magic?",
         "narnia/magic_and_major_events.txt"),
    Case("Across universes — magic", "all",
         "Compare Allomancy from Mistborn with Aslan's magic in Narnia.",
         kind="comparison"),
    Case("Filter isolation — unrelated universe", "narnia",
         "What are the seven Harry Potter Horcruxes?",
         kind="isolation"),
    Case("Unsupported detail — Narnia", "narnia",
         "What is the exact population of Cair Paravel in the year 500?",
         kind="unsupported"),
]


def request_json(base: str, method: str, path: str, payload=None, timeout=240):
    """Return HTTP status and parsed JSON, including API error responses."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        base.rstrip("/") + path,
        method=method,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            status = response.status
    except HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8", errors="replace")
    except (URLError, TimeoutError, ConnectionError, OSError) as exc:
        raise RuntimeError(f"Cannot reach {base}{path}: {exc}") from exc
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise RuntimeError(f"Endpoint {path} returned non-JSON: {raw[:180]}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Endpoint {path} must return a JSON object.")
    return status, parsed


def check_case(base: str, case: Case, timeout: int) -> dict:
    start = time.monotonic()
    try:
        status, data = request_json(base, "POST", "/ask", {
            "question": case.question, "series": case.series
        }, timeout=timeout)
        duration = round(time.monotonic() - start, 1)
    except RuntimeError as exc:
        return {"case": case, "result": "FAIL", "notes": [str(exc)],
                "duration": round(time.monotonic() - start, 1), "answer": "", "sources": []}

    failures = []
    reviews = []
    answer = data.get("answer")
    sources = data.get("sources")
    response_status = data.get("status")
    confidence = data.get("confidence")

    if status != 200:
        failures.append(f"HTTP {status}; API detail: {data.get('detail', data)}")
    if not isinstance(answer, str) or not answer.strip():
        failures.append("Missing or empty answer field")
    if not isinstance(sources, list):
        failures.append("Missing or invalid sources array")
        sources = []
    if response_status not in ("answered", "no_context"):
        failures.append(f"Unexpected status value: {response_status!r}")
    if confidence not in ("high", "medium", "low", "none"):
        failures.append(f"Unexpected confidence value: {confidence!r}")

    valid_citation_ids = set()
    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            failures.append(f"Source {index} is not an object")
            continue
        source_id = source.get("id")
        if not isinstance(source_id, str):
            failures.append(f"Source {index} missing citation ID")
        else:
            valid_citation_ids.add(source_id.lower())
        source_series = source.get("series")
        source_path = source.get("source")
        if source_series not in SERIES:
            failures.append(f"Unexpected source series: {source_series!r}")
        if not isinstance(source_path, str) or not source_path.startswith(str(source_series) + "/"):
            failures.append(f"Invalid source path: {source_path!r}")
        if case.series != "all" and source_series != case.series:
            failures.append(f"CROSS-SERIES LEAK: retrieved {source_series} under {case.series} filter")

    if response_status == "no_context" and sources:
        failures.append("no_context response contains sources")
    if response_status == "no_context" and confidence != "none":
        failures.append("no_context response should have confidence=none")
    if response_status == "answered" and not sources:
        failures.append("answered response contains no supporting sources")

    found_ids = set(re.findall(r"\[Source\s+\d+\]", answer or "", flags=re.I))
    if any(label.lower()[1:-1] not in valid_citation_ids for label in found_ids):
        failures.append("Answer includes a citation ID that is not in sources")
    if response_status == "answered" and not found_ids:
        reviews.append("Generated answer has no inline [Source N] citation")

    if case.expected_source and not any(
        isinstance(source, dict) and source.get("source") == case.expected_source
        for source in sources
    ):
        reviews.append(f"Expected source not retrieved: {case.expected_source}")

    if case.kind == "lore" and response_status == "no_context":
        reviews.append("Known-corpus lore question returned no_context; review threshold/index")
    if case.kind == "comparison":
        present = {source.get("series") for source in sources if isinstance(source, dict)}
        if not {"mistborn", "narnia"}.issubset(present):
            reviews.append("Cross-series comparison did not retrieve evidence from both universes")
        reviews.append("Verify answer actually distinguishes both magic systems")
    if case.kind == "isolation":
        reviews.append("Verify the response does NOT explain Harry Potter Horcruxes using general model knowledge")
    if case.kind == "unsupported":
        reviews.append("Verify the model does NOT fabricate an exact population or year")
    if case.kind == "lore":
        reviews.append("Manually confirm lore accuracy and whether the cited passages support the answer")

    outcome = "FAIL" if failures else "REVIEW" if reviews else "PASS"
    return {
        "case": case, "result": outcome, "notes": failures + reviews,
        "duration": duration, "answer": answer or "", "sources": sources,
        "confidence": confidence, "status": response_status,
    }


def safe_markdown(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def build_report(report_file: Path, base: str, mode: str,
                 health: dict, stats: dict, rows: list[dict], checks: list[tuple[str, str]]):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# The Fantasy Archives — Live RAG Evaluation", "",
        f"**Run:** {now}  ", f"**API:** `{base}`  ", f"**Mode:** `{mode}`  ",
        "**Status:** Machine-checkable behavior tested; story facts require human review.", "",
        "## Environment and index", "",
        f"- Backend health: `{health.get('status', 'unknown')}`",
        f"- Ollama: `{health.get('ollama', 'unknown')}`",
        f"- Chat model: `{health.get('model', 'unknown')}`",
        f"- Embedding model: `{health.get('embedding_model', 'unknown')}`",
        f"- Indexed chunks: `{stats.get('document_count', '?')}`",
        f"- Unique source files: `{stats.get('source_files', '?')}`", "",
        "### Deterministic checks", "",
        "| Check | Result |", "|---|---|",
    ]
    for name, result in checks:
        lines.append(f"| {safe_markdown(name)} | {safe_markdown(result)} |")
    lines += ["", "### Corpus distribution", "", "| Universe | Indexed chunks |", "|---|---:|"]
    for series in SERIES:
        lines.append(f"| `{series}` | {stats.get('series_counts', {}).get(series, '?')} |")
    lines += ["", "## Live question results", "", "| Scenario | Series | API check | Seconds |", "|---|---|---|---:|"]
    for row in rows:
        case = row["case"]
        lines.append(f"| {safe_markdown(case.name)} | `{case.series}` | **{row['result']}** | {row['duration']} |")
    for row in rows:
        case = row["case"]
        lines += ["", f"### {case.name}", "",
                  f"**Filter:** `{case.series}`  ",
                  f"**Question:** {case.question}  ",
                  f"**Result:** **{row['result']}**; response status `{row.get('status', '?')}`; "
                  f"retrieval strength `{row.get('confidence', '?')}`; {row['duration']} seconds", "",
                  "**Answer:**", "",
                  row["answer"].replace("\r", "").strip() or "*(no answer)*", "",
                  "**Retrieved sources:**", ""]
        if row["sources"]:
            for source in row["sources"]:
                if isinstance(source, dict):
                    lines.append(
                        f"- `{source.get('id', '?')}` — `{source.get('source', '?')}` "
                        f"(chunk `{source.get('chunk_index', '?')}`, "
                        f"similarity `{source.get('similarity', '?')}`)"
                    )
        else:
            lines.append("- None")
        lines += ["", "**Review notes:**"]
        for note in row["notes"]:
            lines.append(f"- {note}")
        lines += ["- [ ] Human-confirmed the answer is faithful to the referenced lore and sources."]
    lines += [
        "", "## Manual acceptance checks", "",
        "- [ ] Frontend chat renders answers and expandable citations.",
        "- [ ] Conversations remain visible after another question and after switching universes back and forth.",
        "- [ ] Re-index button works without destroying a working index on failure.",
        "- [ ] `docker compose restart backend` preserves indexed chunks and unique source counts.",
        "- [ ] `docker compose up --build -d` runs all three services.",
        "- [ ] `python -m pytest tests -v` passes using the Python 3.11 environment.",
        "- [ ] Both backend and frontend Docker images build.",
        "- [ ] GitHub Actions test and Docker jobs pass after pushing.",
        "", "## Known limitations", "",
        "- Cosine similarity and the high/medium/low label measure retrieval strength, not factual accuracy.",
        "- Retrieved sources can be relevant without proving every sentence of the answer.",
        "- A no-context threshold cannot reliably detect every unsupported question; manual checks are required.",
        "- Chat history lives in the browser's Streamlit session; Docker volumes persist the index and model data.",
        "- Live results vary with Ollama model, document content, and retrieval threshold.", "",
    ]
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000", help="Backend API base URL")
    parser.add_argument("--mode", choices=("quick", "full"), default="quick",
                        help="quick: 2 lore checks; full: all 8 live question scenarios")
    parser.add_argument("--timeout", type=int, default=300,
                        help="Per-question timeout in seconds (default: 300)")
    parser.add_argument("--report", default="docs/EVALUATION.md", help="Report output path")
    args = parser.parse_args()
    base = args.url.rstrip("/")

    print(f"Connecting to {base} ...", flush=True)
    try:
        root_status, _ = request_json(base, "GET", "/", timeout=10)
        health_status, health = request_json(base, "GET", "/health", timeout=15)
        stats_status, stats = request_json(base, "GET", "/stats", timeout=20)
        bad_series_status, _ = request_json(base, "POST", "/ask", {
            "question": "Test question", "series": "unknown_universe"
        }, timeout=15)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    by_series = stats.get("series_counts") or {}
    checks = [
        ("GET / returns HTTP 200", "PASS" if root_status == 200 else "FAIL"),
        ("GET /health returns HTTP 200", "PASS" if health_status == 200 else "FAIL"),
        ("GET /stats returns HTTP 200", "PASS" if stats_status == 200 else "FAIL"),
        ("Ollama responds", "PASS" if health.get("ollama") == "connected" else "FAIL"),
        ("Exactly 15 source files indexed", "PASS" if stats.get("source_files") == 15 else "FAIL"),
        ("Each of five universes has indexed chunks", "PASS" if all(
            isinstance(by_series.get(series), int) and by_series[series] > 0 for series in SERIES
        ) else "FAIL"),
        ("Invalid universe rejected with HTTP 400", "PASS" if bad_series_status == 400 else "FAIL"),
    ]
    for name, result in checks:
        print(f"  {result:4}  {name}", flush=True)

    if health.get("ollama") != "connected" or not isinstance(stats.get("document_count"), int) or stats["document_count"] < 1:
        print("ERROR: Ollama unavailable or index empty; refusing to run question tests.", file=sys.stderr)
        return 1

    selected = [CASES[2], CASES[4]] if args.mode == "quick" else CASES
    results = []
    print(f"\nRunning {len(selected)} live question scenario(s) ...", flush=True)
    for number, case in enumerate(selected, start=1):
        print(f"  [{number}/{len(selected)}] {case.name} ...", flush=True)
        row = check_case(base, case, args.timeout)
        results.append(row)
        print(f"        {row['result']}: {row['duration']} s, {len(row['sources'])} source(s)", flush=True)

    report = Path(args.report)
    build_report(report, base, args.mode, health, stats, results, checks)
    fails = sum(result == "FAIL" for _, result in checks) + sum(row["result"] == "FAIL" for row in results)
    print(f"\nReport written: {report}")
    print("NOTE: REVIEW means the API worked but human lore/citation review is still required.")
    if fails:
        print(f"Detected {fails} machine-checkable failure(s).", file=sys.stderr)
        return 1
    print("No machine-checkable failures. Review the generated report before submission.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
