"""CKE-shaped scoring of a Polish matura rozprawka (Formula 2023, max 35).

Jev judges argument, functional use of readings, and composition.
Code owns word count, the all-zero rule, and the point sum.
Jev does not count spelling/punctuation errors — those CKE cells stay
unscored or get a coarse language Score, not a tally.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from typesafe_sdk import Noul, NoulCriteria, Score, TypeSafeClient

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
from env import load_api_key

MODEL = "jev-latest"
ESSAYS = Path(__file__).resolve().parent / "data" / "essays.json"

QUESTIONS = {
    "on_topic": Noul(
        instructions={
            "question": "Czy `essay.text` przynajmniej częściowo dotyczy problemu z `essay.topic`?",
            "inspect": "`essay.text`",
        },
        criteria=NoulCriteria(
            true="Widać stanowisko albo rozważanie tego problemu",
            false="Inny temat albo same ogólniki bez związku z poleceniem",
        ),
    ),
    "is_argument": Noul(
        instructions="Czy to wypowiedź argumentacyjna (teza i uzasadnienie), nie opis ani samo streszczenie?",
        criteria=NoulCriteria(
            true="Jest stanowisko i próba uzasadnienia",
            false="Tylko streszczenie fabuły albo luźne impresje",
        ),
    ),
    "has_lektura": Noul(
        instructions="Czy praca odwołuje się do lektury obowiązkowej (np. Lalka, Pan Tadeusz, Dziady)?",
        criteria=NoulCriteria(
            true="Nazwany utwór z kanonu i jakakolwiek treść z niego",
            false="Brak lektury obowiązkowej",
        ),
    ),
    "blad_kardynalny": Noul(
        instructions={
            "question": "Czy jest błąd kardynalny: rażąca nieznajomość fabuły, losów głównych bohaterów albo całkowicie nieuprawniona interpretacja lektury obowiązkowej?",
            "focus": "Tylko lektura obowiązkowa, nie literówka w nazwisku drugoplanowym.",
        },
        criteria=NoulCriteria(
            true={
                "what": "Fałszywa fabuła kanoniczna, np. Wokulski umiera na pierwszej stronie Lalki",
                "examples": ["Izabela prowadzi sklep Wokulskiego od początku powieści"],
            },
            false="Drobny błąd rzeczowy albo poprawne odwołanie",
        ),
    ),
    "lektura_funkcjonalna": Noul(
        instructions="Czy lektura obowiązkowa jest użyta funkcjonalnie: wniosek / refleksja, nie samo streszczenie wątku?",
        criteria=NoulCriteria(
            true="Z utworu wynika argument wobec tematu",
            false="Streszczenie bez wniosku związanego z problemem",
        ),
    ),
    "drugi_utwor_funkcjonalny": Noul(
        instructions="Czy drugi utwór (lub drugi tekst kultury) jest użyty funkcjonalnie?",
        criteria=NoulCriteria(
            true="Drugi tekst pogłębia argument",
            false="Brak drugiego utworu albo samo wymienienie tytułu",
        ),
    ),
    "kontekst": Noul(
        instructions="Czy jest funkcjonalny kontekst (historyczny, filozoficzny, biograficzny, kulturowy…), nie lista haseł?",
        criteria=NoulCriteria(
            true="Kontekst coś wyjaśnia w argumencie",
            false="Brak kontekstu albo puste hasło",
        ),
    ),
    "argumentacja": Score(
        instructions={
            "question": "Jaka jest jakość argumentacji wobec `essay.topic`?",
            "inspect": "`essay.text`",
        },
        criteria=[
            {"what": "Brak argumentacji albo same ogólniki"},
            {"what": "Powierzchowna: teza i jedno słabe uzasadnienie"},
            {"what": "Zadowalająca: dwa argumenty, choć nierówne"},
            {"what": "Bogata: zróżnicowane racje, erudycja, wniosek"},
        ],
    ),
    "struktura": Score(
        instructions="Czy kompozycja jest problemowa (wstęp — rozwinięcie — zakończenie; akapity wokół aspektów problemu, nie linia 'najpierw lektura A, potem B')?",
        criteria=[
            {"what": "Zbiór luźnych zdań, brak organizacji"},
            {"what": "Usterki w podziale ogólnym i w akapitach"},
            {"what": "Usterki albo tylko w skali ogólnej, albo tylko w akapitach"},
            {"what": "Poprawna struktura ogólna i akapitowa; dopuszczalna 1 usterka"},
        ],
    ),
    "spojnosc": Score(
        instructions="Jak spójna jest wypowiedź (kolejny akapit wynika z poprzedniego)?",
        criteria=[
            {"what": "9+ zaburzeń albo wstęp/zakończenie oderwane od całości"},
            {"what": "6–8 zaburzeń albo wstęp/zakończenie niespójne z resztą"},
            {"what": "3–5 zaburzeń spójności"},
            {"what": "Całość spójna albo najwyżej 2 zaburzenia"},
        ],
    ),
    "styl": Noul(
        instructions="Czy styl jest stosowny do pisanej odmiany polszczyzny egzaminacyjnej (nie żargon czatu, nie pastisz)?",
        criteria=NoulCriteria(
            true="Język pisany, jednolity albo funkcjonalnie zróżnicowany",
            false="Kolokwialny, chaotyczny albo udawanie obcej konwencji bez funkcji",
        ),
    ),
    "jezyk_zakres": Score(
        instructions="Jaki jest zakres środków językowych (składnia i leksyka), nie liczba błędów?",
        criteria=[
            {"what": "Wąski: proste zdania, ubogie słownictwo"},
            {"what": "Zadowalający: stosowna składnia i leksyka"},
            {"what": "Szeroki: zróżnicowana składnia, precyzyjna leksyka"},
        ],
    ),
}


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-zÀ-ž0-9]+", text, flags=re.UNICODE))


def band(score: float, n_levels: int) -> int:
    """Map a TypeSafe Score (0 .. n_levels-1) to an integer 0 .. n_levels-1."""
    return int(round(min(n_levels - 1, max(0, score))))


def compose(answers: dict, n_words: int) -> dict:
    """CKE-shaped sum. Zero the paper on cardinal / failed formal gate."""
    kard = answers["blad_kardynalny"].noul
    on_topic = answers["on_topic"].noul
    is_arg = answers["is_argument"].noul
    has_lek = answers["has_lektura"].noul
    formal_ok = kard < 0.70 and on_topic >= 0.50 and is_arg >= 0.50 and has_lek >= 0.50
    formal = 1 if formal_ok else 0

    if kard >= 0.70 or not formal_ok:
        return {
            "formal": 0,
            "literary": 0,
            "composition": 0,
            "language": 0,
            "total": 0,
            "max": 35,
            "gate": "blad_kardynalny" if kard >= 0.70 else "formal_fail",
            "n_words": n_words,
        }

    lek = answers["lektura_funkcjonalna"].noul
    drugi = answers["drugi_utwor_funkcjonalny"].noul
    ctx = answers["kontekst"].noul
    arg = band(answers["argumentacja"].score, 4)  # 0-3
    literary = 0
    if lek >= 0.70:
        literary += 8
    elif lek >= 0.40:
        literary += 4
    if drugi >= 0.70:
        literary += 4
    elif drugi >= 0.40:
        literary += 2
    literary += [0, 2, 3, 4][arg]
    if ctx >= 0.70:
        literary += 2
    elif ctx >= 0.40:
        literary += 1
    literary = min(16, literary)

    struktura = band(answers["struktura"].score, 4)  # 0-3
    spojnosc = band(answers["spojnosc"].score, 4)
    styl = 1 if answers["styl"].noul >= 0.55 else 0
    composition = struktura + spojnosc + styl  # max 7

    zakres = band(answers["jezyk_zakres"].score, 3)  # 0-2
    language = [3, 5, 7][zakres]
    # Ortografia + interpunkcja (max 4) — not counted here.
    language_note = "language excludes CKE spelling/punctuation tallies (max 4 left unscored)"

    short = n_words < 300
    if short:
        composition = 0
        language = 0
        language_note = "under 300 words: CKE scores only formal + literary"

    total = formal + literary + composition + language
    return {
        "formal": formal,
        "literary": literary,
        "composition": composition,
        "language": language,
        "total": total,
        "max": 35 if not short else 17,
        "gate": "short" if short else "ok",
        "n_words": n_words,
        "language_note": language_note,
    }


def grade(essay: dict) -> dict:
    n_words = word_count(essay["text"])
    state = {
        "task": "CKE matura język polski — wypracowanie (rozprawka), Formuła 2023",
        "essay": {"topic": essay["topic"], "text": essay["text"]},
        "rules": {
            "min_words": 300,
            "blad_kardynalny_zeroes_paper": True,
            "streszczenie_nie_jest_argumentem": True,
        },
    }
    with TypeSafeClient(api_key=load_api_key()) as client:
        response = client.system_one(state=state, questions=QUESTIONS, model=MODEL)
    a = response.answers
    points = compose(a, n_words)
    traits = {
        "on_topic": round(a["on_topic"].noul, 3),
        "is_argument": round(a["is_argument"].noul, 3),
        "has_lektura": round(a["has_lektura"].noul, 3),
        "blad_kardynalny": round(a["blad_kardynalny"].noul, 3),
        "lektura_funkcjonalna": round(a["lektura_funkcjonalna"].noul, 3),
        "drugi_utwor_funkcjonalny": round(a["drugi_utwor_funkcjonalny"].noul, 3),
        "kontekst": round(a["kontekst"].noul, 3),
        "argumentacja": round(a["argumentacja"].score, 2),
        "struktura": round(a["struktura"].score, 2),
        "spojnosc": round(a["spojnosc"].score, 2),
        "styl": round(a["styl"].noul, 3),
        "jezyk_zakres": round(a["jezyk_zakres"].score, 2),
    }
    return {
        "id": essay["id"],
        "topic": essay["topic"],
        "note": essay.get("note"),
        **traits,
        **points,
        "model": response.model,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    essays = json.loads(ESSAYS.read_text(encoding="utf-8"))
    rows = [grade(e) for e in essays]
    if args.json:
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return
    print(f"{'id':<16}{'tot':>5}  form lit cmp lang  kard  funk  arg   gate")
    for r in rows:
        print(
            f"{r['id']:<16}{r['total']:3}/{r['max']:<2}  "
            f"{r['formal']:4} {r['literary']:3} {r['composition']:3} {r['language']:4}  "
            f"{r['blad_kardynalny']:.2f} {r['lektura_funkcjonalna']:.2f} "
            f"{r['argumentacja']:.1f}  {r['gate']}"
        )


if __name__ == "__main__":
    main()
