"""Print inbox/topic tables from data/classified.json. Regenerates RESULTS.md."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLASSIFIED = ROOT / "data" / "classified.json"
TIMING = ROOT / "data" / "timing.json"
RESULTS = ROOT / "RESULTS.md"

INBOX_ORDER = [
    "churn_watch",
    "bug_triage",
    "support_reply",
    "backlog",
    "monitor",
    "archive_praise",
]
INBOX_PL = {
    "churn_watch": "Groźba odejścia",
    "bug_triage": "Błąd do triażu",
    "support_reply": "Odpowiedź merytoryczna",
    "backlog": "Prośba o funkcję",
    "monitor": "Obserwować",
    "archive_praise": "Pochwała",
}


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    line = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join([line, sep, body])


def build(rows: list[dict], timing: dict) -> str:
    n = len(rows)
    wall = timing.get("classify_wall_seconds")
    workers = timing.get("workers")
    rps = n / wall if wall else None
    inbox = Counter(r["inbox"] for r in rows)
    topic = Counter(r["topic"] for r in rows)
    stars = Counter(r["stars"] for r in rows)
    dates = [r["at"] for r in rows if r.get("at")]

    inbox_rows = []
    for key in INBOX_ORDER:
        c = inbox.get(key, 0)
        inbox_rows.append(
            [f"`{key}`", INBOX_PL[key], str(c), f"{100 * c / n:.1f}%"]
        )

    topic_rows = [
        [f"`{k}`", str(v), f"{100 * v / n:.1f}%"]
        for k, v in topic.most_common()
    ]
    star_rows = [[str(s), str(stars.get(s, 0))] for s in range(1, 6)]

    cross = []
    for key in INBOX_ORDER:
        counts = Counter(r["stars"] for r in rows if r["inbox"] == key)
        cross.append([f"`{key}`"] + [str(counts.get(s, 0)) for s in range(1, 6)])

    parts = [
        "# Results",
        "",
        "Numbers below come from `data/classified.json` after the measured Jev run.",
        "",
        "## Run",
        "",
        md_table(
            ["Field", "Value"],
            [
                ["App", f"{timing.get('app')} (`{timing.get('app_id')}`)"],
                ["Model", f"`{timing.get('model')}`"],
                ["Reviews classified", str(n)],
                ["Questions per review", str(timing.get("questions_per_review", 6))],
                ["Workers", str(workers)],
                ["Wall time", f"{wall:.2f} s ({wall/60:.1f} min)"],
                ["Throughput", f"{rps:.2f} reviews/s" if rps else "—"],
                [
                    "Amortized wall per review",
                    f"{1000 * wall / n:.0f} ms" if wall else "—",
                ],
                ["Review dates", f"{min(dates)} → {max(dates)}" if dates else "—"],
                ["Classify date", str(timing.get("classify_date", "—"))],
            ],
        ),
        "",
        "Jev evaluates all six questions in **one request per review**. "
        "Eight parallel workers hide most of the per-call latency. "
        "A serial run would sit closer to one second per review.",
        "",
        "## Inbox",
        "",
        "Code owns the decision. Jev only returns probabilities.",
        "",
        md_table(["Inbox", "Meaning", "n", "Share"], inbox_rows),
        "",
        "## Topic",
        "",
        md_table(["Topic", "n", "Share"], topic_rows),
        "",
        "## Stars in the corpus",
        "",
        "The fetch pulls NEWEST per star so 1–4★ are not drowned by 5★ fluff.",
        "",
        md_table(["Stars", "n"], star_rows),
        "",
        "## Inbox by star rating",
        "",
        md_table(["Inbox", "1★", "2★", "3★", "4★", "5★"], cross),
        "",
        "## Means",
        "",
        md_table(
            ["Signal", "Mean"],
            [
                ["bug (noul)", f"{sum(r['bug'] for r in rows)/n:.3f}"],
                ["feature_request (noul)", f"{sum(r['feature_request'] for r in rows)/n:.3f}"],
                ["churn (noul)", f"{sum(r['churn'] for r in rows)/n:.3f}"],
                ["needs_reply (noul)", f"{sum(r['needs_reply'] for r in rows)/n:.3f}"],
                ["frustration (score 0–3)", f"{sum(r['frustration'] for r in rows)/n:.2f}"],
            ],
        ),
        "",
    ]
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Write RESULTS.md")
    args = parser.parse_args()
    rows = json.loads(CLASSIFIED.read_text(encoding="utf-8"))
    timing = json.loads(TIMING.read_text(encoding="utf-8"))
    text = build(rows, timing)
    if args.write:
        RESULTS.write_text(text, encoding="utf-8")
        print(f"wrote {RESULTS}")
    else:
        print(text)


if __name__ == "__main__":
    main()
