"""
Creates and executes the walkthrough notebooks in notebooks/ (run after run_pipeline.py).
The notebooks read the pipeline outputs and call the same functions as src/, so the
narrative and the code can never drift apart.

Run:  python src/build_notebooks.py
"""
from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks"

SETUP = """import sys, json
from pathlib import Path
import pandas as pd, numpy as np
from IPython.display import Image, display, Markdown
ROOT = Path.cwd().parent
sys.path.insert(0, str(ROOT / "src"))
pd.set_option("display.max_columns", 40); pd.set_option("display.width", 200)
pd.set_option("display.float_format", lambda x: f"{x:,.2f}")"""


def md(s): return nbf.v4.new_markdown_cell(s.strip())
def code(s): return nbf.v4.new_code_cell(s.strip())


NOTEBOOKS = {
    "01_data_generation.ipynb": [
        md("""# 01 · Synthetic Data Generation
No public dataset has multi-customer transactions **with a consistent running balance**, so the data is simulated.
Each customer gets a hidden *persona* that drives behaviour. The persona is never used by the analysis, only to **validate** it later.

The generator is `src/generate_data.py` and its settings are in `config/generator_config.yaml`."""),
        code(SETUP),
        code("""import yaml
cfg = yaml.safe_load(open(ROOT / "config" / "generator_config.yaml"))
print(json.dumps({k: cfg[k] for k in ["seed", "n_customers", "start_date", "n_months", "persona_mix"]}, indent=1))"""),
        md("""## Persona design
| Persona | What the generator builds in |
|---|---|
| Stable Saver | fixed salary, savings 25–40%, SIPs, 3–8 months buffer |
| Comfortable Spender | fixed salary, thin 5–15% savings, high discretionary tilt |
| EMI-Burdened | loan EMIs at 40–55% of income (above typical lender FOIR limits) |
| Irregular Earner | freelance income, coefficient of variation 0.35–0.60 |
| Lifestyle Creep | spending grows 3–5% per month while income stays flat |
| Shock Event | stable until a medical bill, job loss or salary delay in Mar–Jul 2025 |
| Student / Early-career | family support + stipend, thin buffer |

**Realism rules:** salary on day 1–7; rent, EMI, SIP and insurance on fixed dates; weekend-weighted discretionary spend; Diwali, school-fee, summer-electricity and travel seasonality; payment method driven by amount and category.

**Borrowing:** when a debit would push the balance below ₹1,000, the customer borrows (credit card, instant-loan app or family) and repays app/card loans over the next three months. This keeps every balance consistent and creates a realistic debt-spiral signal."""),
        code("""raw = pd.read_csv(ROOT / "data/raw/transactions_raw.csv", dtype=str)
cust = pd.read_csv(ROOT / "data/raw/customers_raw.csv")
print(f"raw rows: {len(raw):,}   customers: {len(cust)}")
raw.head(8)"""),
        code("""cust.head()"""),
        md("## Injected data-quality issues (logged so the cleaning step can be graded)"),
        code("""log = pd.read_csv(ROOT / "data/raw/injected_issues_log.csv")
log["issue_type"].value_counts().rename("rows").to_frame()"""),
        code("""# a few examples of what the dirty raw data looks like
ids = log.groupby("issue_type").head(1)["transaction_id"]
raw[raw["transaction_id"].isin(ids)][["transaction_id","date","category","merchant","amount","payment_method"]]"""),
        md("## Data dictionary\nSee `data/data_dictionary.md` for every column, its type and its business meaning."),
    ],
    "02_data_cleaning.ipynb": [
        md("""# 02 · Data Cleaning & Validation
The cleaning pipeline (`src/clean_data.py`) works in this order:
1. Remove exact duplicates.
2. Convert amounts stored as text (`₹1,250.00`) and fix sign errors.
3. Parse four date formats and correct year typos (2052 → 2025).
4. Standardise category, payment-method and merchant spellings.
5. Remove near-duplicates (the same transaction re-posted with a new ID).
6. Impute missing values from reliable relationships only. Never guess blindly.
7. **Reconcile every amount against the running balance.** The balance is the system of record, which is how ₹/paise unit errors are caught.
8. Run consistency checks (type vs income/expense, customer master, income field).
9. Flag outliers with a robust z-score. They are **kept**, because a hospital bill is real behaviour."""),
        code(SETUP),
        code("""from clean_data import clean, grade_against_injection
raw = pd.read_csv(ROOT / "data/raw/transactions_raw.csv", dtype=str)
raw["account_balance"] = raw["account_balance"].astype(float)
raw["recurring_flag"] = raw["recurring_flag"].astype(int)
raw["monthly_income"] = raw["monthly_income"].astype(float)
customers = pd.read_csv(ROOT / "data/raw/customers_raw.csv")
df, log, stats = clean(raw, customers)
pd.Series(stats, name="rows").to_frame()"""),
        md("## Missing values before vs after"),
        code("""pd.DataFrame({"missing_before": raw.isna().sum(), "missing_after": df[raw.columns].isna().sum()})"""),
        md("## Balance reconciliation: the key validation\nFor every customer, `balance[t] = balance[t-1] ± amount[t]`. After cleaning there must be **zero** breaks."),
        code("""d = df.sort_values(["customer_id","date","transaction_id"])
prev = d.groupby("customer_id")["account_balance"].shift()
breaks = (prev.notna() & ((d["account_balance"] - prev - d["signed_amount"]).abs() > 0.05)).sum()
print("balance-chain breaks after cleaning:", breaks)"""),
        md("## Scorecard: did we catch what was injected?"),
        code("""grade_against_injection(df, log)"""),
        md("""**Reading the scorecard:**
- Every injected issue was detected.
- Missing merchants on one-off purchases cannot be recovered, so they become `Unknown Merchant` instead of a guess.
- Missing payment methods are filled with the customer's usual method for that subcategory, which is right about 2 times in 3. This is acceptable because payment method is not used by the stress score."""),
        md("## Outliers (flagged, kept)"),
        code("""df[df["is_outlier"] == 1].sort_values("amount", ascending=False)[["customer_id","date","subcategory","merchant","amount"]].head(10)"""),
    ],
    "03_eda.ipynb": [
        md("# 03 · Exploratory Data Analysis\nAll figures are produced by `src/eda.py`. The headline numbers are in `reports/key_metrics.json`."),
        code(SETUP),
        code("""K = json.load(open(ROOT / "reports/key_metrics.json"))
print(f"Total income  ₹{K['total_income']/1e7:.2f} Cr | expenses ₹{K['total_expenses']/1e7:.2f} Cr | savings rate {K['portfolio_savings_rate']:.1%}")
print(f"Lowest-saving month {K['worst_month']} ({K['worst_month_savings_rate']:.1%}); highest {K['best_month']} ({K['best_month_savings_rate']:.1%})")"""),
        md("## 1. Monthly income, expenses and savings"),
        code("""display(Image(ROOT / "reports/figures/01_monthly_cashflow.png", width=900))
pd.read_csv(ROOT / "reports/eda_tables/portfolio_monthly.csv")"""),
        md("## 2. Spending by category & spend type"),
        code("""display(Image(ROOT / "reports/figures/02_spend_by_category.png", width=850))
pd.read_csv(ROOT / "reports/eda_tables/spend_by_category.csv").head(10)"""),
        md("## 3. Spending trends and seasonality"),
        code("""display(Image(ROOT / "reports/figures/03_category_seasonality_heatmap.png", width=950))
print(f"Oct-Nov festive months: {K['festive_uplift']:+.0%} spend vs the other months' average")"""),
        md("## 4. Savings & income stability by occupation"),
        code("""display(Image(ROOT / "reports/figures/04_savings_rate_by_occupation.png", width=800))
display(Image(ROOT / "reports/figures/05_income_stability.png", width=800))
pd.DataFrame({"median savings rate": K["savings_rate_by_occupation"], "median income CV": K["median_income_cv_by_occupation"]})"""),
        md("## 5. Recurring expenses"),
        code("""display(Image(ROOT / "reports/figures/09_recurring_vs_variable.png", width=900))
print(f"Recurring share of expenses: {K['recurring_share_of_expenses']:.0%}; customers with obligations > 50% of income: {K['share_customers_foir_above_50']:.0%}")"""),
        md("## 6. Average transaction value"),
        code("""pd.read_csv(ROOT / "reports/eda_tables/avg_transaction_value_by_category.csv").round(0)"""),
        md("## 7. Weekend vs weekday"),
        code("""display(Image(ROOT / "reports/figures/06_weekend_vs_weekday.png", width=850))"""),
        md("## 8. Payment-method behaviour"),
        code("""display(Image(ROOT / "reports/figures/07_payment_method_mix.png", width=850))
pd.read_csv(ROOT / "reports/eda_tables/payment_method_by_size_band.csv")"""),
        md("## 9. Merchant concentration"),
        code("""display(Image(ROOT / "reports/figures/08_merchant_concentration.png", width=850))
print(f"Top-5 merchants: {K['top5_merchant_share']:.0%} of variable spend; median customer's top-3 merchants: {K['median_customer_top3_merchant_share']:.0%} of their spend")"""),
    ],
    "04_stress_score.ipynb": [
        md("""# 04 · Financial Stress Score
The full methodology is in `docs/stress_score_methodology.md`. In short, there are seven factors. Each is scaled from 0 to 100 between a benchmark "healthy" value and a "maximum stress" value, then weighted.

| Factor | 0 stress | 100 stress | Weight |
|---|---|---|---|
| Savings margin (6m) | ≥ 20% | ≤ −10% | 20 |
| Fixed obligation ratio (6m) | ≤ 30% | ≥ 60% | 20 |
| Emergency buffer | ≥ 6 months | ≤ 0.5 month | 20 |
| Income instability (CV) | ≤ 0.10 | ≥ 0.60 | 10 |
| Expense growth (de-seasonalised, 6m) | ≤ 0% | ≥ +25% | 10 |
| Balance trend (6m, in months of income) | ≥ +0.5 | ≤ −1.0 | 10 |
| Deficit & borrowing frequency | 0 | 1 | 10 |"""),
        code(SETUP),
        code("""from stress_score import FACTORS, customer_factors, score, scale
cm = pd.read_csv(ROOT / "data/analytics/customer_month.csv")
f = customer_factors(cm, cm["year_month"].max())
s = score(f)
s[["customer_id","stress_score","stress_band","top_stress_driver"] + [c for c in s.columns if c.startswith("sub_")]].sort_values("stress_score", ascending=False).head(10)"""),
        md("## Worked example: one customer, step by step"),
        code("""cid = s.sort_values("stress_score", ascending=False).iloc[3]["customer_id"]
r = s.set_index("customer_id").loc[cid]
rows = []
for name, (col, z, h, w) in FACTORS.items():
    rows.append(dict(factor=name, raw_value=round(r[col], 3), zero_stress_at=z, max_stress_at=h,
                     sub_score=r[f"sub_{name}"], weight=w, points=r[f"contrib_{name}"]))
t = pd.DataFrame(rows); display(t)
print(f"{cid}: score = sum(points) = {t.points.sum():.1f} -> band {r['stress_band']}")"""),
        md("## Distribution and drivers"),
        code("""display(Image(ROOT / "reports/figures/10_stress_score_distribution.png", width=850))
display(Image(ROOT / "reports/figures/11_risk_map.png", width=850))
display(Image(ROOT / "reports/figures/12_stress_drivers.png", width=750))"""),
        md("## Validation\nAre the scores meaningful? See notebook 06 and `reports/model_validation.md`."),
    ],
    "05_cashflow_risk.ipynb": [
        md("""# 05 · Next-Month Cash-Flow Risk
- **Expected income:** median of the last 3 months for stable earners, mean of the last 6 months for volatile earners.
- **Expected outflows:** the recurring median plus the weighted recent variable spend, multiplied by the seasonal index, plus known seasonal one-offs.
- **Expected ending balance:** balance + expected income − expected outflows.
- **Uncertainty:** the customer's own month-to-month volatility.
- **Deficit probability:** the chance that the ending balance falls below a **safety cushion** of 25% of expected outflows. Income and bills arrive on different days, so a thin positive month-end still means the account runs dry mid-month.

Full assumptions and limitations are in `docs/cashflow_risk_methodology.md`."""),
        code(SETUP),
        code("""fc = pd.read_csv(ROOT / "data/analytics/cashflow_forecast.csv")
print("Forecast month:", fc.forecast_month.iloc[0], "| seasonal factor:", fc.seasonal_factor_used.iloc[0])
fc["cashflow_risk_tier"].value_counts()"""),
        code("""fc.sort_values("deficit_probability", ascending=False).head(10)[["customer_id","current_balance","expected_income","expected_outflows","expected_ending_balance","safety_cushion","deficit_probability","cashflow_risk_tier"]]"""),
        md("## Watch-list from SQL (Q20)"),
        code("""pd.read_csv(ROOT / "sql/results/Q20_next_month_risk_watch_list_score_forecas.csv")"""),
    ],
    "06_model_validation.ipynb": [
        md("# 06 · Model Validation\nFour tests: a pooled backtest of the forecast, an early-warning test of the score, a persona ground-truth check, and weight sensitivity."),
        code(SETUP),
        code("""display(Markdown(open(ROOT / "reports/model_validation.md").read()))"""),
        code("""ew = pd.read_csv(ROOT / "data/analytics/validation_early_warning.csv")
ew.groupby("stress_band")["borrowed_this_month"].agg(["count","mean"]).reindex(["Low","Moderate","High","Critical"]).rename(columns={"mean":"next-month borrow rate"})"""),
    ],
}


def main() -> None:
    NB.mkdir(exist_ok=True)
    for name, cells in NOTEBOOKS.items():
        nb = nbf.v4.new_notebook()
        nb.cells = cells
        nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
        NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(NB)}}).execute()
        nbf.write(nb, NB / name)
        print("executed", name)


if __name__ == "__main__":
    main()
