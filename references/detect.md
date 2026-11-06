# Detection protocol

What the check does. Editing rules: [SKILL.md](../SKILL.md). Data: [research.md](./research.md).

## Why check before editing

Editing directly changes everything that "seems" AI-written, including what measurement rejected. Example: humans use «من أجل» more than all three models. The report and the user's reply guard against over-cleaning.

## Layers

| Layer | Handles | Owner | Reference |
|---|---|---|---|
| Script | Words, punctuation, structure | `detect.py` | This file |
| Semantic | Renaming, cohesion, colons, identical sentence shapes | The model in session | [Criteria](./semantic-criteria.md) |
| Human | Metaphor and rhymed-prose quality | The user | SKILL.md |

## Running

```bash
python3 scripts/detect.py <file or folder> [--max-hits 5] [--json]
python3 scripts/detect.py <file> --candidates --out candidates.json
python3 scripts/report.py <original> <edited> before.json after.json [--semantic labelled.json] --out report.md
```

Python 3.9 or later, no other dependencies. Reads `.md` and `.txt`, and warns under 150 words.

## Levels

| Level | Meaning | Action |
|---|---|---|
| **A** | Fixed phrase, up in all three models, edit doesn't touch meaning | Review, then propose |
| **B** | Up in all three models, needs rewording | Review each one |
| **F** | Not up in all three together, or the data halves disagree | Propose at lower priority |
| **C** | Whole-text properties | Report only |
| **U** | This data can't measure it | Unmeasured note |
| **X** | Humans equal to or above the models | Never edit |

**A and B require,** on the held-out half and for each of the three models: ratio at least 1.25, lower bound of the 95% CI above 1, and the same direction in both SANAD and ANAD. A differs from B by edit risk, not signal strength.

## Protected text

Before counting, `arabic.py` masks:

- Text inside ﴿ ﴾, { }, « », “ ” and " ".
- Lines with vowel marks on over 30% of letters (verses, hadith, poetry).
- Lines containing ﴿ or ﴾ with vowel marks on over 15% of letters.
- Headings, lists, tables, code and Markdown quotes.

**It misses** a verse or hadith with no brackets and no vowel marks, so checking remains your job.

## Normalisation

Before matching: strip vowel marks and tatweel, أ إ آ → ا, ى → ي, ة → ه. Excerpts still show the author's original letters. Density is per 1000 Arabic words, not characters.

## Reading results

1. Script output is candidates, not verdicts. Read each hit in context.
2. The study describes a corpus. It doesn't test your text statistically.
3. Don't engineer sentence variation to approach level C figures.
4. When an F figure differs between models, that's the point. Don't merge them into "AI overuses X".
