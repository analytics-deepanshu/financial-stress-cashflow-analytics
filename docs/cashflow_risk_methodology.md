# Next-Month Cash-Flow Risk – Methodology

**Goal:** identify customers likely to run short of cash **next month**, early enough to act (a reminder, a payment-date change, a short-term relief offer).

Code: `src/cashflow_forecast.py`. Backtest: `src/validate_model.py` → `reports/model_validation.md`.

## 1. Method

For each customer, using only data up to the current month:

| Component | Estimate | Reasoning |
|---|---|---|
| **Expected income** | Stable earners (income CV < 0.15): **median of the last 3 months**. Volatile earners: **mean of the last 6 months**. | A median ignores one-off bonuses. A longer mean is fairer for freelancers whose income swings. |
| **Expected recurring outflows** | Median of the last 3 months of recurring debits: rent, EMI, utilities, insurance, subscriptions, SIP, debt repayments | These are contractual and highly predictable. The median ignores a missed or doubled month. |
| **Expected variable spend** | Weighted average of the last 3 months of non-recurring spend (weights 0.2 / 0.3 / 0.5, most recent heaviest), excluding flagged outliers, × **portfolio seasonal index** for the target month | Recent behaviour is the best guide. The seasonal index adds the known Diwali uplift (October index ≈ 1.29, learned from Oct 2024). |
| **Seasonal one-offs** | School fees, if the customer paid them in the same calendar month before | These are known calendar events. |
| **Expected ending balance** | current balance + expected income − expected outflows | |
| **Uncertainty (σ)** | Standard deviation of the customer's monthly balance change over the last 6 months (borrowing excluded), with a floor of 5% of expected income | Each customer's own volatility, so a gig worker gets a wider range than a salaried employee. |
| **Safety cushion** | 25% of expected monthly outflows | Income and bills land on different days. A month-end balance that is positive but thin still means the account runs dry mid-month (rent on the 3rd, salary on the 7th). |
| **Deficit probability** | P(ending balance < cushion) = Φ((cushion − expected_end) ÷ σ) | Normal approximation. |
| **Risk tier** | High ≥ 50%, Medium 20–50%, Low < 20% | |

## 2. Backtest (no look-ahead)

There were six one-month-ahead forecasts (target months Apr–Sep 2025), each built only from data before the target month, giving 720 customer-month forecasts in total. A "cash crunch" means the customer had to borrow during the month, or would have ended below zero without borrowing.

| Metric | Result |
|---|---|
| Income forecast error (weighted MAPE) | 10.3% |
| Outflow forecast error (weighted MAPE) | 14.3% |
| Median absolute error of ending balance | ₹7,139 (≈ 9% of a month's income) |
| Base rate of cash crunch | 3.8% of customer-months |
| Crunch rate when flagged **High** | 44% (≈ 12× the base rate) |
| Crunch rate when flagged **Medium** | 26% |
| Crunch rate when **Low** | 1% |
| Recall (High + Medium) | 67% of real crunches were flagged a month ahead |
| AUC | 0.96 |

**Why the cushion is 25%:** cushions of 0%, 25%, 50%, 75% and 100% of expected outflows were tested on the pooled backtest. At 0%, only a third of crunches were caught, because most crunches are intra-month timing problems rather than month-end deficits. 25% doubled recall to 67% with 50 flags across the 720 forecasts. 50% would catch 81% but needs 77 flags, and 100% catches everything but needs 138 flags. 25% was chosen as the balance point for a contact-based intervention. This choice was made on the same window it is evaluated on, so the precision and recall above are slightly optimistic.

## 3. Assumptions

1. Next month looks like the recent past, adjusted for portfolio seasonality.
2. Recurring obligations continue at their recent level. New loans or cancelled subscriptions are not anticipated.
3. Monthly balance changes are roughly normally distributed. This is approximate: shocks (hospital bills, job loss) make the true distribution fat-tailed.
4. The seasonal index is portfolio-wide. Individual festive habits differ.
5. The customer has no other accounts to draw on.

## 4. Limitations

- **Shocks are not predictable from history.** A first-time medical emergency or job loss will be missed. This explains most of the remaining misses (false negatives).
- **Intra-month timing is modelled with a fixed cushion.** A day-level cash-flow simulation (salary day vs rent and EMI days) would be more precise.
- **Twelve months of history** means each calendar month is seen only once. The seasonal index for September is 1.0 because there is no prior September.
- **Small sample of events** (27 crunches in the backtest). The tier crunch rates have wide confidence intervals.
- **Synthetic data.** The method should be re-validated on real data before it informs any customer-facing decision.

## 5. How it would be used

| Tier | Suggested action | Cost of a false alarm |
|---|---|---|
| High | Contact this week: offer to realign EMI or auto-debit dates to after salary day, or a short-term relief product | A phone call |
| Medium + High/Critical stress band | Proactive budget nudge and low-balance alerts | A push notification |
| Medium | Low-balance alert only | Negligible |

Because a false alarm costs little and a missed crunch can push a customer to a high-cost instant-loan app, the threshold deliberately favours **recall over precision**.
