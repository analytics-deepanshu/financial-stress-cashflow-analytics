# SQL Analysis (PostgreSQL)

**Files**

| File | What it does |
|---|---|
| `sql/01_schema.sql` | Tables, keys and constraints |
| `sql/02_load_data.sql` | `\copy` loads |
| `sql/03_views.sql` | `vw_customer_month`, built in SQL from raw transactions, and `vw_powerbi_customer_360` |
| `sql/04_analysis_queries.sql` | The 20 queries |
| `sql/results/Qnn_*.csv` | The output of every query |

**Run:** `createdb finstress` once, then `python src/run_sql.py`. Alternatively, run the four files in order with `psql -d finstress -f …` from the project root.

## Technique coverage

| Technique | Queries |
|---|---|
| Aggregation, GROUP BY | all |
| CASE (banding, pivots, conditional sums) | Q01, Q03, Q07, Q09, Q12, Q14, Q15, Q16, Q17, Q18, Q20 |
| CTEs (incl. multi-step) | Q03, Q04, Q05, Q06, Q08, Q09, Q10, Q11, Q12, Q13, Q15, Q16, Q18, Q19 |
| Subqueries (scalar, correlated, derived tables) | Q02, Q04, Q07, Q10, Q12, Q14, Q18 |
| Window: LAG | Q04, Q05, Q11 |
| Window: running total `SUM() OVER (ORDER BY …)` | Q05 |
| Window: moving average with a `ROWS BETWEEN` frame | Q10 |
| Window: RANK / ROW_NUMBER / NTILE | Q06, Q11 (gaps-and-islands), Q13, Q15 |
| Window shares `SUM(SUM(x)) OVER ()` | Q07, Q09, Q13 |
| HAVING | Q16, Q17 |
| DISTINCT ON, generate_series, STDDEV_POP, string_agg | Q18 / view, Q08, Q15, Q10 |

## Queries and findings

| # | Business question | Key result | So what |
|---|---|---|---|
| Q01 | Monthly income, spend, investment, borrowing and savings rate | Savings rate ranges from **12% (Dec)** to **27% (Feb)**. Borrowing peaks in Dec–Jan. | Seasonality is large enough that month-on-month comparisons must be like-for-like. |
| Q02 | Top spending categories and their share | Groceries 22%, Rent 15%, Loan EMI 12% | Over a quarter of spend is fixed obligations, which cannot be cut quickly. |
| Q03 | Savings-rate bands by occupation | **All 6 students** and **44% of gig workers** have negative 12-month savings, against 15% of salaried customers. | Occupation is a first-cut risk segment. |
| Q04 | Biggest month-over-month spend jumps (latest month) | Top jumps of +8% to +27% in Sep 2025 | Feeds the "unusual activity" alert list. |
| Q05 | Running total of portfolio net savings | ₹2.5 crore cumulative over 12 months. December and Apr–Jun add the least. | Shows where in the year the portfolio stops building reserves. |
| Q06 | Top / bottom 3 savers per city tier | Best savers save 37–48%. The worst are at −8% to −26%, mostly students and gig workers plus a few over-committed salaried customers. | A fair peer comparison within the same cost-of-living tier. |
| Q07 | Transaction size bands | 63% of transactions are under ₹2,000 but carry only 20% of value. Large tickets (≥ ₹10K) are 4% of count and 34% of value. | Many small payments plus a few large ones: monitor value, not count. |
| Q08 | Weekend vs weekday spend per day | Travel and gifts double at weekends. Food delivery +73%, shopping +66%. | Weekend nudges matter most (Insight 9). |
| Q09 | Fixed-obligation (FOIR-style) bands | **15%** of customers are over 50%, with an average stress score of 54 against 20 below 30%. | A credit-decision guardrail (Insight 2). |
| Q10 | Months with spend > 1.5× own trailing 3-month average | The biggest spikes are hospitalisations (5–6×), followed by April school fees (about 2.2–2.5×). | Separates genuine shocks from predictable seasonal costs. |
| Q11 | 3+ consecutive months of falling balance (gaps-and-islands) | Streaks of up to 6 months, mostly gig workers and students. Some are still only "Moderate". | A sustained drain is a leading indicator. |
| Q12 | Lifestyle creep (Jan–Mar vs Jul–Sep, income stable) | 10 customers with spend +23–32% and income +4–11% | Early intervention target (Insight 6). |
| Q13 | Each customer's #1 habitual merchant | Neighbourhood kirana stores are #1 for most customers, at about 12% of variable spend each. | Spend is fragmented; no single merchant is a major dependency. |
| Q14 | Payment method by ticket size (pivot) | UPI handles 55–66% of payments under ₹10K. NACH and bank transfer take 58% of payments ≥ ₹10K. | Large obligations arrive by auto-debit, so date alignment with salary matters. |
| Q15 | Income-volatility quartiles (NTILE) | The top quartile is all 18 gig workers plus 12 salaried customers with bonus or job-change income. It has the highest average stress (33). | Volatility drives stress even at similar income levels. |
| Q16 | Festive (Oct–Nov) uplift by category | Shopping +59%, Travel +27%, Dining +22%; fixed costs flat | Quantifies the festive budget gap (Insight 4). |
| Q17 | Customers with 3+ deficit months | The worst customers ran deficits in 11–12 of 12 months and borrowed in most of them. | The core intervention list. |
| Q18 | Survival months (balance ÷ essential spend) | 15 under 1 month, 21 at 1–3 months, 54 at 6+ months | 30% are below the 3-month guideline (Insight 3). |
| Q19 | Does one card or loan-app borrowing lead to more? | **16 of 17 (94%)** borrowed again, with 3.9 later events on average | The debt-spiral trigger (Insight 5). |
| Q20 | Next-month watch-list (score + forecast) | 9 customers, each with a recommended action | Ready-to-use operational output (Insight 8). |

Every query in `04_analysis_queries.sql` has a header comment with the business question and the techniques used.
