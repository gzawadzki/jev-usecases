"""Raise QWK without new Jev calls: thresholds and a linear map on saved traits."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import cohen_kappa_score, confusion_matrix
from sklearn.model_selection import StratifiedKFold

HERE = Path(__file__).resolve().parent
JSONL = HERE / "data" / "eval_sample.jsonl"


def load_rows() -> list[dict]:
    rows = []
    with JSONL.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def qwk(gold, pred) -> float:
    return float(cohen_kappa_score(gold, pred, weights="quadratic"))


def clip_int(x) -> np.ndarray:
    return np.clip(np.rint(x), 1, 6).astype(int)


def apply_cuts(raw: np.ndarray, cuts: np.ndarray) -> np.ndarray:
    # cuts: 5 boundaries between 1..6
    return 1 + np.digitize(raw, cuts, right=False)


def search_cuts(raw: np.ndarray, gold: np.ndarray) -> np.ndarray:
    """Nelder-Mead on 5 cutpoints, seeded from biased-shifted integers."""
    from scipy.optimize import minimize

    def nll(cuts):
        pred = apply_cuts(raw, np.sort(cuts))
        return -qwk(gold, pred)

    x0 = np.array([1.5, 2.5, 3.5, 4.5, 5.5]) + (np.mean(raw) - np.mean(gold))
    best = x0
    best_s = nll(x0)
    rng = np.random.default_rng(7)
    for _ in range(8):
        start = np.sort(x0 + rng.normal(0, 0.25, size=5))
        res = minimize(nll, start, method="Nelder-Mead")
        if res.fun < best_s:
            best_s = res.fun
            best = np.sort(res.x)
    return np.sort(best)


def cv_apply(raw, gold, fit_fn, pred_fn, folds=5):
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=7)
    preds = np.zeros(len(gold), dtype=int)
    for tr, te in skf.split(raw.reshape(-1, 1), gold):
        model = fit_fn(raw[tr], gold[tr])
        preds[te] = pred_fn(model, raw[te])
    return preds


def main() -> None:
    rows = load_rows()
    gold = np.array([r["gold"] for r in rows])
    raw = np.array([r["raw"] for r in rows], dtype=float)
    capped = np.array([r["pred"] for r in rows])
    uncapped = np.array([r["uncapped"] for r in rows])
    X = np.array(
        [
            [
                r["raw"],
                r["thesis"],
                r["evidence"],
                r["off_prompt"],
                r["errors_obscure"],
            ]
            for r in rows
        ]
    )

    print(f"n={len(rows)}  mean raw={raw.mean():.3f}  mean gold={gold.mean():.3f}")
    print(f"baseline capped   QWK {qwk(gold, capped):.4f}")
    print(f"baseline uncapped QWK {qwk(gold, uncapped):.4f}")

    shift = raw.mean() - gold.mean()
    shifted = clip_int(raw - shift)
    print(f"shift {shift:.3f} then round  QWK {qwk(gold, shifted):.4f}  (optimistic, same 1000)")

    def fit_cuts(r, g):
        return search_cuts(r, g)

    def pred_cuts(cuts, r):
        return apply_cuts(r, cuts)

    cuts_cv = cv_apply(raw, gold, fit_cuts, pred_cuts)
    print(f"cutpoints 5-fold CV           QWK {qwk(gold, cuts_cv):.4f}")
    cuts_all = search_cuts(raw, gold)
    print(f"cutpoints fit-all (overfit)   QWK {qwk(gold, apply_cuts(raw, cuts_all)):.4f}  cuts={cuts_all.round(3)}")

    def fit_lin(r, g):
        m = LinearRegression().fit(r.reshape(-1, 1), g)
        return m

    def pred_lin(m, r):
        return clip_int(m.predict(r.reshape(-1, 1)))

    lin_cv = cv_apply(raw, gold, fit_lin, pred_lin)
    print(f"linear raw→gold 5-fold CV     QWK {qwk(gold, lin_cv):.4f}")

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=7)
    log_pred = np.zeros(len(gold), dtype=int)
    for tr, te in skf.split(X, gold):
        clf = LogisticRegression(max_iter=1000)
        clf.fit(X[tr], gold[tr])
        log_pred[te] = clf.predict(X[te])
    print(f"logreg on traits 5-fold CV    QWK {qwk(gold, log_pred):.4f}")

    labels = [1, 2, 3, 4, 5, 6]
    print("confusion after cutpoint CV (gold\\pred)")
    cm = confusion_matrix(gold, cuts_cv, labels=labels)
    for i, lab in enumerate(labels):
        print(f"  {lab} " + " ".join(f"{v:4d}" for v in cm[i]))
    print("pred dist", dict(zip(labels, cm.sum(0).tolist())))
    out = HERE / "data" / "cuts.json"
    out.write_text(
        json.dumps(
            {
                "cuts": [float(x) for x in cuts_all],
                "qwk_cv": qwk(gold, cuts_cv),
                "qwk_fit_all": qwk(gold, apply_cuts(raw, cuts_all)),
                "baseline_qwk": qwk(gold, capped),
                "n": len(rows),
                "note": "Apply to Jev raw (holistic+1). 5-fold CV QWK is the honest figure.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
