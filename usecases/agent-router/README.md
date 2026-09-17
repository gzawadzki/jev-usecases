# Agent router

A bank chatbot with several specialists. The user types one line. Code must load **at most one** agent's context (tools, RAG, system prompt) — or none.

Jev reads short **agent cards** (`does`, `does_not`, examples) and returns:

- a `Choice` over card ids plus `none`
- a Noul: does this even need a specialist?
- a Noul per card: does *this* agent actually do that?

`decide()` in `router.py` owns the policy (thresholds, close calls → `clarify`).

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
