# Financial Stress & Cash-Flow Risk Analytics – Project Documentation

*An end-to-end data analytics case study: Python · Pandas · NumPy · PostgreSQL · Power BI · Excel*

---

## 1. Project overview

This project analyses 12 months of bank-account transactions for 120 retail customers. It answers three questions a bank or fintech asks every month:

1. **How healthy are our customers' finances, and what drives the difference?**
2. **Who is financially stressed right now, and why?** This is answered with a transparent 0–100 Financial Stress Score.
3. **Who is likely to run short of cash next month?** This is answered with a backtested cash-flow forecast.

The output is a cleaned and validated dataset, 20 SQL analyses, a stress score and forecast that have both been validated, a 4-page Power BI dashboard specification, an Excel management summary, and 11 management insights with recommendations.

## 2. Business problem

Retail banks and lending apps see financial distress **after** it happens: a bounced EMI, a missed card payment, a loan-app default. By that point the customer has usually already borrowed at high cost, and the relationship is damaged.

The signals appear **months earlier** in ordinary transaction data: shrinking savings, rising fixed commitments, thinning balances and small emergency borrowings. Most institutions lack a simple, explainable way to turn those signals into a prioritised action list.

**Who would use this:** a retail bank's customer-analytics team, a collections-prevention team, or a personal-finance app's "financial health" feature.

## 3. Objectives

| # | Objective | Deliverable |
|---|---|---|
| 1 | Build a realistic, internally consistent transaction dataset | Persona-based generator, 41k transactions, running balances that reconcile |
| 2 | Clean and validate it in a measurable way | Cleaning pipeline + scorecard of detected vs injected issues |
| 3 | Describe spending, saving and income behaviour | EDA (12 figures) + 20 SQL queries |
| 4 | Quantify financial stress per customer | 7-factor, benchmark-anchored Stress Score |
| 5 | Predict next-month cash shortfalls | Forecast with a 6-month backtest |
| 6 | Communicate to management | Power BI design, Excel summary, insights report |

## 4. Dataset description

No public dataset combines multiple customers, categorised transactions and a **consistent running balance**, so the data was simulated (`src/generate_data.py`, seed 42).

- **Scale:** 120 customers × 12 months (Oct 2024 – Sep 2025), giving **41,711 raw / 41,135 clean** transactions.
- **Fields:** the 15 requested fields (transaction id, customer, date, type, category, subcategory, merchant, amount, payment method, income/expense, balance, recurring flag, location, income, financial goal). Cleaning adds derived fields. See `data/data_dictionary.md`.
- **Indian context:** INR amounts, 22 cities across Tier 1/2/3, and UPI, NACH auto-debit, NEFT and IMPS payment rails. Seasonality covers Diwali, school fees in April and June, summer electricity bills, and holiday travel. Mutual-fund SIPs, and borrowing from instant-loan apps, card cash advances and family, are also modelled.
- **Hidden personas:** each customer is one of 7 personas (Stable Saver, Comfortable Spender, EMI-Burdened, Irregular Earner, Lifestyle Creep, Shock Event, Student). Personas drive behaviour but are **never used by the analysis**. They exist only to validate the stress score afterwards.
- **Consistency guarantee:** transactions are posted in time order with a running balance. When a payment would overdraw the account, the customer borrows, and repays over the next three months. Every balance therefore reconciles exactly.
- **Realistic dirt:** 7,551 data-quality issues of 13 types were injected into the raw file and logged separately.

## 5. Data cleaning process

`src/clean_data.py` → `reports/data_quality_report.md`

| Step | Problem | Method |
|---|---|---|
| 1 | Exact duplicates (411) | `drop_duplicates` |
| 2 | Amounts stored as text "₹1,250.00" (411), negative amounts (206) | Strip symbols, convert to numeric, take absolute value |
| 3 | 4 date formats (1,234) and year typos 2052 → 2025 (82) | Explicit format list; fix the year only when swapping its digits gives a valid year |
| 4 | Category / payment / merchant spelling variants (≈3,700) | Normalise keys (case, `_`, `and` → `&`), map to the canonical list or the most common spelling |
| 5 | Same transaction re-posted with a new ID (165) | Duplicate on customer + time + amount + merchant + balance |
| 6 | Missing category / merchant / payment method (411 each) | Impute **only from reliable relationships**: subcategory → category; a customer's single habitual merchant or recurring payee; the customer's usual payment method. Otherwise `Unknown Merchant`. |
| 7 | Amounts recorded in paise (123) | **Balance reconciliation:** the implied amount (Δbalance) is compared with the recorded amount, and ×100 mismatches are corrected |
| 8 | Consistency | Credit/Debit vs Income/Expense, customer master, income field: zero violations |
| 9 | Outliers | Robust z-score (median/MAD on log amount, per subcategory), plus one-off debits above monthly income. **Flagged, not removed.** |

**Result:** every injected issue type was detected (99.4–100%), with **zero balance-chain breaks** after cleaning. The 123 paise errors alone would have overstated total spending by 27%.

## 6. Exploratory data analysis

`src/eda.py` → `reports/figures/`, `notebooks/03_eda.ipynb`

| Topic | Headline |
|---|---|
| Monthly income vs expenses | ₹13.2 Cr income, ₹10.7 Cr expenses, **19.0%** portfolio savings rate. The lowest month is Dec (12.4%) and the best is Feb (27.3%). |
| Spending by category | Groceries 22%, Rent 15%, Loan EMI 12%. Fixed obligations are 29% of spend, essential variable 42%, discretionary 29%. |
| Trends & seasonality | Oct–Nov spend is +13% (shopping +59%). Travel peaks in May and Dec. School fees spike April and June. |
| Recurring expenses | 38% of expenses recur monthly. 15% of customers have fixed obligations above 50% of income. |
| Income stability | Median income CV: salaried 0.10, gig 0.47 |
| Savings | Median savings rate: salaried 15%, gig 5.6%, students −16%. 23% of customers have negative 12-month savings. |
| Average transaction value | Median expense ₹1,397, mean ₹2,800 (right-skewed by rent, EMI, travel) |
| Weekend vs weekday | +47% spend per day at weekends. Weekends carry 40% of discretionary spend. |
| Payment methods | UPI is 61% of debits. Large payments move to NACH auto-debit and bank transfer. |
| Merchant concentration | The top 5 merchants hold 22% of variable spend. The median customer's top 3 merchants hold 25% of their spend. Spend is fragmented. |

## 7. SQL analysis

`sql/` → `docs/sql_analysis.md`

There are 20 PostgreSQL queries, each tied to a business question. They cover aggregations, CASE, CTEs, subqueries, window functions (LAG, running totals, moving averages with frames, RANK, ROW_NUMBER, NTILE), gaps-and-islands, pivots and HAVING. A SQL view (`vw_customer_month`) rebuilds the monthly customer table directly from transactions, so the SQL layer does not depend on Python outputs for its core metrics. All queries were run against PostgreSQL 16, and their outputs are saved in `sql/results/`.

## 8. Financial Stress Score methodology

`src/stress_score.py` → `docs/stress_score_methodology.md`

There are seven factors. Each is scaled from 0 to 100 against an **external benchmark** (not percentiles) and weighted 60% structural / 40% dynamic:

| Factor | Healthy (0) | Max stress (100) | Weight |
|---|---|---|---|
| Savings margin | ≥ 20% | ≤ −10% | 20 |
| Fixed obligation ratio | ≤ 30% | ≥ 60% | 20 |
| Emergency buffer | ≥ 6 months | ≤ 0.5 month | 20 |
| Income instability (CV) | ≤ 0.10 | ≥ 0.60 | 10 |
| Expense growth (de-seasonalised) | ≤ 0% | ≥ +25% / 6m | 10 |
| Balance trend | ≥ +0.5 months of income | ≤ −1.0 | 10 |
| Deficit & borrowing frequency | none | half of months / 2 borrowing months | 10 |

The score bands are Low 0–30, Moderate 31–60, High 61–80 and Critical 81–100.

**Current distribution:** 72 Low · 35 Moderate · 12 High · 1 Critical.

**Validation:**
- High and Critical customers borrowed the next month **16.7% / 75%** of the time, against **0%** for Low (AUC 0.93).
- The score separates the hidden at-risk personas with AUC 0.94.
- 92% of customers keep the same band under equal weights.

## 9. Power BI dashboard explanation

`powerbi/POWERBI_BUILD_GUIDE.md`, `powerbi/dax_measures.md`, `powerbi/finstress_theme.json`, `data/powerbi/`

The data model is a star schema: 3 facts, 5 dimensions, and 2 one-to-one detail tables. There are 52 DAX measures. Slicers for month range, occupation, city tier and stress band are synced across pages.

| Page | Purpose | Key visuals |
|---|---|---|
| 1. Executive Overview | Is the portfolio healthy? | KPI cards, income vs expense trend, savings-rate columns, spend-type split, stress-band bar, stress trend |
| 2. Spending Intelligence | Where does money go and why? | Category ranking, category × month heatmap, top merchants, recurring vs variable, payment method by ticket size, weekend vs weekday |
| 3. Financial Risk | Who is at risk and why? | Risk KPI cards, score histogram, obligations-vs-savings scatter, decomposition tree of drivers, balance trend by band, watch-list table |
| 4. Customer Deep Dive | One customer, explained | Drill-through target: profile, score gauge, factor contributions, income/expense/balance trend, category mix, forecast text, red-flag count, latest transactions |

## 10. Key insights

The full set is in `reports/insights_report.md`. The top five:

1. **Students and gig workers are in deficit in 78% and 57% of months**, against 18% for salaried customers. They are 20% of customers but 55% of borrowers.
2. **Fixed obligations above 50% of income** (15% of customers) means an average stress score of 54 against 20, and none of them scored Low.
3. **30% of customers have less than 3 months of buffer.** Their median buffer in the High band is 0.8 months.
4. **Diwali overspend turns into borrowing in Dec–Jan**: 33% of all borrowing months fall in those 2 months.
5. **16 of 17 customers (94%) who used a loan app or card cash advance borrowed again.** The first borrowing event is the trigger to act on.

## 11. Business recommendations

1. A weekly **next-month watch-list** (9 customers for Oct 2025), with **EMI / auto-debit date realignment** to after salary day.
2. **Contact customers within 7 days of their first high-cost borrowing**, offering a lower-cost alternative.
3. A **fixed-obligation ratio ≤ 50% guardrail** in every credit decision, and restructuring offers for the 18 customers above it.
4. **Automated buffer-building** (3-month target) for the 36 customers below it.
5. A **pre-festive budgeting campaign** every September.
6. **Spending-trend alerts** for lifestyle creep before it shows in balances.
7. **Balance reconciliation** as a mandatory pipeline check.

## 12. Limitations

- **The data is synthetic.** Results show that the methods work as designed on realistic behaviour; they are not evidence about real customers.
- **One account per customer.** Other accounts, cards and investments are invisible, so buffers may be understated.
- **12 months of history.** Each calendar month appears only once, so the seasonal index is approximate, and the 25% forecast cushion was tuned on the evaluation window.
- **Score weights come from guidelines, not from fitting to outcomes.** They should be re-estimated against real delinquency data.
- **Shocks** (medical, job loss) cannot be forecast from history. This is most of the forecast's remaining misses.
- **Normal approximation** for forecast uncertainty understates tail risk.

## 13. Future improvements

1. **Outcome-based calibration:** fit factor weights with logistic regression on 30/60/90-day delinquency, keeping the benchmarks as monotonic constraints.
2. **Day-level cash-flow simulation:** model the salary date against EMI and rent dates to predict the *day* the balance runs out.
3. **Machine-learning forecast:** gradient boosting with customer features, compared against this baseline.
4. **Survival analysis:** time-to-first-borrowing for Moderate customers.
5. **Real data:** open-banking (Account Aggregator) feeds, or a bank's anonymised sample.
6. **Automation:** schedule the pipeline monthly, publish to Power BI Service with row-level security per relationship manager, and send email alerts for new High-tier customers.
7. **A/B testing of interventions:** measure whether date realignment or nudges actually reduce borrowing.
