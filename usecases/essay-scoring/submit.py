"""Score Kaggle AES 2 test.csv with Jev and write submission.csv."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from typesafe_sdk import TypeSafeClient

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
from env import load_api_key

from score import MODEL, QUESTIONS, compose

HERE = Path(__file__).resolve().parent
TEST = HERE / "data" / "kaggle" / "test.csv"
OUT = HERE / "data" / "submission.csv"
INFERRED_PROMPT = (
    "The assigned argumentative prompt (infer the issue from the student essay)"
)


def grade_text(client: TypeSafeClient, essay_id: str, text: str) -> dict:
    response = client.system_one(
        state={
            "task": "AES 2 holistic scoring",
            "essay": {"prompt": INFERRED_PROMPT, "text": text},
        },
        questions=QUESTIONS,
        model=MODEL,
    )
    a = response.answers
    out = compose(
        a["holistic"].score,
        a["thesis"].noul,
        a["evidence"].noul,
        a["off_prompt"].noul,
        a["errors_obscure"].noul,
    )
    return {
        "essay_id": essay_id,
        "score": out["aes_score"],
        "raw": out["raw_holistic"],
        "inbox": out["inbox"],
        "model": response.model,
    }


def main() -> None:
    if not TEST.exists():
        raise SystemExit(f"Missing {TEST}. Download the competition files first.")
    with TEST.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    results = []
    with TypeSafeClient(api_key=load_api_key()) as client:
        for row in rows:
            rec = grade_text(client, row["essay_id"], row["full_text"])
            results.append(rec)
            print(f"{rec['essay_id']}  {rec['score']}  raw={rec['raw']:.2f}  {rec['inbox']}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["essay_id", "score"])
        w.writeheader()
        for rec in results:
            w.writerow({"essay_id": rec["essay_id"], "score": rec["score"]})
    print(f"wrote {OUT} ({len(results)} rows)")


if __name__ == "__main__":
    main()
