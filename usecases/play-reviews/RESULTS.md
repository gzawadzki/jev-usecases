# Results

Numbers below come from `data/classified.json` after the measured Jev run. Regenerate with `python usecases/play-reviews/summarize.py --write` from the repository root.

## Run

| Field | Value |
| --- | --- |
| App | Bank Millennium (`wit.android.bcpBankingApp.millenniumPL`) |
| Model | `jev-1.13.0` |
| Reviews classified | 2975 |
| Questions per review | 6 |
| Workers | 8 |
| Wall time | 301.63 s (5.0 min) |
| Throughput | 9.86 reviews/s |
| Amortized wall per review | 101 ms |
| Review dates | 2020-09-18T20:04:02 → 2026-09-16T21:08:21 |
| Classify date | 2026-09-18 |

Jev evaluates all six questions in **one request per review**. Eight parallel workers hide most of the per-call latency. A serial run would sit closer to one second per review.

## Inbox

Code owns the decision. Jev only returns probabilities.

| Inbox | Meaning | n | Share |
| --- | --- | --- | --- |
| `churn_watch` | Groźba odejścia | 167 | 5.6% |
| `bug_triage` | Błąd do triażu | 963 | 32.4% |
| `support_reply` | Odpowiedź merytoryczna | 799 | 26.9% |
| `backlog` | Prośba o funkcję | 332 | 11.2% |
| `monitor` | Obserwować | 286 | 9.6% |
| `archive_praise` | Pochwała | 428 | 14.4% |

## Topic

| Topic | n | Share |
| --- | --- | --- |
| `other` | 624 | 21.0% |
| `performance` | 555 | 18.7% |
| `payments` | 547 | 18.4% |
| `praise` | 434 | 14.6% |
| `feature_gap` | 277 | 9.3% |
| `login_activation` | 222 | 7.5% |
| `history_ux` | 176 | 5.9% |
| `loans_upsell` | 64 | 2.2% |
| `device_os` | 49 | 1.6% |
| `channel_lockin` | 22 | 0.7% |
| `cards_fx` | 5 | 0.2% |

## Stars in the corpus

The fetch pulls NEWEST per star so 1–4★ are not drowned by 5★ fluff.

| Stars | n |
| --- | --- |
| 1 | 769 |
| 2 | 763 |
| 3 | 712 |
| 4 | 594 |
| 5 | 137 |

## Inbox by star rating

| Inbox | 1★ | 2★ | 3★ | 4★ | 5★ |
| --- | --- | --- | --- | --- | --- |
| `churn_watch` | 122 | 35 | 8 | 2 | 0 |
| `bug_triage` | 252 | 352 | 274 | 85 | 0 |
| `support_reply` | 280 | 225 | 203 | 88 | 3 |
| `backlog` | 36 | 79 | 110 | 107 | 0 |
| `monitor` | 76 | 65 | 77 | 60 | 8 |
| `archive_praise` | 3 | 7 | 40 | 252 | 126 |

## Means

| Signal | Mean |
| --- | --- |
| bug (noul) | 0.420 |
| feature_request (noul) | 0.209 |
| churn (noul) | 0.070 |
| needs_reply (noul) | 0.703 |
| frustration (score 0–3) | 0.98 |
