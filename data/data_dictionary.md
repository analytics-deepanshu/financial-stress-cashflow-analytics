# Data Dictionary

All amounts are in Indian Rupees (₹). The period covered is **1 Oct 2024 – 30 Sep 2025** (12 months). The default build has 120 customers and about 41,000 clean transactions (seed 42).

## Files by layer

| Layer | File | Grain | Produced by |
|---|---|---|---|
| Raw | `raw/transactions_raw.csv` | 1 row per transaction **with injected errors** | `generate_data.py` |
| Raw | `raw/customers_raw.csv` | 1 row per customer | `generate_data.py` |
| Raw (audit) | `raw/injected_issues_log.csv` | 1 row per injected issue | `generate_data.py` |
| Raw (hidden) | `raw/_ground_truth_transactions.csv`, `raw/_hidden_personas.csv` | truth copies, used **only** to grade cleaning and validate the score | `generate_data.py` |
| Processed | `processed/transactions_clean.csv` | 1 row per transaction | `clean_data.py` |
| Processed | `processed/customers_clean.csv` | 1 row per customer | `clean_data.py` |
| Processed | `processed/cleaning_log.csv` | 1 row per fix applied | `clean_data.py` |
| Analytics | `analytics/customer_month.csv` | 1 row per customer × month | `features.py` |
| Analytics | `analytics/customer_stress_score.csv` | 1 row per customer | `stress_score.py` |
| Analytics | `analytics/stress_score_history.csv` | 1 row per customer × scoring month | `stress_score.py` |
| Analytics | `analytics/cashflow_forecast.csv` | 1 row per customer (next month) | `cashflow_forecast.py` |
| Analytics | `analytics/validation_*.csv` | backtest / early-warning / persona checks | `validate_model.py` |
| Power BI | `powerbi/*.csv` | star schema | `export_powerbi.py` |

---

## transactions (raw and clean)

| Column | Type | Description | Example |
|---|---|---|---|
| `transaction_id` | text | Unique ID. IDs above TXN9000000 in the raw file are re-posted duplicates. | TXN0001234 |
| `customer_id` | text | Customer key → customers | C0042 |
| `date` | timestamp | Date and time of posting. In raw, mixed formats and some year typos. | 2025-03-14 19:42:00 |
| `transaction_type` | text | `Credit` (money in) or `Debit` (money out) | Debit |
| `category` | text | One of 25 standard categories (see below) | Food Delivery |
| `subcategory` | text | Finer grouping within the category | Food Delivery App |
| `merchant` | text | Counterparty. `Unknown Merchant` where unrecoverable. | Swiggy |
| `amount` | number | Positive transaction value in ₹. In raw, can be text, negative, or recorded in paise. | 486.20 |
| `payment_method` | text | UPI, UPI Autopay, Credit Card, Debit Card, Net Banking, NEFT, IMPS, Auto-Debit (NACH), ATM/Cash, Bank Credit | UPI |
| `income_expense` | text | `Income`, `Expense`, `Investment` (SIP) or `Borrowing` | Expense |
| `account_balance` | number | Savings-account balance **after** this transaction. This is the system of record. | 84,312.55 |
| `recurring_flag` | 0/1 | 1 = scheduled, repeating payment or credit (salary, rent, EMI, SIP, utilities, subscriptions, insurance, debt repayment) | 0 |
| `location` | text | Customer's city for in-person spend, `Online` for e-commerce and app payments | Pune |
| `monthly_income` | number | Declared monthly income (copied from customer master) | 85,000 |
| `financial_goal` | text | Customer's stated goal (copied from customer master) | Home Down Payment |

**Added by cleaning** (clean file only):

| Column | Type | Description |
|---|---|---|
| `is_outlier` | 0/1 | Flagged as an outlier (robust z-score > 3.5 within its subcategory, **or** a one-off debit larger than monthly income). Kept, not deleted. |
| `exceeds_monthly_income` | 0/1 | A single debit larger than declared monthly income |
| `signed_amount` | number | +amount for credits, −amount for debits |
| `year_month` | text | `YYYY-MM` |
| `txn_date` | date | Date part of `date` |
| `day_of_week` | text | Monday…Sunday |
| `is_weekend` | 0/1 | Saturday or Sunday |
| `spend_type` | text | `Fixed Obligation`, `Essential Variable`, `Discretionary`, `Investment`, or `Not Spend` (income and borrowing) |

## Category reference

| Spend type | Categories |
|---|---|
| Income (credits) | Salary, Freelance Income, Family Support, Part-time Income, Interest |
| Borrowing (credits) | Borrowing: Credit Card Cash Advance, Instant Loan App, Borrowed from Family |
| Fixed Obligation | Housing (rent), Loan EMI, Insurance, Debt Repayment |
| Essential Variable | Groceries, Utilities, Transport, Healthcare, Education |
| Discretionary | Food Delivery, Dining Out, Shopping, Entertainment, Travel, Personal Care, Subscriptions, Cash Withdrawal, Gifts & Festivals |
| Investment | Investments (mutual fund SIP) |

## customers

| Column | Type | Description |
|---|---|---|
| `customer_id` | text | Primary key |
| `age_band` | text | 18-22, 21-25, 26-30, 31-40, 41-50, 51-60 |
| `city`, `city_tier` | text | 22 Indian cities in Tier 1 / 2 / 3 |
| `occupation_type` | text | Salaried, Freelancer/Gig, Student |
| `declared_monthly_income` | number | Monthly income at the start of the period (before the April increment) |
| `financial_goal` | text | Emergency Fund, Home Down Payment, Debt Repayment, Retirement, Child Education, Travel, Wealth Creation, Vehicle Purchase |
| `has_active_loan` | boolean | Customer pays a loan EMI |
| `income_band` | text | <25K, 25K-50K, 50K-1L, 1L-1.5L, 1.5L+ (added by cleaning) |

## customer_month (key columns)

| Column | Definition |
|---|---|
| `income` | Sum of Income credits (borrowing excluded) |
| `expenses` | Sum of Expense debits (SIP excluded) |
| `core_expenses` | Expenses excluding flagged outliers and school fees (used for trend detection) |
| `investment`, `borrowing` | SIP outflows; borrowed inflows |
| `fixed_obligations` | Rent + EMI + insurance + debt repayment |
| `essential_variable`, `discretionary` | Spend by spend type |
| `essential_spend` | fixed_obligations + essential_variable |
| `net_cash_flow` | income − expenses |
| `savings_rate` | net_cash_flow ÷ income (clipped to [−2, 1]) |
| `expense_to_income`, `fixed_obligation_ratio` | expenses ÷ income; fixed_obligations ÷ income |
| `balance_change` | Sum of all signed amounts (what the bank balance did) |
| `opening_balance`, `month_end_balance`, `month_min_balance` | Balance at the start of the month, at the end, and the lowest point within the month |
| `is_deficit_month` | 1 if net_cash_flow < 0 |
| `borrowed_this_month`, `n_borrow_events` | Borrowing indicator and count |
| `weekend_spend`, `weekday_spend` | Expenses split by day type |

## customer_stress_score (key columns)

| Column | Definition |
|---|---|
| `savings_rate_6m` … `deficit_borrow_index` | Raw factor values (see `docs/stress_score_methodology.md`) |
| `sub_<factor>` | Factor scaled to 0–100 |
| `contrib_<factor>` | Points the factor adds to the score (sub × weight ÷ 100) |
| `stress_score` | 0–100 |
| `stress_band` | Low (0–30), Moderate (31–60), High (61–80), Critical (81–100) |
| `top_stress_driver` | Factor contributing the most points (`none` if score < 10) |

## cashflow_forecast (key columns)

| Column | Definition |
|---|---|
| `expected_income`, `expected_outflows` | Next-month estimates (outflows include SIP and debt repayment) |
| `expected_ending_balance` | current_balance + expected_income − expected_outflows |
| `safety_cushion` | 25% of expected outflows |
| `uncertainty_sigma` | Standard deviation of the customer's monthly balance change (last 6 months, borrowing excluded) |
| `deficit_probability` | P(ending balance < safety cushion) |
| `cashflow_risk_tier` | High ≥ 50%, Medium 20–50%, Low < 20% |
| `projected_shortfall` | max(0, −expected_ending_balance) |
