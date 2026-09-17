"""Download Bank Millennium Google Play reviews via google-play-scraper.

Google Play will not give you all ~400k reviews from a public scrape. The
unofficial batchexecute RPC paginates with continuation tokens and typically
caps one (sort, score, lang) stream after a few thousand items. Combining
streams (NEWEST + MOST_RELEVANT + RATING) x stars 1-5 x langs gets much more
than a single `reviews(count=N)` call, then we dedupe by reviewId.

Official full dump: Google Play Developer API, only if you own the app.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from google_play_scraper import Sort, reviews

APP_ID = "wit.android.bcpBankingApp.millenniumPL"
OUT_DEFAULT = Path(__file__).resolve().parent / "data" / "reviews.json"

# One RPC page is ~200; the library will loop internally up to 4500.
BATCH = 400


def _iso(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row(raw: dict) -> dict:
    return {
        "reviewId": raw.get("reviewId"),
        "user": raw.get("userName"),
        "stars": raw.get("score"),
        "at": _iso(raw.get("at")),
        "content": (raw.get("content") or "").strip(),
        "thumbsUp": raw.get("thumbsUpCount") or 0,
        "version": raw.get("reviewCreatedVersion") or raw.get("appVersion"),
        "reply": raw.get("replyContent"),
        "repliedAt": _iso(raw.get("repliedAt")),
    }


def fetch_stream(
    *,
    lang: str,
    country: str,
    sort: Sort,
    score: int | None,
    want: int,
    sleep_s: float,
) -> list[dict]:
    # Continuation tokens remember the first `count`. Keep BATCH stable.
    collected: list[dict] = []
    token = None
    while len(collected) < want:
        kwargs = {
            "app_id": APP_ID,
            "lang": lang,
            "country": country,
            "sort": sort,
            "count": BATCH,
        }
        if score is not None:
            kwargs["filter_score_with"] = score
        if token is not None:
            kwargs["continuation_token"] = token
        batch, token = reviews(**kwargs)
        if not batch:
            break
        collected.extend(_row(r) for r in batch)
        if token is None or token.token is None:
            break
        if sleep_s:
            time.sleep(sleep_s)
    return collected[:want]


def harvest(
    limit: int,
    langs: list[str],
    country: str,
    min_len: int,
    sleep_s: float,
) -> list[dict]:
    """Fill a quota by walking sort x star streams until unique reviews hit limit."""
    seen: set[str] = set()
    out: list[dict] = []
    # NEWEST per star first: a single NEWEST dump is ~90% 5★ fluff.
    # Then MOST_RELEVANT / RATING, which overlap a lot but add older items.
    sorts = (Sort.NEWEST, Sort.MOST_RELEVANT, Sort.RATING)
    scores = (1, 2, 3, 4, 5)
    per_star = max(BATCH, limit // (len(langs) * len(scores)))

    def ingest(rows: list[dict], budget: int) -> int:
        added = 0
        for row in rows:
            if len(out) >= limit or added >= budget:
                break
            rid = row["reviewId"]
            if not rid or rid in seen:
                continue
            if len(row["content"]) < min_len:
                continue
            seen.add(rid)
            out.append(row)
            added += 1
        return added

    for lang in langs:
        for sort in sorts:
            for score in scores:
                if len(out) >= limit:
                    return out
                want = min(per_star, limit - len(out))
                print(
                    f"  {lang} {sort.name} ★{score} want={want} have={len(out)}",
                    flush=True,
                )
                try:
                    rows = fetch_stream(
                        lang=lang,
                        country=country,
                        sort=sort,
                        score=score,
                        want=want,
                        sleep_s=sleep_s,
                    )
                except Exception as exc:
                    print(f"    skip: {exc}")
                    time.sleep(1)
                    continue
                added = ingest(rows, want)
                print(f"    +{added} unique (stream {len(rows)})")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Millennium Play reviews")
    parser.add_argument("--limit", type=int, default=3000)
    parser.add_argument("--langs", default="pl", help="comma-separated, e.g. pl,en")
    parser.add_argument("--country", default="pl")
    parser.add_argument("--min-len", type=int, default=12)
    parser.add_argument("--sleep", type=float, default=0.15)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()
    langs = [x.strip() for x in args.langs.split(",") if x.strip()]
    print(f"fetching up to {args.limit} unique reviews, langs={langs}")
    rows = harvest(args.limit, langs, args.country, args.min_len, args.sleep)
    rows.sort(key=lambda r: r.get("at") or "", reverse=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    stars = {s: sum(1 for r in rows if r["stars"] == s) for s in range(1, 6)}
    print(f"wrote {len(rows)} -> {args.out}")
    print("stars", stars)


if __name__ == "__main__":
    main()
