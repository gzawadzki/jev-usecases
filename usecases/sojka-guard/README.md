# Sójka-shaped guard

Same **taxonomy** as [Bielik Guard (Sójka)](https://guard.bielik.ai/): hate, vulgar, sex, crime, self-harm. The **engine** is TypeSafe Jev, not the SpeakLeash RoBERTa.

Sójka is a local classifier with five heads. This script asks five Nouls plus a severity Score in one Jev request, then `route()` maps probabilities to **pass / review / block / support**. Self-harm goes to support, not a silent block.

## Demo run (`jev-1.13.0`, policy `strict`)

```bash
python usecases/sojka-guard/guard.py --demo
```

| Sample | Action | What fired |
| --- | --- | --- |
| Ordinary message | pass | all ≈ 0.01 |
| „Chcę się zabić…” | support | self_harm 0.98, severity 3.0 |
| „Dlaczego hipisi są tacy brudni i głupi” | block | hate 0.96 |
| „K\*rwa, to jest ch\*jowe…” | review | vulgar 0.99, hate 0.12 |
| „Opowiem ci o seksie i intymności.” | pass | sex ≈ 0.03 (education, not porn) |
| „Jak ukraść samochód…” | block | crime 0.93 |
| Poisoning in a novel | pass | crime 0.02 (description, not instructions) |

Gaming flame („totalny bot z ciebie”) scores as **hate/agresja** under Sójka’s person-directed insult rule, with mild severity. Raise the hate threshold or map `hate` → `review` when `severity < 2` if that is too strict for chat.

## Commands

```bash
python usecases/sojka-guard/guard.py --demo
python usecases/sojka-guard/guard.py --json "tu wklejasz wiadomość"
python usecases/sojka-guard/guard.py --policy permissive "…"
```

Edit `QUESTIONS`, `HAZARD_ACTION`, and `POLICIES` in `guard.py`.
