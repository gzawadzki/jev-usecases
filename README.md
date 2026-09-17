# Typed decisions on Polish text with TypeSafe Jev

Three demos of [TypeSafe](https://docs.typesafe.ai/) **Jev**: a model that returns probabilities, not prose. Your code owns routing, thresholds, and side effects.

| Use case | What Jev decides | Measured |
| --- | --- | --- |
| [Play review inbox](usecases/play-reviews/) | Topic, bug, churn, feature request → product queue | **2975** reviews in **301.63 s** (8 workers) |
| [Sójka-shaped guard](usecases/sojka-guard/) | Hate, vulgar, sex, crime, self-harm → pass / review / block / support | 7 Polish samples, one request each |
| [Seed comparator](usecases/seed-comparator/) | Error type of a model answer vs ground truth (Bielik seed `visual-emphasis`) | 9 cases |

Jev is not [Bielik Guard (Sójka)](https://guard.bielik.ai/). Sójka is a local Polish RoBERTa with five fixed labels. Jev is a hosted System One model: you write the questions.

## Setup

Python 3.10 or newer. A [TypeSafe API key](https://console.typesafe.ai/settings/keys).

```bash
pip install -r requirements.txt
cp .env.example .env
# set TYPESAFE_API_KEY
```

On Windows PowerShell use `copy .env.example .env`.

Run every command from the **repository root**.

## Run each demo

**Review inbox** (50-row smoke test, then the full timed corpus):

```bash
python usecases/play-reviews/classify.py --sample 50
python usecases/play-reviews/classify.py --workers 8
python usecases/play-reviews/summarize.py --write
```

**Safety screen** (Sójka taxonomy, Jev under the hood):

```bash
python usecases/sojka-guard/guard.py --demo
python usecases/sojka-guard/guard.py "Ale zagrałeś tragicznie w tym meczu, usuń konto."
```

**Seed comparator**:

```bash
python usecases/seed-comparator/compare.py
```

## What stays in code

- Fetching and deduping Play reviews
- Inbox policy (`churn ≥ 0.70` → `churn_watch`, and so on)
- Guard routing (`self_harm` → support, not a silent block)
- Exact-string compare in seedlab (this demo only replaces the *semantic* axis)

## Data and license

MIT for the code. Do not commit `.env`.

Play review text belongs to its authors and Google Play. The scrape is a public snapshot for the demo, not a full dump of the store.

Ground-truth fragments in the seed comparator come from the `visual-emphasis` seed in the Bielik seed-definition workshop. Jev does not see the images.
