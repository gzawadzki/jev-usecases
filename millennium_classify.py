"""Classify Bank Millennium Google Play reviews with TypeSafe (Jev)."""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from typesafe_sdk import Choice, Noul, NoulCriteria, Score, TypeSafeClient

MODEL = "jev-latest"
DATA_DIR = Path(__file__).resolve().parent / "data"
REVIEWS_PATH = DATA_DIR / "reviews.json"
CHECKPOINT = DATA_DIR / "classified.jsonl"
OUT_PATH = DATA_DIR / "classified.json"

QUESTIONS = {
    "topic": Choice(
        instructions={
            "question": "Jaki jest główny temat recenzji aplikacji Banku Millennium?",
            "inspect": "`review.text`",
            "focus": "Jedna dominująca skarga lub pochwała, nie ocena gwiazdkowa.",
        },
        criteria={
            "payments": {
                "what": "BLIK, karta, przelew, płatność w sklepie, awaria płatności",
                "not_for": "Ogólne lagowanie bez płatności",
            },
            "history_ux": {
                "what": "Historia, wyszukiwanie dat, tryb ciemny, czcionka, skróty, czytelność",
                "not_for": "Crash uniemożliwiający start aplikacji",
            },
            "login_activation": {
                "what": "Aktywacja, PIN, 2FA, numer telefonu, blokada po PIN, nowe urządzenie",
            },
            "device_os": {
                "what": "Stary Android, GrapheneOS, brak aktualizacji, crash po update OS",
            },
            "loans_upsell": {
                "what": "Wciskanie pożyczki, wniosek kredytowy, ocena zdolności",
            },
            "cards_fx": {
                "what": "Karta walutowa, przypisanie karty, płatności za granicą",
            },
            "feature_gap": {
                "what": "Brak konkretnej funkcji (debet, oszczędzanie, wyciągi pełnomocnika, zlecenie zmienne)",
                "not_for": "Ogólne 'chcę żeby działało'",
            },
            "performance": {
                "what": "Lagi, zawieszanie, awarie, niska liczba klatek, crash w sklepie",
            },
            "channel_lockin": {
                "what": "Wymuszenie aplikacji kosztem pulpitu / SMS, bez telefonu brak dostępu",
            },
            "praise": {
                "what": "Pochwała banku lub aplikacji bez konkretnej skargi",
            },
            "other": {
                "what": "Inny temat albo mieszanka bez wyraźnego lidera",
            },
        },
    ),
    "bug": Noul(
        instructions={
            "question": "Czy recenzja zgłasza konkretny błąd działania aplikacji?",
            "inspect": "`review.text`",
        },
        criteria=NoulCriteria(
            true={
                "what": "Crash, zła data, lag, nieczytelny UI, awaria płatności, błąd po aktualizacji",
                "examples": ["wyszukiwanie daty wyskakuje 2026", "SEGV_MTESERR"],
            },
            false={
                "what": "Brak funkcji, upsell, opinia o banku, sama pochwała",
            },
        ),
    ),
    "feature_request": Noul(
        instructions={
            "question": "Czy recenzja prosi o nową albo przywróconą funkcję?",
            "inspect": "`review.text`",
        },
        criteria=NoulCriteria(
            true={
                "what": "Brakuje X, warto dodać, w ING jest, dajcie skrót / debet / zaokrąglanie",
            },
            false={
                "what": "Tylko błąd, awaria, upsell albo pochwała",
            },
        ),
    ),
    "churn": Noul(
        instructions={
            "question": "Czy autor grozi odejściem z banku albo już rezygnuje?",
            "inspect": "`review.text`",
        },
        criteria=NoulCriteria(
            true={
                "what": "Zrezygnuję, zmieniam bank, spłacę i odchodzę, dawno bym zrezygnował",
            },
            false={
                "what": "Krytyka bez zapowiedzi odejścia, albo deklaracja że zostaje",
            },
        ),
    ),
    "needs_reply": Noul(
        instructions={
            "question": "Czy zespół produktu albo support powinien odpowiedzieć merytorycznie, a nie samym podziękowaniem?",
            "inspect": "`review.text`",
            "focus": "Jest konkret do sprawdzenia albo do wyjaśnienia.",
        },
        criteria=NoulCriteria(
            true={
                "what": "Reprodukowalny błąd, luka funkcji, groźba odejścia, problem karty/logowania",
            },
            false={
                "what": "Krótka pochwała albo ogólnik bez faktów",
            },
        ),
    ),
    "frustration": Score(
        instructions={
            "question": "Jak bardzo sfrustrowany jest autor recenzji?",
            "inspect": "`review.text`",
            "focus": "Ton wypowiedzi, nie liczba gwiazdek w sklepie.",
        },
        criteria=[
            {
                "what": "Zadowolony lub neutralny",
                "signals": ["Pochwała", "Spokojna sugestia"],
            },
            {
                "what": "Irytacja, ale konkretna i konstruktywna",
                "signals": ["Odejmuję gwiazdki za X", "Proszę naprawić"],
            },
            {
                "what": "Silna złość, wulgaryzm, poczucie bycia oszukanym",
                "signals": ["Wciskanie", "żerują", "stoisz jak ch..."],
            },
            {
                "what": "Zerwanie relacji: odejście, nienawiść do banku",
                "signals": ["Rezygnuję", "nie polecam", "przereklamowany"],
            },
        ],
    ),
}


def load_api_key() -> str:
    key = os.environ.get("TYPESAFE_API_KEY")
    if key:
        return key
    env_path = Path(__file__).with_name(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("TYPESAFE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("Set TYPESAFE_API_KEY or put it in .env")


def route(row: dict) -> str:
    """Inbox for a product team. Code owns the decision."""
    if row["churn"] >= 0.7 or row["frustration"] >= 2.5:
        return "churn_watch"
    if row["bug"] >= 0.7:
        return "bug_triage"
    if row["feature_request"] >= 0.7:
        return "backlog"
    if row["needs_reply"] >= 0.55:
        return "support_reply"
    if row["topic"] == "praise" and row["frustration"] < 0.6:
        return "archive_praise"
    return "monitor"


def classify_one(client: TypeSafeClient, review: dict) -> dict:
    state = {
        "app": "Bank Millennium",
        "store": "Google Play",
        "review": {
            "text": review["content"],
            "stars": review["stars"],
            "author": review["user"],
        },
    }
    response = client.system_one(state=state, questions=QUESTIONS, model=MODEL)
    a = response.answers
    out = {
        **review,
        "topic": a["topic"].choice,
        "topic_confidence": round(a["topic"].confidence, 3),
        "topic_p": {k: round(v, 3) for k, v in a["topic"].probabilities.items()},
        "bug": round(a["bug"].noul, 3),
        "feature_request": round(a["feature_request"].noul, 3),
        "churn": round(a["churn"].noul, 3),
        "needs_reply": round(a["needs_reply"].noul, 3),
        "frustration": round(a["frustration"].score, 2),
        "model": response.model,
    }
    out["inbox"] = route(out)
    return out


def _review_key(review: dict) -> str:
    return review.get("reviewId") or f"{review.get('user')}|{review.get('at')}|{review.get('content','')[:80]}"


def load_checkpoint() -> dict[str, dict]:
    done: dict[str, dict] = {}
    if not CHECKPOINT.exists():
        return done
    with CHECKPOINT.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            done[_review_key(row)] = row
    return done


def classify_all(reviews: list[dict], workers: int = 4) -> list[dict]:
    key = load_api_key()
    done = load_checkpoint()
    pending = [(i, r) for i, r in enumerate(reviews) if _review_key(r) not in done]
    print(f"classify {len(reviews)}  cached={len(reviews) - len(pending)}  pending={len(pending)}", flush=True)
    results: list[dict | None] = [None] * len(reviews)
    for i, r in enumerate(reviews):
        cached = done.get(_review_key(r))
        if cached is not None:
            results[i] = cached

    if not pending:
        return results  # type: ignore[return-value]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    finished = 0

    def work(i: int, review: dict) -> tuple[int, dict]:
        with TypeSafeClient(api_key=key) as client:
            return i, classify_one(client, review)

    with ThreadPoolExecutor(max_workers=workers) as pool, CHECKPOINT.open(
        "a", encoding="utf-8"
    ) as log:
        futs = [pool.submit(work, i, r) for i, r in pending]
        for fut in as_completed(futs):
            i, row = fut.result()
            results[i] = row
            with lock:
                log.write(json.dumps(row, ensure_ascii=False) + "\n")
                log.flush()
                finished += 1
                if finished % 50 == 0 or finished == len(pending):
                    print(f"  {finished}/{len(pending)}", flush=True)
    return results  # type: ignore[return-value]


def print_table(rows: list[dict]) -> None:
    print(
        f"{'inbox':<16}{'★':<3}{'topic':<18}{'bug':>5}{'feat':>6}{'churn':>6}{'frust':>6}  text"
    )
    for r in rows:
        snippet = " ".join(r["content"].split())[:62]
        print(
            f"{r['inbox']:<16}{r['stars']:<3}{r['topic']:<18}"
            f"{r['bug']:5.2f}{r['feature_request']:6.2f}{r['churn']:6.2f}"
            f"{r['frustration']:6.1f}  {snippet}"
        )
    print()
    from collections import Counter

    print("inbox:", dict(Counter(r["inbox"] for r in rows)))
    print("topic:", dict(Counter(r["topic"] for r in rows)))


def stratified_sample(reviews: list[dict], n: int, seed: int) -> list[dict]:
    by_star: dict[int, list[dict]] = defaultdict(list)
    for row in reviews:
        by_star[int(row["stars"])].append(row)
    rng = random.Random(seed)
    for bucket in by_star.values():
        rng.shuffle(bucket)
    stars = sorted(by_star)
    picked: list[dict] = []
    i = 0
    while len(picked) < min(n, len(reviews)):
        star = stars[i % len(stars)]
        i += 1
        if by_star[star]:
            picked.append(by_star[star].pop())
    return picked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--sample", type=int, default=0, help="Stratified sample size; 0 = all")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    reviews = json.loads(REVIEWS_PATH.read_text(encoding="utf-8"))
    if args.sample:
        reviews = stratified_sample(reviews, args.sample, args.seed)
        print(f"sample {len(reviews)} of corpus", flush=True)
    rows = classify_all(reviews, workers=args.workers)
    if args.json:
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return
    if len(rows) <= 80:
        print_table(rows)
    else:
        from collections import Counter

        print("inbox:", dict(Counter(r["inbox"] for r in rows)))
        print("topic:", dict(Counter(r["topic"] for r in rows)))
        print("stars:", dict(Counter(r["stars"] for r in rows)))
    OUT_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT_PATH} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
