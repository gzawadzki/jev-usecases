"""AES-2-shaped essay scoring with Jev: rubric dimensions, then a 1-6 in code.

Kaggle AES 2.0 asked for one holistic integer (QWK). A product needs the
same number plus the reasons. Jev scores the rubric traits; this file
caps the integer when the essay is off-prompt or empty of a claim.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from typesafe_sdk import Noul, NoulCriteria, Score, TypeSafeClient

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
from env import load_api_key

MODEL = "jev-latest"
DATA = Path(__file__).resolve().parent / "data"
ESSAYS = DATA / "essays.json"

# Holistic 1-6 from the AES 2 public rubric discussion (score of 6 … 1).
HOLISTIC_LEVELS = [
    {
        "what": "Score 1: no viable point of view, or little or no evidence",
        "signals": ["Off the prompt", "A few sentences with no claim"],
    },
    {
        "what": "Score 2: seriously limited; little development; frequent errors",
        "signals": ["Vague maybe-yes-maybe-no", "Meaning starts to blur"],
    },
    {
        "what": "Score 3: a view with weak or thin evidence; one or more clear weaknesses",
        "signals": ["Repeats the claim", "One anecdote, no reasoning"],
    },
    {
        "what": "Score 4: generally organized and focused; some evidence; some errors",
        "signals": ["Both sides mentioned", "Uneven but readable"],
    },
    {
        "what": "Score 5: well organized; appropriate vocabulary; few errors",
        "signals": ["Clear line of argument", "A real counterargument"],
    },
    {
        "what": "Score 6: skillful, coherent, varied sentences, almost error-free",
        "signals": ["Precise claim with conditions", "Evidence used, not just named"],
    },
]

QUESTIONS = {
    "holistic": Score(
        instructions={
            "question": "What holistic AES score does `essay.text` earn on `essay.prompt`?",
            "inspect": "`essay.text`",
            "focus": "The published 1-6 rubric, not handwriting or length alone.",
        },
        criteria=HOLISTIC_LEVELS,
    ),
    "thesis": Noul(
        instructions={
            "question": "Does `essay.text` take a viable point of view on `essay.prompt`?",
            "inspect": "`essay.text`",
        },
        criteria=NoulCriteria(
            true="A readable yes/no/conditional stance on the prompt",
            false="No claim, or the claim is about something else",
        ),
    ),
    "evidence": Noul(
        instructions="Does the essay support that stance with reasons or examples, not just repetition?",
        criteria=NoulCriteria(
            true="At least one reason or example that could change a skeptic's mind",
            false="Restates the claim, or examples are missing",
        ),
    ),
    "off_prompt": Noul(
        instructions="Is `essay.text` answering a different question than `essay.prompt`?",
        criteria=NoulCriteria(
            true="Topic drift: vacation, unrelated story, ignores the issue",
            false="On the assigned issue, even if the argument is weak",
        ),
    ),
    "errors_obscure": Noul(
        instructions="Do grammar or mechanics errors make the meaning hard to follow?",
        criteria=NoulCriteria(
            true="Broken sentences hide the claim",
            false="Errors exist but a reader still gets the argument",
        ),
    ),
}


def compose(holistic: float, thesis: float, evidence: float, off_prompt: float, errors: float) -> dict:
    """Map Jev outputs to an AES integer. Caps are policy, not the model."""
    raw = holistic + 1.0  # Score level 0 → AES 1
    caps = []
    if off_prompt >= 0.70:
        caps.append(1)
    if thesis < 0.35 and evidence < 0.35:
        caps.append(2)
    if errors >= 0.70:
        caps.append(2)
    capped = raw
    for cap in caps:
        capped = min(capped, cap)
    aes = int(round(min(6, max(1, capped))))
    if off_prompt >= 0.70 or aes <= 2:
        inbox = "reteach"
    elif aes <= 4:
        inbox = "revise"
    else:
        inbox = "strong"
    return {"aes_score": aes, "raw_holistic": round(raw, 2), "inbox": inbox}


def grade(essay: dict) -> dict:
    state = {
        "task": "AES 2 holistic scoring",
        "essay": {
            "prompt": essay["prompt"],
            "text": essay["text"],
        },
    }
    with TypeSafeClient(api_key=load_api_key()) as client:
        response = client.system_one(state=state, questions=QUESTIONS, model=MODEL)
    a = response.answers
    traits = {
        "holistic": round(a["holistic"].score, 2),
        "thesis": round(a["thesis"].noul, 3),
        "evidence": round(a["evidence"].noul, 3),
        "off_prompt": round(a["off_prompt"].noul, 3),
        "errors_obscure": round(a["errors_obscure"].noul, 3),
    }
    out = compose(
        traits["holistic"],
        traits["thesis"],
        traits["evidence"],
        traits["off_prompt"],
        traits["errors_obscure"],
    )
    return {
        "id": essay["id"],
        "prompt": essay["prompt"],
        "expected_score": essay["expected_score"],
        **traits,
        **out,
        "hit": out["aes_score"] == essay["expected_score"],
        "within_1": abs(out["aes_score"] - essay["expected_score"]) <= 1,
        "model": response.model,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="AES-2-shaped Jev essay scorer")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    essays = json.loads(ESSAYS.read_text(encoding="utf-8"))
    rows = [grade(e) for e in essays]
    if args.json:
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return
    print(f"{'id':<22}{'exp':>4}{'got':>4}{'raw':>6}  th  ev  off  err  inbox")
    for r in rows:
        print(
            f"{r['id']:<22}{r['expected_score']:4}{r['aes_score']:4}{r['raw_holistic']:6.2f}  "
            f"{r['thesis']:.2f} {r['evidence']:.2f} {r['off_prompt']:.2f} "
            f"{r['errors_obscure']:.2f}  {r['inbox']}"
        )
    print(
        f"\nexact {sum(r['hit'] for r in rows)}/{len(rows)}  "
        f"within-1 {sum(r['within_1'] for r in rows)}/{len(rows)}"
    )


if __name__ == "__main__":
    main()
