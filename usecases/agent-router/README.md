# Agent router

A bank chatbot with several specialists. The user types one line. Code must load **at most one** agent's context (tools, RAG, system prompt) — or none.

Jev reads short **agent cards** and answers **seven questions in one request** (Choice + Nouls). They cannot see one another's answers. `decide()` in `router.py` combines them.

## Questions in one Jev call

State is `{ "utterance": "<linia użytkownika>", "product": "bank chat" }`.

### `which` — Choice

Pick **one** id. Options: `transactions`, `payments`, `navigation`, `lending`, `identity`, `none`.

| | |
| --- | --- |
| Question | Który jeden agent powinien dostać `utterance` i swój kontekst? |
| Inspect | `utterance` |
| Focus | Intencja, nie wspólne słowa. „Gdzie jest X w aplikacji” to `navigation`, nie treść X. „Pokaż / status / zrób X” to agent od X. |

Each option's criteria are the card: `what` (does), `not_for` (does_not), `loads`, `examples`. `none` is small talk / weather / jokes.

Returns `choice`, a probability per option, and `confidence` (how peaked the distribution is).

### `needs_specialist` — Noul

Gate: load a specialist at all?

| | |
| --- | --- |
| Question | Czy `utterance` wymaga narzędzi albo danych bankowych? |
| True | Saldo, historia, przelew, BLIK, wniosek, zdolność, logowanie, PIN, ścieżka w menu |
| False | Pogoda, żart, ciekawostka, czysta rozmowa |

Returns `noul` in 0–1. Below `GATE` (0.30) the router returns `none` even if `which` named someone.

### `fits::<id>` — one Noul per card

Five independent yes/no questions. Each card can score high; they are not a softmax.

| id | True (does this job) | False (wrong specialist) |
| --- | --- | --- |
| `fits::transactions` | pokazać saldo i historię; szukać po dacie/kwocie | gdzie kliknąć; składać wnioski; **wykonać** przelew |
| `fits::payments` | zainicjować przelew / BLIK / limit | sama historia; nawigacja po menu |
| `fits::navigation` | która zakładka, jaka ścieżka | odczytać dane klienta albo treść wniosku |
| `fits::lending` | status wniosku, zdolność, dokumenty | „gdzie jest przycisk wniosku”; saldo |
| `fits::identity` | logowanie, PIN, 2FA, nowe urządzenie | płatności i historia, gdy dostęp działa |

Example for `fits::navigation`:

- Question: Czy agent `navigation` (Agent nawigacyjny) robi to, o co prosi `utterance`?
- Focus: tylko ta karta; sąsiedzi mają własne Noule.

On „gdzie są wnioski kredytowe?” expect `fits::navigation` high-ish and `fits::lending` also non-zero (shared words). Choice should still pick `navigation`. On „status wniosku Kowalskiego” the reverse.

## How code combines them

```
if needs_specialist < 0.30 or max(fits) < 0.35:
    none
elif which is a card and fits[which] >= 0.35:
    load which
    # unless another card's fits is clearly higher → clarify
elif one card's fits leads by > 0.12:
    load that card
else:
    clarify   # dopytaj, nie zgaduj
```

Choice answers *who wins the competition*. Each Noul answers *does this card actually do it*, so all can be low (Mastodon vs Twitter-shaped miss). That is why `none` is possible even with five specialists.

## Cards

| id | Loads | Not |
| --- | --- | --- |
| `transactions` | saldo, historia | gdzie kliknąć; nowy przelew |
| `payments` | przelew, BLIK | sama historia |
| `navigation` | mapa ekranów | treść wniosku, saldo |
| `lending` | wnioski, zdolność | „gdzie jest przycisk” |
| `identity` | logowanie, PIN | płatności |

The split that embeddings miss: **„gdzie są wnioski kredytowe?”** → `navigation`. **„status wniosku kredytowego Kowalskiego”** → `lending`.

## Demo (`jev-1.13.0`) — 10/10

```bash
python usecases/agent-router/router.py --demo
python usecases/agent-router/router.py "gdzie są wnioski kredytowe?"
```

| Utterance | Agent |
| --- | --- |
| pokaż mi ostatnie transkacje klienta | `transactions` (typo in the query) |
| gdzie są wnioski kredytowe? | `navigation` |
| jaki jest status wniosku kredytowego Kowalskiego | `lending` |
| zrób przelew 50 zł BLIKIEM na telefon żony | `payments` |
| nie mogę się zalogować, PIN odrzuca | `identity` |
| jak wejść w historię karty w aplikacji | `navigation` |
| co poszło z konta wczoraj | `transactions` |
| czy Kowalski dostanie kredyt gotówkowy | `lending` |
| jaka jutro pogoda w Gdańsku | `none` |
| opowiedz krótki żart o banku | `none` |

Edit `data/cards.json` and `data/queries.json`. Policy knobs: `GATE`, `FITS`, `CLARIFY_GAP` in `router.py`.

With dozens of cards, add a second Jev pass on the top three (see TypeSafe [skill suggestion](https://docs.typesafe.ai/cookbooks/skill_suggestion.md)). Five cards fit in one request.
