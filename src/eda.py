"""
Exploratory Data Analysis: produces figures (reports/figures/*.png), summary tables
(reports/eda_tables/*.csv) and reports/key_metrics.json, which the insights report quotes.

Run:  python src/eda.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC, AN = ROOT / "data" / "processed", ROOT / "data" / "analytics"
FIG, TAB = ROOT / "reports" / "figures", ROOT / "reports" / "eda_tables"

# validated reference palette (see docs/design_notes.md)
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
SERIES = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA]
BAND_COLORS = {"Low": "#0ca30c", "Moderate": "#fab219", "High": "#ec835a", "Critical": "#d03b3b"}
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.titlecolor": INK, "axes.titlesize": 13,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "legend.frameon": False, "lines.linewidth": 2, "axes.titlepad": 26,
})


def inr(x: float, _=None) -> str:
    """Indian short format: ₹ K / L (lakh) / Cr (crore)"""
    a = abs(x)
    s = "-" if x < 0 else ""
    if a >= 1e7:
        return f"{s}₹{a / 1e7:.2f} Cr"
    if a >= 1e5:
        return f"{s}₹{a / 1e5:.1f} L"
    if a >= 1e3:
        return f"{s}₹{a / 1e3:.0f}K"
    return f"{s}₹{a:.0f}"


def subtitle(ax, text):
    ax.text(0, 1.015, text, transform=ax.transAxes, color=INK2, fontsize=9.5, va="bottom")


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / name, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> dict:
    FIG.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    tx = pd.read_csv(PROC / "transactions_clean.csv", parse_dates=["date"])
    cust = pd.read_csv(PROC / "customers_clean.csv")
    cm = pd.read_csv(AN / "customer_month.csv")
    ss = pd.read_csv(AN / "customer_stress_score.csv")
    fc = pd.read_csv(AN / "cashflow_forecast.csv")
    K: dict = {}
    exp = tx[tx["income_expense"] == "Expense"].copy()

    # ---------------- 1. Monthly income / expenses / net -----------------------------
    pm = cm.groupby("year_month")[["income", "expenses", "net_cash_flow", "investment", "borrowing"]].sum()
    pm["savings_rate"] = pm["net_cash_flow"] / pm["income"]
    pm.to_csv(TAB / "portfolio_monthly.csv")
    K["total_income"] = float(pm["income"].sum())
    K["total_expenses"] = float(pm["expenses"].sum())
    K["portfolio_savings_rate"] = float(pm["net_cash_flow"].sum() / pm["income"].sum())
    K["worst_month"] = pm["savings_rate"].idxmin()
    K["worst_month_savings_rate"] = float(pm["savings_rate"].min())
    K["best_month"] = pm["savings_rate"].idxmax()
    K["best_month_savings_rate"] = float(pm["savings_rate"].max())

    labels = pd.to_datetime(pm.index + "-01").strftime("%b\n%y")
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    x = np.arange(len(pm))
    a1.plot(x, pm["income"], color=BLUE, marker="o", ms=4)
    a1.plot(x, pm["expenses"], color=ORANGE, marker="o", ms=4)
    a1.text(x[-1] + 0.15, pm["income"].iloc[-1], "Income", color=INK2, va="center")
    a1.text(x[-1] + 0.15, pm["expenses"].iloc[-1], "Expenses", color=INK2, va="center")
    a1.yaxis.set_major_formatter(mt.FuncFormatter(inr))
    a1.set_title("Monthly income vs expenses, all 200 customers")
    subtitle(a1, "Expenses climb in the Oct–Dec festive season and again in Apr–Jun (school fees, summer power bills)")
    a1.set_xlim(-0.4, len(pm) - 0.2)
    a1.legend(["Income", "Expenses"], loc="upper left", ncol=2)
    a2.bar(x, pm["savings_rate"] * 100, color=AQUA, width=0.6)
    for xi, v in zip(x, pm["savings_rate"] * 100):
        a2.text(xi, v + 0.6, f"{v:.0f}%", ha="center", color=INK2, fontsize=8.5)
    a2.set_ylabel("Savings rate (%)")
    a2.set_xticks(x, labels)
    a2.set_ylim(0, pm["savings_rate"].max() * 100 + 6)
    save(fig, "01_monthly_cashflow.png")

    # ---------------- 2. Spending by category ----------------------------------------
    cat = exp.groupby(["category", "spend_type"])["amount"].sum().reset_index().sort_values("amount")
    cat["share"] = cat["amount"] / cat["amount"].sum()
    cat.sort_values("amount", ascending=False).to_csv(TAB / "spend_by_category.csv", index=False)
    K["top_categories"] = cat.sort_values("amount", ascending=False).head(5)[["category", "share"]].to_dict("records")
    st_share = exp.groupby("spend_type")["amount"].sum() / exp["amount"].sum()
    K["spend_type_share"] = st_share.round(4).to_dict()
    colors = {"Fixed Obligation": BLUE, "Essential Variable": AQUA, "Discretionary": ORANGE}
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(cat["category"], cat["amount"], color=[colors[s] for s in cat["spend_type"]], height=0.65)
    for i, (v, s) in enumerate(zip(cat["amount"], cat["share"])):
        ax.text(v, i, f"  {inr(v)}  ({s:.1%})", va="center", color=INK2, fontsize=8.5)
    ax.xaxis.set_major_formatter(mt.FuncFormatter(inr))
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, cat["amount"].max() * 1.3)
    ax.set_title("Where the money goes: 12-month spend by category")
    subtitle(ax, f"Fixed obligations {st_share.get('Fixed Obligation', 0):.0%} · essential variable "
                 f"{st_share.get('Essential Variable', 0):.0%} · discretionary {st_share.get('Discretionary', 0):.0%}")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colors.values()]
    ax.legend(handles, colors.keys(), loc="lower right")
    save(fig, "02_spend_by_category.png")

    # ---------------- 3. Category x month heatmap (index vs own average) -------------
    cm_cat = exp[exp["spend_type"] != "Fixed Obligation"].pivot_table(
        index="category", columns="year_month", values="amount", aggfunc="sum").fillna(0)
    idx = cm_cat.div(cm_cat.mean(axis=1), axis=0)
    idx = idx.loc[cm_cat.sum(axis=1).sort_values(ascending=False).index]
    idx.round(3).to_csv(TAB / "category_seasonality_index.csv")
    fig, ax = plt.subplots(figsize=(12, 6.5))
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    cmap = LinearSegmentedColormap.from_list("div", ["#2a78d6", "#f0efec", "#e34948"])
    im = ax.imshow(idx.values, aspect="auto", cmap=cmap, norm=TwoSlopeNorm(1.0, 0.0, 2.5))
    ax.set_yticks(range(len(idx)), idx.index)
    ax.set_xticks(range(idx.shape[1]), pd.to_datetime(idx.columns + "-01").strftime("%b %y"), rotation=0, fontsize=8.5)
    for i in range(idx.shape[0]):
        for j in range(idx.shape[1]):
            v = idx.values[i, j]
            ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=7.5,
                    color="#ffffff" if (v > 1.9 or v < 0.35) else INK)
    ax.grid(False)
    ax.set_title("Seasonality: monthly spend vs the category's own average (1.0 = normal)")
    subtitle(ax, "Red = above normal, blue = below. Gifts and travel concentrate in festive and holiday months")
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    cb.outline.set_visible(False)
    save(fig, "03_category_seasonality_heatmap.png")
    oct_nov = exp[exp["year_month"].isin(["2024-10", "2024-11"])]["amount"].sum() / 2
    rest = exp[~exp["year_month"].isin(["2024-10", "2024-11"])]["amount"].sum() / 10
    K["festive_uplift"] = float(oct_nov / rest - 1)

    # ---------------- 4. Savings rate by occupation & income band --------------------
    cs = cm.groupby("customer_id")[["income", "expenses"]].sum()
    cs["savings_rate"] = (cs["income"] - cs["expenses"]) / cs["income"]
    cs = cs.join(cust.set_index("customer_id"))
    seg = cs.groupby("occupation_type")["savings_rate"].describe()[["count", "mean", "25%", "50%", "75%"]]
    seg.to_csv(TAB / "savings_rate_by_occupation.csv")
    K["savings_rate_by_occupation"] = cs.groupby("occupation_type")["savings_rate"].median().round(4).to_dict()
    K["savings_rate_by_tier"] = cs.groupby("city_tier")["savings_rate"].median().round(4).to_dict()
    K["share_customers_negative_savings"] = float((cs["savings_rate"] < 0).mean())
    order = ["Salaried", "Freelancer/Gig", "Student"]
    fig, ax = plt.subplots(figsize=(9, 5))
    data = [cs.loc[cs["occupation_type"] == o, "savings_rate"] * 100 for o in order]
    bp = ax.boxplot(data, orientation="horizontal", patch_artist=True, widths=0.5, showfliers=True,
                    medianprops=dict(color=INK, linewidth=2), whiskerprops=dict(color=AXIS),
                    capprops=dict(color=AXIS), flierprops=dict(marker="o", markersize=4, markerfacecolor=MUTED, markeredgecolor="none"))
    for p in bp["boxes"]:
        p.set(facecolor="#cde2fb", edgecolor=BLUE, linewidth=1.2)
    for i, d in enumerate(data, start=1):
        ax.scatter(d, np.random.default_rng(1).normal(i, 0.06, len(d)), s=10, color=BLUE, alpha=0.5, zorder=3)
    ax.set_yticks(range(1, 4), [f"{o}\n(n={len(d)})" for o, d in zip(order, data)])
    ax.axvline(20, color=MUTED, ls="--", lw=1)
    ax.text(20.5, 3.4, "20% guideline", color=INK2, fontsize=8.5)
    ax.axvline(0, color=AXIS, lw=1)
    ax.set_xlabel("12-month savings rate (%)")
    ax.set_title("Savings rate by occupation type")
    subtitle(ax, "Each dot is a customer. Students and gig workers cluster near or below zero")
    save(fig, "04_savings_rate_by_occupation.png")

    # ---------------- 5. Income stability -----------------------------------------------
    cv = cm.groupby("customer_id")["income"].agg(lambda s: s.std(ddof=0) / s.mean()).rename("income_cv")
    cvj = cust.set_index("customer_id").join(cv)
    K["median_income_cv_by_occupation"] = cvj.groupby("occupation_type")["income_cv"].median().round(3).to_dict()
    cvj.groupby("occupation_type")["income_cv"].describe().to_csv(TAB / "income_volatility_by_occupation.csv")
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for i, o in enumerate(order):
        d = cvj.loc[cvj["occupation_type"] == o, "income_cv"]
        ax.scatter(d, np.random.default_rng(2).normal(i, 0.07, len(d)), s=16, color=SERIES[i], alpha=0.75)
        ax.text(d.median(), i + 0.32, f"median {d.median():.2f}", ha="center", color=INK2, fontsize=8.5)
    ax.set_yticks(range(3), order)
    ax.axvline(0.15, color=MUTED, ls="--", lw=1)
    ax.text(0.155, 2.45, "stable < 0.15", color=INK2, fontsize=8.5)
    ax.set_xlabel("Coefficient of variation of monthly income (std ÷ mean)")
    ax.set_title("Income stability by occupation")
    subtitle(ax, "Salaried income only moves for bonuses and job changes; gig income swings month to month")
    save(fig, "05_income_stability.png")

    # ---------------- 6. Weekend vs weekday ---------------------------------------------
    days = pd.Series(pd.date_range(tx["date"].min().normalize(), tx["date"].max().normalize()))
    n_we, n_wd = int((days.dt.dayofweek >= 5).sum()), int((days.dt.dayofweek < 5).sum())
    var = exp[exp["recurring_flag"] == 0]
    ww = var.groupby(["category", "is_weekend"])["amount"].sum().unstack(fill_value=0)
    ww["weekday_per_day"] = ww[0] / n_wd
    ww["weekend_per_day"] = ww[1] / n_we
    ww["uplift"] = ww["weekend_per_day"] / ww["weekday_per_day"] - 1
    ww = ww.sort_values("uplift")
    ww[["weekday_per_day", "weekend_per_day", "uplift"]].to_csv(TAB / "weekend_vs_weekday.csv")
    K["weekend_uplift_total"] = float((var[var.is_weekend == 1]["amount"].sum() / n_we) /
                                      (var[var.is_weekend == 0]["amount"].sum() / n_wd) - 1)
    K["weekend_uplift_by_category"] = ww["uplift"].round(3).sort_values(ascending=False).head(5).to_dict()
    fig, ax = plt.subplots(figsize=(10, 6))
    y = np.arange(len(ww))
    ax.hlines(y, ww["weekday_per_day"], ww["weekend_per_day"], color=AXIS, lw=2)
    ax.scatter(ww["weekday_per_day"], y, color=BLUE, s=55, zorder=3, label="Weekday (per day)")
    ax.scatter(ww["weekend_per_day"], y, color=ORANGE, s=55, zorder=3, label="Weekend (per day)")
    for yi, (a, b, u) in enumerate(zip(ww["weekday_per_day"], ww["weekend_per_day"], ww["uplift"])):
        ax.text(max(a, b), yi, f"   {u:+.0%}", va="center", color=INK2, fontsize=8.5)
    ax.set_yticks(y, ww.index)
    ax.grid(axis="y", visible=False)
    ax.xaxis.set_major_formatter(mt.FuncFormatter(inr))
    ax.set_title("Weekend vs weekday spend per day (non-recurring spend)")
    subtitle(ax, f"Discretionary categories jump at weekends; overall weekend uplift {K['weekend_uplift_total']:+.0%} per day")
    ax.legend(loc="lower right")
    save(fig, "06_weekend_vs_weekday.png")

    # ---------------- 7. Payment method by size band ------------------------------------
    var2 = exp.copy()
    var2["size_band"] = pd.cut(var2["amount"], [0, 500, 2000, 10000, np.inf],
                               labels=["Micro (<₹500)", "Small (₹500–2K)", "Medium (₹2K–10K)", "Large (>₹10K)"])
    top = ["UPI", "Credit Card", "Auto-Debit (NACH)", "Net Banking"]
    var2["pm"] = np.where(var2["payment_method"].isin(top), var2["payment_method"], "Other")
    pmix = pd.crosstab(var2["size_band"], var2["pm"], normalize="index")[top + ["Other"]]
    pmix.to_csv(TAB / "payment_method_by_size_band.csv")
    K["upi_share_micro"] = float(pmix.loc["Micro (<₹500)", "UPI"])
    K["upi_share_large"] = float(pmix.loc["Large (>₹10K)", "UPI"])
    K["payment_method_count_share"] = (exp["payment_method"].value_counts(normalize=True).round(4).head(6).to_dict())
    fig, ax = plt.subplots(figsize=(10, 4.8))
    left = np.zeros(len(pmix))
    pal = [BLUE, ORANGE, AQUA, YELLOW, "#c3c2b7"]
    for c, col in zip(pmix.columns, pal):
        ax.barh(range(len(pmix)), pmix[c], left=left, color=col, height=0.6, edgecolor=SURFACE, linewidth=2, label=c)
        for i, (l, v) in enumerate(zip(left, pmix[c])):
            if v > 0.07:
                ax.text(l + v / 2, i, f"{v:.0%}", ha="center", va="center", color="#ffffff" if col in (BLUE, ORANGE) else INK, fontsize=8.5)
        left += pmix[c].values
    ax.set_yticks(range(len(pmix)), pmix.index)
    ax.xaxis.set_major_formatter(mt.PercentFormatter(1))
    ax.grid(False)
    ax.set_title("Payment method by transaction size (share of transactions)")
    nach_large = pmix.loc["Large (>₹10K)", "Auto-Debit (NACH)"]
    subtitle(ax, f"UPI leads at every size, but its share falls for large payments, where NACH auto-debits "
                 f"(EMIs, insurance) take {nach_large:.0%}.  Other = UPI Autopay, debit card, NEFT/IMPS, cash")
    ax.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    save(fig, "07_payment_method_mix.png")

    # ---------------- 8. Merchant concentration -----------------------------------------
    mer = var.groupby("merchant")["amount"].sum().sort_values(ascending=False)
    mshare = mer / mer.sum()
    K["top5_merchant_share"] = float(mshare.head(5).sum())
    K["top10_merchant_share"] = float(mshare.head(10).sum())
    K["n_merchants"] = int(mer.size)
    K["top_merchants"] = mshare.head(5).round(4).to_dict()
    cust_conc = (var.groupby(["customer_id", "merchant"])["amount"].sum().groupby(level=0)
                 .apply(lambda s: s.nlargest(3).sum() / s.sum()))
    K["median_customer_top3_merchant_share"] = float(cust_conc.median())
    mshare.head(20).to_csv(TAB / "top_merchants.csv")
    top15 = mshare.head(15)[::-1]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(top15.index, top15.values, color=BLUE, height=0.65)
    for i, v in enumerate(top15.values):
        ax.text(v, i, f" {v:.1%}", va="center", color=INK2, fontsize=8.5)
    ax.xaxis.set_major_formatter(mt.PercentFormatter(1))
    ax.grid(axis="y", visible=False)
    ax.set_title("Top 15 merchants by share of non-recurring spend")
    subtitle(ax, f"Top 5 merchants = {K['top5_merchant_share']:.0%} of discretionary/variable spend across {K['n_merchants']} merchants")
    save(fig, "08_merchant_concentration.png")

    # ---------------- 9. Recurring vs variable expenses ---------------------------------
    rv = exp.assign(kind=np.where(exp["recurring_flag"] == 1, "Recurring", "Non-recurring")).pivot_table(
        index="year_month", columns="kind", values="amount", aggfunc="sum")
    rv["recurring_share"] = rv["Recurring"] / (rv["Recurring"] + rv["Non-recurring"])
    rv.to_csv(TAB / "recurring_vs_variable.csv")
    K["recurring_share_of_expenses"] = float(exp.loc[exp.recurring_flag == 1, "amount"].sum() / exp["amount"].sum())
    rec_inc = cm.groupby("customer_id")[["fixed_obligations", "income"]].sum()
    rec_inc["foir"] = rec_inc["fixed_obligations"] / rec_inc["income"]
    K["share_customers_foir_above_50"] = float((rec_inc["foir"] > 0.5).mean())
    K["median_foir"] = float(rec_inc["foir"].median())
    fig, ax = plt.subplots(figsize=(11, 4.8))
    x = np.arange(len(rv))
    ax.bar(x, rv["Recurring"], color=BLUE, width=0.62, label="Recurring", edgecolor=SURFACE, linewidth=2)
    ax.bar(x, rv["Non-recurring"], bottom=rv["Recurring"], color=ORANGE, width=0.62, label="Non-recurring",
           edgecolor=SURFACE, linewidth=2)
    for xi, (r, s) in enumerate(zip(rv["Recurring"], rv["recurring_share"])):
        ax.text(xi, r / 2, f"{s:.0%}", ha="center", va="center", color="#ffffff", fontsize=8.5)
    ax.set_xticks(x, pd.to_datetime(rv.index + "-01").strftime("%b\n%y"))
    ax.yaxis.set_major_formatter(mt.FuncFormatter(inr))
    ax.grid(axis="x", visible=False)
    ax.set_title("Recurring vs non-recurring expenses by month")
    subtitle(ax, "Label = recurring share. Recurring commitments are the floor that cannot be cut quickly")
    ax.legend(loc="upper right", ncol=2)
    save(fig, "09_recurring_vs_variable.png")

    # ---------------- 10. Average transaction value -------------------------------------
    atv = exp.groupby("category")["amount"].agg(["mean", "median", "count"]).sort_values("median", ascending=False)
    atv.to_csv(TAB / "avg_transaction_value_by_category.csv")
    K["avg_expense_txn_value"] = float(exp["amount"].mean())
    K["median_expense_txn_value"] = float(exp["amount"].median())

    # ---------------- 11. Stress-score distribution ---------------------------------------
    bands = ["Low", "Moderate", "High", "Critical"]
    K["band_counts"] = ss["stress_band"].value_counts().reindex(bands, fill_value=0).to_dict()
    K["mean_stress_score"] = float(ss["stress_score"].mean())
    K["top_drivers_high_critical"] = (ss[ss["stress_band"].isin(["High", "Critical"])]["top_stress_driver"]
                                      .value_counts().to_dict())
    fig, ax = plt.subplots(figsize=(10, 4.8))
    bins = np.arange(0, 105, 5)
    for b, (lo, hi) in zip(bands, [(0, 30), (30, 60), (60, 80), (80, 100.1)]):
        d = ss.loc[(ss["stress_score"] > lo) | ((lo == 0) & (ss["stress_score"] >= 0))]
        d = d.loc[d["stress_score"] <= hi, "stress_score"]
        ax.hist(d, bins=bins, color=BAND_COLORS[b], edgecolor=SURFACE, linewidth=2,
                label=f"{b} ({K['band_counts'][b]})")
    for x0 in (30, 60, 80):
        ax.axvline(x0, color=MUTED, ls="--", lw=1)
    ax.set_xlabel("Financial Stress Score (0 = no stress, 100 = critical)")
    ax.set_ylabel("Customers")
    ax.grid(axis="x", visible=False)
    ax.set_title("Financial Stress Score distribution (as of Sep 2025)")
    subtitle(ax, "Most customers are healthy; a long right tail holds the customers who need intervention")
    ax.legend(title="Band (customers)", title_fontsize=9)
    save(fig, "10_stress_score_distribution.png")

    # ---------------- 12. Risk map: obligations vs savings --------------------------------
    fig, ax = plt.subplots(figsize=(10, 6))
    for b in bands:
        d = ss[ss["stress_band"] == b]
        ax.scatter(d["fixed_obligation_ratio_6m"] * 100, d["savings_rate_6m"] * 100, s=40,
                   color=BAND_COLORS[b], edgecolor=SURFACE, linewidth=1.2, label=b, alpha=0.9)
    ax.axvline(50, color=MUTED, ls="--", lw=1)
    ax.axhline(0, color=AXIS, lw=1)
    ax.text(50.5, ax.get_ylim()[1] * 0.92, "50% obligation ratio\n(typical lender ceiling)", color=INK2, fontsize=8.5)
    ax.set_xlabel("Fixed obligation ratio, last 6 months (%)")
    ax.set_ylabel("Savings rate, last 6 months (%)")
    ax.set_title("Risk map: committed income vs savings")
    subtitle(ax, "Bottom-right = most income already committed and nothing left over")
    ax.legend(title="Stress band")
    save(fig, "11_risk_map.png")

    # ---------------- 13. Score drivers among High/Critical --------------------------------
    hc = ss[ss["stress_band"].isin(["High", "Critical"])]
    contrib = hc[[c for c in ss.columns if c.startswith("contrib_")]].mean().sort_values()
    contrib.index = contrib.index.str.replace("contrib_", "").str.replace("_", " ").str.capitalize()
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.barh(contrib.index, contrib.values, color=ORANGE, height=0.6)
    for i, v in enumerate(contrib.values):
        ax.text(v, i, f" {v:.1f} pts", va="center", color=INK2, fontsize=8.5)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Average points contributed to the score")
    ax.set_title(f"What drives stress for the {len(hc)} High/Critical customers")
    subtitle(ax, "Average contribution of each factor to the 0–100 score")
    save(fig, "12_stress_drivers.png")
    K["avg_contrib_high_critical"] = contrib.round(2).to_dict()

    # ---------------- forecast + segments for insights -------------------------------------
    K["forecast_month"] = str(fc["forecast_month"].iloc[0])
    K["forecast_tiers"] = fc["cashflow_risk_tier"].value_counts().to_dict()
    K["forecast_total_shortfall"] = float(fc["projected_shortfall"].sum())
    K["forecast_seasonal_factor"] = float(fc["seasonal_factor_used"].iloc[0])
    ssj = ss.merge(cust, on="customer_id")
    K["stress_by_occupation"] = ssj.groupby("occupation_type")["stress_score"].mean().round(1).to_dict()
    K["high_crit_share_by_occupation"] = ssj.groupby("occupation_type")["stress_band"].apply(
        lambda s: s.isin(["High", "Critical"]).mean()).round(3).to_dict()
    K["stress_by_loan"] = ssj.groupby("has_active_loan")["stress_score"].mean().round(1).to_dict()
    K["stress_by_tier"] = ssj.groupby("city_tier")["stress_score"].mean().round(1).to_dict()
    bor = tx[tx["income_expense"] == "Borrowing"]
    K["borrowing_events"] = int(len(bor))
    K["customers_who_borrowed"] = int(bor["customer_id"].nunique())
    K["borrowing_total"] = float(bor["amount"].sum())
    K["borrowing_source_share"] = bor["subcategory"].value_counts(normalize=True).round(3).to_dict()
    rep_cust = set(tx.loc[tx["category"] == "Debt Repayment", "customer_id"])
    rb = cm[cm["customer_id"].isin(rep_cust)].sort_values(["customer_id", "year_month"])
    first_b = rb[rb["borrowed_this_month"] == 1].groupby("customer_id")["year_month"].min()
    after = rb.merge(first_b.rename("first_b"), on="customer_id")
    after = after[after["year_month"] > after["first_b"]]
    repeat = after.groupby("customer_id")["borrowed_this_month"].max()
    K["repeat_borrow_rate_after_app_or_card"] = float(repeat.mean()) if len(repeat) else 0.0
    K["n_customers_app_or_card_borrowers"] = int(len(repeat))
    # lifestyle creep signal: expense growth with stable income
    creep = ss[(ss["expense_growth_6m"] > 0.10) & (ss["income_cv"] < 0.15)]
    K["creep_customers"] = int(len(creep))
    K["creep_customers_band"] = creep["stress_band"].value_counts().to_dict()
    K["low_buffer_customers"] = int((ss["buffer_months"] < 1).sum())
    K["buffer_median"] = float(ss["buffer_months"].median())
    hi = ss["stress_band"].isin(["High", "Critical"])
    K["high_crit_balance_share"] = float(ss.loc[hi, "current_balance"].sum() / ss["current_balance"].sum())
    K["high_crit_customer_share"] = float(hi.mean())

    (ROOT / "reports" / "key_metrics.json").write_text(json.dumps(K, indent=2, default=str))
    return K


if __name__ == "__main__":
    k = main()
    print(json.dumps(k, indent=1, default=str)[:6000])
