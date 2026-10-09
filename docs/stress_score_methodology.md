# Financial Stress Score – Methodology

**Goal:** give every customer one transparent number from 0 to 100 that says how close they are to being unable to absorb a bad month. Higher means more stress. Every point in the score can be traced to a factor, a benchmark and a weight. There is no black box.

Code: `src/stress_score.py`. Validation: `reports/model_validation.md`.

## 1. Design principles

1. **Benchmark-anchored scaling, not percentiles.** Each factor is scaled against an external guideline, such as the 20% savings rule or the 3–6 month emergency fund. Percentiles would always put 25% of customers in the "worst" quartile, even in a healthy portfolio. With benchmarks, a healthy portfolio scores low and a stressed one scores high.
2. **Recent window.** Ratios use the **last 6 months**, so the score reflects the current situation rather than a year-old one. Income stability uses all available months, because volatility needs a longer series to measure.
3. **No double counting.** The expense-to-income ratio equals 1 − savings rate, so it is **not** a separate factor. It is reported as a KPI. Factor 7 instead captures *how often* expenses exceeded income, which an average hides.
4. **Explainable.** The score is stored with each factor's sub-score and points, plus the top driver, so an analyst can tell a customer *why* they scored what they did.

## 2. The seven factors

Each raw value *x* is converted to a sub-score from 0 to 100 with a clipped linear scale:

```
sub = clip( (x − healthy_value) / (stress_value − healthy_value) × 100 , 0 , 100 )
```

This works in either direction. For example, a buffer of 6 months gives 0, and a buffer of 0.5 months gives 100.

| # | Factor | Measure | 0 stress at | 100 stress at | Weight | Why it matters | Benchmark source |
|---|---|---|---|---|---|---|---|
| 1 | **Savings margin** | (income − expenses) ÷ income, last 6 months | ≥ 20% | ≤ −10% | 20 | The money left over each month is the first line of defence against any shock. | The 50/30/20 budgeting rule (20% to savings). −10% means spending 10% more than earned. |
| 2 | **Fixed obligation ratio** | (rent + EMI + insurance + debt repayment) ÷ income, last 6 months | ≤ 30% | ≥ 60% | 20 | Committed outflows cannot be cut quickly. A high ratio leaves no room to adjust when income dips. | Indian lenders' FOIR (fixed obligation to income ratio) limits are typically around 40–55%. 60% is beyond what most would lend against. |
| 3 | **Emergency buffer** | current balance ÷ average monthly essential spend | ≥ 6 months | ≤ 0.5 month | 20 | This is how long the household can keep running if income stops. | The common "3–6 months of expenses" emergency-fund guideline. Under half a month means one late salary breaks the budget. |
| 4 | **Income instability** | coefficient of variation (std ÷ mean) of monthly income | ≤ 0.10 | ≥ 0.60 | 10 | Volatile income makes every fixed commitment riskier, even when the average is fine. | A CV of 0.10 is a salaried income with an occasional bonus. A CV of 0.60 means a typical month is 60% away from average. |
| 5 | **Expense growth** | trend of *de-seasonalised core spend* over 6 months (fitted line, end ÷ start − 1) | ≤ 0% | ≥ +25% | 10 | Lifestyle creep erodes savings before it shows up in the balance. It is a leading indicator. | +25% in 6 months is about 4% a month, a pace that turns a healthy saver into a deficit within a year. |
| 6 | **Balance trend** | change in balance over 6 months, in months of income | ≥ +0.5 | ≤ −1.0 | 10 | It confirms whether the household is building or burning reserves, using the bank's own ledger. | Losing one full month of income from savings in 6 months is a sustained drain. |
| 7 | **Deficit & borrowing** | max(share of deficit months ÷ 50%, borrowing months ÷ 2), capped at 1 | 0 | 1 | 10 | Repeated deficits and borrowing to cover them are the most direct observed signs of stress. | Deficit in half of the months, or borrowing in 2 of the last 6 months, already counts as maximum stress. |

**Details on factor 5.** "Core spend" excludes flagged one-off outliers (such as hospital bills) and school fees. Each month is divided by the portfolio's seasonal index for that month (1.0 = average month). Without this step, the Diwali months would look like "growth", or the drop after them would hide real creep.

## 3. Weights and the final score

```
stress_score = Σ ( sub_score_i × weight_i ) / Σ weight_i          (weights sum to 100)
```

- **Factors 1–3 (60%)** are *structural*: they decide whether a household can absorb a bad month at all.
- **Factors 4–7 (40%)** are *dynamic*: they describe direction and volatility, which shows whether things are getting worse.

**Bands:** 0–30 Low · 31–60 Moderate · 61–80 High · 81–100 Critical.

**Top driver:** the factor that contributes the most points. It is shown as "none" when the score is under 10.

## 4. Worked example

Customer C0115 (EMI-heavy salaried customer), as of Sep 2025:

| Factor | Raw value | Sub-score | Weight | Points |
|---|---|---|---|---|
| Savings margin | −27% | 100 | 20 | 20.0 |
| Fixed obligation ratio | 82% | 100 | 20 | 20.0 |
| Emergency buffer | 0.57 months | 99 | 20 | 19.7 |
| Income instability | 0.10 | 0 | 10 | 0.0 |
| Expense growth | −1% | 0 | 10 | 0.0 |
| Balance trend | −0.08 months | 39 | 10 | 3.9 |
| Deficit & borrowing | 1.0 | 100 | 10 | 10.0 |
| **Score** | | | | **73.6 → High** |

How to read it: this customer's income is perfectly stable, so the problem is *structural*. More than 80% of income is committed (EMI, rent, and repayments of earlier short-term borrowing) before any spending, and there is barely two weeks of buffer. Telling this customer to "spend less on food delivery" would not help. Loan restructuring would.

(The worked example in `notebooks/04_stress_score.ipynb` is recalculated live from the data.)

## 5. Validation summary

Full detail is in `reports/model_validation.md`.

| Test | Result |
|---|---|
| **Early warning:** stress band in month *m* vs borrowing in month *m+1* (720 customer-months) | Low 0% · Moderate 4.6% · High 16.7% · Critical 75% borrow next month. AUC 0.93 |
| **Persona ground truth** (only possible with synthetic data) | AUC 0.94 separating at-risk from healthy personas. All 30 Stable Savers scored Low. 18 of 18 EMI-Burdened customers scored Moderate or worse. |
| **Weight sensitivity** (equal weights instead) | 92% of customers keep the same band; rank correlation 0.98 |

**Known blind spot.** Shock-event customers who recovered before the scoring month score Low. The score measures *current* stress, not past stress. That is intended, but it means a recovered customer's reduced buffer only shows up through factor 3.

## 6. Limitations

- The thresholds are informed by guidelines, not fitted to default outcomes. With real loan-performance data, the weights should be re-estimated, for example with a logistic regression on 90-day delinquency, and the benchmarks kept as constraints.
- Linear scaling assumes each extra percentage point matters equally. A logistic curve could better reflect "cliff edges" such as a FOIR above 50%.
- Data covers one savings account per customer. Money held at other banks or in investments is invisible, so the buffer may be understated for some customers.
- Synthetic data: the validation results show that the method *works as designed*. They do not prove its performance on real customers.
