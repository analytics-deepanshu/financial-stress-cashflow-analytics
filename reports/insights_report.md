# Key Insights for Management

**Scope:** 120 customers · 41,135 cleaned transactions · Oct 2024 – Sep 2025 · synthetic data (seed 42)
**Format:** Finding → Evidence → Business impact → Recommendation

Numbers come from `reports/key_metrics.json`, `sql/results/` and `reports/model_validation.md`. If the data is regenerated with another seed, rerun the pipeline and refresh these figures.

---

### 1. Gig workers and students are in deficit most months, not occasionally

- **Finding:** For freelance/gig customers and students, spending more than they earn is the normal state.
- **Evidence:**
  - Deficit months by group: students **78%** of months, gig workers **57%**, salaried customers **18%**.
  - Median 12-month savings rate: students **−16%**, gig workers **5.6%**, salaried **15.0%**.
  - Average stress score: students 56.6, gig workers 41.6, salaried 21.6.
  - Every student (6 of 6) borrowed at least once, against 9 of 96 salaried customers (SQL Q03, Q17).
- **Business impact:** These two groups are 20% of customers but 55% of the customers who borrowed (11 of 20). Generic budgeting tips will not fix a structural income problem.
- **Recommendation:**
  - For gig workers, offer an **income-smoothing feature**: a sweep account that pays a fixed "salary" from a buffer each month.
  - For students, set **low-balance alerts** and avoid offering instant credit.
  - Track these segments separately on the dashboard (occupation slicer).

### 2. Committing more than half of income to fixed obligations is the clearest structural risk signal

- **Finding:** Customers whose rent, EMI, insurance and debt repayments exceed 50% of income have almost three times the stress score of everyone else.
- **Evidence:**
  - **18 customers (15%)** are over the 50% "lender limit". Their average stress score is **54**, against **20** for those under 30% (SQL Q09).
  - Of the 17 over 50% in the last 6 months, **none** scored Low: 10 Moderate, 6 High, 1 Critical.
  - Fixed obligations are the second-largest driver of the score for High/Critical customers (10.8 points on average).
- **Business impact:** These customers cannot adjust spending when income dips, because the money is committed before the month starts. Any new credit offered to them adds directly to default risk.
- **Recommendation:**
  - Add a **fixed-obligation-ratio check (≤ 50%) to every credit and pre-approved-loan decision**.
  - Offer **tenure extension or loan consolidation** to the 18 customers already over the limit.

### 3. 30% of customers could not survive three months without income

- **Finding:** Emergency buffers are thin for a large minority.
- **Evidence:**
  - **15 customers (12.5%)** hold less than one month of essential spending, and another **21** hold 1–3 months, so **36 customers (30%)** are below the 3-month guideline (SQL Q18).
  - The median buffer is **0.8 months** in the High band, against **9.4 months** in the Low band.
- **Business impact:** For these customers, one delayed salary or medical bill turns directly into borrowing. Buffer is the second-largest score driver for stressed customers (16.9 points on average).
- **Recommendation:**
  - Launch an **automated "buffer builder"**: round-ups plus a small auto-sweep on salary day, with a 3-month target shown in-app.
  - Prioritise the 15 customers below one month.

### 4. Diwali overspending turns into borrowing in December and January

- **Finding:** Festive spending is not absorbed in the month it happens. It shows up as borrowing one to two months later.
- **Evidence:**
  - Oct–Nov spending is **+13%** above the average of other months, with Shopping at **+59%** and Travel at **+27%** (SQL Q16).
  - December has the year's **lowest savings rate (12.4%)**.
  - **December and January account for 19 of 58 borrowing months (33%)** although they are only 2 of 12 months.
  - The October 2025 forecast already applies a **+29% seasonal index** to variable spend.
- **Business impact:** The festive season is predictable, yet it pushes customers towards high-cost credit (cards and instant-loan apps) every year.
- **Recommendation:**
  - Run a **pre-festive campaign in September**: a "festive fund" goal plus a spending plan.
  - Schedule extra monitoring for **High/Medium-tier customers in Dec–Jan**.

### 5. One instant-loan or card advance almost always leads to more

- **Finding:** Short-term borrowing is a spiral, not a one-off.
- **Evidence:**
  - **17 customers** borrowed from a credit-card cash advance or instant-loan app; **16 of them (94%) borrowed again**, averaging **3.9 further borrowing events** (SQL Q19).
  - Instant-loan apps are the largest source of borrowing (**44%** of events).
  - Repayments now consume **7% of these customers' income**.
- **Business impact:** Each repayment instalment reduces next month's cash, which triggers the next loan. The customer drifts into a debt spiral while their bank balance looks "fine" because of the borrowed money.
- **Recommendation:**
  - Treat the **first borrowing event as a trigger**: contact within 7 days and offer a lower-cost alternative (overdraft at bank rates) or a repayment plan.
  - Count borrowed credits **out of income** in every affordability check, as this project does.

### 6. Lifestyle creep is invisible in balances but visible in de-seasonalised spend

- **Finding:** A group of stable-income customers is quietly spending much faster than they earn.
- **Evidence:**
  - Comparing two "ordinary" quarters (Jan–Mar vs Jul–Sep 2025, so festive and school-fee peaks cannot distort the result), **10 customers** grew core spending **+23% to +32%** while income grew only **+4% to +11%** (SQL Q12).
  - **9 of them are still Low or Moderate stress**, because their balances have not yet dropped.
- **Business impact:** At this pace the savings margin erodes by about 20 percentage points every six months. Most of these customers will reach High stress within a year, and today is the cheapest point to intervene.
- **Recommendation:**
  - Send **trend-based alerts** ("your spending is up 25% vs Q1 while income is flat"), driven by the expense-growth factor.
  - Report "rising-stress" customers separately from "high-stress" customers.

### 7. The Stress Score is a reliable early-warning tool, so outreach can be focused

- **Finding:** The score predicts who will borrow next month, so resources can go where they matter.
- **Evidence:**
  - Over 720 customer-months, the **next-month borrowing rate** by band was:

    | Band | Next-month borrowing rate |
    |---|---|
    | Low | **0%** |
    | Moderate | **4.6%** |
    | High | **16.7%** |
    | Critical | **75%** (n = 4) |

  - AUC = **0.93**.
  - Only **13 customers (11%)** are currently High or Critical (`reports/model_validation.md`).
- **Business impact:** Low-band customers (60%) needed no intervention in the test period. Focusing on the top two bands covers most real distress with a small contact list.
- **Recommendation:** Recalculate the score **monthly**, and route High and Critical customers to a relationship-manager queue with the top driver shown, so the conversation starts with the actual cause.

### 8. Nine customers are likely to run short of cash in October 2025, and two-thirds of them would be missed by the stress band alone

- **Finding:** The next-month forecast catches timing-driven shortfalls that the slower-moving stress score does not.
- **Evidence:**
  - **6 High and 3 Medium** risk customers were flagged for October 2025.
  - **6 of the 9 sit in the Moderate stress band**, not High or Critical (SQL Q20).
  - In the backtest, customers flagged **High** had a cash crunch **44%** of the time, against a **3.8%** base rate (about **12× lift**). Recall for High + Medium was **67%**.
- **Business impact:** Using the stress band alone would miss most of next month's actual shortfalls. The two tools answer different questions: *who is fragile* (score) and *who is about to run out* (forecast).
- **Recommendation:**
  - Run the **forecast watch-list weekly in the last 10 days of each month**.
  - Offer High-tier customers an **EMI or auto-debit date realignment to after salary day**. This is cheap, and it removes the intra-month gap that causes most crunches.

### 9. Weekend spending drives a disproportionate share of discretionary spend

- **Finding:** Discretionary spending is concentrated on weekends.
- **Evidence:**
  - Weekends are 29% of days but carry **40% of discretionary spend**.
  - Overall weekend spend per day is **+47%** higher than on weekdays.
  - Food delivery is **+73%** higher per day, and shopping **+66%** (SQL Q08).
- **Business impact:** For stressed customers, the weekend is when the budget breaks. A weekday-only nudge strategy misses the moment of decision.
- **Recommendation:**
  - Time spending nudges for **Friday evening**.
  - Offer opt-in **weekend spending caps** for High-stress customers.
  - Partner offers for food delivery should not be pushed to High/Critical customers.

### 10. Tier 1 city customers are more stressed than Tier 3, despite higher incomes

- **Finding:** Location affects financial resilience more than income level suggests.
- **Evidence:**
  - Average stress score is **30.0 in Tier 1** against **12.1 in Tier 3**.
  - Median savings rate is **9.2% in Tier 1** against **22.8% in Tier 3**.
  - Rent is the second-largest spend category (15% of all spending), and Tier 1 rents take the biggest share of income.
- **Business impact:** Income-based targeting ("high income = low risk") would mis-rank customers. A ₹1 lakh earner in Mumbai can be more fragile than a ₹75,000 earner in Mysuru.
- **Recommendation:**
  - Use **city-tier-adjusted affordability** (cost-of-living factor) in product eligibility.
  - Show tier as a standard slicer in risk reporting.

### 11. Without balance reconciliation, a 0.3% data error would have overstated spending by 27%

- **Finding:** A tiny share of unit errors can distort every downstream number.
- **Evidence:**
  - **123 transactions (0.3%)** had amounts recorded in paise instead of rupees. If uncaught, they would have inflated total expenses by **₹2.9 crore (27%)**.
  - All 123 were found by reconciling each amount against the change in account balance.
  - Exact duplicates alone would have added another 1%.
  - Every injected issue type was detected, and zero balance-chain breaks remain (`reports/data_quality_report.md`).
- **Business impact:** Savings rates, stress scores and forecasts built on unreconciled data would be materially wrong, and wrong in the direction of over-reporting stress.
- **Recommendation:** Make **balance reconciliation a mandatory automated check** in the data pipeline, and treat the account balance as the system of record.

---

## Summary of recommended actions

| Priority | Action | Who it targets | Expected effect |
|---|---|---|---|
| 1 | Weekly forecast watch-list + EMI / auto-debit date realignment | 9 customers flagged for Oct 2025 | Prevents intra-month shortfalls and the borrowing they trigger |
| 2 | Contact after first card or loan-app borrowing | 17 formal borrowers, plus every future first-time borrower | Breaks the 94% repeat-borrowing pattern |
| 3 | Fixed-obligation ratio ≤ 50% in all credit decisions; restructuring offers | 18 customers over the limit | Stops structural over-commitment |
| 4 | Buffer-builder sweeps (3-month target) | 36 customers under 3 months of buffer | Converts shocks from "borrow" to "absorb" |
| 5 | September pre-festive campaign | All customers, especially Moderate+ | Flattens the Dec–Jan borrowing peak |
| 6 | Trend alerts for rising spend | 10 lifestyle-creep customers | Cheapest intervention, made before stress appears |
