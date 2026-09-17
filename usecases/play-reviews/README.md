# Play review inbox

Route [Bank Millennium](https://play.google.com/store/apps/details?id=wit.android.bcpBankingApp.millenniumPL) Google Play reviews into a product inbox.

Jev answers six questions in **one request per review**. `route()` in `classify.py` turns those numbers into `churn_watch`, `bug_triage`, `backlog`, `support_reply`, `monitor`, or `archive_praise`.

## Measured run

| Field | Value |
| --- | --- |
| Reviews | 2975 |
| Model | `jev-1.13.0` |
| Workers | 8 |
| Wall time | **301.63 s** (5.0 min) |
| Throughput | **9.86 reviews/s** |
| Date | 2026-09-18 |

Fetch of that unique set (NEWEST × stars 1–5) finished in under 15 s. Public Play scrape does not return all ~400k ratings.

Full tables: [RESULTS.md](RESULTS.md).

## Inbox (measured)

| Inbox | n | Share |
| --- | --- | --- |
| bug_triage | 963 | 32.4% |
| support_reply | 799 | 26.9% |
| archive_praise | 428 | 14.4% |
| backlog | 332 | 11.2% |
| monitor | 286 | 9.6% |
| churn_watch | 167 | 5.6% |

## Reproduce

From the repository root:

```bash
python usecases/play-reviews/fetch.py --limit 3000
python usecases/play-reviews/classify.py --sample 50
python usecases/play-reviews/classify.py --workers 8
python usecases/play-reviews/summarize.py --write
```

Interrupted classify runs resume from `data/classified.jsonl` (gitignored).

## How fetch works

`google-play-scraper` paginates Play's `batchexecute` RPC with continuation tokens. One `(sort, star, lang)` stream usually stops after a few thousand rows. This fetcher combines NEWEST, MOST_RELEVANT, and RATING with stars 1–5, then dedupes by `reviewId`. It pulls 1–4★ first so the set is not 90% “super”.

If you own the app, use the Google Play Developer API `reviews.list` instead.
