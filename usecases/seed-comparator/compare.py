"""Semantic comparator for a Bielik seed: Jev judges answer vs ground truth.

This is not the blind LLM-sędzia (that one sees the image, no GT).
Jev is text-only. It sits beside seedlab compare() (normalized strings +
Levenshtein) and types errors with the seed's error_types.

Vocabulary follows seed-definition CONTEXT.md.
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
CASES_PATH = Path(__file__).resolve().parent / "data" / "cases.json"

CRITERIA = """
Odpowiedź musi zawierać wyłącznie fragmenty tekstu faktycznie wyróżnione
(zbiór fragmentów wyróżnionych i nic poza nimi).
Styl układu (tytuły, nagłówki, etykiety pól, logo) nie jest wyróżnieniem.
Oznaczenie obok tekstu (checkbox, radio, ptaszek, strzałka) wyróżnia tekst,
na który wskazuje. Przekreślenie liczy się jako wyróżnienie.
Fragmenty powinny obejmować całe słowa. Przykład negatywny → pusta lista [].
"""

QUESTIONS = {
    "same_set": Noul(
        instructions={
            "question": "Czy `answer.fragments` to ten sam zbiór treści co `ground_truth`, dopuszczając drobne różnice zapisu?",
            "focus": "Znaczenie fragmentów, nie identyczność znaków.",
        },
        criteria=NoulCriteria(
            true={
                "what": "Te same wyróżnione fragmenty; wolno: wielkość liter, cudzysłowy, oczywista literówka w jednym słowie",
            },
            false={
                "what": "Brakuje wyróżnienia, jest extra fragment, albo odpowiedź nie jest listą fragmentów",
            },
        ),
    ),
    "niewlasciwy_format": Noul(
        instructions="Czy `answer.raw` nie jest listą stringów (JSON array of strings)?",
        criteria=NoulCriteria(
            true="Nie da się odczytać listy fragmentów: proza, obiekty, markdown bez tablicy stringów",
            false="Da się odczytać listę stringów, także pustą []",
        ),
    ),
    "literowka": Noul(
        instructions="Czy któryś fragment z `answer.fragments` to ten sam tekst co w `ground_truth`, ale z drobną literówką lub inną interpunkcją?",
        criteria=NoulCriteria(
            true="Prawie to samo słowo/zdanie, 1–2 znaki różnicy",
            false="Brak pary różniącej się tylko literówką; albo format jest zły",
        ),
    ),
    "nadmiarowy_fragment": Noul(
        instructions="Czy `answer.fragments` zawiera treść, której nie ma w `ground_truth` (nagłówek, etykieta, zgadywanie 'ważnego')?",
        criteria=NoulCriteria(
            true="Extra fragment, który nie jest literówką istniejącego GT",
            false="Brak dodatkowego fragmentu albo zły format",
        ),
    ),
    "brakujacy_fragment": Noul(
        instructions="Czy w `answer.fragments` brakuje któregoś elementu `ground_truth`?",
        criteria=NoulCriteria(
            true="GT ma fragment, którego nie ma w odpowiedzi nawet jako literówka",
            false="Wszystkie fragmenty GT są obecne albo format jest zły",
        ),
    ),
    "error_type": Choice(
        instructions={
            "question": "Jaki pojedynczy typ błędu najlepiej opisuje `answer` względem `ground_truth`?",
            "focus": "Jeden etykieta; brak gdy zbiór się zgadza.",
        },
        criteria={
            "brak": "Zbiór fragmentów się zgadza",
            "niewlasciwy_format": "Nie jest listą stringów",
            "literowka": "Prawie te same fragmenty, różnica zapisu",
            "nadmiarowy_fragment": "Jest treść spoza GT (układ, zgadywanie)",
            "brakujacy_fragment": "Brakuje wyróżnienia z GT",
        },
    ),
}


def screen(case: dict) -> dict:
    state = {
        "seed": "visual-emphasis",
        "criteria": CRITERIA,
        "ground_truth": case["ground_truth"],
        "answer": {
            "raw": case["answer_raw"],
            "fragments": case.get("answer_fragments"),
        },
        "negative_example": case.get("negative", False),
    }
    with TypeSafeClient(api_key=load_api_key()) as client:
        response = client.system_one(state=state, questions=QUESTIONS, model=MODEL)
    a = response.answers
    return {
        "id": case["id"],
        "note": case.get("note"),
        "ground_truth": case["ground_truth"],
        "answer_raw": case["answer_raw"],
        "same_set": round(a["same_set"].noul, 3),
        "niewlasciwy_format": round(a["niewlasciwy_format"].noul, 3),
        "literowka": round(a["literowka"].noul, 3),
        "nadmiarowy_fragment": round(a["nadmiarowy_fragment"].noul, 3),
        "brakujacy_fragment": round(a["brakujacy_fragment"].noul, 3),
        "error_type": a["error_type"].choice,
        "error_confidence": round(a["error_type"].confidence, 3),
        "model": response.model,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    rows = [screen(c) for c in cases]
    if args.json:
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return
    print(
        f"{'id':<22}{'same':>6}{'fmt':>6}{'typo':>6}{'extra':>6}{'miss':>6}  error"
    )
    for r in rows:
        print(
            f"{r['id']:<22}{r['same_set']:6.2f}{r['niewlasciwy_format']:6.2f}"
            f"{r['literowka']:6.2f}{r['nadmiarowy_fragment']:6.2f}"
            f"{r['brakujacy_fragment']:6.2f}  {r['error_type']}"
        )


if __name__ == "__main__":
    main()
