-- =====================================================================================
-- 04_analysis_queries.sql  |  20 business questions answered in PostgreSQL
-- Each query starts with a marker line "-- @@ Qnn | title" (used by src/run_sql.py to
-- run them one by one and save results to sql/results/Qnn.csv).
-- Techniques used: aggregation, GROUP BY / HAVING, CASE, CTEs, subqueries,
-- window functions (LAG, SUM OVER, AVG OVER ROWS, RANK, ROW_NUMBER, NTILE), DISTINCT ON,
-- generate_series, conditional pivots.
-- =====================================================================================


-- @@ Q01 | Monthly portfolio cash flow
-- Business question: How much did customers earn, spend, invest and borrow each month,
--                    and what was the portfolio savings rate?
-- Techniques: conditional aggregation (SUM + CASE), GROUP BY
SELECT
    year_month,
    ROUND(SUM(CASE WHEN income_expense = 'Income'     THEN amount ELSE 0 END), 0) AS total_income,
    ROUND(SUM(CASE WHEN income_expense = 'Expense'    THEN amount ELSE 0 END), 0) AS total_expenses,
    ROUND(SUM(CASE WHEN income_expense = 'Investment' THEN amount ELSE 0 END), 0) AS total_invested,
    ROUND(SUM(CASE WHEN income_expense = 'Borrowing'  THEN amount ELSE 0 END), 0) AS total_borrowed,
    ROUND(100.0 * (SUM(CASE WHEN income_expense = 'Income'  THEN amount ELSE 0 END)
                 - SUM(CASE WHEN income_expense = 'Expense' THEN amount ELSE 0 END))
               / SUM(CASE WHEN income_expense = 'Income' THEN amount ELSE 0 END), 1) AS savings_rate_pct
FROM transactions
GROUP BY year_month
ORDER BY year_month;


-- @@ Q02 | Top 10 spending categories and their share
-- Business question: Which categories absorb the most money, and what share of total spend?
-- Techniques: aggregation, scalar subquery for the denominator, ORDER BY / LIMIT
SELECT
    category,
    spend_type,
    COUNT(*)                         AS n_transactions,
    ROUND(SUM(amount), 0)            AS total_spend,
    ROUND(AVG(amount), 0)            AS avg_ticket,
    ROUND(100.0 * SUM(amount) / (SELECT SUM(amount) FROM transactions WHERE income_expense = 'Expense'), 2)
                                     AS share_of_spend_pct
FROM transactions
WHERE income_expense = 'Expense'
GROUP BY category, spend_type
ORDER BY total_spend DESC
LIMIT 10;


-- @@ Q03 | Savings-rate bands by occupation
-- Business question: How are customers distributed across savings-rate bands, and does it
--                    differ between salaried, gig and student customers?
-- Techniques: CTE, CASE banding, GROUP BY on two dimensions, conditional counts
WITH cust AS (
    SELECT customer_id,
           (SUM(income) - SUM(expenses)) / NULLIF(SUM(income), 0) AS savings_rate
    FROM vw_customer_month
    GROUP BY customer_id
),
banded AS (
    SELECT c.occupation_type,
           CASE WHEN s.savings_rate <  0    THEN '1. Negative (<0%)'
                WHEN s.savings_rate <  0.10 THEN '2. Thin (0-10%)'
                WHEN s.savings_rate <  0.20 THEN '3. Fair (10-20%)'
                ELSE                              '4. Healthy (20%+)' END AS savings_band
    FROM cust s JOIN customers c USING (customer_id)
)
SELECT occupation_type,
       COUNT(*) AS customers,
       SUM(CASE WHEN savings_band LIKE '1.%' THEN 1 ELSE 0 END) AS negative,
       SUM(CASE WHEN savings_band LIKE '2.%' THEN 1 ELSE 0 END) AS thin,
       SUM(CASE WHEN savings_band LIKE '3.%' THEN 1 ELSE 0 END) AS fair,
       SUM(CASE WHEN savings_band LIKE '4.%' THEN 1 ELSE 0 END) AS healthy,
       ROUND(100.0 * SUM(CASE WHEN savings_band LIKE '1.%' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_negative
FROM banded
GROUP BY occupation_type
ORDER BY pct_negative DESC;


-- @@ Q04 | Month-over-month expense change (latest month)
-- Business question: Which customers' spending jumped the most versus the previous month?
-- Techniques: LAG window function, percentage change, filtering on a window result via CTE
WITH mom AS (
    SELECT customer_id, year_month, expenses,
           LAG(expenses) OVER (PARTITION BY customer_id ORDER BY year_month) AS prev_expenses
    FROM vw_customer_month
)
SELECT customer_id, year_month,
       ROUND(prev_expenses, 0) AS prev_month_expenses,
       ROUND(expenses, 0)      AS this_month_expenses,
       ROUND(100.0 * (expenses - prev_expenses) / NULLIF(prev_expenses, 0), 1) AS mom_change_pct
FROM mom
WHERE year_month = (SELECT MAX(year_month) FROM transactions)
  AND prev_expenses IS NOT NULL
ORDER BY mom_change_pct DESC
LIMIT 10;


-- @@ Q05 | Running total of portfolio net savings
-- Business question: How has cumulative net savings (income - expenses) built up through the year,
--                    and how much did each month add?
-- Techniques: SUM() OVER (ORDER BY) running total, LAG for MoM delta
WITH m AS (
    SELECT year_month, SUM(net_cash_flow) AS net_savings
    FROM vw_customer_month
    GROUP BY year_month
)
SELECT year_month,
       ROUND(net_savings, 0)                                         AS net_savings,
       ROUND(SUM(net_savings) OVER (ORDER BY year_month), 0)         AS cumulative_net_savings,
       ROUND(100.0 * (net_savings - LAG(net_savings) OVER (ORDER BY year_month))
             / NULLIF(LAG(net_savings) OVER (ORDER BY year_month), 0), 1) AS mom_change_pct
FROM m
ORDER BY year_month;


-- @@ Q06 | Best and worst savers within each city tier
-- Business question: Who are the top-3 and bottom-3 savers in each city tier (fair peer comparison)?
-- Techniques: RANK() with PARTITION BY, two-direction ranking, CTE
WITH sr AS (
    SELECT cm.customer_id, c.city_tier, c.occupation_type,
           ROUND((SUM(cm.income) - SUM(cm.expenses)) / NULLIF(SUM(cm.income), 0), 3) AS savings_rate
    FROM vw_customer_month cm JOIN customers c USING (customer_id)
    GROUP BY cm.customer_id, c.city_tier, c.occupation_type
),
ranked AS (
    SELECT *,
           RANK() OVER (PARTITION BY city_tier ORDER BY savings_rate DESC) AS rank_best,
           RANK() OVER (PARTITION BY city_tier ORDER BY savings_rate ASC)  AS rank_worst
    FROM sr
)
SELECT city_tier,
       CASE WHEN rank_best <= 3 THEN 'Top 3' ELSE 'Bottom 3' END AS grp,
       customer_id, occupation_type, savings_rate
FROM ranked
WHERE rank_best <= 3 OR rank_worst <= 3
ORDER BY city_tier, grp DESC, savings_rate DESC;


-- @@ Q07 | Transaction size bands
-- Business question: How are expense transactions distributed by ticket size, and where does
--                    the money (not the count) actually go?
-- Techniques: CASE banding, window SUM() OVER () for shares of total
SELECT size_band,
       COUNT(*)                                                  AS n_transactions,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)        AS pct_of_transactions,
       ROUND(SUM(amount), 0)                                     AS total_amount,
       ROUND(100.0 * SUM(amount) / SUM(SUM(amount)) OVER (), 1)  AS pct_of_value,
       ROUND(AVG(amount), 0)                                     AS avg_amount
FROM (
    SELECT amount,
           CASE WHEN amount <   500 THEN '1. Micro (<500)'
                WHEN amount <  2000 THEN '2. Small (500-2K)'
                WHEN amount < 10000 THEN '3. Medium (2K-10K)'
                WHEN amount < 50000 THEN '4. Large (10K-50K)'
                ELSE                     '5. Very large (50K+)' END AS size_band
    FROM transactions
    WHERE income_expense = 'Expense'
) t
GROUP BY size_band
ORDER BY size_band;


-- @@ Q08 | Weekend vs weekday spend per day by category
-- Business question: Which categories are weekend-driven (spend per day, adjusting for the
--                    fact there are 2.5x more weekdays than weekend days)?
-- Techniques: generate_series calendar CTE, conditional aggregation, ratio
WITH cal AS (
    SELECT SUM(CASE WHEN EXTRACT(ISODOW FROM d) >= 6 THEN 1 ELSE 0 END) AS weekend_days,
           SUM(CASE WHEN EXTRACT(ISODOW FROM d) <  6 THEN 1 ELSE 0 END) AS weekday_days
    FROM generate_series((SELECT MIN(txn_date) FROM transactions),
                         (SELECT MAX(txn_date) FROM transactions), INTERVAL '1 day') AS d
),
spend AS (
    SELECT category,
           SUM(CASE WHEN is_weekend = 1 THEN amount ELSE 0 END) AS weekend_spend,
           SUM(CASE WHEN is_weekend = 0 THEN amount ELSE 0 END) AS weekday_spend
    FROM transactions
    WHERE income_expense = 'Expense' AND recurring_flag = 0
    GROUP BY category
)
SELECT s.category,
       ROUND(s.weekday_spend / c.weekday_days, 0) AS weekday_spend_per_day,
       ROUND(s.weekend_spend / c.weekend_days, 0) AS weekend_spend_per_day,
       ROUND(100.0 * ((s.weekend_spend / c.weekend_days) / NULLIF(s.weekday_spend / c.weekday_days, 0) - 1), 1)
           AS weekend_uplift_pct
FROM spend s CROSS JOIN cal c
ORDER BY weekend_uplift_pct DESC;


-- @@ Q09 | Fixed-obligation burden (FOIR-style)
-- Business question: What share of income is pre-committed to rent, EMIs, insurance and debt
--                    repayment, and how many customers exceed typical lender limits?
-- Techniques: CTE, ratio, CASE banding, aggregate over bands
WITH burden AS (
    SELECT customer_id,
           SUM(fixed_obligations) / NULLIF(SUM(income), 0) AS obligation_ratio
    FROM vw_customer_month
    GROUP BY customer_id
)
SELECT CASE WHEN obligation_ratio < 0.30 THEN '1. Comfortable (<30%)'
            WHEN obligation_ratio < 0.40 THEN '2. Watch (30-40%)'
            WHEN obligation_ratio < 0.50 THEN '3. Stretched (40-50%)'
            ELSE                               '4. Over lender limit (50%+)' END AS obligation_band,
       COUNT(*)                                 AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_customers,
       ROUND(AVG(obligation_ratio) * 100, 1)    AS avg_ratio_pct,
       ROUND(AVG(s.stress_score), 1)            AS avg_stress_score
FROM burden b
LEFT JOIN customer_stress_score s USING (customer_id)
GROUP BY 1
ORDER BY 1;


-- @@ Q10 | Unusual spending months
-- Business question: Which customers spent more than 1.5x their own trailing 3-month average
--                    in a month (a possible shock or loss of control)?
-- Techniques: AVG() OVER with a ROWS BETWEEN frame (excludes the current month), CTE filter
WITH t AS (
    SELECT customer_id, year_month, expenses,
           AVG(expenses) OVER (PARTITION BY customer_id ORDER BY year_month
                               ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS trailing_3m_avg,
           COUNT(*)     OVER (PARTITION BY customer_id ORDER BY year_month
                               ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS months_in_window
    FROM vw_customer_month
)
SELECT t.customer_id, t.year_month,
       ROUND(t.expenses, 0)        AS expenses,
       ROUND(t.trailing_3m_avg, 0) AS trailing_3m_avg,
       ROUND(t.expenses / t.trailing_3m_avg, 2) AS spike_ratio,
       (SELECT string_agg(DISTINCT x.subcategory, ', ')
          FROM transactions x
         WHERE x.customer_id = t.customer_id AND x.year_month = t.year_month
           AND x.income_expense = 'Expense' AND x.amount > 0.5 * t.trailing_3m_avg) AS large_items
FROM t
WHERE months_in_window = 3
  AND t.expenses > 1.5 * t.trailing_3m_avg
ORDER BY spike_ratio DESC
LIMIT 15;


-- @@ Q11 | Customers with 3+ consecutive months of falling balance
-- Business question: Whose month-end balance has declined for at least three months in a row
--                    (a sustained drain rather than a one-off)?
-- Techniques: LAG to flag declines, gaps-and-islands with ROW_NUMBER to find streaks
WITH b AS (
    SELECT customer_id, year_month, month_end_balance,
           CASE WHEN month_end_balance < LAG(month_end_balance) OVER w THEN 1 ELSE 0 END AS declined
    FROM vw_customer_month
    WINDOW w AS (PARTITION BY customer_id ORDER BY year_month)
),
islands AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY year_month)
         - ROW_NUMBER() OVER (PARTITION BY customer_id, declined ORDER BY year_month) AS grp
    FROM b
),
streaks AS (
    SELECT customer_id, MIN(year_month) AS streak_start, MAX(year_month) AS streak_end,
           COUNT(*) AS months_declining
    FROM islands
    WHERE declined = 1
    GROUP BY customer_id, grp
    HAVING COUNT(*) >= 3
)
SELECT s.customer_id, c.occupation_type, s.streak_start, s.streak_end, s.months_declining,
       ROUND(sc.current_balance, 0) AS current_balance, sc.stress_band
FROM streaks s
JOIN customers c USING (customer_id)
LEFT JOIN customer_stress_score sc USING (customer_id)
ORDER BY s.months_declining DESC, sc.stress_score DESC
LIMIT 20;


-- @@ Q12 | Lifestyle creep: expenses growing faster than income
-- Business question: Which customers increased spending much faster than income while income
--                    stayed roughly stable? Compares Jan-Mar 2025 with Jul-Sep 2025: two
--                    "ordinary" quarters with no Diwali, school fees or summer-travel peaks,
--                    so seasonality cannot masquerade as creep. One-off outliers are excluded.
-- Techniques: CTE with quarter CASE split, conditional AVG, comparison of growth rates
WITH m AS (
    SELECT customer_id, year_month,
           SUM(CASE WHEN income_expense = 'Income' THEN amount ELSE 0 END) AS income,
           SUM(CASE WHEN income_expense = 'Expense' AND is_outlier = 0
                     AND subcategory <> 'School Fees' THEN amount ELSE 0 END) AS core_exp
    FROM transactions
    GROUP BY customer_id, year_month
),
q AS (
    SELECT customer_id,
           AVG(CASE WHEN year_month BETWEEN '2025-01' AND '2025-03' THEN income   END) AS inc_q1,
           AVG(CASE WHEN year_month BETWEEN '2025-07' AND '2025-09' THEN income   END) AS inc_q3,
           AVG(CASE WHEN year_month BETWEEN '2025-01' AND '2025-03' THEN core_exp END) AS exp_q1,
           AVG(CASE WHEN year_month BETWEEN '2025-07' AND '2025-09' THEN core_exp END) AS exp_q3
    FROM m
    GROUP BY customer_id
)
SELECT q.customer_id, c.occupation_type,
       ROUND(100.0 * (inc_q3 / NULLIF(inc_q1, 0) - 1), 1) AS income_growth_pct,
       ROUND(100.0 * (exp_q3 / NULLIF(exp_q1, 0) - 1), 1) AS expense_growth_pct,
       ROUND(100.0 * ((exp_q3 / NULLIF(exp_q1, 0)) - (inc_q3 / NULLIF(inc_q1, 0))), 1) AS gap_pct_points,
       s.stress_band
FROM q
JOIN customers c USING (customer_id)
LEFT JOIN customer_stress_score s USING (customer_id)
WHERE (exp_q3 / NULLIF(exp_q1, 0)) - (inc_q3 / NULLIF(inc_q1, 0)) > 0.15
  AND inc_q3 / NULLIF(inc_q1, 0) > 0.90          -- income roughly stable: rules out job-loss cases
ORDER BY gap_pct_points DESC
LIMIT 15;


-- @@ Q13 | Each customer's #1 merchant and how dependent they are on it
-- Business question: Which merchants are most often a customer's top habitual merchant (one-off
--                    outliers excluded), and how much of that customer's variable spend do they capture?
-- Techniques: ROW_NUMBER() to pick the top row per group, share via window SUM, then aggregate
WITH cm AS (
    SELECT customer_id, merchant, SUM(amount) AS spend,
           SUM(SUM(amount)) OVER (PARTITION BY customer_id) AS customer_total
    FROM transactions
    WHERE income_expense = 'Expense' AND recurring_flag = 0 AND is_outlier = 0
    GROUP BY customer_id, merchant
),
top1 AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY spend DESC) AS rn
    FROM cm
)
SELECT merchant AS top_merchant,
       COUNT(*)                                   AS customers_with_it_as_no1,
       ROUND(AVG(100.0 * spend / customer_total), 1) AS avg_share_of_their_variable_spend_pct
FROM top1
WHERE rn = 1
GROUP BY merchant
ORDER BY customers_with_it_as_no1 DESC
LIMIT 10;


-- @@ Q14 | Payment-method mix by ticket size (pivot)
-- Business question: Which payment rails are used for small vs large payments?
-- Techniques: CASE pivot (rows -> columns), percentage within row
SELECT size_band,
       COUNT(*) AS n,
       ROUND(100.0 * AVG(CASE WHEN payment_method = 'UPI'               THEN 1 ELSE 0 END), 1) AS upi_pct,
       ROUND(100.0 * AVG(CASE WHEN payment_method = 'UPI Autopay'       THEN 1 ELSE 0 END), 1) AS upi_autopay_pct,
       ROUND(100.0 * AVG(CASE WHEN payment_method = 'Credit Card'       THEN 1 ELSE 0 END), 1) AS credit_card_pct,
       ROUND(100.0 * AVG(CASE WHEN payment_method = 'Debit Card'        THEN 1 ELSE 0 END), 1) AS debit_card_pct,
       ROUND(100.0 * AVG(CASE WHEN payment_method = 'Auto-Debit (NACH)' THEN 1 ELSE 0 END), 1) AS nach_pct,
       ROUND(100.0 * AVG(CASE WHEN payment_method IN ('Net Banking','NEFT','IMPS') THEN 1 ELSE 0 END), 1) AS bank_transfer_pct,
       ROUND(100.0 * AVG(CASE WHEN payment_method = 'ATM/Cash'          THEN 1 ELSE 0 END), 1) AS cash_pct
FROM (
    SELECT payment_method,
           CASE WHEN amount <   500 THEN '1. Micro (<500)'
                WHEN amount <  2000 THEN '2. Small (500-2K)'
                WHEN amount < 10000 THEN '3. Medium (2K-10K)'
                ELSE                     '4. Large (10K+)' END AS size_band
    FROM transactions
    WHERE transaction_type = 'Debit'
) t
GROUP BY size_band
ORDER BY size_band;


-- @@ Q15 | Income volatility quartiles
-- Business question: How volatile is each customer's income, and which occupations sit in the
--                    most volatile quartile?
-- Techniques: STDDEV_POP / AVG (coefficient of variation), NTILE(4), aggregation by quartile
WITH v AS (
    SELECT customer_id,
           STDDEV_POP(income) / NULLIF(AVG(income), 0) AS income_cv
    FROM vw_customer_month
    GROUP BY customer_id
),
q AS (
    SELECT v.*, c.occupation_type,
           NTILE(4) OVER (ORDER BY income_cv) AS volatility_quartile
    FROM v JOIN customers c USING (customer_id)
)
SELECT volatility_quartile,
       ROUND(MIN(q.income_cv), 3) AS min_cv,
       ROUND(MAX(q.income_cv), 3) AS max_cv,
       SUM(CASE WHEN occupation_type = 'Salaried'       THEN 1 ELSE 0 END) AS salaried,
       SUM(CASE WHEN occupation_type = 'Freelancer/Gig' THEN 1 ELSE 0 END) AS freelancer_gig,
       SUM(CASE WHEN occupation_type = 'Student'        THEN 1 ELSE 0 END) AS student,
       ROUND(AVG(s.stress_score), 1) AS avg_stress_score
FROM q LEFT JOIN customer_stress_score s USING (customer_id)
GROUP BY volatility_quartile
ORDER BY volatility_quartile;


-- @@ Q16 | Festive-season uplift by category
-- Business question: How much higher is monthly spend in the Diwali months (Oct-Nov) than in
--                    the rest of the year, by category?
-- Techniques: CTE, conditional averages of monthly totals, ratio, HAVING to drop tiny categories
WITH monthly AS (
    SELECT category, year_month, SUM(amount) AS spend
    FROM transactions
    WHERE income_expense = 'Expense'
    GROUP BY category, year_month
)
SELECT category,
       ROUND(AVG(CASE WHEN year_month IN ('2024-10','2024-11') THEN spend END), 0)     AS avg_festive_month,
       ROUND(AVG(CASE WHEN year_month NOT IN ('2024-10','2024-11') THEN spend END), 0) AS avg_other_month,
       ROUND(100.0 * (AVG(CASE WHEN year_month IN ('2024-10','2024-11') THEN spend END)
                    / NULLIF(AVG(CASE WHEN year_month NOT IN ('2024-10','2024-11') THEN spend END), 0) - 1), 1)
             AS festive_uplift_pct
FROM monthly
GROUP BY category
HAVING SUM(spend) > 100000
ORDER BY festive_uplift_pct DESC NULLS FIRST;


-- @@ Q17 | Chronic deficit customers
-- Business question: Which customers spent more than they earned in 3 or more months, and did
--                    they fall back on borrowing?
-- Techniques: GROUP BY + HAVING, conditional counts, join to customer attributes
SELECT cm.customer_id, c.occupation_type, c.has_active_loan,
       SUM(CASE WHEN cm.net_cash_flow < 0 THEN 1 ELSE 0 END) AS deficit_months,
       SUM(cm.borrowed_this_month)                            AS months_with_borrowing,
       ROUND(SUM(cm.borrowing), 0)                            AS total_borrowed,
       ROUND(SUM(cm.net_cash_flow), 0)                        AS net_cash_flow_12m
FROM vw_customer_month cm
JOIN customers c USING (customer_id)
GROUP BY cm.customer_id, c.occupation_type, c.has_active_loan
HAVING SUM(CASE WHEN cm.net_cash_flow < 0 THEN 1 ELSE 0 END) >= 3
ORDER BY deficit_months DESC, total_borrowed DESC
LIMIT 20;


-- @@ Q18 | Survival months: how long could each customer last without income?
-- Business question: If income stopped today, how many months of essential spending would the
--                    latest balance cover? How many customers are below 1 and 3 months?
-- Techniques: CTE, DISTINCT ON to get the latest balance, correlated-free subquery, CASE bands
WITH latest AS (
    SELECT DISTINCT ON (customer_id) customer_id, account_balance AS latest_balance
    FROM transactions
    ORDER BY customer_id, txn_ts DESC, transaction_id DESC
),
essential AS (
    SELECT customer_id, AVG(essential_spend) AS avg_essential
    FROM vw_customer_month
    WHERE year_month > (SELECT TO_CHAR(TO_DATE(MAX(year_month), 'YYYY-MM') - INTERVAL '6 months', 'YYYY-MM')
                        FROM transactions)
    GROUP BY customer_id
)
SELECT CASE WHEN latest_balance / avg_essential < 1 THEN '1. Under 1 month'
            WHEN latest_balance / avg_essential < 3 THEN '2. 1-3 months'
            WHEN latest_balance / avg_essential < 6 THEN '3. 3-6 months'
            ELSE                                          '4. 6+ months' END AS survival_band,
       COUNT(*) AS customers,
       ROUND(AVG(latest_balance), 0) AS avg_balance,
       ROUND(AVG(avg_essential), 0)  AS avg_monthly_essential_spend
FROM latest JOIN essential USING (customer_id)
GROUP BY 1
ORDER BY 1;


-- @@ Q19 | Borrowing dependency: does one borrowing event lead to more?
-- Business question: After a customer first borrows from a card or instant-loan app, how many
--                    go on to borrow again, and how much do repayments eat into income?
-- Techniques: CTE with MIN() first-event date, self-join on later events, aggregation
WITH first_borrow AS (
    SELECT customer_id, MIN(txn_ts) AS first_ts
    FROM transactions
    WHERE income_expense = 'Borrowing' AND subcategory <> 'Borrowed from Family'
    GROUP BY customer_id
),
later AS (
    SELECT f.customer_id,
           COUNT(t.transaction_id) AS later_borrow_events
    FROM first_borrow f
    LEFT JOIN transactions t
           ON t.customer_id = f.customer_id AND t.income_expense = 'Borrowing' AND t.txn_ts > f.first_ts
    GROUP BY f.customer_id
),
repay AS (
    SELECT customer_id,
           SUM(CASE WHEN category = 'Debt Repayment' THEN amount ELSE 0 END)
         / NULLIF(SUM(CASE WHEN income_expense = 'Income' THEN amount ELSE 0 END), 0) AS repayment_to_income
    FROM transactions GROUP BY customer_id
)
SELECT COUNT(*)                                                   AS customers_who_borrowed_formally,
       SUM(CASE WHEN later_borrow_events > 0 THEN 1 ELSE 0 END)   AS borrowed_again,
       ROUND(100.0 * AVG(CASE WHEN later_borrow_events > 0 THEN 1 ELSE 0 END), 1) AS repeat_rate_pct,
       ROUND(AVG(later_borrow_events), 1)                         AS avg_later_events,
       ROUND(100.0 * AVG(r.repayment_to_income), 1)               AS avg_repayment_pct_of_income
FROM later l JOIN repay r USING (customer_id);


-- @@ Q20 | Next-month risk watch-list (score + forecast)
-- Business question: Which customers should be contacted first: those with the highest chance
--                    of a cash shortfall next month, with their stress band and main driver?
-- Techniques: joins across model tables, ordering by risk, CASE for an action label
SELECT f.customer_id, c.occupation_type, c.city,
       s.stress_score, s.stress_band, s.top_stress_driver,
       ROUND(f.current_balance, 0)          AS current_balance,
       ROUND(f.expected_net_cash_flow, 0)   AS expected_net_cash_flow,
       ROUND(f.expected_ending_balance, 0)  AS expected_ending_balance,
       ROUND(100 * f.deficit_probability, 1) AS deficit_probability_pct,
       f.cashflow_risk_tier,
       CASE WHEN f.cashflow_risk_tier = 'High' THEN 'Contact this week: offer payment-date realignment / short-term relief'
            WHEN f.cashflow_risk_tier = 'Medium' AND s.stress_band IN ('High','Critical')
                 THEN 'Proactive nudge: spending alert + budget plan'
            WHEN f.cashflow_risk_tier = 'Medium' THEN 'Monitor: low-balance alert'
            ELSE 'Monitor' END AS recommended_action
FROM cashflow_forecast f
JOIN customers c USING (customer_id)
JOIN customer_stress_score s USING (customer_id)
WHERE f.cashflow_risk_tier IN ('High','Medium') OR s.stress_band = 'Critical'
ORDER BY f.deficit_probability DESC, s.stress_score DESC;
