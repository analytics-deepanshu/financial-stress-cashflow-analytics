# Power BI Build Guide

This guide builds the 4-page dashboard from the CSVs in `data/powerbi/` in about 60–90 minutes. The `.pbix` file is not included: it is a binary file that only Power BI Desktop (Windows) can create. Every input you need is here.

**Before you start:** install Power BI Desktop (free, Microsoft Store) and run `python run_pipeline.py`, so that `data/powerbi/` is populated.

---

## Step 1 – Load the data (5 min)

1. Go to **Home → Get data → Text/CSV** and load each file from `data/powerbi/`:

| File | Role | Grain |
|---|---|---|
| `fact_transactions.csv` | Fact | 1 row per transaction (~41k) |
| `fact_customer_month.csv` | Fact | 1 row per customer per month (1,440) |
| `fact_stress_history.csv` | Fact | 1 row per customer per scoring month (840) |
| `dim_customer.csv` | Dimension | 1 row per customer, with current score and forecast |
| `dim_date.csv` | Dimension | 1 row per day, including Indian fiscal year and season |
| `dim_category.csv` | Dimension | category → spend type |
| `dim_merchant.csv` | Dimension | merchant → primary category, channel |
| `dim_stress_band.csv` | Lookup | band sort order and colour |
| `dim_risk_tier.csv` | Lookup | tier sort order and colour |
| `customer_stress_score.csv` | 1:1 detail | all 7 factor sub-scores and contributions |
| `cashflow_forecast.csv` | 1:1 detail | forecast components |

2. In Power Query (**Transform data**), check these types:
   - `dim_date[date]`, `fact_transactions[txn_date]`, and every `month_start` column → **Date**
   - amounts and balances → **Decimal number**
   - `fact_transactions[transaction_id]` → **Text**
3. Click **Close & Apply**.

## Step 2 – Model (10 min)

1. Go to **Model view** and create the relationships below. All are single direction, from dimension to fact.

| From (one side) | To (many side) |
|---|---|
| `dim_date[date]` | `fact_transactions[txn_date]` |
| `dim_date[date]` | `fact_customer_month[month_start]` |
| `dim_date[date]` | `fact_stress_history[month_start]` |
| `dim_customer[customer_id]` | `fact_transactions[customer_id]` |
| `dim_customer[customer_id]` | `fact_customer_month[customer_id]` |
| `dim_customer[customer_id]` | `fact_stress_history[customer_id]` |
| `dim_customer[customer_id]` | `customer_stress_score[customer_id]` (1:1) |
| `dim_customer[customer_id]` | `cashflow_forecast[customer_id]` (1:1) |
| `dim_category[category]` | `fact_transactions[category]` |
| `dim_merchant[merchant]` | `fact_transactions[merchant]` |
| `dim_stress_band[stress_band]` | `dim_customer[stress_band]` |
| `dim_risk_tier[cashflow_risk_tier]` | `dim_customer[cashflow_risk_tier]` |

2. Select `dim_date` and choose **Table tools → Mark as date table → `date`**.
3. Set these sort orders with **Column tools → Sort by column**:
   - `dim_date[month_label]` by `month_sort`
   - `dim_date[month_name]` by `month_num`
   - `dim_date[day_of_week]` by `day_of_week_num`
   - `dim_stress_band[stress_band]` by `band_sort`
   - `dim_risk_tier[cashflow_risk_tier]` by `tier_sort`
   - `dim_category[spend_type]` by `spend_type_sort`
4. Hide the foreign-key columns on the fact tables (right-click → Hide in report view). This keeps the Fields pane clean.
5. Load the theme: **View → Themes → Browse for themes →** `powerbi/finstress_theme.json`.

## Step 3 – Measures (15 min)

Create the `_Measures` table and paste every measure from `dax_measures.md`.

Format the measures as follows:
- Currency measures: Format → Currency → **₹ English (India)**, 0 decimals
- Ratios: **Percentage**, 1 decimal
- Scores: Decimal, 1 decimal

## Step 4 – Pages

Use a 1280 × 720 canvas, a 16 px outer margin, and 12 px gaps between visuals.

Every page has the same **header band** across the top (about 56 px):
- Title (left)
- Slicers (right): **Month range** (`dim_date[date]`, Between style), **Occupation** (`dim_customer[occupation_type]`, dropdown), **City tier** (dropdown), and **Stress band** (dropdown)

Sync the slicers across all pages with **View → Sync slicers**. Exclude the Stress band slicer from Page 4.

### Page 1 – Executive Overview

*Question answered: is the portfolio healthy, and is it getting better or worse?*

| Position | Visual | Fields |
|---|---|---|
| Row 1 (6 cards) | Card (new) | `Total Income`, `Total Expenses`, `Savings Rate`, `Latest Total Balance`, `Avg Stress Score`, `% High+Critical` (reference label: `High+Critical Customers`) |
| Row 2 left (2/3 width) | Line chart | X: `dim_date[month_label]`; Y: `Total Income`, `Total Expenses`. Add `Savings Rate` as a **separate small column chart below it**, not as a secondary axis. |
| Row 2 right (1/3) | Donut or 100% bar | Legend: `dim_category[spend_type]`; Values: `Total Expenses` |
| Row 3 left | Clustered bar | Axis: `dim_stress_band[stress_band]`; Value: `Customers`; Data colours via conditional formatting → `Stress Band Colour` |
| Row 3 right | Line chart | X: `dim_date[month_label]`; Y: `Avg Stress Score (History)` |

Add a text box with three bullet insights (copy them from `reports/insights_report.md`).

### Page 2 – Spending Intelligence

*Question answered: where does the money go, and what behaviour drives it?*

| Position | Visual | Fields |
|---|---|---|
| Top left | Bar chart (sorted desc) | Axis: `dim_category[category]`; Value: `Total Expenses`; Tooltip: `Category Rank`, `Avg Transaction Value` |
| Top right | Matrix heatmap | Rows: `category`; Columns: `dim_date[month_label]`; Values: `Total Expenses`, with background colour scale (white → blue) |
| Middle left | Bar chart | Axis: `dim_merchant[merchant]`, Top N filter = 10 by `Total Expenses`; Card beside it: `Top 5 Merchant Share` |
| Middle centre | Stacked column | X: `month_label`; Y: `Recurring Expenses` and (`Total Expenses` – recurring) as 2 measures; Card: `Recurring Share` |
| Middle right | 100% stacked bar | Axis: `fact_transactions[size_band]`; Legend: `payment_method`; Value: count of `transaction_id` |
| Bottom | Clustered bar | Axis: `category`; Values: `Weekday Spend per Day`, `Weekend Spend per Day`; Tooltip: `Weekend Uplift %` |

### Page 3 – Financial Risk

*Question answered: who is at risk, how much, and why?*

| Position | Visual | Fields |
|---|---|---|
| Row 1 cards | Card | `High+Critical Customers`, `At-Risk Next Month`, `Projected Shortfall`, `Customers <1 Month Buffer`, `Borrowing Customers` |
| Left | Column chart (histogram) | Use a 10-point bin of `dim_customer[stress_score]` (right-click → New group → Bin size 10); Value: `Customers` |
| Centre | Scatter | X: `fixed_obligation_ratio_6m`; Y: `savings_rate_6m`; Legend: `stress_band`; Size: `current balance`; Details: `customer_id`. Add a constant X line at 0.5 (Analytics pane). |
| Right | Decomposition tree | Analyse: `Customers`; Explain by: `stress_band` → `top_stress_driver` → `occupation_type` → `city_tier` |
| Bottom left | Line chart | X: `month_label`; Y: `Avg Month-End Balance`; Legend: `dim_customer[stress_band]` |
| Bottom right | Table (watch-list) | `customer_label`, `stress_score`, `stress_band`, `top_stress_driver`, `cashflow_risk_tier`, `deficit_probability`, `expected_ending_balance`. Filter: tier in High/Medium **or** band = Critical. Sort by `deficit_probability` desc. Conditional formatting: background on band and tier columns using the colour measures. |

**Drill-through.** On the watch-list table and the scatter, the user can right-click a customer → Drill through → **Customer Deep Dive**.

### Page 4 – Customer Deep Dive (drill-through target)

1. Add `dim_customer[customer_id]` to the **Drill-through** well, and keep "Keep all filters" on.
2. Also add a **dropdown slicer** on `dim_customer[customer_label]`, so the page works when opened directly.

| Position | Visual | Fields |
|---|---|---|
| Header | Text (measure-driven) | `Deep Dive Title` (use a card with the measure, or a button with a dynamic title) |
| Row 1 cards | Card | `Total Income`, `Total Expenses`, `Savings Rate`, `Latest Total Balance`, `Median Buffer Months` |
| Left | Gauge | Value: `Avg Stress Score`, min 0, max 100; target line at 60 |
| Left below | Bar chart | Factor contributions: from `customer_stress_score` drag the 7 `contrib_*` columns into Values (or unpivot them in Power Query into factor/points columns, which is the cleaner way). Sorted desc. |
| Centre | Line/column | X: `month_label`; Columns: `Total Income`, `Total Expenses`; separate line visual below: `Avg Month-End Balance` |
| Right | Donut | `dim_category[category]` by `Total Expenses` (Top 6, the rest grouped as Other) |
| Bottom | Multi-row card | `Top Driver Text`, `Forecast Text`, `Risk Flags` (label it "Red flags (of 5)") |
| Bottom right | Table | Last 15 transactions: `txn_datetime`, `merchant`, `category`, `amount`, `account_balance` |

Add a **Back** button (Insert → Buttons → Back) in the top-left corner.

## Step 5 – Finishing (10 min)

- Rename every visual title in plain English, for example "Income vs expenses by month" rather than "Sum of amount by month".
- **View → Selection pane**: set the tab order so keyboard users move left to right.
- Turn off **Edit interactions** on the cards that should ignore cross-filtering, such as the overall KPI cards on Page 3.
- Add **alt text** to every chart (Format → General → Alt text).
- Use **File → Export → Export to PDF** to make screenshots for `docs/screenshots/`.

## Design rules used

- One y-axis per chart. Never use dual axes; savings rate gets its own small chart.
- Status colours (green, amber, orange, red) are reserved for stress bands and risk tiers, and always appear with the band name. They are never used for ordinary data series.
- Categorical series follow a fixed colour order taken from the theme file: blue, orange, aqua, yellow, then magenta.
- Gridlines are light and recessive. Data labels go only on the bars that matter, not on every point.
