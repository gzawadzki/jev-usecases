"""Route a bank-chat utterance to one specialist via Jev.

Each specialist has a short agent card (does / does_not / examples).
Jev returns a Choice over cards plus Nouls (needs a specialist, fits each card).
Code loads at most one agent's context — or none.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from typesafe_sdk import Choice, Noul, NoulCriteria, TypeSafeClient

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
from env import load_api_key

MODEL = "jev-latest"
DATA = Path(__file__).resolve().parent / "data"
CARDS_PATH = DATA / "cards.json"
QUERIES_PATH = DATA / "queries.json"

GATE = 0.30
FITS = 0.35
CLARIFY_GAP = 0.12


def _choice_option(card: dict) -> dict:
    return {
        "what": "; ".join(card["does"]),
        "not_for": "; ".join(card["does_not"]),
        "loads": card["loads"],
        "examples": card["examples"],
    }


def questions(cards: list[dict]) -> dict:
    """One Choice + 1+N Nouls. All run in parallel on the same utterance."""
    which_criteria = {c["id"]: _choice_option(c) for c in cards}
    which_criteria["none"] = {
        "what": "Small talk, wiedza ogólna, albo prośba spoza systemów banku",
        "not_for": "Cokolwiek, co wymaga salda, wniosku, płatności, logowania albo mapy ekranów",
        "examples": ["jaka pogoda w Gdańsku", "opowiedz żart o banku"],
    }
    q: dict = {
        "which": Choice(
            instructions={
                "question": "Który jeden agent powinien dostać `utterance` i swój kontekst?",
                "inspect": "`utterance`",
                "focus": (
                    "Intencja, nie wspólne słowa. "
                    "'Gdzie jest X w aplikacji' to navigation, nie treść X. "
                    "'Pokaż / status / zrób X' to agent od X."
                ),
            },
            criteria=which_criteria,
        ),
        "needs_specialist": Noul(
            instructions={
                "question": "Czy `utterance` wymaga narzędzi albo danych bankowych?",
                "inspect": "`utterance`",
                "focus": "Czy trzeba załadować specjalistę, czy wystarczy rozmowa.",
            },
            criteria=NoulCriteria(
                true={
                    "what": "Saldo, historia, przelew, BLIK, wniosek, zdolność, logowanie, PIN, ścieżka w menu",
                    "examples": [
                        "pokaż transakcje",
                        "gdzie są wnioski",
                        "zrób przelew",
                    ],
                },
                false={
                    "what": "Pogoda, żart, ciekawostka, czysta rozmowa bez systemów banku",
                    "examples": ["jaka pogoda", "opowiedz żart"],
                },
            ),
        ),
    }
    for card in cards:
        q[f"fits::{card['id']}"] = Noul(
            instructions={
                "question": (
                    f"Czy agent `{card['id']}` ({card['title']}) robi to, o co prosi `utterance`?"
                ),
                "inspect": "`utterance`",
                "focus": "Tylko ta karta. Sąsiednie agenty oceniane są osobnymi pytaniami.",
            },
            criteria=NoulCriteria(
                true={
                    "what": "; ".join(card["does"]),
                    "examples": card["examples"],
                },
                false={
                    "what": "; ".join(card["does_not"]),
                    "not_for": f"To nie jest zadanie dla `{card['id']}`, nawet jeśli padają te same słowa",
                },
            ),
        )
    return q


def decide(answers: dict, card_ids: list[str]) -> dict:
    which = answers["which"].choice
    needs = answers["needs_specialist"].noul
    fits = {cid: answers[f"fits::{cid}"].noul for cid in card_ids}
    ranked = sorted(fits.items(), key=lambda kv: -kv[1])
    best_id, best = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0

    if needs < GATE or max(fits.values()) < FITS:
        agent, reason = "none", "no_specialist"
    elif which != "none" and which in fits and fits[which] >= FITS:
        agent, reason = which, "choice"
        if best_id != which and best - fits[which] > CLARIFY_GAP:
            agent, reason = "clarify", "fits_disagree_with_choice"
        elif best_id != which and abs(best - fits[which]) <= CLARIFY_GAP:
            agent, reason = "clarify", "close_call"
    elif best >= FITS and best - second > CLARIFY_GAP:
        agent, reason = best_id, "fits"
    else:
        agent, reason = "clarify", "ambiguous"

    return {
        "agent": agent,
        "reason": reason,
        "which": which,
        "needs_specialist": round(needs, 3),
        "fits": {k: round(v, 3) for k, v in fits.items()},
        "which_confidence": round(answers["which"].confidence, 3),
    }


def route_utterance(text: str, cards: list[dict]) -> dict:
    state = {"utterance": text, "product": "bank chat"}
    with TypeSafeClient(api_key=load_api_key()) as client:
        response = client.system_one(
            state=state, questions=questions(cards), model=MODEL
        )
    out = decide(response.answers, [c["id"] for c in cards])
    out["text"] = text
    out["model"] = response.model
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Route bank-chat utterances to agents")
    parser.add_argument("text", nargs="?", help="One utterance")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    cards = json.loads(CARDS_PATH.read_text(encoding="utf-8"))

    if args.demo:
        queries = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
        rows = []
        for q in queries:
            row = route_utterance(q["text"], cards)
            row["expected"] = q["expected"]
            row["hit"] = row["agent"] == q["expected"]
            rows.append(row)
        if args.json:
            json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
            print()
            return
        print(f"{'hit':<5}{'got':<16}{'exp':<16}{'need':>5}  text")
        for r in rows:
            mark = "ok" if r["hit"] else "miss"
            print(
                f"{mark:<5}{r['agent']:<16}{r['expected']:<16}"
                f"{r['needs_specialist']:5.2f}  {r['text']}"
            )
        print(f"\n{sum(r['hit'] for r in rows)}/{len(rows)} hit")
        return

    if not args.text:
        parser.error("pass an utterance or --demo")
    result = route_utterance(args.text, cards)
    if args.json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return
    print(f"{result['agent']}  ({result['reason']})  needs={result['needs_specialist']:.2f}")
    for cid, p in sorted(result["fits"].items(), key=lambda kv: -kv[1]):
        print(f"  fits {p:.2f}  {cid}")


if __name__ == "__main__":
    main()
