-- =====================================================================================
-- 02_load_data.sql  |  Loads the CSVs produced by the Python pipeline.
-- Run from the PROJECT ROOT folder (paths are relative):
--     psql -d finstress -f sql/02_load_data.sql
-- \copy runs on the client, so no server file permissions are needed.
-- =====================================================================================

\copy customers FROM 'data/processed/customers_clean.csv' WITH (FORMAT csv, HEADER true)

\copy transactions (transaction_id, customer_id, txn_ts, transaction_type, category, subcategory, merchant, amount, payment_method, income_expense, account_balance, recurring_flag, location, monthly_income, financial_goal, is_outlier, exceeds_monthly_income, signed_amount, year_month, txn_date, day_of_week, is_weekend, spend_type) FROM 'data/processed/transactions_clean.csv' WITH (FORMAT csv, HEADER true)

\copy customer_stress_score FROM 'data/analytics/customer_stress_score.csv' WITH (FORMAT csv, HEADER true)

\copy cashflow_forecast FROM 'data/analytics/cashflow_forecast.csv' WITH (FORMAT csv, HEADER true)

ANALYZE;

-- Row-count sanity check
SELECT 'customers' AS table_name, COUNT(*) AS row_count FROM customers
UNION ALL SELECT 'transactions', COUNT(*) FROM transactions
UNION ALL SELECT 'customer_stress_score', COUNT(*) FROM customer_stress_score
UNION ALL SELECT 'cashflow_forecast', COUNT(*) FROM cashflow_forecast;
