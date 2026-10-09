"""
Exports a Power BI-ready star schema to data/powerbi/.

  Facts : fact_transactions, fact_customer_month, fact_stress_history
  Dims  : dim_customer (incl. current score & forecast), dim_date, dim_category,
          dim_merchant, dim_stress_band, dim_risk_tier
  1:1   : customer_stress_score, cashflow_forecast (component-level detail)

Relationships to create in Power BI are listed in powerbi/POWERBI_BUILD_GUIDE.md.
Run:  python src/export_powerbi.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC, AN, OUT = ROOT / "data" / "processed", ROOT / "data" / "analytics", ROOT / "data" / "powerbi"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tx = pd.read_csv(PROC / "transactions_clean.csv", parse_dates=["date"])
    cust = pd.read_csv(PROC / "customers_clean.csv")
    cm = pd.read_csv(AN / "customer_month.csv")
    ss = pd.read_csv(AN / "customer_stress_score.csv")
    fc = pd.read_csv(AN / "cashflow_forecast.csv")
    hist = pd.read_csv(AN / "stress_score_history.csv")

    # ---- fact_transactions
    ft = tx[["transaction_id", "customer_id", "date", "txn_date", "transaction_type", "category",
             "subcategory", "merchant", "amount", "signed_amount", "payment_method", "income_expense",
             "account_balance", "recurring_flag", "location", "is_outlier", "is_weekend"]].copy()
    ft = ft.rename(columns={"date": "txn_datetime"})
    ft["txn_date"] = pd.to_datetime(ft["txn_date"]).dt.date
    ft["size_band"] = pd.cut(ft["amount"], [0, 500, 2000, 10000, np.inf],
                             labels=["1 Micro (<500)", "2 Small (500-2K)", "3 Medium (2K-10K)", "4 Large (10K+)"])
    ft.to_csv(OUT / "fact_transactions.csv", index=False)

    # ---- fact_customer_month
    fcm = cm.copy()
    fcm["month_start"] = pd.to_datetime(fcm["month_start"]).dt.date
    fcm.to_csv(OUT / "fact_customer_month.csv", index=False)

    # ---- fact_stress_history
    h = hist.copy()
    h["month_start"] = pd.to_datetime(h["as_of_month"] + "-01").dt.date
    h.to_csv(OUT / "fact_stress_history.csv", index=False)

    # ---- dim_customer (attributes + current score + forecast for slicing)
    dc = (cust.merge(ss[["customer_id", "stress_score", "stress_band", "top_stress_driver", "buffer_months",
                         "savings_rate_6m", "fixed_obligation_ratio_6m", "income_cv"]], on="customer_id", how="left")
              .merge(fc[["customer_id", "cashflow_risk_tier", "deficit_probability", "expected_ending_balance",
                         "projected_shortfall"]], on="customer_id", how="left"))
    dc["customer_label"] = dc["customer_id"] + " · " + dc["occupation_type"] + " · " + dc["city"]
    dc["top_stress_driver"] = dc["top_stress_driver"].str.replace("_", " ").str.capitalize()
    dc.to_csv(OUT / "dim_customer.csv", index=False)

    # ---- dim_date (daily calendar incl. Indian fiscal year)
    d = pd.DataFrame({"date": pd.date_range(tx["date"].min().normalize(), tx["date"].max().normalize())})
    d["year"] = d["date"].dt.year
    d["month_num"] = d["date"].dt.month
    d["month_name"] = d["date"].dt.strftime("%b")
    d["year_month"] = d["date"].dt.strftime("%Y-%m")
    d["month_label"] = d["date"].dt.strftime("%b %Y")
    d["month_start"] = d["date"].dt.to_period("M").dt.start_time.dt.date
    d["month_sort"] = d["year"] * 100 + d["month_num"]
    d["quarter"] = "Q" + d["date"].dt.quarter.astype(str)
    d["fiscal_year"] = np.where(d["month_num"] >= 4, "FY" + (d["year"] + 1).astype(str).str[-2:],
                                "FY" + d["year"].astype(str).str[-2:])
    d["day_of_week"] = d["date"].dt.day_name()
    d["day_of_week_num"] = d["date"].dt.dayofweek + 1
    d["is_weekend"] = (d["date"].dt.dayofweek >= 5).astype(int)
    d["season"] = d["month_num"].map({10: "Festive", 11: "Festive", 12: "Holiday", 4: "School fees", 6: "School fees",
                                      5: "Summer travel"}).fillna("Regular")
    d["date"] = d["date"].dt.date
    d.to_csv(OUT / "dim_date.csv", index=False)

    # ---- dim_category
    cats = tx.groupby("category").agg(spend_type=("spend_type", "first"), income_expense=("income_expense", "first")).reset_index()
    order = {"Fixed Obligation": 1, "Essential Variable": 2, "Discretionary": 3, "Investment": 4, "Not Spend": 5}
    cats["spend_type_sort"] = cats["spend_type"].map(order)
    cats["is_essential"] = cats["spend_type"].isin(["Fixed Obligation", "Essential Variable"]).astype(int)
    cats.to_csv(OUT / "dim_category.csv", index=False)

    # ---- dim_merchant
    m = tx.groupby("merchant").agg(primary_category=("category", lambda s: s.mode()[0]),
                                   n_transactions=("transaction_id", "size")).reset_index()
    m["channel"] = np.where(m["merchant"].isin(tx.loc[tx["location"] == "Online", "merchant"].unique()), "Online", "In-store")
    m.to_csv(OUT / "dim_merchant.csv", index=False)

    # ---- small lookup tables for sorting and colours
    pd.DataFrame({"stress_band": ["Low", "Moderate", "High", "Critical"], "band_sort": [1, 2, 3, 4],
                  "score_min": [0, 30.1, 60.1, 80.1], "score_max": [30, 60, 80, 100],
                  "band_color": ["#0CA30C", "#FAB219", "#EC835A", "#D03B3B"]}).to_csv(OUT / "dim_stress_band.csv", index=False)
    pd.DataFrame({"cashflow_risk_tier": ["Low", "Medium", "High"], "tier_sort": [1, 2, 3],
                  "rule": ["P(deficit) < 20%", "20% <= P(deficit) < 50%", "P(deficit) >= 50%"],
                  "tier_color": ["#0CA30C", "#FAB219", "#D03B3B"]}).to_csv(OUT / "dim_risk_tier.csv", index=False)

    ss.to_csv(OUT / "customer_stress_score.csv", index=False)
    fc.to_csv(OUT / "cashflow_forecast.csv", index=False)
    for f in sorted(OUT.glob("*.csv")):
        print(f"{f.name:<28} {sum(1 for _ in open(f)) - 1:>7,} rows")


if __name__ == "__main__":
    main()
