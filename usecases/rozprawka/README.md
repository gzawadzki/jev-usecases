# Rozprawka (CKE Formuła 2023)

Polish matura *wypracowanie* is not AES 1–6. Official max is **35 points**. Some cells are judgments. Some are counts. Jev can do the first. Code must do the second.

| CKE cell | Max | Who |
| --- | --- | --- |
| Formal conditions (on topic, argument, mandatory reading, no *błąd kardynalny*) | 1 | Jev Nouls + code: fail → **0 for the whole paper** |
| Literary and cultural competence (functional reading, not a plot summary; second text; context; argument quality) | 16 | Jev Nouls + Score, summed in `compose()` |
| Composition (structure 3 + cohesion 3 + style 1) | 7 | Jev Scores / Noul |
| Language range | 7 of 11 | Jev Score (wide / adequate / narrow) |
| Spelling + punctuation | 4 of 11 | **Not Jev** — CKE counts errors |
| Word count &lt; 300 | — | **Code**: score only formal + literary |

This is not an official examiner. It follows the published shape of the [CKE Informator](https://cke.gov.pl/egzamin-maturalny/egzamin-maturalny-w-formule-2023/informatory/).

## Demo (`jev-1.13.0`)

Topic: *Czy praca uszlachetnia człowieka?*

```bash
python usecases/rozprawka/grade.py
```

| Paper | Total | Gate |
| --- | --- | --- |
| Functional *Lalka* + *Pan Tadeusz* (312 words) | **31/35** | ok (4 pts of spelling/punctuation left unscored) |
| Plot summary of *Lalka* | **0/35** | `formal_fail` (summary ≠ argument) |
| Cardinal plot error (Wokulski dies on page one) | **0/35** | `blad_kardynalny` 0.98 |

Questions are in `grade.py`. Policy (zero the paper, 300-word cap, how Nouls become the 16 literary points) is in `compose()`.
