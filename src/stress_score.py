"""
Financial Stress Score (0-100, higher = more stress).

Seven factors, each converted to a 0-100 sub-score with a *benchmark-anchored* linear scale:
the "no stress" end is a widely used personal-finance guideline, the "maximum stress" end
is a level at which lenders or planners would treat the household as unable to absorb a shock.

| # | Factor                     | Measure (look-back)                              | 0 stress at | 100 stress at | Weight |
|---|----------------------------|--------------------------------------------------|-------------|---------------|--------|
| 1 | Savings margin             | (income - expenses) / income, last 6 months      | >= 20%      | <= -10%       | 20 |
| 2 | Fixed obligation ratio     | (rent+EMI+insurance+debt repay) / income, 6m     | <= 30%      | >= 60%        | 20 |
| 3 | Emergency buffer           | balance / avg monthly essential spend            | >= 6 months | <= 0.5 month  | 20 |
| 4 | Income instability         | coefficient of variation of monthly income, all  | <= 0.10     | >= 0.60       | 10 |
| 5 | Expense growth             | trend of de-seasonalised core spend over 6m      | <= 0%       | >= +25%       | 10 |
| 6 | Balance trend              | 6-month balance change, in months of income      | >= +0.5     | <= -1.0       | 10 |
| 7 | Deficit & borrowing        | max(share of deficit months / 50%, borrow months / 2) | 0      | 1 (capped)    | 10 |

Why "expense-to-income ratio" is not a separate factor: expense/income = 1 - savings rate, so
including both would double-count the same signal. It is reported as a KPI instead, and factor 7
captures *how often* expenses exceeded income, which the average ratio hides.

Weights: the three structural factors (1-3) decide whether a household can absorb a bad month,
so they carry 60%. The dynamic factors (4-7) describe direction and volatility and carry 40%.
A sensitivity check with equal weights is produced in validate_model.py.

Expense growth is measured on *core* spend (excluding flagged one-off outliers and school fees),
divided by the portfolio's seasonal index for each month, with a straight line fitted over the
6-month window. Without this, Diwali or school-fee months would look like "growth" (or hide it).

Run:  python src/stress_score.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "data" / "analytics"

FACTORS = {
    # name: (column, value_at_0_stress, value_at_100_stress, weight)
    "savings_margin": ("savings_rate_6m", 0.20, -0.10, 20),
    "fixed_obligations": ("fixed_obligation_ratio_6m", 0.30, 0.60, 20),
    "emergency_buffer": ("buffer_months", 6.0, 0.5, 20),
    "income_instability": ("income_cv", 0.10, 0.60, 10),
    "expense_growth": ("expense_growth_6m", 0.0, 0.25, 10),
    "balance_trend": ("balance_trend_income_months", 0.5, -1.0, 10),
    "deficit_borrowing": ("deficit_borrow_index", 0.0, 1.0, 10),
}
BANDS = [(30, "Low"), (60, "Moderate"), (80, "High"), (100, "Critical")]


def scale(x: pd.Series, zero_at: float, hundred_at: float) -> pd.Series:
    """linear map: zero_at -> 0, hundred_at -> 100, clipped to [0, 100] (works for either direction)"""
    return ((x - zero_at) / (hundred_at - zero_at) * 100).clip(0, 100)


def band(score: float) -> str:
    for upper, name in BANDS:
        if score <= upper:
            return name
    return "Critical"


def customer_factors(cm: pd.DataFrame, as_of: str, window: int = 6) -> pd.DataFrame:
    """Raw factor values per customer using data up to and including `as_of` (YYYY-MM)."""
    hist = cm[cm["year_month"] <= as_of].sort_values(["customer_id", "year_month"])
    win = hist.groupby("customer_id").tail(window)
    port = hist.groupby("year_month")["core_expenses"].sum()
    season = port / port.mean()      # portfolio seasonal index (1.0 = average month)
    rows = []
    for cid, w in win.groupby("customer_id"):
        h = hist[hist["customer_id"] == cid]
        inc, exp = w["income"].sum(), w["expenses"].sum()
        avg_inc = max(w["income"].mean(), 1.0)
        sr = (inc - exp) / inc if inc > 0 else -1.0
        foir = w["fixed_obligations"].sum() / inc if inc > 0 else 1.0
        ess = max(w["essential_spend"].mean(), 1.0)
        bal = w["month_end_balance"].iloc[-1]
        buffer = max(bal, 0) / ess
        cv = h["income"].std(ddof=0) / h["income"].mean() if h["income"].mean() > 0 else 1.0
        # de-seasonalised core spend: divide by the portfolio's seasonal index, then fit a line
        adj = (w["core_expenses"] / w["year_month"].map(season)).values
        if len(adj) >= 3 and adj.mean() > 0:
            slope, intercept = np.polyfit(np.arange(len(adj)), adj, 1)
            start, end = intercept, intercept + slope * (len(adj) - 1)
            growth = end / start - 1 if start > 0 else 0.0
        else:
            growth = 0.0
        start_bal = w["opening_balance"].iloc[0]
        trend = (bal - start_bal) / avg_inc
        deficit_share = w["is_deficit_month"].mean()
        borrow_months = w["borrowed_this_month"].sum()
        dbi = min(1.0, max(deficit_share / 0.5, borrow_months / 2))
        rows.append(dict(
            customer_id=cid, as_of_month=as_of,
            avg_monthly_income=round(avg_inc, 2), avg_monthly_expenses=round(w["expenses"].mean(), 2),
            savings_rate_6m=sr, fixed_obligation_ratio_6m=foir, expense_to_income_6m=exp / inc if inc else np.nan,
            current_balance=bal, avg_essential_spend=ess, buffer_months=buffer, income_cv=cv,
            expense_growth_6m=growth, balance_trend_income_months=trend,
            deficit_months_6m=int(w["is_deficit_month"].sum()), borrow_months_6m=int(borrow_months),
            deficit_borrow_index=dbi,
        ))
    return pd.DataFrame(rows)


def score(f: pd.DataFrame, weights: dict | None = None) -> pd.DataFrame:
    out = f.copy()
    total_w = 0
    out["stress_score"] = 0.0
    for name, (col, z, h, w) in FACTORS.items():
        w = weights.get(name, w) if weights else w
        out[f"sub_{name}"] = scale(out[col], z, h).round(1)
        out[f"contrib_{name}"] = (out[f"sub_{name}"] * w / 100).round(2)
        out["stress_score"] += out[f"sub_{name}"] * w
        total_w += w
    out["stress_score"] = (out["stress_score"] / total_w).round(1)
    out["stress_band"] = out["stress_score"].map(band)
    contrib_cols = [f"contrib_{n}" for n in FACTORS]
    out["top_stress_driver"] = out[contrib_cols].idxmax(axis=1).str.replace("contrib_", "", regex=False)
    out.loc[out["stress_score"] < 10, "top_stress_driver"] = "none"
    return out


def main() -> None:
    cm = pd.read_csv(ANALYTICS / "customer_month.csv")
    latest = cm["year_month"].max()
    s = score(customer_factors(cm, latest))
    s.to_csv(ANALYTICS / "customer_stress_score.csv", index=False)

    # monthly history of the score (from month 6 onward) for trend visuals
    months = sorted(cm["year_month"].unique())[5:]
    hist = pd.concat([score(customer_factors(cm, m))[["customer_id", "as_of_month", "stress_score", "stress_band"]]
                      for m in months])
    hist.to_csv(ANALYTICS / "stress_score_history.csv", index=False)

    print(f"Scored {len(s)} customers as of {latest}")
    print(s["stress_band"].value_counts().reindex([b for _, b in BANDS]).to_string())
    print(s["stress_score"].describe().round(1).to_string())


if __name__ == "__main__":
    main()
