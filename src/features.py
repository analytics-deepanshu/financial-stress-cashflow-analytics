"""
Feature engineering: builds the customer-month table that the stress score,
forecast, SQL views and Power BI all share.

Definitions (used consistently everywhere in the project):
- income            : credits tagged Income (salary, freelance, family support, stipend, interest).
                      Borrowed money is NOT income.
- expenses          : debits tagged Expense (consumption + fixed obligations + debt repayments).
                      SIP investments are NOT expenses; they are savings that leave the account.
- net_cash_flow     : income - expenses            (the "earning vs spending" view)
- savings_rate      : net_cash_flow / income        (SIP counts as saving)
- fixed_obligations : rent + loan EMI + insurance + short-term debt repayment
- essential_spend   : fixed obligations + essential variable spend (groceries, utilities, transport,
                      healthcare, education)  -> what a household must pay to keep running
- core_expenses     : expenses excluding flagged one-off outliers and school fees (for trend detection)
- balance_change    : every credit - every debit (includes SIP and borrowing) -> what the bank sees

Run:  python src/features.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
ANALYTICS = ROOT / "data" / "analytics"


def load_clean() -> tuple[pd.DataFrame, pd.DataFrame]:
    tx = pd.read_csv(PROC / "transactions_clean.csv", parse_dates=["date"])
    cust = pd.read_csv(PROC / "customers_clean.csv")
    return tx, cust


def build_customer_month(tx: pd.DataFrame) -> pd.DataFrame:
    t = tx.copy()
    ie, st = t["income_expense"], t["spend_type"]
    amt = t["amount"]
    t["income"] = np.where(ie == "Income", amt, 0)
    t["expenses"] = np.where(ie == "Expense", amt, 0)
    t["investment"] = np.where(ie == "Investment", amt, 0)
    t["borrowing"] = np.where(ie == "Borrowing", amt, 0)
    t["fixed_obligations"] = np.where(st == "Fixed Obligation", amt, 0)
    t["essential_variable"] = np.where(st == "Essential Variable", amt, 0)
    t["discretionary"] = np.where(st == "Discretionary", amt, 0)
    t["debt_repayment"] = np.where(t["category"] == "Debt Repayment", amt, 0)
    # core expenses: exclude one-off outliers (hospital bills) and school fees, used for trend detection
    t["core_expenses"] = np.where((ie == "Expense") & (t["is_outlier"] == 0) & (t["subcategory"] != "School Fees"), amt, 0)
    t["recurring_expenses"] = np.where((ie == "Expense") & (t["recurring_flag"] == 1), amt, 0)
    t["weekend_spend"] = np.where((ie == "Expense") & (t["is_weekend"] == 1), amt, 0)
    t["weekday_spend"] = np.where((ie == "Expense") & (t["is_weekend"] == 0), amt, 0)
    t["n_expense_txn"] = (ie == "Expense").astype(int)
    t["borrow_event"] = (ie == "Borrowing").astype(int)

    t = t.sort_values(["customer_id", "date", "transaction_id"])
    g = t.groupby(["customer_id", "year_month"])
    cm = g[["income", "expenses", "core_expenses", "investment", "borrowing", "fixed_obligations", "essential_variable",
            "discretionary", "debt_repayment", "recurring_expenses", "weekend_spend", "weekday_spend",
            "n_expense_txn", "borrow_event"]].sum()
    cm["balance_change"] = g["signed_amount"].sum()
    cm["month_end_balance"] = g["account_balance"].last()
    cm["month_min_balance"] = g["account_balance"].min()
    cm["n_transactions"] = g.size()
    cm = cm.reset_index()

    cm["month_start"] = pd.to_datetime(cm["year_month"] + "-01")
    cm["net_cash_flow"] = cm["income"] - cm["expenses"]
    cm["essential_spend"] = cm["fixed_obligations"] + cm["essential_variable"]
    inc = cm["income"].replace(0, np.nan)
    cm["savings_rate"] = (cm["net_cash_flow"] / inc).clip(-2, 1)
    cm["expense_to_income"] = (cm["expenses"] / inc).clip(0, 5)
    cm["fixed_obligation_ratio"] = (cm["fixed_obligations"] / inc).clip(0, 5)
    cm["is_deficit_month"] = (cm["net_cash_flow"] < 0).astype(int)
    cm["borrowed_this_month"] = (cm["borrow_event"] > 0).astype(int)
    cm["opening_balance"] = cm["month_end_balance"] - cm["balance_change"]
    cm = cm.rename(columns={"borrow_event": "n_borrow_events"})
    return cm


def main() -> None:
    ANALYTICS.mkdir(parents=True, exist_ok=True)
    tx, _ = load_clean()
    cm = build_customer_month(tx)
    cm.to_csv(ANALYTICS / "customer_month.csv", index=False)
    print(f"customer_month rows: {len(cm):,}  ({cm.customer_id.nunique()} customers x {cm.year_month.nunique()} months)")


if __name__ == "__main__":
    main()
