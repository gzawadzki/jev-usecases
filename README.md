# Route Google Play reviews with TypeSafe Jev

This repo classifies **Bank Millennium** Android reviews into a product inbox. The model is TypeSafe **Jev** (`jev-1.13.0`): it returns typed probabilities, not generated text. Your code decides **churn_watch**, **bug_triage**, **backlog**, **support_reply**, **monitor**, or **archive_praise**.

App: [`wit.android.bcpBankingApp.millenniumPL`](https://play.google.com/store/apps/details?id=wit.android.bcpBankingApp.millenniumPL)

## Measured run

| | |
| --- | --- |
| Reviews classified | **2975** |
| Questions per review | **6** (one HTTP request) |
| Workers | 8 |
| Wall time | **301.63 s** (5.0 min) |
| Throughput | **9.86 reviews/s** |
| Amortized wall per review | **101 ms** |
| Model | `jev-1.13.0` |
| Date | 2026-09-18 |

Fetch of those 2975 unique Polish reviews (NEWEST × stars 1–5, continuation tokens) finished in under 15 s. Public Play scrape does not return all ~400k store ratings; see [How fetch works](#how-fetch-works).

Full tables: [RESULTS.md](RESULTS.md).

## Why Jev here

A chat LLM would write a paragraph you then parse. Jev takes the review as **state** and six **questions** (one Choice, four Nouls, one Score) and returns numbers you can threshold.

This is not [Bielik Guard / Sójka](https://guard.bielik.ai/). Sójka is a local Polish safety classifier with five fixed labels. Jev is a hosted decision model. `sojka_guard.py` is a separate Sójka-shaped safety demo on the same API.

## Pipeline

```
Google Play  →  data/reviews.json  →  Jev  →  data/classified.json
 millennium_fetch.py                 millennium_classify.py
```

1. `millennium_fetch.py` paginates Play reviews and dedupes by `reviewId`.
2. `millennium_classify.py` sends each review to Jev and appends a jsonl checkpoint.
3. `summarize.py` rebuilds [RESULTS.md](RESULTS.md).

## Inbox rules

Edit thresholds in `millennium_classify.py` (`route()`). Current policy:

| Condition | Inbox |
| --- | --- |
| `churn ≥ 0.70` or `frustration ≥ 2.5` | `churn_watch` |
| `bug ≥ 0.70` | `bug_triage` |
| `feature_request ≥ 0.70` | `backlog` |
| `needs_reply ≥ 0.55` | `support_reply` |
| topic `praise` and low frustration | `archive_praise` |
| else | `monitor` |

Headline counts from the measured run:

| Inbox | n | Share |
| --- | --- | --- |
| bug_triage | 963 | 32.4% |
| support_reply | 799 | 26.9% |
| archive_praise | 428 | 14.4% |
| backlog | 332 | 11.2% |
| monitor | 286 | 9.6% |
| churn_watch | 167 | 5.6% |

## Reproduce

1. Python 3.10+ and a [TypeSafe API key](https://console.typesafe.ai/settings/keys).
2. Install and configure:

```bash
pip install -r requirements.txt
copy .env.example .env
# set TYPESAFE_API_KEY in .env
```

3. Fetch (optional; this clone already has `data/reviews.json`):

```bash
python millennium_fetch.py --limit 3000
```

4. Classify. `--sample 50` is a cheap smoke test. Omit it for the full corpus (~5 min, ~3k API calls):

```bash
python millennium_classify.py --sample 50
python millennium_classify.py --workers 8
python summarize.py --write
```

Interrupted runs resume from `data/classified.jsonl`.

## How fetch works

`google-play-scraper` calls Play's public `batchexecute` RPC. One page is about 200 reviews. A continuation token walks further. One `(sort, star, lang)` stream usually dies after a few thousand rows.

This fetcher combines **NEWEST**, **MOST_RELEVANT**, and **RATING** with **stars 1–5** and keeps unique `reviewId`s. It pulls 1–4★ first so the set is not 90% “super”.

The **Google Play Developer API** `reviews.list` can dump everything if you own the app. This repo does not.

## Files

| Path | Role |
| --- | --- |
| `millennium_fetch.py` | Scrape and dedupe |
| `millennium_classify.py` | Jev questions, routing, checkpoint |
| `summarize.py` | Tables → `RESULTS.md` |
| `sojka_guard.py` | Separate 5-label safety screen |
| `data/reviews.json` | 2975 reviews used in the timed run |
| `data/classified.json` | Jev answers + inbox |
| `data/timing.json` | Wall-clock metadata |
| `.env.example` | `TYPESAFE_API_KEY` |

Do not commit `.env`.

## License

MIT. Review text belongs to its authors and Google Play. This repo stores a public scrape for the demo.
