# The Fantasy Archives — Live RAG Evaluation

**Run:** 2026-10-13 16:52 UTC  
**API:** `http://localhost:8000`  
**Mode:** `full`  
**Status:** Machine-checkable behavior tested; story facts require human review.

## Environment and index

- Backend health: `healthy`
- Ollama: `connected`
- Chat model: `llama3.2:1b`
- Embedding model: `nomic-embed-text`
- Indexed chunks: `216`
- Unique source files: `15`

### Deterministic checks

| Check | Result |
|---|---|
| GET / returns HTTP 200 | PASS |
| GET /health returns HTTP 200 | PASS |
| GET /stats returns HTTP 200 | PASS |
| Ollama responds | PASS |
| Exactly 15 source files indexed | PASS |
| Each of five universes has indexed chunks | PASS |
| Invalid universe rejected with HTTP 400 | PASS |

### Corpus distribution

| Universe | Indexed chunks |
|---|---:|
| `lord_of_the_rings` | 26 |
| `red_rising` | 30 |
| `mistborn` | 44 |
| `harry_potter` | 54 |
| `narnia` | 62 |

## Live question results

| Scenario | Series | API check | Seconds |
|---|---|---|---:|
| Lord of the Rings — One Ring | `lord_of_the_rings` | **REVIEW** | 10.4 |
| Red Rising — Colors | `red_rising` | **REVIEW** | 17.1 |
| Mistborn — Metallic Arts | `mistborn` | **REVIEW** | 7.6 |
| Harry Potter — Deathly Hallows | `harry_potter` | **REVIEW** | 7.1 |
| Narnia — Deep Magic | `narnia` | **REVIEW** | 5.6 |
| Across universes — magic | `all` | **REVIEW** | 16.7 |
| Filter isolation — unrelated universe | `narnia` | **REVIEW** | 0.0 |
| Unsupported detail — Narnia | `narnia` | **REVIEW** | 0.0 |

### Lord of the Rings — One Ring

**Filter:** `lord_of_the_rings`  
**Question:** How was the One Ring finally destroyed?  
**Result:** **REVIEW**; response status `answered`; retrieval strength `low`; 10.4 seconds

**Answer:**

[Source 1] [Source 2] [Source 3]

The One Ring was finally destroyed in the fires of Mount Doom, where it was cast into the lava by Frodo Baggins. This act of destruction was a result of the Ring's corrupting influence on Frodo, and it is said that the Ring's power declined significantly after its destruction.

There is no mention of the Ring being destroyed by the other characters in the passage provided.

**Retrieved sources:**

- `Source 1` — `lord_of_the_rings/events_and_artifacts.txt` (chunk `3`, similarity `0.737`)
- `Source 2` — `lord_of_the_rings/events_and_artifacts.txt` (chunk `4`, similarity `0.715`)
- `Source 3` — `lord_of_the_rings/events_and_artifacts.txt` (chunk `7`, similarity `0.704`)
- `Source 4` — `lord_of_the_rings/world_and_history.txt` (chunk `4`, similarity `0.671`)
- `Source 5` — `lord_of_the_rings/events_and_artifacts.txt` (chunk `2`, similarity `0.661`)

**Review notes:**
- Manually confirm lore accuracy and whether the cited passages support the answer
- [ ] Human-confirmed the answer is faithful to the referenced lore and sources.

### Red Rising — Colors

**Filter:** `red_rising`  
**Question:** How does the Society use the Color hierarchy to control people?  
**Result:** **REVIEW**; response status `answered`; retrieval strength `medium`; 17.1 seconds

**Answer:**

Based on the provided document passages, the Society uses the Color hierarchy to control people by exploiting and manipulating individuals based on their genetic differences. The following points illustrate how the Society uses the Color hierarchy to control people:

1. **Genetic engineering and controlled reproduction**: The Society has produced significant biological differences between Colors, reinforcing the claim that each group possesses a natural place in society. This allows the Society to control individuals based on their genetic makeup.
2. **Inheritance of privilege**: Those born into the Gold caste (ruling caste) inherit their position and advantages, while those born into other Colors are relegated to lower positions. This perpetuates the Color hierarchy and maintains the Society's power.
3. **Education and cultural conditioning**: The Society uses history, education, and cultural conditioning to discourage challenges to the hierarchy. This helps to maintain the status quo and suppress dissent.
4. **Institutionalized abuse**: The Society exploits individuals from lower Colors, such as Pinks (companions and entertainers) and Reds (miners), for labor and pleasure. This perpetuates social inequalities and reinforces the Color hierarchy.
5. **Propaganda and manipulation**: The Society uses propaganda and manipulation to maintain its power and control over individuals. For example, the Society's ideology emphasizes the superiority of the Gold caste, reinforcing their dominance.

Overall, the Society's control mechanisms are based on its rigid Color hierarchy, which exploits and manipulates individuals based on their genetic differences.

**Retrieved sources:**

- `Source 1` — `red_rising/society_and_colors.txt` (chunk `1`, similarity `0.772`)
- `Source 2` — `red_rising/society_and_colors.txt` (chunk `2`, similarity `0.757`)
- `Source 3` — `red_rising/society_and_colors.txt` (chunk `0`, similarity `0.722`)
- `Source 4` — `red_rising/society_and_colors.txt` (chunk `3`, similarity `0.691`)
- `Source 5` — `red_rising/society_and_colors.txt` (chunk `4`, similarity `0.681`)

**Review notes:**
- Generated answer has no inline [Source N] citation
- Manually confirm lore accuracy and whether the cited passages support the answer
- [ ] Human-confirmed the answer is faithful to the referenced lore and sources.

### Mistborn — Metallic Arts

**Filter:** `mistborn`  
**Question:** How does Feruchemy differ from Allomancy?  
**Result:** **REVIEW**; response status `answered`; retrieval strength `low`; 7.6 seconds

**Answer:**

Based on the provided document passages, Feruchemy differs from Allomancy in the following ways:

1. **Energy source**: Feruchemy uses an external source to temporarily reduce an attribute in order to save it for future use, whereas Allomancy relies on consuming and metabolically burning specific metals to produce supernatural effects.
2. **Purpose**: Feruchemy is described as an end-neutral system, shifting personal resources across time rather than gaining power from nothing, whereas Allomancy is an end-positive system, where the energy powering its effects comes from an external source associated with Preservation.
3. **Limitations**: Feruchemy has limitations, such as requiring planning to store attributes before using them, and tapping an attribute at an unusually high rate can reduce efficiency, whereas Allomancy has no such limitations.

This answers the question without relying on external knowledge or speculation.

**Retrieved sources:**

- `Source 1` — `mistborn/magic_systems.txt` (chunk `6`, similarity `0.715`)
- `Source 2` — `mistborn/magic_systems.txt` (chunk `5`, similarity `0.705`)
- `Source 3` — `mistborn/magic_systems.txt` (chunk `1`, similarity `0.697`)
- `Source 4` — `mistborn/magic_systems.txt` (chunk `9`, similarity `0.695`)
- `Source 5` — `mistborn/magic_systems.txt` (chunk `8`, similarity `0.666`)

**Review notes:**
- Generated answer has no inline [Source N] citation
- Manually confirm lore accuracy and whether the cited passages support the answer
- [ ] Human-confirmed the answer is faithful to the referenced lore and sources.

### Harry Potter — Deathly Hallows

**Filter:** `harry_potter`  
**Question:** What are the three Deathly Hallows?  
**Result:** **REVIEW**; response status `answered`; retrieval strength `low`; 7.1 seconds

**Answer:**

Based on the provided passages, the three Deathly Hallows are:

1. The Elder Wand (also known as the Deathstick)
2. The Resurrection Stone
3. The Cloak of Invisibility

**Retrieved sources:**

- `Source 1` — `harry_potter/spells_and_artifacts.txt` (chunk `12`, similarity `0.739`)
- `Source 2` — `harry_potter/hogwarts_and_wizarding_world.txt` (chunk `3`, similarity `0.673`)
- `Source 3` — `harry_potter/spells_and_artifacts.txt` (chunk `0`, similarity `0.666`)
- `Source 4` — `harry_potter/spells_and_artifacts.txt` (chunk `20`, similarity `0.654`)
- `Source 5` — `harry_potter/hogwarts_and_wizarding_world.txt` (chunk `0`, similarity `0.653`)

**Review notes:**
- Generated answer has no inline [Source N] citation
- Manually confirm lore accuracy and whether the cited passages support the answer
- [ ] Human-confirmed the answer is faithful to the referenced lore and sources.

### Narnia — Deep Magic

**Filter:** `narnia`  
**Question:** How does the Deep Magic differ from the Deeper Magic?  
**Result:** **REVIEW**; response status `answered`; retrieval strength `low`; 5.6 seconds

**Answer:**

The Deep Magic differs from the Deeper Magic in that it is an ancient, non-supernatural law that governs Narnia, as opposed to the Deeper Magic, which appears to be a supernatural law invoked by the White Witch. [Source 1]

This is based on the fact that the Deep Magic is presented as part of Narnia's ancient moral order, whereas the Deeper Magic seems to be a more powerful, supernatural law.

It is not clear how the White Witch and the Lady of the Green Kirtle understand the Deeper Magic, or how Aslan's actions relate to it, without explicit canonical evidence. [Source 3]

**Retrieved sources:**

- `Source 1` — `narnia/magic_and_major_events.txt` (chunk `6`, similarity `0.695`)
- `Source 2` — `narnia/magic_and_major_events.txt` (chunk `7`, similarity `0.661`)
- `Source 3` — `narnia/magic_and_major_events.txt` (chunk `22`, similarity `0.656`)

**Review notes:**
- Manually confirm lore accuracy and whether the cited passages support the answer
- [ ] Human-confirmed the answer is faithful to the referenced lore and sources.

### Across universes — magic

**Filter:** `all`  
**Question:** Compare Allomancy from Mistborn with Aslan's magic in Narnia.  
**Result:** **REVIEW**; response status `answered`; retrieval strength `low`; 16.7 seconds

**Answer:**

Based on the provided passages, I can answer the question as follows:

Allomancy in the Mistborn series is connected to the divine powers Preservation and Ruin, similar to Aslan's magic in Narnia. Both systems are described as end-positive systems, where the energy powering their effects comes from an external source.

In the Mistborn series, Allomancy involves the use of specific metals, such as Iron and Steel, to access supernatural effects. These metals are associated with Preservation, which is the divine power that shapes Scadrial's magical laws.

In Narnia, Aslan's magic is described as distinct from the limited enchantments used by human magicians. Aslan's creative power is distinct from the mortal limitations of the world, and he often appears when characters face significant moral or political decisions. The White Witch, a human magician, and the Lady of the Green Kirtle, a mysterious figure, also use different forms of magic in their own worlds.

However, it is not clear if Aslan's magic, as depicted in Narnia, directly parallels the Allomancy system in the Mistborn series. The passages do not explicitly compare the two, and Aslan's actions in Narnia are not described in terms of the Allomantic system.

**Retrieved sources:**

- `Source 1` — `narnia/magic_and_major_events.txt` (chunk `3`, similarity `0.747`)
- `Source 2` — `narnia/characters_and_factions.txt` (chunk `1`, similarity `0.745`)
- `Source 3` — `narnia/magic_and_major_events.txt` (chunk `22`, similarity `0.739`)
- `Source 4` — `mistborn/magic_systems.txt` (chunk `1`, similarity `0.722`)
- `Source 5` — `mistborn/magic_systems.txt` (chunk `0`, similarity `0.715`)

**Review notes:**
- Generated answer has no inline [Source N] citation
- Verify answer actually distinguishes both magic systems
- [ ] Human-confirmed the answer is faithful to the referenced lore and sources.

### Filter isolation — unrelated universe

**Filter:** `narnia`  
**Question:** What are the seven Harry Potter Horcruxes?  
**Result:** **REVIEW**; response status `no_context`; retrieval strength `none`; 0.0 seconds

**Answer:**

I don't know based on the indexed documents.

**Retrieved sources:**

- None

**Review notes:**
- Verify the response does NOT explain Harry Potter Horcruxes using general model knowledge
- [ ] Human-confirmed the answer is faithful to the referenced lore and sources.

### Unsupported detail — Narnia

**Filter:** `narnia`  
**Question:** What is the exact population of Cair Paravel in the year 500?  
**Result:** **REVIEW**; response status `no_context`; retrieval strength `none`; 0.0 seconds

**Answer:**

I don't know based on the indexed documents.

**Retrieved sources:**

- None

**Review notes:**
- Verify the model does NOT fabricate an exact population or year
- [ ] Human-confirmed the answer is faithful to the referenced lore and sources.

## Manual acceptance checks

- [ ] Frontend chat renders answers and expandable citations.
- [ ] Conversations remain visible after another question and after switching universes back and forth.
- [ ] Re-index button works without destroying a working index on failure.
- [ ] `docker compose restart backend` preserves indexed chunks and unique source counts.
- [ ] `docker compose up --build -d` runs all three services.
- [ ] `python -m pytest tests -v` passes using the Python 3.11 environment.
- [ ] Both backend and frontend Docker images build.
- [ ] GitHub Actions test and Docker jobs pass after pushing.

## Known limitations

- Cosine similarity and the high/medium/low label measure retrieval strength, not factual accuracy.
- Retrieved sources can be relevant without proving every sentence of the answer.
- A no-context threshold cannot reliably detect every unsupported question; manual checks are required.
- Chat history lives in the browser's Streamlit session; Docker volumes persist the index and model data.
- Live results vary with Ollama model, document content, and retrieval threshold.
