# Essay scoring (AES 2 shape)

[Learning Agency Lab – Automated Essay Scoring 2.0](https://www.kaggle.com/competitions/learning-agency-lab-automated-essay-scoring-2) asked for **one integer 1–6** per argumentative essay. The metric is quadratic weighted kappa (QWK): being off by two points hurts more than being off by one.

Winning stacks were DeBERTa + trees on 17k labeled essays. That is the right tool if the only output is a leaderboard number.

A classroom product needs the **same scale plus the reasons**. Jev scores the public holistic rubric as a `Score` and four Nouls. Code then caps the integer (off-prompt → 1, no claim → at most 2) and routes `strong` / `revise` / `reteach`.

This demo is **not** a Kaggle submission. Eight short original essays, not the competition train set.

## Questions in one Jev call

| Id | Primitive | Asks |
| --- | --- | --- |
| `holistic` | Score, six levels | AES 1–6 on `essay.text` vs `essay.prompt` |
| `thesis` | Noul | Viable point of view on the prompt? |
| `evidence` | Noul | Reasons or examples, not repetition? |
| `off_prompt` | Noul | Answering a different question? |
| `errors_obscure` | Noul | Mechanics hide the meaning? |

`compose()` in `score.py`: `aes_score = round(holistic) + 1`, then min with policy caps.

## Demo (`jev-1.13.0`) — exact 5/8, within 1 point 8/8

```bash
python usecases/essay-scoring/score.py
```

Jev ran hot on the mid-high band (a 4 became 5, a 5 became 6). Off-prompt vacation essay correctly capped at 1 (`off_prompt` 0.99). Broken English still read as a claim, so `errors_obscure` 0.19 did not fire the cap — the Noul is “meaning hidden”, not “has mistakes”.

That gap is why AES 2 used QWK and 17k labels, not eight prompts. The useful artifact here is the **trait vector** you can show a teacher or feed a classical model, not a claim that Jev wins the competition.
