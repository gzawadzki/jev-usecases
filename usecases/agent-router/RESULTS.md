# Agent router results

Questions (one request): `which` (Choice), `needs_specialist` (Noul), `fits::<id>` (Noul × 5). See the [README](README.md#questions-in-one-jev-call).


Model `jev-1.13.0`. Ten utterances in `data/queries.json`. **10/10** matched `expected`.

| utterance | expected | got | needs | top `fits` |
| --- | --- | --- | --- | --- |
| pokaż mi ostatnie transkacje klienta | transactions | transactions | 0.97 | transactions 0.79 |
| gdzie są wnioski kredytowe? | navigation | navigation | 0.95 | navigation 0.49, lending 0.41 |
| status wniosku kredytowego Kowalskiego | lending | lending | 0.97 | lending 0.59 |
| przelew 50 zł BLIKIEM | payments | payments | 0.98 | payments 0.58 |
| nie mogę się zalogować, PIN odrzuca | identity | identity | 0.93 | identity 0.37 |
| jak wejść w historię karty w aplikacji | navigation | navigation | 0.75 | navigation 0.45 |
| co poszło z konta wczoraj | transactions | transactions | 0.95 | transactions 0.62 |
| czy Kowalski dostanie kredyt gotówkowy | lending | lending | 0.93 | lending 0.63 |
| jaka jutro pogoda w Gdańsku | none | none | 0.03 | (all ≤ 0.12) |
| opowiedz krótki żart o banku | none | none | 0.03 | (all ≤ 0.15) |

„Gdzie są wnioski” vs „status wniosku”: Choice is certain (`confidence` 1.0) both times. The `fits` Nouls stay closer on the first one (0.49 vs 0.41) — that is the pair to watch in production (`CLARIFY_GAP`).
