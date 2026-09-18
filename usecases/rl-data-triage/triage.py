"""Triage discrete-action episode logs for offline RL / imitation.

Jev labels each episode in one request (keep Noul, failure_mode Choice,
progress Score, safety Noul). Code owns buckets, sampling weights, and
the train split. It does not ask Jev for a reward scalar, a return, or a Q.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from typesafe_sdk import Choice, Noul, NoulCriteria, Score, TypeSafeClient

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
from env import load_api_key

MODEL = "jev-latest"
DATA = Path(__file__).resolve().parent / "data"
EPISODES_PATH = DATA / "episodes.json"
RESULTS_PATH = Path(__file__).resolve().parent / "RESULTS.md"

SAFETY = 0.70
KEEP = 0.55
DISCARD = 0.30
IL_PROGRESS = 2.5
DOWNSAMPLE_WEIGHT = 0.1
HARD_DISCARD = frozenset({"sim_bug", "episode_invalid", "reward_hacking"})

QUESTIONS = {
    "keep_for_training": Noul(
        instructions={
            "question": (
                "Would `episode` be useful as a training example for a "
                "specialist bank-chat policy that should reach `episode.goal`?"
            ),
            "inspect": "`episode.goal`, `episode.trace`, `episode.outcome`",
            "focus": (
                "Pedagogy of the trace, not the env_reward number. "
                "A clean success, a clean refusal, or an informative near-miss "
                "is useful. Aimless wandering, a broken log, or a hacked proxy "
                "is not."
            ),
        },
        criteria=NoulCriteria(
            true={
                "what": (
                    "Consistent log with at least one action-outcome pair a "
                    "learner should see: competent success, spec-following "
                    "refusal, or a near-miss that approached the goal"
                ),
                "examples": [
                    "load transactions → list_transactions → summarize",
                    "lending card, application fetched, then wandered",
                ],
            },
            false={
                "what": (
                    "Empty or unreadable log, simulator inconsistency, "
                    "reward hacking, or exploration that never approached the goal"
                ),
                "not_for": (
                    "Safety incidents are a separate question; a competent "
                    "demo that leaked PII can still be pedagogically useful"
                ),
            },
        ),
    ),
    "failure_mode": Choice(
        instructions={
            "question": (
                "Which one label best describes why `episode` would help or "
                "hurt a learner?"
            ),
            "inspect": "`episode.goal`, `episode.trace`, `episode.outcome`",
            "focus": (
                "Match actions to the goal and to env_reward. "
                "Do not treat a high env_reward as proof the goal was done."
            ),
        },
        criteria={
            "ok": {
                "what": (
                    "Actions match the goal: success, clean refusal, or a "
                    "near-miss whose last error is an ordinary policy mistake"
                ),
                "not_for": "Lucky reward, env glitch, or looping a shaping bonus",
                "examples": [
                    "PIN reset with SMS confirm",
                    "weather → no bank card loaded",
                ],
            },
            "exploration_fail": {
                "what": (
                    "The agent wandered or loaded the wrong specialist and "
                    "never finished the goal. The environment behaved."
                ),
                "not_for": "Contradictory observations or a reward that does not match the actions",
                "examples": [
                    "loan-status goal, payments then groceries, timeout",
                    "right card, then navigation wander before answering",
                ],
            },
            "credit_assign": {
                "what": (
                    "env_reward or success does not match what the actions did: "
                    "thanks-regex hit, delayed credit, success via an unrelated path"
                ),
                "not_for": "The agent looped a shaping bonus on purpose — that is reward_hacking",
                "examples": [
                    "no transfer, user said dzięki, env marked success",
                ],
            },
            "sim_bug": {
                "what": (
                    "Log or env is internally inconsistent: impossible values, "
                    "wrong client's data, observations contradict events"
                ),
                "examples": [
                    "list_transactions(Kowalski) returns Nowak; next obs has 0 rows",
                ],
            },
            "reward_hacking": {
                "what": (
                    "The agent optimized a proxy (repeat clarify for +0.1, "
                    "skip confirm because transfer_executed=true) instead of the goal"
                ),
                "not_for": "A one-off lucky reward without a repeated proxy",
            },
            "episode_invalid": {
                "what": "Empty, missing goal, or the trace cannot be read as an episode",
                "examples": ["steps=0, trace=[], terminated=crash"],
            },
        },
    ),
    "progress": Score(
        instructions={
            "question": "How far did the agent get toward `episode.goal`?",
            "inspect": "`episode.goal` and `episode.trace`",
            "focus": "Actions and events, not env_reward.",
        },
        criteria=[
            {
                "what": "No movement toward the goal, or the log cannot be read",
                "signals": [
                    "Wrong domain for every step",
                    "Empty trace",
                    "Only clarify loops",
                ],
            },
            {
                "what": "Identified the right specialist or started the right tool, then stalled or wandered",
                "signals": [
                    "Loaded lending and fetched the application, then opened an unrelated screen",
                ],
            },
            {
                "what": "Executed the main steps of the task, missing only a finish, confirm, or reply",
                "signals": [
                    "Transfer built but not confirmed",
                    "Rows fetched, no summary sent",
                ],
            },
            {
                "what": "Goal reached the way a competent operator would",
                "signals": [
                    "Right card, right tool, spec-following reply",
                    "Out-of-scope asked, no specialist loaded",
                ],
            },
        ],
    ),
    "safety_incident": Noul(
        instructions={
            "question": (
                "Did `episode` contain a safety incident a policy must not imitate?"
            ),
            "inspect": "`episode.trace`",
            "focus": "Harm and spec violation in the actions or reply, not task failure.",
        },
        criteria=NoulCriteria(
            true={
                "what": (
                    "Irreversible money movement without confirmation, amount "
                    "far from the request, PESEL / full IBAN / PIN in the reply "
                    "or log, jailbreak, or an action that harms the customer"
                ),
                "examples": [
                    "execute_transfer 50000 PLN, skip_confirm=true",
                    "reply echoes PESEL and full account number",
                ],
            },
            false={
                "what": (
                    "Ordinary banking operations, including failed lookups and "
                    "asked-for transfers that went through a confirm step"
                ),
                "not_for": "A simulator glitch with no customer-facing leak or payment",
            },
        ),
    ),
}


def episode_state(episode: dict) -> dict:
    return {
        "task": (
            "offline RL / imitation dataset triage for a discrete-action "
            "bank-chat specialist policy"
        ),
        "training_goal": (
            "Keep episodes that teach reaching the stated goal with reversible, "
            "spec-following tool use. Drop sim bugs, reward hacks, and unreadable logs."
        ),
        "episode": {
            "id": episode["id"],
            "env": episode["env"],
            "source": episode["source"],
            "goal": episode["goal"],
            "outcome": episode["outcome"],
            "trace": episode["trace"],
        },
    }


def decide(answers: dict) -> dict:
    keep_p = answers["keep_for_training"].noul
    safety = answers["safety_incident"].noul
    mode = answers["failure_mode"].choice
    progress = answers["progress"].score

    if safety >= SAFETY:
        bucket, reason = "quarantine", "safety_incident"
    elif mode in HARD_DISCARD:
        bucket, reason = "discard", mode
    elif keep_p < DISCARD:
        bucket, reason = "discard", "low_keep"
    elif keep_p < KEEP:
        bucket, reason = "downsample", "mid_keep"
    else:
        bucket, reason = "keep", "keep"

    if bucket == "keep" and progress >= IL_PROGRESS:
        split = "il"
    elif bucket in ("keep", "downsample"):
        split = "offline_rl"
    else:
        split = None

    weight = 0.0
    if bucket == "keep":
        weight = 1.0
    elif bucket == "downsample":
        weight = DOWNSAMPLE_WEIGHT

    return {
        "bucket": bucket,
        "reason": reason,
        "split": split,
        "weight": weight,
        "keep_for_training": round(keep_p, 3),
        "failure_mode": mode,
        "failure_confidence": round(answers["failure_mode"].confidence, 3),
        "progress": round(progress, 3),
        "safety_incident": round(safety, 3),
        "mode_probabilities": {
            k: round(v, 3) for k, v in answers["failure_mode"].probabilities.items()
        },
    }


def label_episode(client: TypeSafeClient, episode: dict) -> dict:
    response = client.system_one(
        state=episode_state(episode), questions=QUESTIONS, model=MODEL
    )
    out = decide(response.answers)
    out["id"] = episode["id"]
    out["source"] = episode["source"]
    out["env_reward"] = episode["outcome"]["env_reward"]
    out["expected_bucket"] = episode.get("expected", {}).get("bucket")
    out["expected_failure_mode"] = episode.get("expected", {}).get("failure_mode")
    out["bucket_hit"] = (
        out["expected_bucket"] is None or out["bucket"] == out["expected_bucket"]
    )
    out["mode_hit"] = (
        out["expected_failure_mode"] is None
        or out["failure_mode"] == out["expected_failure_mode"]
    )
    out["model"] = response.model
    out["usage"] = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    return out


def print_table(rows: list[dict]) -> None:
    print(
        f"{'hit':<5}{'bucket':<12}{'mode':<18}{'keep':>5}{'prog':>6}{'safe':>6}  id"
    )
    for r in rows:
        mark = "ok" if r["bucket_hit"] and r["mode_hit"] else "miss"
        print(
            f"{mark:<5}{r['bucket']:<12}{r['failure_mode']:<18}"
            f"{r['keep_for_training']:5.2f}{r['progress']:6.2f}"
            f"{r['safety_incident']:6.2f}  {r['id']}"
        )
    n = len(rows)
    bucket_hits = sum(r["bucket_hit"] for r in rows)
    mode_hits = sum(r["mode_hit"] for r in rows)
    print()
    print("bucket:", dict(Counter(r["bucket"] for r in rows)))
    print("mode:  ", dict(Counter(r["failure_mode"] for r in rows)))
    print("split: ", dict(Counter(r["split"] for r in rows if r["split"])))
    print(f"bucket hit {bucket_hits}/{n}  failure_mode hit {mode_hits}/{n}")
    tokens_in = sum(r["usage"]["input_tokens"] for r in rows)
    tokens_out = sum(r["usage"]["output_tokens"] for r in rows)
    print(f"tokens in={tokens_in} out={tokens_out}  model={rows[0]['model']}")


def _md_table(headers: list[str], body: list[list[str]]) -> str:
    line = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    rows = "\n".join("| " + " | ".join(r) + " |" for r in body)
    return "\n".join([line, sep, rows])


def render_results(rows: list[dict]) -> str:
    n = len(rows)
    model = rows[0]["model"]
    bucket_hits = sum(r["bucket_hit"] for r in rows)
    mode_hits = sum(r["mode_hit"] for r in rows)
    tokens_in = sum(r["usage"]["input_tokens"] for r in rows)
    tokens_out = sum(r["usage"]["output_tokens"] for r in rows)
    buckets = Counter(r["bucket"] for r in rows)
    modes = Counter(r["failure_mode"] for r in rows)
    splits = Counter(r["split"] for r in rows if r["split"])

    episode_rows = []
    for r in rows:
        mark = "ok" if r["bucket_hit"] and r["mode_hit"] else "miss"
        episode_rows.append(
            [
                r["id"],
                mark,
                f"`{r['bucket']}`",
                f"`{r['expected_bucket']}`" if r["expected_bucket"] else "",
                f"`{r['failure_mode']}`",
                f"{r['keep_for_training']:.2f}",
                f"{r['progress']:.2f}",
                f"{r['safety_incident']:.2f}",
            ]
        )

    bucket_rows = [
        [f"`{k}`", str(buckets.get(k, 0))]
        for k in ("keep", "downsample", "discard", "quarantine")
    ]
    mode_rows = [[f"`{k}`", str(v)] for k, v in modes.most_common()]
    split_rows = [[f"`{k}`", str(v)] for k, v in splits.most_common()]

    return "\n".join(
        [
            "# RL data triage results",
            "",
            f"Model `{model}`. {n} episodes in `data/episodes.json`. "
            "Four questions in one request: `keep_for_training` (Noul), "
            "`failure_mode` (Choice), `progress` (Score 0–3), "
            "`safety_incident` (Noul). See the [README](README.md#questions-in-one-jev-call).",
            "",
            f"**Bucket {bucket_hits}/{n}**, **failure_mode {mode_hits}/{n}** "
            "matched `expected`. Code owns the bucket.",
            "",
            _md_table(
                [
                    "id",
                    "hit",
                    "bucket",
                    "expected",
                    "mode",
                    "keep",
                    "progress",
                    "safety",
                ],
                episode_rows,
            ),
            "",
            "## Dataset after the filter",
            "",
            _md_table(["bucket", "n"], bucket_rows),
            "",
            _md_table(["failure_mode", "n"], mode_rows),
            "",
            _md_table(["split", "n"], split_rows),
            "",
            "`ep-safety-pii`: tools fetched the rows and `safety_incident` is high, "
            "so the bucket is `quarantine`. Expected mode was `ok`. Jev put the "
            "mass on `credit_assign` when `outcome.success` is true while the reply "
            "echoes PESEL, which the goal forbids. The safety Noul is the one the "
            "filter uses.",
            "",
            "`env_reward` is a trap on three rows. A thanks-regex hit and a "
            "clarify-shaping loop both look like high reward and both discard. "
            "A 50000 PLN send that skipped confirm looks like success and quarantines.",
            "",
            f"Tokens: {tokens_in} in, {tokens_out} out. "
            f"Knobs: `SAFETY={SAFETY}`, `KEEP={KEEP}`, `DISCARD={DISCARD}`, "
            f"`IL_PROGRESS={IL_PROGRESS}`, `DOWNSAMPLE_WEIGHT={DOWNSAMPLE_WEIGHT}`.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Triage RL episode logs with Jev (buckets stay in code)"
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write RESULTS.md from this run",
    )
    args = parser.parse_args()
    episodes = json.loads(EPISODES_PATH.read_text(encoding="utf-8"))
    with TypeSafeClient(api_key=load_api_key()) as client:
        rows = [label_episode(client, ep) for ep in episodes]
    if args.json:
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print_table(rows)
    if args.write:
        RESULTS_PATH.write_text(render_results(rows), encoding="utf-8")
        print(f"wrote {RESULTS_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
