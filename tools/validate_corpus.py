"""Validate The Fantasy Archives text corpus and build its Markdown manifest.

Run from any folder:
    python tools/validate_corpus.py

Only uses the Python standard library. Does not edit the lore documents.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = ROOT / "backend" / "docs"
MANIFEST_PATH = ROOT / "docs" / "CORPUS_MANIFEST.md"

EXPECTED = {
    "lord_of_the_rings": (
        "The Lord of the Rings",
        ["world_and_history.txt", "characters_and_factions.txt", "events_and_artifacts.txt"],
    ),
    "red_rising": (
        "Red Rising",
        ["society_and_colors.txt", "characters_and_factions.txt", "events_and_technology.txt"],
    ),
    "mistborn": (
        "Mistborn",
        ["world_and_history.txt", "magic_systems.txt", "characters_and_factions.txt"],
    ),
    "harry_potter": (
        "Harry Potter",
        ["hogwarts_and_wizarding_world.txt", "characters_and_factions.txt", "spells_and_artifacts.txt"],
    ),
    "narnia": (
        "The Chronicles of Narnia",
        ["world_and_history.txt", "characters_and_factions.txt", "magic_and_major_events.txt"],
    ),
}

REQUIRED_FIELDS = ("TITLE", "SERIES", "COVERAGE", "SPOILER LEVEL", "CANON BASIS")
WORD_PATTERN = re.compile(r"\b\w+(?:['\u2019-]\w+)*\b", re.UNICODE)


def word_count(value: str) -> int:
    """Count words, including names with hyphens or apostrophes."""
    return len(WORD_PATTERN.findall(value))


def header_value(text: str, field: str) -> str | None:
    """Read a field only from the document's opening header lines."""
    for line in text.splitlines()[:12]:
        key, separator, value = line.partition(":")
        if separator and key.strip().upper() == field:
            return value.strip() or None
    return None


def normalize_paragraph(paragraph: str) -> str:
    """Normalize paragraph text for exact-duplicate detection."""
    return " ".join(paragraph.casefold().split())


def md_cell(value: str) -> str:
    """Escape Markdown table separators."""
    return value.replace("|", "\\|").replace("\n", " ")


def validate() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    records: list[dict[str, str | int]] = []
    paragraphs: dict[str, list[str]] = {}
    expected_paths: set[Path] = set()
    totals: Counter[str] = Counter()

    for folder, (series_name, filenames) in EXPECTED.items():
        for filename in filenames:
            path = DOCS_ROOT / folder / filename
            expected_paths.add(path)
            relative = path.relative_to(ROOT).as_posix()

            if not path.is_file():
                errors.append(f"Missing file: {relative}")
                continue

            try:
                content = path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeError) as exc:
                errors.append(f"Could not read {relative}: {exc}")
                continue

            count = word_count(content)
            if count < 250:
                errors.append(f"Too little content: {relative} ({count} words; minimum 250)")
            elif count < 500:
                warnings.append(f"Shorter than target: {relative} ({count} words; target 500+)")

            fields = {name: header_value(content, name) for name in REQUIRED_FIELDS}
            for name, value in fields.items():
                if not value:
                    errors.append(f"Missing or empty '{name}' header: {relative}")

            if fields["SERIES"] and fields["SERIES"].casefold() != series_name.casefold():
                errors.append(f"Wrong SERIES in {relative}: {fields['SERIES']!r}; expected {series_name!r}")
            if fields["SPOILER LEVEL"] and fields["SPOILER LEVEL"].upper() != "FULL":
                errors.append(f"SPOILER LEVEL must be FULL in {relative}")

            for heading in ("OVERVIEW", "CANON NOTES AND LIMITATIONS"):
                if not re.search(rf"(?m)^\s*{re.escape(heading)}\s*$", content):
                    warnings.append(f"Missing recommended section '{heading}': {relative}")

            for block in re.split(r"\n\s*\n", content):
                if word_count(block) >= 40:
                    key = normalize_paragraph(block)
                    paragraphs.setdefault(key, []).append(relative)

            totals[series_name] += count
            records.append(
                {
                    "path": relative,
                    "series": series_name,
                    "coverage": fields["COVERAGE"] or "NOT PROVIDED",
                    "words": count,
                    "spoiler": fields["SPOILER LEVEL"] or "NOT PROVIDED",
                }
            )
            print(f"{relative}: {count:,} words")

    if DOCS_ROOT.exists():
        extra = sorted(set(DOCS_ROOT.rglob("*.txt")) - expected_paths)
        for path in extra:
            warnings.append(
                f"Extra .txt file not included in manifest (may still be indexed): "
                f"{path.relative_to(ROOT).as_posix()}"
            )
    else:
        errors.append(f"Document folder not found: {DOCS_ROOT}")

    for occurrences in paragraphs.values():
        unique = sorted(set(occurrences))
        if len(unique) > 1:
            warnings.append("Identical long paragraph in: " + ", ".join(unique))

    total_words = sum(int(record["words"]) for record in records)
    print(f"\nDocuments found: {len(records)}/15")
    print(f"Total word count: {total_words:,}")
    if total_words < 7_500:
        warnings.append(f"Corpus under suggested 7,500-word target ({total_words:,}).")

    if errors:
        print("\nERRORS (fix these before generating a manifest):")
        for error in errors:
            print(f"  ERROR: {error}")
    if warnings:
        print("\nWARNINGS (review, but they do not block generation):")
        for warning in warnings:
            print(f"  WARNING: {warning}")

    if errors:
        print("\nManifest was not written. Resolve errors and rerun.")
        return 1

    lines = [
        "# Fantasy Archives - Corpus Manifest",
        "",
        "> Generated by `tools/validate_corpus.py`. Regenerate after editing lore documents.",
        "",
        "## Corpus summary",
        "",
        f"- Documents: **{len(records)}** (expected: 15)",
        f"- Fictional universes: **{len(EXPECTED)}**",
        f"- Combined word count: **{total_words:,}** (includes document headers)",
        "- Spoiler scope: **Full published-series spoilers**",
        "- Canon verification: **Pending manual review**. Structural checks do not verify factual accuracy.",
        "- Pages: **Not measured**. Page counts depend on export layout, font, and margins.",
        "",
        "## Document inventory",
        "",
        "| File | Universe | Coverage | Words | Spoilers | Verification |",
        "|---|---|---|---:|---|---|",
    ]

    for record in records:
        lines.append(
            f"| `{record['path']}` | {md_cell(str(record['series']))} | "
            f"{md_cell(str(record['coverage']))} | {int(record['words']):,} | "
            f"{md_cell(str(record['spoiler']))} | Pending review |"
        )

    lines.extend(["", "## Totals by universe", "", "| Universe | Words |", "|---|---:|"])
    for series_name, _ in EXPECTED.values():
        lines.append(f"| {series_name} | {totals[series_name]:,} |")

    lines.extend(
        [
            "",
            "## Editorial verification checklist",
            "",
            "- [ ] Check important plot events, relationships, and character fates against reliable book references.",
            "- [ ] Confirm publication/coverage cutoff for incomplete series (especially Red Rising).",
            "- [ ] Distinguish book canon from film or television adaptations.",
            "- [ ] Verify potentially conflicting facts and clarify ambiguous terms across eras.",
            "- [ ] Confirm original summaries do not reproduce long copyrighted excerpts.",
            "- [ ] Validate factual QA using the actual RAG application after indexing.",
            "",
            "## Notes",
            "",
            "Files under `backend/docs/` are the only lore inputs expected for this project.",
            "Verification statuses remain pending until a human actually reviews the content.",
            "Do not manually edit this generated manifest; update the source files and rerun the validator.",
            "",
        ]
    )
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nManifest generated: {MANIFEST_PATH.relative_to(ROOT).as_posix()}")
    if warnings:
        print(f"Completed with {len(warnings)} warning(s) to review.")
    else:
        print("All structural validation checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(validate())