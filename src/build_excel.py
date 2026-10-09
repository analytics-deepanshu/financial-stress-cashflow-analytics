"""
Builds excel/management_summary.xlsx: a formula-driven summary for non-technical managers.
Data sheets hold values exported from the pipeline; every KPI and summary cell is an Excel
formula, so the workbook recalculates if the data sheets are edited.

Run:  python src/build_excel.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
AN, PROC = ROOT / "data" / "analytics", ROOT / "data" / "processed"
OUT = ROOT / "excel" / "management_summary.xlsx"

FONT = "Arial"
HDR_FILL = PatternFill("solid", fgColor="1F3A5F")
SUB_FILL = PatternFill("solid", fgColor="EEF3F9")
THIN = Side(style="thin", color="D9D9D9")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
INR = '₹#,##0;(₹#,##0);"-"'
PCT = '0.0%;(0.0%);"-"'
BAND_FILL = {"Low": "D8F0D8", "Moderate": "FDEFC8", "High": "FAD9CB", "Critical": "F3C6C6"}


def style_header(ws, row: int, ncols: int, start_col: int = 1) -> None:
    for c in range(start_col, start_col + ncols):
        cell = ws.cell(row=row, column=c)
        cell.font = Font(name=FONT, bold=True, color="FFFFFF")
        cell.fill = HDR_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BOX


def write_table(ws, df: pd.DataFrame, start_row: int = 1, formats: dict | None = None) -> None:
    formats = formats or {}
    for j, col in enumerate(df.columns, start=1):
        ws.cell(row=start_row, column=j, value=col)
    style_header(ws, start_row, len(df.columns))
    for i, row in enumerate(df.itertuples(index=False), start=start_row + 1):
        for j, v in enumerate(row, start=1):
            cell = ws.cell(row=i, column=j, value=None if pd.isna(v) else v)
            cell.font = Font(name=FONT)
            cell.border = BOX
            fmt = formats.get(df.columns[j - 1])
            if fmt:
                cell.number_format = fmt


def autosize(ws, widths: dict | None = None, default: int = 14) -> None:
    for col in range(1, ws.max_column + 1):
        letter = get_column_letter(col)
        ws.column_dimensions[letter].width = (widths or {}).get(letter, default)


def main() -> None:
    cm = pd.read_csv(AN / "customer_month.csv")
    ss = pd.read_csv(AN / "customer_stress_score.csv")
    fc = pd.read_csv(AN / "cashflow_forecast.csv")
    cust = pd.read_csv(PROC / "customers_clean.csv")
    tx = pd.read_csv(PROC / "transactions_clean.csv")

    wb = Workbook()

    # ------------------------------------------------------------------ Read Me
    ws = wb.active
    ws.title = "Read Me"
    lines = [
        ("Financial Stress & Cash-Flow Risk: Management Summary", True, 14),
        ("Data: synthetic transactions for 120 customers, Oct 2024 to Sep 2025 (see project README).", False, 10),
        ("", False, 10),
        ("Sheet guide", True, 11),
        ("KPI Summary: headline numbers (all formulas, linked to the data sheets).", False, 10),
        ("Monthly Trend: portfolio income, expenses and savings rate by month, with charts.", False, 10),
        ("Category Spend: 12-month spend by category with share and rank.", False, 10),
        ("Band Summary: customers per stress band and per occupation (COUNTIFS / AVERAGEIFS).", False, 10),
        ("Customers: one row per customer with score, drivers and next-month forecast (filterable).", False, 10),
        ("Watch List: customers to contact first, sorted by deficit probability.", False, 10),
        ("", False, 10),
        ("Definitions", True, 11),
        ("Income = salary, freelance, family support, stipend and interest credits. Borrowed money is not income.", False, 10),
        ("Expenses = consumption + rent + EMIs + insurance + debt repayment. SIP investments are savings, not expenses.", False, 10),
        ("Savings rate = (income - expenses) / income.", False, 10),
        ("Fixed obligation ratio = (rent + EMI + insurance + debt repayment) / income, last 6 months.", False, 10),
        ("Buffer months = current balance / average monthly essential spend.", False, 10),
        ("Stress score 0-100: Low 0-30, Moderate 31-60, High 61-80, Critical 81-100. Method: docs/stress_score_methodology.md", False, 10),
        ("Forecast tier: High if P(month-end balance < 0) >= 50%, Medium 20-50%, Low < 20%.", False, 10),
        ("", False, 10),
        ("Colour key: blue text = input data values; black text = formulas.", False, 10),
    ]
    for i, (t, bold, size) in enumerate(lines, start=1):
        ws.cell(row=i, column=1, value=t).font = Font(name=FONT, bold=bold, size=size)
    ws.column_dimensions["A"].width = 120

    # ------------------------------------------------------------------ Monthly Trend
    mt = cm.groupby("year_month")[["income", "expenses", "investment", "borrowing"]].sum().reset_index()
    mt.columns = ["Month", "Income (₹)", "Expenses (₹)", "Invested (₹)", "Borrowed (₹)"]
    wsM = wb.create_sheet("Monthly Trend")
    write_table(wsM, mt, formats={c: INR for c in mt.columns[1:]})
    n = len(mt)
    for c in range(1, 6):
        for r in range(2, n + 2):
            wsM.cell(row=r, column=c).font = Font(name=FONT, color="0000FF")
    extra = ["Net cash flow (₹)", "Savings rate", "Expense MoM change"]
    for j, h in enumerate(extra, start=6):
        wsM.cell(row=1, column=j, value=h)
    style_header(wsM, 1, 8)
    for r in range(2, n + 2):
        wsM[f"F{r}"] = f"=B{r}-C{r}"
        wsM[f"G{r}"] = f"=IFERROR(F{r}/B{r},0)"
        wsM[f"H{r}"] = "" if r == 2 else f"=IFERROR(C{r}/C{r - 1}-1,0)"
        for col, fmt in (("F", INR), ("G", PCT), ("H", PCT)):
            wsM[f"{col}{r}"].number_format = fmt
            wsM[f"{col}{r}"].font = Font(name=FONT)
            wsM[f"{col}{r}"].border = BOX
    tot = n + 2
    wsM[f"A{tot}"] = "Total / overall"
    for col in "BCDEF":
        wsM[f"{col}{tot}"] = f"=SUM({col}2:{col}{n + 1})"
        wsM[f"{col}{tot}"].number_format = INR
    wsM[f"G{tot}"] = f"=IFERROR(F{tot}/B{tot},0)"
    wsM[f"G{tot}"].number_format = PCT
    for col in "ABCDEFG":
        wsM[f"{col}{tot}"].font = Font(name=FONT, bold=True)
        wsM[f"{col}{tot}"].fill = SUB_FILL
    autosize(wsM, {"A": 12}, 18)
    wsM.freeze_panes = "B2"

    lc = LineChart()
    lc.title = "Monthly income vs expenses"
    lc.y_axis.title = "₹"
    lc.y_axis.numFmt = '₹#,##0,,"M"'
    lc.add_data(Reference(wsM, min_col=2, max_col=3, min_row=1, max_row=n + 1), titles_from_data=True)
    lc.set_categories(Reference(wsM, min_col=1, min_row=2, max_row=n + 1))
    lc.height, lc.width = 8, 18
    for s, col in zip(lc.series, ("2A78D6", "EB6834")):
        s.graphicalProperties.line.solidFill = col
        s.graphicalProperties.line.width = 22000
        s.smooth = False
    wsM.add_chart(lc, "J2")
    bc = BarChart()
    bc.title = "Portfolio savings rate by month"
    bc.add_data(Reference(wsM, min_col=7, min_row=1, max_row=n + 1), titles_from_data=True)
    bc.set_categories(Reference(wsM, min_col=1, min_row=2, max_row=n + 1))
    bc.y_axis.numFmt = "0%"
    bc.legend = None
    bc.height, bc.width = 7, 18
    bc.series[0].graphicalProperties.solidFill = "1BAF7A"
    wsM.add_chart(bc, "J19")

    # ------------------------------------------------------------------ Category Spend
    exp = tx[tx["income_expense"] == "Expense"]
    cs = exp.groupby(["category", "spend_type"])["amount"].sum().reset_index().sort_values("amount", ascending=False)
    cs.columns = ["Category", "Spend type", "12-month spend (₹)"]
    wsC = wb.create_sheet("Category Spend")
    write_table(wsC, cs, formats={"12-month spend (₹)": INR})
    k = len(cs)
    for r in range(2, k + 2):
        wsC[f"C{r}"].font = Font(name=FONT, color="0000FF")
    wsC["D1"], wsC["E1"] = "Share of spend", "Rank"
    style_header(wsC, 1, 5)
    for r in range(2, k + 2):
        wsC[f"D{r}"] = f"=C{r}/SUM($C$2:$C${k + 1})"
        wsC[f"D{r}"].number_format = PCT
        wsC[f"E{r}"] = f"=RANK(C{r},$C$2:$C${k + 1})"
        for col in "DE":
            wsC[f"{col}{r}"].font = Font(name=FONT)
            wsC[f"{col}{r}"].border = BOX
    wsC[f"A{k + 2}"] = "Total"
    wsC[f"C{k + 2}"] = f"=SUM(C2:C{k + 1})"
    wsC[f"C{k + 2}"].number_format = INR
    wsC[f"D{k + 2}"] = f"=SUM(D2:D{k + 1})"
    wsC[f"D{k + 2}"].number_format = PCT
    for col in "ABCD":
        wsC[f"{col}{k + 2}"].font = Font(name=FONT, bold=True)
        wsC[f"{col}{k + 2}"].fill = SUB_FILL
    wsC.conditional_formatting.add(f"D2:D{k + 1}", ColorScaleRule(start_type="min", start_color="FFFFFF",
                                                                  end_type="max", end_color="6DA7EC"))
    autosize(wsC, {"A": 20, "B": 20, "C": 20})

    # ------------------------------------------------------------------ Customers
    cdf = (cust[["customer_id", "occupation_type", "city", "city_tier", "declared_monthly_income", "has_active_loan"]]
           .merge(ss[["customer_id", "stress_score", "stress_band", "top_stress_driver", "savings_rate_6m",
                      "fixed_obligation_ratio_6m", "buffer_months", "income_cv", "current_balance"]], on="customer_id")
           .merge(fc[["customer_id", "expected_ending_balance", "deficit_probability", "cashflow_risk_tier"]],
                  on="customer_id"))
    cdf["top_stress_driver"] = cdf["top_stress_driver"].str.replace("_", " ").str.capitalize()
    cdf = cdf.sort_values("stress_score", ascending=False)
    cdf.columns = ["Customer", "Occupation", "City", "City tier", "Monthly income (₹)", "Active loan",
                   "Stress score", "Stress band", "Top driver", "Savings rate (6m)", "Obligation ratio (6m)",
                   "Buffer (months)", "Income CV", "Current balance (₹)", "Expected end balance (₹)",
                   "P(deficit)", "Forecast tier"]
    wsK = wb.create_sheet("Customers")
    fm = {"Monthly income (₹)": INR, "Current balance (₹)": INR, "Expected end balance (₹)": INR,
          "Savings rate (6m)": PCT, "Obligation ratio (6m)": PCT, "P(deficit)": PCT, "Buffer (months)": "0.0",
          "Income CV": "0.00", "Stress score": "0.0"}
    write_table(wsK, cdf, formats=fm)
    nc = len(cdf)
    for r in range(2, nc + 2):
        for c in range(1, 18):
            wsK.cell(row=r, column=c).font = Font(name=FONT, color="0000FF")
    for b, col in BAND_FILL.items():
        wsK.conditional_formatting.add(f"H2:H{nc + 1}", CellIsRule(operator="equal", formula=[f'"{b}"'],
                                                                   fill=PatternFill("solid", fgColor=col)))
    wsK.auto_filter.ref = f"A1:Q{nc + 1}"
    wsK.freeze_panes = "B2"
    autosize(wsK, {"A": 11, "C": 13, "I": 20}, 14)

    # ------------------------------------------------------------------ Band Summary
    wsB = wb.create_sheet("Band Summary")
    hdr = ["Stress band", "Customers", "% of customers", "Avg score", "Avg savings rate", "Avg buffer (months)",
           "Avg obligation ratio", "Forecast High/Medium"]
    for j, h in enumerate(hdr, start=1):
        wsB.cell(row=1, column=j, value=h)
    style_header(wsB, 1, len(hdr))
    rng = lambda col: f"Customers!${col}$2:${col}${nc + 1}"
    for i, b in enumerate(["Low", "Moderate", "High", "Critical"], start=2):
        wsB[f"A{i}"] = b
        wsB[f"A{i}"].fill = PatternFill("solid", fgColor=BAND_FILL[b])
        wsB[f"B{i}"] = f"=COUNTIF({rng('H')},A{i})"
        wsB[f"C{i}"] = f"=IFERROR(B{i}/$B$6,0)"
        wsB[f"D{i}"] = f"=IFERROR(AVERAGEIF({rng('H')},A{i},{rng('G')}),0)"
        wsB[f"E{i}"] = f"=IFERROR(AVERAGEIF({rng('H')},A{i},{rng('J')}),0)"
        wsB[f"F{i}"] = f"=IFERROR(AVERAGEIF({rng('H')},A{i},{rng('L')}),0)"
        wsB[f"G{i}"] = f"=IFERROR(AVERAGEIF({rng('H')},A{i},{rng('K')}),0)"
        wsB[f"H{i}"] = (f"=COUNTIFS({rng('H')},A{i},{rng('Q')},\"High\")"
                        f"+COUNTIFS({rng('H')},A{i},{rng('Q')},\"Medium\")")
    wsB["A6"] = "Total"
    wsB["B6"] = "=SUM(B2:B5)"
    wsB["C6"] = "=SUM(C2:C5)"
    wsB["D6"] = f"=AVERAGE({rng('G')})"
    wsB["H6"] = "=SUM(H2:H5)"
    for r in range(2, 7):
        for col, fmt in zip("BCDEFGH", ["0", PCT, "0.0", PCT, "0.0", PCT, "0"]):
            wsB[f"{col}{r}"].number_format = fmt
            wsB[f"{col}{r}"].font = Font(name=FONT, bold=(r == 6))
            wsB[f"{col}{r}"].border = BOX
        wsB[f"A{r}"].font = Font(name=FONT, bold=True)
        wsB[f"A{r}"].border = BOX
    # occupation x band
    wsB["A9"] = "Customers by occupation and stress band"
    wsB["A9"].font = Font(name=FONT, bold=True, size=11)
    hdr2 = ["Occupation", "Low", "Moderate", "High", "Critical", "Total", "% High+Critical"]
    for j, h in enumerate(hdr2, start=1):
        wsB.cell(row=10, column=j, value=h)
    style_header(wsB, 10, len(hdr2))
    for i, occ in enumerate(["Salaried", "Freelancer/Gig", "Student"], start=11):
        wsB[f"A{i}"] = occ
        for j, b in enumerate(["Low", "Moderate", "High", "Critical"]):
            col = "BCDE"[j]
            wsB[f"{col}{i}"] = f"=COUNTIFS({rng('B')},$A{i},{rng('H')},{col}$10)"
        wsB[f"F{i}"] = f"=SUM(B{i}:E{i})"
        wsB[f"G{i}"] = f"=IFERROR((D{i}+E{i})/F{i},0)"
        wsB[f"G{i}"].number_format = PCT
        for col in "ABCDEFG":
            wsB[f"{col}{i}"].font = Font(name=FONT)
            wsB[f"{col}{i}"].border = BOX
    autosize(wsB, {"A": 18}, 16)
    bcb = BarChart()
    bcb.title = "Customers per stress band"
    bcb.add_data(Reference(wsB, min_col=2, min_row=1, max_row=5), titles_from_data=True)
    bcb.set_categories(Reference(wsB, min_col=1, min_row=2, max_row=5))
    bcb.legend = None
    bcb.height, bcb.width = 7, 12
    bcb.series[0].graphicalProperties.solidFill = "2A78D6"
    wsB.add_chart(bcb, "J2")

    # ------------------------------------------------------------------ Watch List
    wl = cdf[(cdf["Forecast tier"].isin(["High", "Medium"])) | (cdf["Stress band"] == "Critical")].copy()
    wl = wl.sort_values(["P(deficit)", "Stress score"], ascending=False)
    wl = wl[["Customer", "Occupation", "City", "Stress score", "Stress band", "Top driver", "Current balance (₹)",
             "Expected end balance (₹)", "P(deficit)", "Forecast tier"]]
    wl["Suggested action"] = wl.apply(lambda r: "Contact this week: payment-date realignment / short-term relief"
                                      if r["Forecast tier"] == "High" else
                                      ("Spending alert + budget plan" if r["Stress band"] in ("High", "Critical")
                                       else "Low-balance alert"), axis=1)
    wsW = wb.create_sheet("Watch List")
    write_table(wsW, wl, formats={"Current balance (₹)": INR, "Expected end balance (₹)": INR,
                                  "P(deficit)": PCT, "Stress score": "0.0"})
    autosize(wsW, {"A": 11, "F": 20, "K": 58}, 15)
    wsW.freeze_panes = "B2"

    # ------------------------------------------------------------------ KPI Summary (first tab after Read Me)
    wsS = wb.create_sheet("KPI Summary", 1)
    wsS["A1"] = "Headline KPIs (12 months, Oct 2024 to Sep 2025)"
    wsS["A1"].font = Font(name=FONT, bold=True, size=14)
    t = n + 2
    kpis = [
        ("Total income", f"='Monthly Trend'!B{t}", INR),
        ("Total expenses", f"='Monthly Trend'!C{t}", INR),
        ("Net cash flow (income - expenses)", f"='Monthly Trend'!F{t}", INR),
        ("Portfolio savings rate", f"='Monthly Trend'!G{t}", PCT),
        ("Total invested (SIPs)", f"='Monthly Trend'!D{t}", INR),
        ("Total borrowed (cards, loan apps, family)", f"='Monthly Trend'!E{t}", INR),
        ("Customers", f"=COUNTA({rng('A')})", "0"),
        ("Average stress score", f"=AVERAGE({rng('G')})", "0.0"),
        ("Customers in High or Critical stress", "=COUNTIF(Customers!$H:$H,\"High\")+COUNTIF(Customers!$H:$H,\"Critical\")", "0"),
        ("...as % of customers", "=IFERROR(B11/B9,0)", PCT),
        ("Customers with < 1 month buffer", f"=COUNTIF({rng('L')},\"<1\")", "0"),
        ("Customers flagged High/Medium for next month", "=COUNTIF(Customers!$Q:$Q,\"High\")+COUNTIF(Customers!$Q:$Q,\"Medium\")", "0"),
        ("Median savings rate (6m)", f"=MEDIAN({rng('J')})", PCT),
        ("Lowest-saving month", f"=INDEX('Monthly Trend'!A2:A{n + 1},MATCH(MIN('Monthly Trend'!G2:G{n + 1}),'Monthly Trend'!G2:G{n + 1},0))", "@"),
        ("Highest-saving month", f"=INDEX('Monthly Trend'!A2:A{n + 1},MATCH(MAX('Monthly Trend'!G2:G{n + 1}),'Monthly Trend'!G2:G{n + 1},0))", "@"),
    ]
    wsS["A2"], wsS["B2"] = "KPI", "Value"
    style_header(wsS, 2, 2)
    for i, (label, f, fmt) in enumerate(kpis, start=3):
        wsS[f"A{i}"] = label
        wsS[f"B{i}"] = f
        wsS[f"B{i}"].number_format = fmt
        wsS[f"A{i}"].font = Font(name=FONT)
        wsS[f"B{i}"].font = Font(name=FONT, color="008000")
        wsS[f"B{i}"].alignment = Alignment(horizontal="right")
        for col in "AB":
            wsS[f"{col}{i}"].border = BOX
    wsS["A19"] = "Green values link to other sheets; edit the data sheets and these update automatically."
    wsS["A19"].font = Font(name=FONT, italic=True, color="52514E", size=9)
    wsS.column_dimensions["A"].width = 46
    wsS.column_dimensions["B"].width = 20

    wb.calculation.fullCalcOnLoad = True   # Excel computes every formula when the file is opened
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
