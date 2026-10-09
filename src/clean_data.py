"""
Data cleaning & validation.

Input : data/raw/transactions_raw.csv, data/raw/customers_raw.csv
Output: data/processed/transactions_clean.csv
        data/processed/customers_clean.csv
        data/processed/cleaning_log.csv          (one row per fix, per transaction)
        reports/data_quality_report.md           (detected vs injected scorecard)

Every step records what it changed in `cleaning_log`, so the process is auditable.
The account balance is treated as the system of record: amounts are reconciled
against the change in balance, which is how unit errors (paise vs rupees) are caught.

Run:  python src/clean_data.py
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

VALID_YEARS = {2024, 2025}

CANON_CATEGORIES = [
    "Salary", "Freelance Income", "Family Support", "Part-time Income", "Interest", "Borrowing",
    "Housing", "Loan EMI", "Utilities", "Insurance", "Subscriptions", "Education", "Debt Repayment",
    "Investments", "Groceries", "Food Delivery", "Dining Out", "Transport", "Shopping",
    "Entertainment", "Travel", "Healthcare", "Personal Care", "Cash Withdrawal", "Gifts & Festivals",
]
PAYMENT_ALIASES = {
    "upi": "UPI", "bhim upi": "UPI", "credit card": "Credit Card", "cc": "Credit Card",
    "credit-card": "Credit Card", "debit card": "Debit Card", "dc": "Debit Card",
    "debit-card": "Debit Card", "net banking": "Net Banking", "netbanking": "Net Banking",
    "net-banking": "Net Banking", "auto-debit (nach)": "Auto-Debit (NACH)", "nach": "Auto-Debit (NACH)",
    "auto debit": "Auto-Debit (NACH)", "neft": "NEFT", "imps": "IMPS", "upi autopay": "UPI Autopay",
    "upi-autopay": "UPI Autopay", "atm/cash": "ATM/Cash", "cash": "ATM/Cash", "atm": "ATM/Cash",
    "bank credit": "Bank Credit",
}
DATE_FORMATS = ["%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%Y/%m/%d %H:%M"]


def _key(s: str) -> str:
    """normalise text for matching: lower, '&' for 'and', single spaces"""
    s = str(s).strip().lower().replace("_", " ").replace(" and ", " & ")
    return re.sub(r"\s+", " ", s)


CAT_LOOKUP = {_key(c): c for c in CANON_CATEGORIES}


def parse_date(s: str) -> tuple[pd.Timestamp | None, str | None]:
    """returns (timestamp, fix_label)"""
    s = str(s).strip()
    for i, fmt in enumerate(DATE_FORMATS):
        try:
            t = pd.to_datetime(s, format=fmt)
        except ValueError:
            continue
        fix = None if i == 0 else "date_format_standardised"
        if t.year not in VALID_YEARS:
            y = str(t.year)
            swapped = int(y[:2] + y[3] + y[2])       # 2052 -> 2025
            if swapped in VALID_YEARS:
                t = t.replace(year=swapped)
                fix = "future_date_year_corrected"
            else:
                return None, "invalid_date"
        return t, fix
    return None, "invalid_date"


def clean(raw: pd.DataFrame, customers: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    df = raw.copy()
    log: list[tuple[str, str, str]] = []
    stats: dict = {"raw_rows": len(df)}

    def note(ids, step, detail=""):
        for i in ids:
            log.append((i, step, detail))

    # 1. Exact duplicates -----------------------------------------------------------
    dup_mask = df.duplicated(keep="first")
    note(df.loc[dup_mask, "transaction_id"], "exact_duplicate_removed")
    df = df.loc[~dup_mask].copy()
    stats["exact_duplicates_removed"] = int(dup_mask.sum())

    # 2. Amount: text -> number, sign errors ---------------------------------------
    amt_txt = df["amount"].astype(str)
    is_text = amt_txt.str.contains(r"[₹,]", regex=True)
    note(df.loc[is_text, "transaction_id"], "amount_text_converted")
    df["amount"] = pd.to_numeric(amt_txt.str.replace(r"[₹,\s]", "", regex=True), errors="coerce")
    neg = df["amount"] < 0
    note(df.loc[neg, "transaction_id"], "negative_amount_sign_fixed")
    df["amount"] = df["amount"].abs()
    stats["amount_text_converted"] = int(is_text.sum())
    stats["negative_amounts_fixed"] = int(neg.sum())

    # 3. Dates -----------------------------------------------------------------------
    parsed = df["date"].map(parse_date)
    df["date"] = parsed.map(lambda x: x[0])
    fixes = parsed.map(lambda x: x[1])
    for lab in ("date_format_standardised", "future_date_year_corrected", "invalid_date"):
        note(df.loc[fixes == lab, "transaction_id"], lab)
        stats[lab] = int((fixes == lab).sum())
    df = df.loc[df["date"].notna()].copy()
    df["date"] = pd.to_datetime(df["date"])

    # 4. Text standardisation --------------------------------------------------------
    cat_before = df["category"].copy()
    df["category"] = df["category"].map(lambda v: CAT_LOOKUP.get(_key(v)) if pd.notna(v) else np.nan)
    changed = cat_before.notna() & (cat_before != df["category"])
    note(df.loc[changed, "transaction_id"], "category_standardised")
    stats["category_standardised"] = int(changed.sum())

    pm_before = df["payment_method"].copy()
    df["payment_method"] = df["payment_method"].map(
        lambda v: PAYMENT_ALIASES.get(_key(v), str(v).strip()) if pd.notna(v) else np.nan)
    changed = pm_before.notna() & (pm_before != df["payment_method"])
    note(df.loc[changed, "transaction_id"], "payment_method_standardised")
    stats["payment_method_standardised"] = int(changed.sum())

    # merchants: trim/collapse spaces, then map case variants to the most common spelling
    m_before = df["merchant"].copy()
    df["merchant"] = df["merchant"].map(lambda v: re.sub(r"\s+", " ", str(v).strip()) if pd.notna(v) else np.nan)
    canon = (df.dropna(subset=["merchant"]).assign(k=lambda d: d["merchant"].str.lower())
             .groupby("k")["merchant"].agg(lambda s: s.value_counts().index[0]))
    df["merchant"] = df["merchant"].map(lambda v: canon.get(v.lower(), v) if pd.notna(v) else np.nan)
    changed = m_before.notna() & (m_before != df["merchant"])
    note(df.loc[changed, "transaction_id"], "merchant_standardised")
    stats["merchant_standardised"] = int(changed.sum())

    # 5. Near-duplicates (same txn re-posted with a new ID) ------------------------
    keys = ["customer_id", "date", "transaction_type", "amount", "merchant", "account_balance"]
    df = df.sort_values("transaction_id")
    near = df.duplicated(subset=keys, keep="first")
    note(df.loc[near, "transaction_id"], "near_duplicate_removed")
    df = df.loc[~near].copy()
    stats["near_duplicates_removed"] = int(near.sum())

    # 6. Missing values (imputed from reliable relationships, never guessed blindly) ---
    sub_to_cat = df.dropna(subset=["category"]).groupby("subcategory")["category"].agg(lambda s: s.mode()[0])
    miss = df["category"].isna()
    df.loc[miss, "category"] = df.loc[miss, "subcategory"].map(sub_to_cat)
    note(df.loc[miss, "transaction_id"], "category_imputed_from_subcategory")
    stats["category_imputed"] = int(miss.sum())

    sub_merchants = df.dropna(subset=["merchant"]).groupby("subcategory")["merchant"].nunique()
    single = df.dropna(subset=["merchant"]).groupby("subcategory")["merchant"].first()[sub_merchants == 1]
    # recurring payments go to the same merchant every month for the same customer
    rec = df.dropna(subset=["merchant"]).loc[df["recurring_flag"] == 1]
    # same customer + subcategory + amount  -> same merchant (e.g. Netflix 649 vs Spotify 119)
    cust_sub_amt = rec.assign(a=rec["amount"].round(0)).groupby(["customer_id", "subcategory", "a"])["merchant"].agg(
        lambda s: s.mode()[0])
    n_merch = rec.groupby(["customer_id", "subcategory"])["merchant"].nunique()
    cust_sub_merchant = rec.groupby(["customer_id", "subcategory"])["merchant"].agg(lambda s: s.mode()[0])[n_merch == 1]
    # a customer who always uses one merchant for a subcategory (e.g. their local kirana store)
    known = df.dropna(subset=["merchant"])
    cs_n = known.groupby(["customer_id", "subcategory"])["merchant"].agg(["nunique", "size", "first"])
    cust_single = cs_n.loc[(cs_n["nunique"] == 1) & (cs_n["size"] >= 3), "first"]
    miss = df["merchant"].isna()
    fill = []
    for i, r in df.loc[miss].iterrows():
        if r["subcategory"] in single.index:
            fill.append(single[r["subcategory"]])
        elif (r["customer_id"], r["subcategory"]) in cust_single.index:
            fill.append(cust_single[(r["customer_id"], r["subcategory"])])
        elif r["recurring_flag"] == 1 and (r["customer_id"], r["subcategory"], round(r["amount"])) in cust_sub_amt.index:
            fill.append(cust_sub_amt[(r["customer_id"], r["subcategory"], round(r["amount"]))])
        elif r["recurring_flag"] == 1 and (r["customer_id"], r["subcategory"]) in cust_sub_merchant.index:
            fill.append(cust_sub_merchant[(r["customer_id"], r["subcategory"])])
        else:
            fill.append("Unknown Merchant")
    df.loc[miss, "merchant"] = fill
    note(df.loc[miss, "transaction_id"], "merchant_imputed")
    stats["merchant_imputed"] = int(miss.sum())
    stats["merchant_set_unknown"] = int(sum(f == "Unknown Merchant" for f in fill))

    pm_mode = (df.dropna(subset=["payment_method"]).groupby(["customer_id", "subcategory"])["payment_method"]
               .agg(lambda s: s.mode()[0]))
    pm_cat = df.dropna(subset=["payment_method"]).groupby("subcategory")["payment_method"].agg(lambda s: s.mode()[0])
    miss = df["payment_method"].isna()
    df.loc[miss, "payment_method"] = [
        pm_mode.get((r.customer_id, r.subcategory), pm_cat.get(r.subcategory, "Unknown"))
        for r in df.loc[miss].itertuples()]
    note(df.loc[miss, "transaction_id"], "payment_method_imputed")
    stats["payment_method_imputed"] = int(miss.sum())

    # 7. Balance reconciliation (balance = previous balance +/- amount) --------------
    df = df.sort_values(["customer_id", "date", "transaction_id"]).reset_index(drop=True)
    sign = np.where(df["transaction_type"] == "Credit", 1, -1)
    prev = df.groupby("customer_id")["account_balance"].shift()
    implied = (df["account_balance"] - prev) * sign          # amount implied by the balance movement
    mismatch = prev.notna() & ((implied - df["amount"]).abs() > 0.05)
    paise = mismatch & ((df["amount"] / 100 - implied).abs() < 0.05)
    note(df.loc[paise, "transaction_id"], "paise_unit_error_fixed")
    df.loc[paise, "amount"] = (df.loc[paise, "amount"] / 100).round(2)
    other = mismatch & ~paise
    note(df.loc[other, "transaction_id"], "amount_reconciled_to_balance")
    df.loc[other, "amount"] = implied[other].round(2)
    stats["paise_errors_fixed"] = int(paise.sum())
    stats["other_balance_mismatches_fixed"] = int(other.sum())
    prev = df.groupby("customer_id")["account_balance"].shift()
    still = prev.notna() & (((df["account_balance"] - prev) * sign - df["amount"]).abs() > 0.05)
    stats["balance_breaks_after_cleaning"] = int(still.sum())

    # 8. Consistency checks -----------------------------------------------------------
    ok_pairs = {("Credit", "Income"), ("Credit", "Borrowing"), ("Debit", "Expense"), ("Debit", "Investment")}
    pair_bad = ~df[["transaction_type", "income_expense"]].apply(tuple, axis=1).isin(ok_pairs)
    stats["type_mismatch_rows"] = int(pair_bad.sum())
    stats["unknown_customers"] = int((~df["customer_id"].isin(customers["customer_id"])).sum())
    inc_map = customers.set_index("customer_id")["declared_monthly_income"]
    stats["income_field_mismatch"] = int((df["customer_id"].map(inc_map) != df["monthly_income"]).sum())
    stats["non_positive_amounts"] = int((df["amount"] <= 0).sum())

    # 9. Outliers (flagged, NOT removed: a hospital bill is real behaviour) ----------
    # robust z-score of log(amount) within each subcategory
    la = np.log1p(df["amount"])
    med = la.groupby(df["subcategory"]).transform("median")
    mad = (la - med).abs().groupby(df["subcategory"]).transform("median").replace(0, np.nan)
    rz = 0.6745 * (la - med) / mad
    df["exceeds_monthly_income"] = ((df["transaction_type"] == "Debit")
                                    & (df["amount"] > df["monthly_income"])).astype(int)
    # a non-recurring debit larger than a month's income is also a one-off (e.g. hospital bill),
    # even when it is "normal" for its own subcategory
    one_off = (df["exceeds_monthly_income"] == 1) & (df["recurring_flag"] == 0)
    df["is_outlier"] = ((rz.abs() > 3.5).fillna(False) | one_off).astype(int)
    stats["outliers_flagged"] = int(df["is_outlier"].sum())
    stats["debits_above_monthly_income"] = int(df["exceeds_monthly_income"].sum())

    # 10. Derived columns used throughout the project ------------------------------
    df["signed_amount"] = df["amount"] * sign
    df["year_month"] = df["date"].dt.to_period("M").astype(str)
    df["txn_date"] = df["date"].dt.date
    df["day_of_week"] = df["date"].dt.day_name()
    df["is_weekend"] = (df["date"].dt.dayofweek >= 5).astype(int)
    df["spend_type"] = df["category"].map(SPEND_TYPE).fillna("Not Spend")

    stats["clean_rows"] = len(df)
    log_df = pd.DataFrame(log, columns=["transaction_id", "cleaning_step", "detail"])
    return df, log_df, stats


SPEND_TYPE = {
    "Housing": "Fixed Obligation", "Loan EMI": "Fixed Obligation", "Insurance": "Fixed Obligation",
    "Debt Repayment": "Fixed Obligation", "Utilities": "Essential Variable", "Groceries": "Essential Variable",
    "Transport": "Essential Variable", "Healthcare": "Essential Variable", "Education": "Essential Variable",
    "Food Delivery": "Discretionary", "Dining Out": "Discretionary", "Shopping": "Discretionary",
    "Entertainment": "Discretionary", "Travel": "Discretionary", "Personal Care": "Discretionary",
    "Subscriptions": "Discretionary", "Cash Withdrawal": "Discretionary", "Gifts & Festivals": "Discretionary",
    "Investments": "Investment",
}


def grade_against_injection(clean_df: pd.DataFrame, clean_log: pd.DataFrame) -> pd.DataFrame:
    """Compares what we fixed with what the generator secretly broke."""
    inj = pd.read_csv(RAW / "injected_issues_log.csv")
    truth = pd.read_csv(RAW / "_ground_truth_transactions.csv", parse_dates=["date"])
    step_map = {
        "exact_duplicate": "exact_duplicate_removed", "near_duplicate_reposted": "near_duplicate_removed",
        "missing_category": "category_imputed_from_subcategory", "missing_merchant": "merchant_imputed",
        "missing_payment_method": "payment_method_imputed", "category_variant": "category_standardised",
        "payment_method_variant": "payment_method_standardised", "merchant_formatting": "merchant_standardised",
        "negative_amount": "negative_amount_sign_fixed", "paise_unit_error": "paise_unit_error_fixed",
        "amount_as_text": "amount_text_converted", "mixed_date_format": "date_format_standardised",
        "future_date_year_typo": "future_date_year_corrected",
    }
    fixed = set(zip(clean_log["transaction_id"], clean_log["cleaning_step"]))
    rows = []
    t = truth.set_index("transaction_id")
    c = clean_df.set_index("transaction_id")
    for issue, g in inj.groupby("issue_type"):
        step = step_map[issue]
        detected = sum((tid, step) in fixed for tid in g["transaction_id"])
        # value-level accuracy: does the cleaned value equal the ground truth?
        col = {"missing_category": "category", "missing_merchant": "merchant",
               "missing_payment_method": "payment_method", "category_variant": "category",
               "payment_method_variant": "payment_method", "merchant_formatting": "merchant",
               "negative_amount": "amount", "paise_unit_error": "amount", "amount_as_text": "amount",
               "mixed_date_format": "date", "future_date_year_typo": "date"}.get(issue)
        if col:
            ids = [i for i in g["transaction_id"] if i in c.index]
            if col == "amount":
                acc = np.mean([abs(c.at[i, col] - t.at[i, col]) < 0.01 for i in ids])
            else:
                acc = np.mean([c.at[i, col] == t.at[i, col] for i in ids])
        else:
            acc = np.nan
        rows.append(dict(issue_type=issue, injected=len(g), detected=detected,
                         detection_rate=detected / len(g), value_restored_correctly=acc))
    return pd.DataFrame(rows).sort_values("injected", ascending=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (ROOT / "reports").mkdir(exist_ok=True)
    raw = pd.read_csv(RAW / "transactions_raw.csv", dtype=str)
    raw["account_balance"] = raw["account_balance"].astype(float)
    raw["recurring_flag"] = raw["recurring_flag"].astype(int)
    raw["monthly_income"] = raw["monthly_income"].astype(float)
    customers = pd.read_csv(RAW / "customers_raw.csv")

    df, log, stats = clean(raw, customers)

    # customers: income band for segmentation
    customers["income_band"] = pd.cut(customers["declared_monthly_income"],
                                      [0, 25000, 50000, 100000, 150000, np.inf],
                                      labels=["<25K", "25K-50K", "50K-1L", "1L-1.5L", "1.5L+"]).astype(str)

    df.to_csv(OUT / "transactions_clean.csv", index=False)
    customers.to_csv(OUT / "customers_clean.csv", index=False)
    log.to_csv(OUT / "cleaning_log.csv", index=False)

    scorecard = grade_against_injection(df, log)
    scorecard.to_csv(ROOT / "reports" / "data_quality_scorecard.csv", index=False)
    write_report(stats, scorecard)
    print(pd.Series(stats).to_string())
    print(scorecard.to_string(index=False))


def write_report(stats: dict, sc: pd.DataFrame) -> None:
    lines = ["# Data Quality Report", "",
             "Generated by `src/clean_data.py`. The raw file had issues deliberately injected by the generator "
             "and logged separately; this report grades the cleaning pipeline against that log.", "",
             "## Cleaning summary", "", "| Check | Rows |", "|---|---:|"]
    labels = {
        "raw_rows": "Raw rows", "exact_duplicates_removed": "Exact duplicates removed",
        "near_duplicates_removed": "Near-duplicates (re-posted with new ID) removed",
        "amount_text_converted": "Amounts stored as text (₹, commas) converted",
        "negative_amounts_fixed": "Negative amounts (sign errors) corrected",
        "date_format_standardised": "Non-standard date formats parsed",
        "future_date_year_corrected": "Future dates (year typo) corrected", "invalid_date": "Unparseable dates dropped",
        "category_standardised": "Category spellings standardised",
        "payment_method_standardised": "Payment-method aliases standardised",
        "merchant_standardised": "Merchant names trimmed / re-cased",
        "category_imputed": "Missing category imputed from subcategory",
        "merchant_imputed": "Missing merchant imputed", "merchant_set_unknown": "...of which set to 'Unknown Merchant'",
        "payment_method_imputed": "Missing payment method imputed (customer x subcategory mode)",
        "paise_errors_fixed": "Paise/rupee unit errors fixed via balance reconciliation",
        "other_balance_mismatches_fixed": "Other amount-vs-balance mismatches",
        "balance_breaks_after_cleaning": "Balance-chain breaks remaining after cleaning",
        "type_mismatch_rows": "Credit/Debit vs Income/Expense mismatches",
        "unknown_customers": "Transactions for unknown customers",
        "income_field_mismatch": "monthly_income disagreeing with customer master",
        "non_positive_amounts": "Zero/negative amounts remaining",
        "outliers_flagged": "Outliers flagged and kept (robust z > 3.5, or one-off debit > monthly income)",
        "debits_above_monthly_income": "Single debits larger than monthly income (flagged)",
        "clean_rows": "Clean rows",
    }
    for k, lab in labels.items():
        lines.append(f"| {lab} | {stats.get(k, 0):,} |")
    lines += ["", "## Scorecard: injected vs detected", "",
              "| Issue | Injected | Detected | Detection rate | Value restored to truth |",
              "|---|---:|---:|---:|---:|"]
    for r in sc.itertuples():
        acc = "n/a (row removed)" if pd.isna(r.value_restored_correctly) else f"{r.value_restored_correctly:.1%}"
        lines.append(f"| {r.issue_type} | {r.injected:,} | {r.detected:,} | {r.detection_rate:.1%} | {acc} |")
    lines += ["", "Notes:",
              "- Missing merchants on non-recurring transactions with many possible merchants cannot be recovered "
              "and are set to `Unknown Merchant` rather than guessed; this explains value-restoration below 100%.",
              "- Missing payment methods are imputed with the customer's usual method for that subcategory, which "
              "is a best estimate, not a certainty.",
              "- Outliers are flagged, not deleted: large hospital bills and travel bookings are genuine behaviour "
              "that the stress score must see."]
    (ROOT / "reports" / "data_quality_report.md").write_text(
    "\n".join(lines) + "\n",
    encoding="utf-8"
)


if __name__ == "__main__":
    main()
