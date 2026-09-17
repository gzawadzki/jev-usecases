# Seed comparator

Jev as a **semantic comparator** for a [Bielik seed](https://github.com/speakleash) test — here `visual-emphasis` from the seed-definition workshop.

In seedlab you already have two axes:

| Method | Sees | Role |
| --- | --- | --- |
| `compare()` | answer + ground truth | normalized strings + Levenshtein |
| LLM-sędzia | **image**, no ground truth | catches errors in ground truth |

Jev is **text-only**. It cannot replace the blind vision judge. It sits beside `compare()`: same inputs, meaning of fragments, seed `error_types` (`niewlasciwy_format`, `literowka`, `nadmiarowy_fragment`, `brakujacy_fragment`).

A three-way disagreement is seedlab step 5 (rozbieżność).

## Measured cases (`jev-1.13.0`)

```bash
python usecases/seed-comparator/compare.py
```

| Case | same | Jev `error_type` |
| --- | --- | --- |
| Identical three voivodeships | 0.98 | `brak` |
| „śląskie” vs „Województwo śląskie” | 0.21 | `brakujacy_fragment` (does not treat the short name as the same span) |
| Missing diacritic `slaskie` | 0.77 | `literowka` |
| Extra heading „Polska” | 0.06 | `nadmiarowy_fragment` |
| Draft on ve-001: `[]` | 0.02 | `brakujacy_fragment` |
| Draft on ve-002: `[{"text":"1"}]` | 0.02 | `niewlasciwy_format` |
| Draft on ve-003: `["codex"]` | 0.02 | extra **and** missing |
| Negative example, `[]` | 0.98 | `brak` |
| Negative example + guessed „Regulamin” | 0.02 | `nadmiarowy_fragment` |

Cases live in `data/cases.json`. Ground-truth strings come from approved `visual-emphasis` examples; Jev never sees the images.

## Plug into seedlab

Keep `parse_answer` / format checks in code. Call Jev only for the content Nouls. Leave Opus (or another vision model) on the image. Show three columns in the seed test report: string compare, Jev, vision judge.
