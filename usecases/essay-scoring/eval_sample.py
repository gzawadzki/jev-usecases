"""Grade a random train sample with Jev and report quadratic weighted kappa."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from sklearn.metrics import cohen_kappa_score, confusion_matrix
from typesafe_sdk import TypeSafeClient

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
from env import load_api_key

from score import MODEL, QUESTIONS, compose

HERE = Path(__file__).resolve().parent
TRAIN = HERE / "data" / "kaggle" / "train.csv"
CHECKPOINT = HERE / "data" / "eval_sample.jsonl"
INFERRED_PROMPT = (
    "The assigned argumentative prompt (infer the issue from the student essay)"
)


def load_train() -> list[dict]:
    with TRAIN.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def sample_rows(rows: list[dict], n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    if n >= len(rows):
        return list(rows)
    return rng.sample(rows, n)


def load_done() -> dict[str, dict]:
    done: dict[str, dict] = {}
    if not CHECKPOINT.exists():
        return done
    with CHECKPOINT.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            done[rec["essay_id"]] = rec
    return done


def grade_one(client: TypeSafeClient, row: dict) -> dict:
    response = client.system_one(
        state={
            "task": "AES 2 holistic scoring",
            "essay": {"prompt": INFERRED_PROMPT, "text": row["full_text"]},
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
    gold = int(row["score"])
    uncapped = int(round(min(6, max(1, a["holistic"].score + 1.0))))
    return {
        "essay_id": row["essay_id"],
        "gold": gold,
        "pred": out["aes_score"],
        "uncapped": uncapped,
        "raw": round(a["holistic"].score + 1.0, 2),
        "thesis": round(a["thesis"].noul, 3),
        "evidence": round(a["evidence"].noul, 3),
        "off_prompt": round(a["off_prompt"].noul, 3),
        "errors_obscure": round(a["errors_obscure"].noul, 3),
        "inbox": out["inbox"],
        "model": response.model,
    }


def report(rows: list[dict]) -> None:
    gold = [r["gold"] for r in rows]
    pred = [r["pred"] for r in rows]
    uncapped = [r["uncapped"] for r in rows]
    qwk = cohen_kappa_score(gold, pred, weights="quadratic")
    qwk_u = cohen_kappa_score(gold, uncapped, weights="quadratic")
    exact = sum(p == g for p, g in zip(pred, gold))
    within = sum(abs(p - g) <= 1 for p, g in zip(pred, gold))
    print(f"n={len(rows)}")
    print(f"gold {dict(sorted(Counter(gold).items()))}")
    print(f"pred {dict(sorted(Counter(pred).items()))}")
    print(f"QWK capped   {qwk:.4f}")
    print(f"QWK uncapped {qwk_u:.4f}")
    print(f"exact {exact}/{len(rows)} ({100*exact/len(rows):.1f}%)")
    print(f"within-1 {within}/{len(rows)} ({100*within/len(rows):.1f}%)")
    labels = [1, 2, 3, 4, 5, 6]
    cm = confusion_matrix(gold, pred, labels=labels)
    print("confusion gold\\pred  1  2  3  4  5  6")
    for i, lab in enumerate(labels):
        cells = " ".join(f"{v:4d}" for v in cm[i])
        print(f"              {lab} {cells}")
    mean_err = sum(p - g for p, g in zip(pred, gold)) / len(rows)
    print(f"mean pred-gold {mean_err:+.3f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if not TRAIN.exists():
        raise SystemExit(f"Missing {TRAIN}")
    picked = sample_rows(load_train(), args.n, args.seed)
    done = load_done()
    pending = [r for r in picked if r["essay_id"] not in done]
    print(f"sample {len(picked)}  cached={len(picked)-len(pending)}  pending={len(pending)}", flush=True)
    key = load_api_key()
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    finished = 0

    def work(row: dict) -> dict:
        with TypeSafeClient(api_key=key) as client:
            return grade_one(client, row)

    if pending:
        with ThreadPoolExecutor(max_workers=args.workers) as pool, CHECKPOINT.open(
            "a", encoding="utf-8"
        ) as log:
            futs = [pool.submit(work, r) for r in pending]
            for fut in as_completed(futs):
                rec = fut.result()
                done[rec["essay_id"]] = rec
                with lock:
                    log.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    log.flush()
                    finished += 1
                    if finished % 50 == 0 or finished == len(pending):
                        print(f"  {finished}/{len(pending)}", flush=True)

    ordered = [done[r["essay_id"]] for r in picked]
    report(ordered)
    summary = HERE / "data" / "eval_sample_summary.json"
    gold = [r["gold"] for r in ordered]
    pred = [r["pred"] for r in ordered]
    summary.write_text(
        json.dumps(
            {
                "n": len(ordered),
                "seed": args.seed,
                "qwk_capped": cohen_kappa_score(gold, pred, weights="quadratic"),
                "qwk_uncapped": cohen_kappa_score(
                    gold, [r["uncapped"] for r in ordered], weights="quadratic"
                ),
                "exact": sum(p == g for p, g in zip(pred, gold)),
                "within_1": sum(abs(p - g) <= 1 for p, g in zip(pred, gold)),
                "gold": dict(sorted(Counter(gold).items())),
                "pred": dict(sorted(Counter(pred).items())),
                "model": ordered[0]["model"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {summary}")


if __name__ == "__main__":
    main()
