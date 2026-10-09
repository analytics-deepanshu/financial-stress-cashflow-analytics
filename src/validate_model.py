"""
Validation of the Stress Score and the Cash-Flow forecast.

1. Forecast backtest   : six one-month-ahead forecasts (Apr..Sep 2025), each using only data
                         available at the time, compared with what actually happened.
2. Early-warning test  : does a high stress score in month m predict borrowing in month m+1?
                         (pooled over Mar-2025 ... Aug-2025)
3. Persona check       : do customers generated as "at-risk" personas get higher scores?
                         (personas are hidden from the score; this is the ground-truth test
                          that is only possible because the data is synthetic)
4. Weight sensitivity  : how many customers change band if all 7 factors get equal weight?

Output: reports/model_validation.md and data/analytics/validation_*.csv
Run:  python src/validate_model.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from cashflow_forecast import forecast
from stress_score import BANDS, FACTORS, customer_factors, score

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
ANALYTICS = ROOT / "data" / "analytics"
AT_RISK = {"emi_burdened", "irregular_earner", "lifestyle_creep", "shock_event", "student_early_career"}
BAND_ORDER = [b for _, b in BANDS]


def auc(y_true, y_score) -> float:
    """Mann-Whitney AUC: probability a random positive scores higher than a random negative"""
    y_true, y_score = np.asarray(y_true), np.asarray(y_score)
    ranks = pd.Series(y_score).rank().values
    n_pos, n_neg = y_true.sum(), (1 - y_true).sum()
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return float((ranks[y_true == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def main() -> dict:
    tx = pd.read_csv(PROC / "transactions_clean.csv", parse_dates=["date"])
    cm = pd.read_csv(ANALYTICS / "customer_month.csv")
    months = sorted(cm["year_month"].unique())
    res: dict = {}

    # 1. Forecast backtest: pooled over 6 one-month-ahead forecasts --------------------
    bts = []
    for i in range(5, len(months) - 1):
        as_of_i, target_i = months[i], months[i + 1]
        fc = forecast(tx, cm, as_of_i)
        act = cm[cm["year_month"] == target_i].set_index("customer_id")
        debits = (tx[(tx["year_month"] == target_i) & (tx["transaction_type"] == "Debit")]
                  .groupby("customer_id")["amount"].sum())
        b = fc.set_index("customer_id").join(pd.DataFrame({
            "actual_income": act["income"], "actual_outflows": debits,
            "actual_unassisted_end": act["month_end_balance"] - act["borrowing"],
            "actual_borrowed": act["borrowed_this_month"]})).fillna({"actual_outflows": 0})
        bts.append(b.reset_index())
    bt = pd.concat(bts, ignore_index=True)
    bt["actual_cash_crunch"] = ((bt["actual_borrowed"] == 1) | (bt["actual_unassisted_end"] < 0)).astype(int)
    bt.to_csv(ANALYTICS / "validation_forecast_backtest.csv", index=False)
    as_of, target = f"{months[5]}..{months[-2]}", f"{months[6]}..{months[-1]}"

    wmape = lambda a, f: float((a - f).abs().sum() / a.abs().sum())
    res["n_forecasts"] = len(bt)
    res["income_wmape"] = wmape(bt["actual_income"], bt["expected_income"])
    res["outflow_wmape"] = wmape(bt["actual_outflows"], bt["expected_outflows"])
    err = (bt["actual_unassisted_end"] - bt["expected_ending_balance"]).abs()
    res["end_balance_median_abs_err"] = float(err.median())
    res["end_balance_median_abs_err_pct_income"] = float((err / bt["expected_income"].clip(lower=1)).median())
    flagged = bt["cashflow_risk_tier"].isin(["High", "Medium"]).astype(int)
    tp = int(((flagged == 1) & (bt["actual_cash_crunch"] == 1)).sum())
    fp = int(((flagged == 1) & (bt["actual_cash_crunch"] == 0)).sum())
    fn = int(((flagged == 0) & (bt["actual_cash_crunch"] == 1)).sum())
    tn = int(((flagged == 0) & (bt["actual_cash_crunch"] == 0)).sum())
    res.update(bt_tp=tp, bt_fp=fp, bt_fn=fn, bt_tn=tn, bt_actual_crunch=int(bt["actual_cash_crunch"].sum()),
               bt_precision=tp / (tp + fp) if tp + fp else float("nan"),
               bt_recall=tp / (tp + fn) if tp + fn else float("nan"),
               bt_auc=auc(bt["actual_cash_crunch"], bt["deficit_probability"]),
               bt_base_rate=float(bt["actual_cash_crunch"].mean()))
    res["bt_tier_table"] = (bt.groupby("cashflow_risk_tier")["actual_cash_crunch"].agg(["count", "sum", "mean"])
                            .reindex(["High", "Medium", "Low"]).fillna(0))

    # 2. Early warning: score in month m vs borrowing in m+1 ------------------------------
    ew = []
    for i in range(5, len(months) - 1):
        s = score(customer_factors(cm, months[i]))[["customer_id", "stress_score", "stress_band"]]
        nxt = cm[cm["year_month"] == months[i + 1]][["customer_id", "borrowed_this_month"]]
        ew.append(s.merge(nxt, on="customer_id").assign(score_month=months[i]))
    ew = pd.concat(ew)
    ew.to_csv(ANALYTICS / "validation_early_warning.csv", index=False)
    res["ew_table"] = (ew.groupby("stress_band")["borrowed_this_month"].agg(["count", "sum", "mean"])
                       .reindex(BAND_ORDER).fillna(0))
    res["ew_auc"] = auc(ew["borrowed_this_month"], ew["stress_score"])
    res["ew_period"] = f"{months[5]} to {months[-2]}"

    # 3. Persona check -----------------------------------------------------------------------
    s = pd.read_csv(ANALYTICS / "customer_stress_score.csv")
    pers = pd.read_csv(ROOT / "data" / "raw" / "_hidden_personas.csv")
    sp = s.merge(pers, on="customer_id")
    sp["at_risk_persona"] = sp["persona"].isin(AT_RISK).astype(int)
    res["persona_auc"] = auc(sp["at_risk_persona"], sp["stress_score"])
    res["persona_table"] = pd.crosstab(sp["persona"], sp["stress_band"]).reindex(columns=BAND_ORDER, fill_value=0)
    res["persona_mean"] = sp.groupby("persona")["stress_score"].mean().sort_values()
    sp[["customer_id", "persona", "stress_score", "stress_band"]].to_csv(ANALYTICS / "validation_persona_check.csv", index=False)

    # 4. Sensitivity: equal weights ---------------------------------------------------------
    f = customer_factors(cm, months[-1])
    eq = score(f, {k: 1 for k in FACTORS})
    base = score(f)
    res["sens_band_agreement"] = float((eq["stress_band"] == base["stress_band"]).mean())
    res["sens_rank_corr"] = float(base["stress_score"].rank().corr(eq["stress_score"].rank()))
    res["sens_shift"] = pd.crosstab(base["stress_band"], eq["stress_band"]).reindex(
        index=BAND_ORDER, columns=BAND_ORDER, fill_value=0)

    write_report(res, as_of, target)
    return res


def _md(df: pd.DataFrame, fmt: dict | None = None) -> str:
    fmt = fmt or {}
    cols = [df.index.name or ""] + list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for idx, r in df.iterrows():
        vals = [fmt.get(c, "{}").format(v) for c, v in r.items()]
        out.append("| " + " | ".join([str(idx)] + vals) + " |")
    return "\n".join(out)


def write_report(r: dict, as_of: str, target: str) -> None:
    bt = r["bt_tier_table"].rename(columns={"count": "forecasts", "sum": "had cash crunch", "mean": "crunch rate"})
    bt.index.name = "Forecast tier"
    ew = r["ew_table"].rename(columns={"count": "customer-months", "sum": "borrowed next month", "mean": "borrow rate"})
    ew.index.name = "Stress band (month m)"
    pt = r["persona_table"]
    pt.index.name = "Hidden persona"
    sh = r["sens_shift"]
    sh.index.name = "Weighted band \\ Equal-weight band"
    lines = [
        "# Model Validation", "",
        "Generated by `src/validate_model.py`.", "",
        f"## 1. Cash-flow forecast backtest ({r['n_forecasts']} customer-month forecasts, target months {target})", "",
        "Each month's forecast uses only data up to the previous month (no look-ahead).", "",
        "| Metric | Value |", "|---|---:|",
        f"| Income forecast error (weighted MAPE) | {r['income_wmape']:.1%} |",
        f"| Outflow forecast error (weighted MAPE) | {r['outflow_wmape']:.1%} |",
        f"| Median abs. error of ending balance | ₹{r['end_balance_median_abs_err']:,.0f} |",
        f"| ...as share of monthly income | {r['end_balance_median_abs_err_pct_income']:.1%} |",
        f"| Customer-months with an actual cash crunch* | {r['bt_actual_crunch']} |",
        f"| Flagged High/Medium and had a crunch (TP) | {r['bt_tp']} |",
        f"| Flagged but no crunch (FP) | {r['bt_fp']} |",
        f"| Missed (FN) | {r['bt_fn']} |",
        f"| Precision / Recall | {r['bt_precision']:.0%} / {r['bt_recall']:.0%} |",
        f"| AUC of deficit probability | {r['bt_auc']:.2f} |",
        f"| Base rate of cash crunch | {r['bt_base_rate']:.1%} |", "",
        "Flagging = forecast tier High or Medium. The safety-cushion level (25% of expected outflows) was "
        "chosen on this same window, so these figures are slightly optimistic; a longer history would allow "
        "a clean out-of-time test.", "",
        "*Cash crunch = the customer had to borrow during the month, or would have ended below zero without borrowing.", "",
        _md(bt, {"forecasts": "{:.0f}", "had cash crunch": "{:.0f}", "crunch rate": "{:.0%}"}), "",
        f"## 2. Early-warning test: stress band in month m vs borrowing in month m+1 ({r['ew_period']})", "",
        _md(ew, {"customer-months": "{:.0f}", "borrowed next month": "{:.0f}", "borrow rate": "{:.1%}"}), "",
        f"AUC of stress score for next-month borrowing: **{r['ew_auc']:.2f}**", "",
        "## 3. Persona check (ground truth only available because the data is synthetic)", "",
        f"AUC separating at-risk personas from healthy personas: **{r['persona_auc']:.2f}**", "",
        _md(pt), "",
        "Mean score by persona: " + ", ".join(f"{k} {v:.1f}" for k, v in r["persona_mean"].items()), "",
        "## 4. Weight sensitivity (benchmark weights vs equal weights)", "",
        f"- Customers keeping the same band: **{r['sens_band_agreement']:.0%}**",
        f"- Rank correlation of scores: **{r['sens_rank_corr']:.2f}**", "",
        _md(sh), "",
        "Interpretation: rankings are stable to the weighting choice, so conclusions about *who* is most stressed "
        "do not depend on the exact weights; band counts shift mainly at boundaries.",
    ]
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "model_validation.md").write_text(
    "\n".join(lines) + "\n",
    encoding="utf-8"
)


if __name__ == "__main__":
    r = main()
    for k, v in r.items():
        if not isinstance(v, (pd.DataFrame, pd.Series)):
            print(f"{k}: {v}")
    print(r["bt_tier_table"]); print(r["ew_table"])
