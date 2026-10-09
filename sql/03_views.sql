-- =====================================================================================
-- 03_views.sql  |  Analytical views (built in SQL from raw transactions)
--   vw_customer_month       : one row per customer per month - the backbone of most queries
--   vw_powerbi_customer_360 : one row per customer with KPIs + score + forecast for Power BI
-- =====================================================================================

CREATE OR REPLACE VIEW vw_customer_month AS
WITH monthly AS (
    SELECT
        customer_id,
        year_month,
        SUM(CASE WHEN income_expense = 'Income'     THEN amount ELSE 0 END) AS income,
        SUM(CASE WHEN income_expense = 'Expense'    THEN amount ELSE 0 END) AS expenses,
        SUM(CASE WHEN income_expense = 'Investment' THEN amount ELSE 0 END) AS investment,
        SUM(CASE WHEN income_expense = 'Borrowing'  THEN amount ELSE 0 END) AS borrowing,
        SUM(CASE WHEN spend_type = 'Fixed Obligation'   THEN amount ELSE 0 END) AS fixed_obligations,
        SUM(CASE WHEN spend_type = 'Essential Variable' THEN amount ELSE 0 END) AS essential_variable,
        SUM(CASE WHEN spend_type = 'Discretionary'      THEN amount ELSE 0 END) AS discretionary,
        SUM(signed_amount) AS balance_change,
        COUNT(*)           AS n_transactions
    FROM transactions
    GROUP BY customer_id, year_month
),
month_end AS (           -- balance after the last transaction of the month
    SELECT DISTINCT ON (customer_id, year_month)
           customer_id, year_month, account_balance AS month_end_balance
    FROM transactions
    ORDER BY customer_id, year_month, txn_ts DESC, transaction_id DESC
)
SELECT
    m.*,
    e.month_end_balance,
    m.income - m.expenses                                         AS net_cash_flow,
    m.fixed_obligations + m.essential_variable                    AS essential_spend,
    ROUND((m.income - m.expenses) / NULLIF(m.income, 0), 4)       AS savings_rate,
    ROUND(m.fixed_obligations / NULLIF(m.income, 0), 4)           AS fixed_obligation_ratio,
    CASE WHEN m.borrowing > 0 THEN 1 ELSE 0 END                   AS borrowed_this_month
FROM monthly m
JOIN month_end e USING (customer_id, year_month);


CREATE OR REPLACE VIEW vw_powerbi_customer_360 AS
SELECT
    c.*,
    s.stress_score, s.stress_band, s.top_stress_driver,
    s.savings_rate_6m, s.fixed_obligation_ratio_6m, s.buffer_months, s.income_cv,
    s.expense_growth_6m, s.current_balance,
    f.forecast_month, f.expected_income, f.expected_outflows, f.expected_ending_balance,
    f.deficit_probability, f.cashflow_risk_tier, f.projected_shortfall,
    t.total_income_12m, t.total_expenses_12m, t.borrow_events_12m
FROM customers c
LEFT JOIN customer_stress_score s USING (customer_id)
LEFT JOIN cashflow_forecast     f USING (customer_id)
LEFT JOIN (
    SELECT customer_id,
           SUM(CASE WHEN income_expense = 'Income'    THEN amount ELSE 0 END) AS total_income_12m,
           SUM(CASE WHEN income_expense = 'Expense'   THEN amount ELSE 0 END) AS total_expenses_12m,
           SUM(CASE WHEN income_expense = 'Borrowing' THEN 1 ELSE 0 END)      AS borrow_events_12m
    FROM transactions GROUP BY customer_id
) t USING (customer_id);
