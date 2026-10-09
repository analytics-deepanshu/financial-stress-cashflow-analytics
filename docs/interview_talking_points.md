# Interview Talking Points

## The 60-second pitch

> "I built a financial-stress early-warning system on 41,000 bank transactions for 120 customers.
>
> I cleaned the data in a way I could measure. I injected 13 kinds of real-world errors and showed my pipeline caught all of them. Reconciling every amount against the account balance found unit errors that would have overstated spending by 27%.
>
> Then I built a transparent 0–100 stress score from seven factors anchored to real benchmarks, like the 20% savings rule and banks' 50% obligation limits. I also built a next-month cash-shortfall forecast.
>
> I validated both. Customers the score called High borrowed the next month 17% of the time, against 0% for Low. The forecast's High tier had a cash crunch 44% of the time, against a 3.8% base rate.
>
> I finished with 20 SQL analyses, a 4-page Power BI design and 11 management recommendations, such as moving EMI dates to after salary day for flagged customers."

## Questions you will likely get, with honest answers

**"Why synthetic data?"**
No public dataset has many customers with a running balance that reconciles, and I wanted to validate my score against known ground truth. Each customer has a hidden persona that the analysis never sees. That let me prove the score separates at-risk from healthy customers (AUC 0.94), which is impossible with unlabelled real data. The trade-off is that results show the method works, not how real customers behave.

**"Why these weights?"**
The three structural factors (savings, obligations, buffer) get 60%, because they decide whether someone can absorb a bad month. The dynamic factors (volatility, growth, trend, borrowing) get 40%. I tested equal weights: 92% of customers kept the same band and the rank correlation was 0.98. So conclusions about *who* is most stressed do not depend on my exact choice. With real default data, I would fit the weights with logistic regression.

**"Why not use the expense-to-income ratio?"**
It equals 1 − savings rate, so including both double-counts the same signal. I report it as a KPI, and used deficit *frequency* instead, because an average can hide repeated bad months.

**"Why did expense growth need de-seasonalising?"**
My first version compared the last 3 months with the previous 3. Because of Diwali and school fees, it found almost nobody with lifestyle creep. Dividing by a portfolio seasonal index and fitting a 6-month trend fixed it. The SQL version compares two "ordinary" quarters (Jan–Mar vs Jul–Sep), and 9 of the 10 customers it flags were the lifestyle-creep persona.

**"How do you know the forecast works?"**
I ran a backtest with no look-ahead: six monthly forecasts, 720 in total. Income error was 10% and outflow error 14%. The High tier had a cash crunch 44% of the time, about 12 times the 3.8% base rate. I'm upfront that I chose the 25% safety cushion on the same window, so these numbers are slightly optimistic.

**"What would you do differently in a real job?"**
- Calibrate the score against real delinquency outcomes.
- Simulate cash flow at day level (salary date vs EMI date).
- Compare against a gradient-boosting model.
- A/B test the interventions, to show that date realignment actually reduces borrowing.

**"What was the hardest part?"**
Making the data internally consistent. Balances had to reconcile even when customers ran out of money. I solved it by having the simulation borrow when a payment would overdraw the account, with repayments scheduled over the next three months. That also produced a realistic debt-spiral pattern for the analysis to find.

## Numbers to remember

| | |
|---|---|
| 41,135 | clean transactions |
| 120 | customers |
| 12 | months |
| 7,551 | injected data issues, all 13 types detected |
| 27% | spend overstatement prevented by balance reconciliation |
| 0% / 16.7% / 75% | next-month borrowing rate for Low / High / Critical |
| AUC 0.93 | score as an early warning for borrowing |
| AUC 0.94 | score against hidden personas |
| 44% vs 3.8% | crunch rate when the forecast says High, vs the base rate |
| 94% | repeat-borrowing rate after the first loan-app or card advance |
