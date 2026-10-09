-- =====================================================================================
-- 01_schema.sql  |  Financial Stress & Cash-Flow Risk Analytics  |  PostgreSQL 13+
-- Creates the tables. Run first:  psql -d finstress -f sql/01_schema.sql
-- =====================================================================================

DROP VIEW  IF EXISTS vw_powerbi_customer_360, vw_customer_month CASCADE;
DROP TABLE IF EXISTS cashflow_forecast, customer_stress_score, transactions, customers CASCADE;

-- Customer master (one row per customer)
CREATE TABLE customers (
    customer_id              VARCHAR(10) PRIMARY KEY,
    age_band                 VARCHAR(10)  NOT NULL,
    city                     VARCHAR(40)  NOT NULL,
    city_tier                VARCHAR(10)  NOT NULL,
    occupation_type          VARCHAR(20)  NOT NULL,
    declared_monthly_income  NUMERIC(12,2) NOT NULL CHECK (declared_monthly_income > 0),
    financial_goal           VARCHAR(40)  NOT NULL,
    has_active_loan          BOOLEAN      NOT NULL,
    income_band              VARCHAR(10)  NOT NULL
);

-- Cleaned transactions (one row per transaction) - output of src/clean_data.py
CREATE TABLE transactions (
    transaction_id          VARCHAR(12) PRIMARY KEY,
    customer_id             VARCHAR(10) NOT NULL REFERENCES customers(customer_id),
    txn_ts                  TIMESTAMP    NOT NULL,
    transaction_type        VARCHAR(6)   NOT NULL CHECK (transaction_type IN ('Credit','Debit')),
    category                VARCHAR(30)  NOT NULL,
    subcategory             VARCHAR(40)  NOT NULL,
    merchant                VARCHAR(60)  NOT NULL,
    amount                  NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    payment_method          VARCHAR(20)  NOT NULL,
    income_expense          VARCHAR(12)  NOT NULL CHECK (income_expense IN ('Income','Expense','Investment','Borrowing')),
    account_balance         NUMERIC(14,2) NOT NULL,
    recurring_flag          SMALLINT     NOT NULL CHECK (recurring_flag IN (0,1)),
    location                VARCHAR(40)  NOT NULL,
    monthly_income          NUMERIC(12,2) NOT NULL,
    financial_goal          VARCHAR(40)  NOT NULL,
    is_outlier              SMALLINT     NOT NULL,
    exceeds_monthly_income  SMALLINT     NOT NULL,
    signed_amount           NUMERIC(12,2) NOT NULL,
    year_month              CHAR(7)      NOT NULL,      -- 'YYYY-MM'
    txn_date                DATE         NOT NULL,
    day_of_week             VARCHAR(9)   NOT NULL,
    is_weekend              SMALLINT     NOT NULL,
    spend_type              VARCHAR(20)  NOT NULL
);
CREATE INDEX idx_tx_customer_ts ON transactions (customer_id, txn_ts, transaction_id);
CREATE INDEX idx_tx_month       ON transactions (year_month);
CREATE INDEX idx_tx_category    ON transactions (category);

-- Model outputs written by Python (score + forecast), loaded for Power BI / joins
CREATE TABLE customer_stress_score (
    customer_id                  VARCHAR(10) PRIMARY KEY REFERENCES customers(customer_id),
    as_of_month                  CHAR(7),
    avg_monthly_income           NUMERIC(14,2),
    avg_monthly_expenses         NUMERIC(14,2),
    savings_rate_6m              NUMERIC(10,4),
    fixed_obligation_ratio_6m    NUMERIC(10,4),
    expense_to_income_6m         NUMERIC(10,4),
    current_balance              NUMERIC(14,2),
    avg_essential_spend          NUMERIC(14,2),
    buffer_months                NUMERIC(10,2),
    income_cv                    NUMERIC(10,4),
    expense_growth_6m            NUMERIC(10,4),
    balance_trend_income_months  NUMERIC(10,4),
    deficit_months_6m            INT,
    borrow_months_6m             INT,
    deficit_borrow_index         NUMERIC(10,4),
    stress_score                 NUMERIC(5,1),
    sub_savings_margin           NUMERIC(5,1), contrib_savings_margin      NUMERIC(6,2),
    sub_fixed_obligations        NUMERIC(5,1), contrib_fixed_obligations   NUMERIC(6,2),
    sub_emergency_buffer         NUMERIC(5,1), contrib_emergency_buffer    NUMERIC(6,2),
    sub_income_instability       NUMERIC(5,1), contrib_income_instability  NUMERIC(6,2),
    sub_expense_growth           NUMERIC(5,1), contrib_expense_growth      NUMERIC(6,2),
    sub_balance_trend            NUMERIC(5,1), contrib_balance_trend       NUMERIC(6,2),
    sub_deficit_borrowing        NUMERIC(5,1), contrib_deficit_borrowing   NUMERIC(6,2),
    stress_band                  VARCHAR(10),
    top_stress_driver            VARCHAR(30)
);

CREATE TABLE cashflow_forecast (
    customer_id                  VARCHAR(10) PRIMARY KEY REFERENCES customers(customer_id),
    as_of_month                  CHAR(7),
    forecast_month               CHAR(7),
    current_balance              NUMERIC(14,2),
    expected_income              NUMERIC(14,2),
    expected_recurring_outflows  NUMERIC(14,2),
    expected_variable_spend      NUMERIC(14,2),
    expected_seasonal_one_offs   NUMERIC(14,2),
    expected_outflows            NUMERIC(14,2),
    expected_net_cash_flow       NUMERIC(14,2),
    expected_ending_balance      NUMERIC(14,2),
    uncertainty_sigma            NUMERIC(14,2),
    deficit_probability          NUMERIC(6,4),
    cashflow_risk_tier           VARCHAR(10),
    projected_shortfall          NUMERIC(14,2),
    seasonal_factor_used         NUMERIC(6,3),
    safety_cushion               NUMERIC(14,2)
);
