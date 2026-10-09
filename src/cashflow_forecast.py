"""
Next-month cash-flow risk forecast (per customer).

Method (deliberately simple and explainable, no black box):

  Expected income
      stable earners (income CV < 0.15) : median of the last 3 months  (ignores one-off bonuses)
      irregular earners                 : mean of the last 6 months
  Expected outflows = expected recurring outflows + expected variable spend
      recurring  : median of last 3 months of recurring debits (rent, EMI, utilities, insurance,
                   subscriptions, SIP, debt repayments). School fees are excluded from the median
                   and added only if the customer paid school fees in that calendar month before.
      variable   : weighted average of last 3 months of non-recurring spend (weights 0.5/0.3/0.2),
                   excluding flagged outliers (one-off hospital bills), multiplied by a portfolio
                   seasonal index for the target month when that month exists in history
                   (e.g. October = Diwali uplift learned from Oct-2024).
  Expected ending balance = current balance + expected income - expected outflows
  Uncertainty (sigma)     = std-dev of the customer's monthly balance change over the last 6 months
                            (excluding borrowing), floored at 5% of expected income
  Safety cushion          = 25% of expected monthly outflows. Income and bills land on different days,
                            so a month-end balance that is positive but thin still means the account
                            runs dry mid-month. The 25% level was chosen on the pooled backtest
                            (best recall/precision balance, see reports/model_validation.md).
  Deficit probability     = P(ending balance < safety cushion) = Phi((cushion - expected_end) / sigma)
  Risk tier               : High >= 50%, Medium 20-50%, Low < 20%

Assumptions & limitations are documented in docs/cashflow_risk_methodology.md.

Run:  python src/cashflow_forecast.py
"""
from __future__ import annotations

from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
ANALYTICS = ROOT / "data" / "analytics"


SAFETY_CUSHION = 0.25


def norm_cdf(x: float) -> float:
    return 0.5 * (1 + erf(x / sqrt(2)))


def seasonal_index(tx_hist: pd.DataFrame) -> pd.Series:
    """portfolio variable spend per calendar month / average month"""
    v = tx_hist[(tx_hist["income_expense"] == "Expense") & (tx_hist["recurring_flag"] == 0)
                & (tx_hist["is_outlier"] == 0)]
    monthly = v.groupby("year_month")["amount"].sum()
    idx = monthly / monthly.mean()
    idx.index = pd.to_datetime(idx.index + "-01").month
    return idx.groupby(level=0).mean()


def forecast(tx: pd.DataFrame, cm: pd.DataFrame, as_of: str) -> pd.DataFrame:
    target = (pd.Period(as_of, "M") + 1)
    tx_h = tx[tx["year_month"] <= as_of]
    cm_h = cm[cm["year_month"] <= as_of].sort_values(["customer_id", "year_month"])
    season = seasonal_index(tx_h)
    s_factor = float(season.get(target.month, 1.0))

    debits = tx_h[tx_h["transaction_type"] == "Debit"]
    rec = debits[(debits["recurring_flag"] == 1) & (debits["subcategory"] != "School Fees")]
    rec_m = rec.groupby(["customer_id", "year_month"])["amount"].sum().unstack(fill_value=0)
    var = debits[(debits["recurring_flag"] == 0) & (debits["is_outlier"] == 0)]
    var_m = var.groupby(["customer_id", "year_month"])["amount"].sum().unstack(fill_value=0)
    school = debits[debits["subcategory"] == "School Fees"].assign(
        mo=lambda d: pd.to_datetime(d["year_month"] + "-01").dt.month)
    school_amt = school[school["mo"] == target.month].groupby("customer_id")["amount"].mean()

    rows = []
    for cid, h in cm_h.groupby("customer_id"):
        inc = h["income"]
        cv = inc.std(ddof=0) / inc.mean() if inc.mean() > 0 else 1.0
        e_inc = inc.tail(3).median() if cv < 0.15 else inc.tail(6).mean()
        r_hist = rec_m.loc[cid].tail(3) if cid in rec_m.index else pd.Series([0.0])
        e_rec = float(r_hist.median())
        v_hist = var_m.loc[cid].tail(3).values if cid in var_m.index else np.zeros(3)
        w = np.array([0.2, 0.3, 0.5])[-len(v_hist):]
        e_var = float(np.dot(v_hist, w / w.sum())) * s_factor
        e_school = float(school_amt.get(cid, 0.0))
        e_out = e_rec + e_var + e_school
        bal = float(h["month_end_balance"].iloc[-1])
        e_end = bal + e_inc - e_out
        chg = (h["balance_change"] - h["borrowing"]).tail(6)
        sigma = max(float(chg.std(ddof=0)), 0.05 * max(e_inc, 1.0))
        cushion = SAFETY_CUSHION * e_out
        p = norm_cdf((cushion - e_end) / sigma)
        rows.append(dict(
            customer_id=cid, as_of_month=as_of, forecast_month=str(target),
            current_balance=round(bal, 2), expected_income=round(e_inc, 2),
            expected_recurring_outflows=round(e_rec, 2), expected_variable_spend=round(e_var, 2),
            expected_seasonal_one_offs=round(e_school, 2), expected_outflows=round(e_out, 2),
            expected_net_cash_flow=round(e_inc - e_out, 2), expected_ending_balance=round(e_end, 2),
            uncertainty_sigma=round(sigma, 2), deficit_probability=round(p, 4),
            cashflow_risk_tier="High" if p >= 0.5 else ("Medium" if p >= 0.2 else "Low"),
            projected_shortfall=round(max(0.0, -e_end), 2),
            seasonal_factor_used=round(s_factor, 3),
            safety_cushion=round(cushion, 2),
        ))
    return pd.DataFrame(rows)


def main() -> None:
    tx = pd.read_csv(PROC / "transactions_clean.csv", parse_dates=["date"])
    cm = pd.read_csv(ANALYTICS / "customer_month.csv")
    latest = cm["year_month"].max()
    fc = forecast(tx, cm, latest)
    fc.to_csv(ANALYTICS / "cashflow_forecast.csv", index=False)
    print(f"Forecast for {fc.forecast_month.iloc[0]} (seasonal factor {fc.seasonal_factor_used.iloc[0]})")
    print(fc["cashflow_risk_tier"].value_counts().to_string())
    print(f"Total projected shortfall: ₹{fc.projected_shortfall.sum():,.0f}")


if __name__ == "__main__":
    main()
