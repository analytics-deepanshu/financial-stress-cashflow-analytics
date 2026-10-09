# DAX Measures

Create a blank table named **`_Measures`** (Home → Enter data → name it `_Measures`, delete the column after adding the first measure) and add every measure below to it. Folder names in brackets help organise the Fields pane (Measure tools → Display folder).

Table and column names match the CSVs in `data/powerbi/`. Relationships are listed in `POWERBI_BUILD_GUIDE.md`.

---

## [01 Core cash flow]

```DAX
Total Income =
CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[income_expense] = "Income" )
```
Salary, freelance, family support, stipend and interest credits. Borrowed money is excluded on purpose: counting a loan-app credit as income would make a struggling customer look healthier.

```DAX
Total Expenses =
CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[income_expense] = "Expense" )
```
Consumption plus fixed obligations (rent, EMI, insurance, debt repayment). SIP investments are excluded because they are savings.

```DAX
Total Invested =
CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[income_expense] = "Investment" )

Total Borrowed =
CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[income_expense] = "Borrowing" )
```

```DAX
Net Cash Flow = [Total Income] - [Total Expenses]
```

```DAX
Savings Rate = DIVIDE ( [Net Cash Flow], [Total Income] )
```
This is the headline health ratio. `DIVIDE` returns BLANK instead of an error when income is zero (for example, a job-loss month).

```DAX
Expense to Income Ratio = DIVIDE ( [Total Expenses], [Total Income] )
```

## [02 Spend structure]

```DAX
Fixed Obligations =
CALCULATE ( [Total Expenses], dim_category[spend_type] = "Fixed Obligation" )

Essential Variable Spend =
CALCULATE ( [Total Expenses], dim_category[spend_type] = "Essential Variable" )

Discretionary Spend =
CALCULATE ( [Total Expenses], dim_category[spend_type] = "Discretionary" )

Essential Spend = [Fixed Obligations] + [Essential Variable Spend]

Discretionary Share = DIVIDE ( [Discretionary Spend], [Total Expenses] )
```

```DAX
Fixed Obligation Ratio = DIVIDE ( [Fixed Obligations], [Total Income] )
```
This works like a bank's FOIR. Above about 50%, most lenders would decline new credit, which is why the stress score treats 60% as maximum stress.

```DAX
Recurring Expenses =
CALCULATE ( [Total Expenses], fact_transactions[recurring_flag] = 1 )

Recurring Share = DIVIDE ( [Recurring Expenses], [Total Expenses] )
```

```DAX
Expense Txn Count =
CALCULATE ( COUNTROWS ( fact_transactions ), fact_transactions[income_expense] = "Expense" )

Avg Transaction Value = DIVIDE ( [Total Expenses], [Expense Txn Count] )
```

## [03 Time intelligence]

`dim_date` must be marked as a date table: select `dim_date`, then Table tools → Mark as date table → `date`.

```DAX
Income Prev Month =
CALCULATE ( [Total Income], DATEADD ( dim_date[date], -1, MONTH ) )

Income MoM % = DIVIDE ( [Total Income] - [Income Prev Month], [Income Prev Month] )

Expenses Prev Month =
CALCULATE ( [Total Expenses], DATEADD ( dim_date[date], -1, MONTH ) )

Expenses MoM % = DIVIDE ( [Total Expenses] - [Expenses Prev Month], [Expenses Prev Month] )
```

```DAX
Cumulative Net Cash Flow =
CALCULATE (
    [Net Cash Flow],
    FILTER ( ALLSELECTED ( dim_date[date] ), dim_date[date] <= MAX ( dim_date[date] ) )
)
```
This is a running total that respects the date slicer.

```DAX
Expenses 3M Rolling Avg =
DIVIDE (
    CALCULATE ( [Total Expenses], DATESINPERIOD ( dim_date[date], MAX ( dim_date[date] ), -3, MONTH ) ),
    3
)
```
It smooths festive and school-fee spikes so the trend line is readable.

## [04 Behaviour]

```DAX
Weekend Spend per Day =
DIVIDE (
    CALCULATE ( [Total Expenses], dim_date[is_weekend] = 1, fact_transactions[recurring_flag] = 0 ),
    CALCULATE ( COUNTROWS ( dim_date ), dim_date[is_weekend] = 1 )
)

Weekday Spend per Day =
DIVIDE (
    CALCULATE ( [Total Expenses], dim_date[is_weekend] = 0, fact_transactions[recurring_flag] = 0 ),
    CALCULATE ( COUNTROWS ( dim_date ), dim_date[is_weekend] = 0 )
)

Weekend Uplift % = DIVIDE ( [Weekend Spend per Day], [Weekday Spend per Day] ) - 1
```
These compare spend **per day**, because there are about 2.5 times as many weekdays as weekend days. Comparing raw totals would wrongly make weekdays look bigger.

```DAX
Merchant Share of Spend =
DIVIDE ( [Total Expenses], CALCULATE ( [Total Expenses], ALL ( dim_merchant ) ) )

Top 5 Merchant Share =
VAR Top5 = TOPN ( 5, ALL ( dim_merchant[merchant] ), [Total Expenses] )
RETURN DIVIDE ( CALCULATE ( [Total Expenses], Top5 ), CALCULATE ( [Total Expenses], ALL ( dim_merchant ) ) )

Category Rank = RANKX ( ALL ( dim_category[category] ), [Total Expenses], , DESC, DENSE )
```

```DAX
Borrowing Customers =
CALCULATE ( DISTINCTCOUNT ( fact_transactions[customer_id] ), fact_transactions[income_expense] = "Borrowing" )

Borrowing Events =
CALCULATE ( COUNTROWS ( fact_transactions ), fact_transactions[income_expense] = "Borrowing" )
```

## [05 Balances]

```DAX
Avg Month-End Balance = AVERAGE ( fact_customer_month[month_end_balance] )

Latest Total Balance =
VAR LastMonth = MAX ( fact_customer_month[month_start] )
RETURN CALCULATE ( SUM ( fact_customer_month[month_end_balance] ), fact_customer_month[month_start] = LastMonth )

Deficit Months =
CALCULATE ( COUNTROWS ( fact_customer_month ), fact_customer_month[is_deficit_month] = 1 )

Deficit Month Rate = DIVIDE ( [Deficit Months], COUNTROWS ( fact_customer_month ) )
```

## [06 Stress & risk]

```DAX
Customers = COUNTROWS ( dim_customer )

Avg Stress Score = AVERAGE ( dim_customer[stress_score] )

High+Critical Customers =
CALCULATE ( [Customers], dim_customer[stress_band] IN { "High", "Critical" } )

% High+Critical = DIVIDE ( [High+Critical Customers], [Customers] )

Customers <1 Month Buffer =
CALCULATE ( [Customers], dim_customer[buffer_months] < 1 )

Median Buffer Months = MEDIAN ( dim_customer[buffer_months] )
```

```DAX
At-Risk Next Month =
CALCULATE ( [Customers], dim_customer[cashflow_risk_tier] IN { "High", "Medium" } )

Projected Shortfall = SUM ( dim_customer[projected_shortfall] )

Avg Deficit Probability = AVERAGE ( dim_customer[deficit_probability] )
```

```DAX
Avg Stress Score (History) = AVERAGE ( fact_stress_history[stress_score] )
```
Use this on a line chart with `dim_date[month_start]` to show whether stress is building over time.

```DAX
Risk Flags =
VAR sr   = SELECTEDVALUE ( dim_customer[savings_rate_6m] )
VAR foir = SELECTEDVALUE ( dim_customer[fixed_obligation_ratio_6m] )
VAR buf  = SELECTEDVALUE ( dim_customer[buffer_months] )
VAR cv   = SELECTEDVALUE ( dim_customer[income_cv] )
VAR p    = SELECTEDVALUE ( dim_customer[deficit_probability] )
RETURN
    ( sr < 0 ) + ( foir > 0.5 ) + ( buf < 1 ) + ( cv > 0.3 ) + ( p >= 0.2 )
```
This counts how many of five red flags a customer has: negative savings, obligations above 50%, under one month of buffer, volatile income, and a forecast cash shortfall. It is used on the Customer Deep Dive cards.

## [07 Formatting & dynamic text]

```DAX
Stress Band Colour =
SWITCH (
    SELECTEDVALUE ( dim_customer[stress_band] ),
    "Low", "#0CA30C", "Moderate", "#FAB219", "High", "#EC835A", "Critical", "#D03B3B",
    "#898781"
)

Risk Tier Colour =
SWITCH (
    SELECTEDVALUE ( dim_customer[cashflow_risk_tier] ),
    "Low", "#0CA30C", "Medium", "#FAB219", "High", "#D03B3B", "#898781"
)
```
Apply these with Format → Conditional formatting → Field value. Always show the band **name** next to the colour as well, so the colour never carries meaning on its own.

```DAX
Selected Customer = SELECTEDVALUE ( dim_customer[customer_label], "All customers" )

Deep Dive Title = "Customer deep dive: " & [Selected Customer]

Top Driver Text =
"Main stress driver: " & SELECTEDVALUE ( dim_customer[top_stress_driver], "n/a" )

Forecast Text =
VAR p = SELECTEDVALUE ( dim_customer[deficit_probability] )
RETURN
    IF ( ISBLANK ( p ), BLANK (),
         "Next month: " & SELECTEDVALUE ( dim_customer[cashflow_risk_tier] ) & " risk ("
         & FORMAT ( p, "0%" ) & " chance of a cash shortfall)" )
```
