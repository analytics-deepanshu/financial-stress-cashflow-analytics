"""
Synthetic transaction generator for the Financial Stress & Cash-Flow Risk project.

How it works (short version):
1. Create customers, each with a hidden *persona* (e.g. EMI-Burdened, Irregular Earner).
   The persona sets income level, income volatility, spending ratio, loans, SIPs and buffer.
2. Simulate each customer month by month:
      income credits  -> fixed obligations (rent, EMI, utilities, insurance, SIP, subscriptions)
      -> variable spending split across categories with weekend + festive seasonality
      -> scheduled repayments of any earlier short-term borrowing.
3. Post transactions in time order and keep a running account balance.
   If a debit would push the balance below a floor, the customer *borrows*
   (credit-card cash advance, instant-loan app, family) and repays it over the next 3 months.
   This makes balances internally consistent and produces a realistic debt-spiral signal.
4. Save a clean "truth" copy, then inject logged data-quality issues into the RAW file.

Run:  python src/generate_data.py
"""
from __future__ import annotations

import calendar
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------------------
CITIES = {
    1: ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Pune", "Kolkata", "Ahmedabad"],
    2: ["Jaipur", "Lucknow", "Indore", "Chandigarh", "Kochi", "Nagpur", "Bhopal", "Coimbatore"],
    3: ["Patna", "Dehradun", "Ranchi", "Mysuru", "Guwahati", "Udaipur"],
}
TIER_WEIGHTS = {1: 0.55, 2: 0.30, 3: 0.15}
RENT_TIER_FACTOR = {1: 1.0, 2: 0.78, 3: 0.62}

KIRANA_STORES = ["Sharma General Store", "Gupta Kirana", "Balaji Provision Store", "Annapurna Stores",
                 "Sri Lakshmi Stores", "Patel Kirana", "Krishna Super Mart", "New Bharat Stores",
                 "Ganesh Provisions", "Royal Daily Needs", "Mahalaxmi Kirana", "City Fresh Mart"]

GOALS = ["Emergency Fund", "Home Down Payment", "Debt Repayment", "Retirement",
         "Child Education", "Travel", "Wealth Creation", "Vehicle Purchase"]

# Variable-spend categories: subcategory -> merchants
VARIABLE = {
    "Groceries": {
        "Supermarket": ["DMart", "Reliance Smart", "More Supermarket", "Spencer's"],
        "Online Grocery": ["BigBasket", "Blinkit", "Zepto", "Swiggy Instamart"],
        "Kirana Store": ["Neighbourhood Kirana"],   # replaced by the customer's own local store
    },
    "Food Delivery": {"Food Delivery App": ["Swiggy", "Zomato"]},
    "Dining Out": {
        "Restaurant": ["Barbeque Nation", "Haldiram's", "Local Restaurant", "Domino's"],
        "Cafe": ["Starbucks", "Cafe Coffee Day", "Third Wave Coffee"],
    },
    "Transport": {
        "Ride Hailing": ["Uber", "Ola", "Rapido"],
        "Fuel": ["Indian Oil", "HP Petrol Pump", "Bharat Petroleum"],
        "Public Transport": ["Metro Card Recharge"],
    },
    "Shopping": {
        "Online Shopping": ["Amazon", "Flipkart", "Myntra", "Ajio", "Nykaa", "Meesho"],
        "Electronics": ["Croma", "Reliance Digital"],
        "Apparel Store": ["Westside", "Lifestyle", "Max Fashion"],
    },
    "Entertainment": {"Movies & Events": ["BookMyShow", "PVR INOX"],
                      "Gaming": ["Google Play", "Steam"]},
    "Travel": {
        "Flights": ["IndiGo", "Air India"],
        "Trains": ["IRCTC"],
        "Hotels": ["MakeMyTrip", "OYO", "Goibibo"],
    },
    "Healthcare": {
        "Pharmacy": ["Apollo Pharmacy", "PharmEasy", "Tata 1mg"],
        "Consultation": ["Practo", "Local Clinic"],
    },
    "Personal Care": {"Salon & Services": ["Urban Company", "Local Salon"],
                      "Fitness": ["Cult.fit"]},
    "Cash Withdrawal": {"ATM": ["ATM Withdrawal"]},
    "Education": {"Online Course": ["Coursera", "Udemy", "upGrad"]},
    "Gifts & Festivals": {
        "Festive Shopping": ["Festival Market", "Tanishq", "Sweets Shop"],
        "Gifts": ["Gift Purchase"],
    },
}
ONLINE_MERCHANTS = {
    "BigBasket", "Blinkit", "Zepto", "Swiggy Instamart", "Swiggy", "Zomato", "Amazon",
    "Flipkart", "Myntra", "Ajio", "Nykaa", "Meesho", "BookMyShow", "Google Play", "Steam",
    "IndiGo", "Air India", "IRCTC", "MakeMyTrip", "OYO", "Goibibo", "PharmEasy", "Tata 1mg",
    "Practo", "Coursera", "Udemy", "upGrad", "Urban Company", "Netflix", "Spotify",
    "Disney+ Hotstar", "Amazon Prime", "YouTube Premium",
}

# Probability a category is used in a given month, its typical ticket size (INR) and max count
PRESENCE = {"Groceries": 1.0, "Food Delivery": 0.85, "Dining Out": 0.55, "Transport": 0.95,
            "Shopping": 0.70, "Entertainment": 0.45, "Travel": 0.12, "Healthcare": 0.45,
            "Personal Care": 0.50, "Cash Withdrawal": 0.55, "Education": 0.06, "Gifts & Festivals": 0.0}
TICKET = {"Groceries": 1800, "Food Delivery": 450, "Dining Out": 1400, "Transport": 450,
          "Shopping": 2200, "Entertainment": 700, "Travel": 6000, "Healthcare": 900,
          "Personal Care": 900, "Cash Withdrawal": 2000, "Education": 2500, "Gifts & Festivals": 3000}
CAP = {"Groceries": 5, "Food Delivery": 6, "Dining Out": 3, "Transport": 5, "Shopping": 3,
       "Entertainment": 2, "Travel": 3, "Healthcare": 2, "Personal Care": 2, "Cash Withdrawal": 2,
       "Education": 1, "Gifts & Festivals": 3}
BUDGET_W = {"Groceries": 0.30, "Food Delivery": 0.09, "Dining Out": 0.07, "Transport": 0.12,
            "Shopping": 0.15, "Entertainment": 0.04, "Travel": 0.08, "Healthcare": 0.05,
            "Personal Care": 0.04, "Cash Withdrawal": 0.05, "Education": 0.03,
            "Gifts & Festivals": 0.0}
DISCRETIONARY_TILT = {"Food Delivery": 1.6, "Dining Out": 1.5, "Shopping": 1.6,
                      "Entertainment": 1.4, "Travel": 1.3, "Personal Care": 1.3}

# Seasonality on variable spend (calendar month -> multiplier)
SEASON = {1: 0.95, 2: 0.92, 3: 1.00, 4: 1.00, 5: 1.10, 6: 1.00,
          7: 0.95, 8: 1.00, 9: 0.97, 10: 1.25, 11: 1.20, 12: 1.15}
TRAVEL_MONTHS = {5: 2.5, 12: 2.0, 10: 1.5, 11: 1.3}

SUBSCRIPTIONS = {"Netflix": 649, "Spotify": 119, "Disney+ Hotstar": 299,
                 "Amazon Prime": 299, "YouTube Premium": 149}

PERSONAS = {
    "stable_saver": dict(occ="Salaried", inc=(55000, 200000), cv=(0.0, 0.0), exp=(0.55, 0.66),
                         sip=(0.10, 0.18), loan_p=0.30, emi=(0.08, 0.16), buf=(3.0, 8.0),
                         rent_p=0.60, tilt=0.8),
    "comfortable_spender": dict(occ="Salaried", inc=(40000, 160000), cv=(0.0, 0.0), exp=(0.84, 0.95),
                                sip=(0.0, 0.04), loan_p=0.35, emi=(0.08, 0.16), buf=(1.0, 2.5),
                                rent_p=0.75, tilt=1.5),
    "emi_burdened": dict(occ="Salaried", inc=(35000, 120000), cv=(0.0, 0.0), exp=(0.95, 1.06),
                         sip=(0.0, 0.0), loan_p=1.0, emi=(0.40, 0.55), buf=(0.4, 1.3),
                         rent_p=0.55, tilt=1.0),
    "irregular_earner": dict(occ="Freelancer/Gig", inc=(30000, 120000), cv=(0.35, 0.60),
                             exp=(0.82, 0.97), sip=(0.0, 0.04), loan_p=0.30, emi=(0.08, 0.18),
                             buf=(1.0, 3.0), rent_p=0.75, tilt=1.1),
    "lifestyle_creep": dict(occ="Salaried", inc=(45000, 150000), cv=(0.0, 0.0), exp=(0.70, 0.78),
                            sip=(0.0, 0.05), loan_p=0.50, emi=(0.10, 0.18), buf=(1.5, 3.0),
                            rent_p=0.75, tilt=1.4),
    "shock_event": dict(occ="Salaried", inc=(40000, 140000), cv=(0.0, 0.0), exp=(0.70, 0.84),
                        sip=(0.03, 0.10), loan_p=0.40, emi=(0.08, 0.18), buf=(1.5, 3.0),
                        rent_p=0.70, tilt=1.0),
    "student_early_career": dict(occ="Student", inc=(9000, 22000), cv=(0.0, 0.0), exp=(0.92, 1.05),
                                 sip=(0.0, 0.0), loan_p=0.0, emi=(0.0, 0.0), buf=(0.3, 1.2),
                                 rent_p=0.65, tilt=1.3),
}


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def load_config() -> dict:
    with open(ROOT / "config" / "generator_config.yaml") as f:
        return yaml.safe_load(f)


def month_list(start: str, n: int) -> list[pd.Timestamp]:
    first = pd.Timestamp(start)
    return [first + pd.DateOffset(months=i) for i in range(n)]


def ts(rng, month: pd.Timestamp, day: int, hour_range=(8, 22)) -> pd.Timestamp:
    days_in = calendar.monthrange(month.year, month.month)[1]
    day = int(min(max(day, 1), days_in))
    hour = int(rng.integers(hour_range[0], hour_range[1]))
    minute = int(rng.integers(0, 60))
    return pd.Timestamp(year=month.year, month=month.month, day=day, hour=hour, minute=minute)


def weekend_weighted_day(rng, month: pd.Timestamp, discretionary: bool) -> int:
    days_in = calendar.monthrange(month.year, month.month)[1]
    days = np.arange(1, days_in + 1)
    dows = np.array([pd.Timestamp(month.year, month.month, d).dayofweek for d in days])
    if discretionary:
        w = np.select([dows == 4, dows == 5, dows == 6], [1.3, 1.9, 1.7], 1.0)
    else:
        w = np.select([dows == 5, dows == 6], [1.3, 1.2], 1.0)
    return int(rng.choice(days, p=w / w.sum()))


def pay_method(rng, category: str, amount: float, occ: str) -> str:
    if category == "Cash Withdrawal":
        return "ATM/Cash"
    if category in ("Travel", "Shopping", "Gifts & Festivals") and amount > 3000:
        opts, p = ["Credit Card", "Debit Card", "UPI", "Net Banking"], [0.45, 0.20, 0.25, 0.10]
    elif amount > 15000:
        opts, p = ["Credit Card", "Net Banking", "UPI", "Debit Card"], [0.35, 0.30, 0.20, 0.15]
    else:
        opts, p = ["UPI", "Debit Card", "Credit Card"], [0.78, 0.10, 0.12]
    if occ == "Student":
        opts, p = ["UPI", "Debit Card"], [0.9, 0.1]
    return str(rng.choice(opts, p=p))


# --------------------------------------------------------------------------------------
# Customers
# --------------------------------------------------------------------------------------
def make_customers(cfg: dict, rng) -> pd.DataFrame:
    n = cfg["n_customers"]
    mix = cfg["persona_mix"]
    counts = {k: int(round(v * n)) for k, v in mix.items()}
    diff = n - sum(counts.values())
    counts["stable_saver"] += diff
    personas = [p for p, c in counts.items() for _ in range(c)]
    rng.shuffle(personas)

    rows = []
    for i, persona in enumerate(personas, start=1):
        P = PERSONAS[persona]
        tier = int(rng.choice([1, 2, 3], p=[TIER_WEIGHTS[t] for t in (1, 2, 3)]))
        city = str(rng.choice(CITIES[tier]))
        inc_scale = {1: 1.0, 2: 0.85, 3: 0.75}[tier]
        income = float(np.round(rng.uniform(*P["inc"]) * inc_scale, -2))
        if P["occ"] == "Student":
            age = "18-22"
        else:
            age = str(rng.choice(["21-25", "26-30", "31-40", "41-50", "51-60"],
                                 p=[0.15, 0.30, 0.32, 0.16, 0.07]))
        has_loan = bool(rng.random() < P["loan_p"])
        goal_p = np.ones(len(GOALS))
        if persona == "emi_burdened":
            goal_p[GOALS.index("Debt Repayment")] = 5
        if persona == "stable_saver":
            goal_p[GOALS.index("Wealth Creation")] = 3
            goal_p[GOALS.index("Retirement")] = 2
        if persona == "student_early_career":
            goal_p[GOALS.index("Child Education")] = 0
            goal_p[GOALS.index("Retirement")] = 0
            goal_p[GOALS.index("Travel")] = 3
        rows.append(dict(
            customer_id=f"C{i:04d}",
            age_band=age,
            city=city,
            city_tier=f"Tier {tier}",
            occupation_type=P["occ"],
            declared_monthly_income=income,
            financial_goal=str(rng.choice(GOALS, p=goal_p / goal_p.sum())),
            has_active_loan=has_loan,
            persona=persona,
        ))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------
# Simulation of one customer
# --------------------------------------------------------------------------------------
def simulate_customer(c: pd.Series, months: list[pd.Timestamp], cfg: dict, rng) -> list[dict]:
    P = PERSONAS[c.persona]
    tier = int(c.city_tier[-1])
    income = c.declared_monthly_income
    occ = c.occupation_type

    # Customer-level fixed parameters
    exp_ratio = rng.uniform(*P["exp"])
    sip_share = rng.uniform(*P["sip"])
    if sip_share > 0 and rng.random() < 0.25 and c.persona != "stable_saver":
        sip_share = 0.0
    emi_share = rng.uniform(*P["emi"]) if c.has_active_loan else 0.0
    is_renter = rng.random() < P["rent_p"]
    if occ == "Student":
        rent = income * rng.uniform(0.30, 0.42) if is_renter else 0.0
    else:
        rent = income * rng.uniform(0.17, 0.27) * RENT_TIER_FACTOR[tier] if is_renter else 0.0
    rent = float(np.round(rent, -2))
    emi_amt = float(np.round(income * emi_share, 0))
    sip_amt = float(np.round(income * sip_share, -2))
    salary_day = int(rng.integers(1, 8))
    emi_day = int(rng.choice([5, 7, 10]))
    sip_day = int(rng.choice([5, 10, 15]))
    has_broadband = rng.random() < (0.3 if occ == "Student" else 0.7)
    has_gas = occ != "Student" and rng.random() < 0.6
    gas_phase = int(rng.integers(0, 2))
    insurance = 0.0 if occ == "Student" else (float(np.round(income * rng.uniform(0.01, 0.03), -1))
                                               if rng.random() < 0.6 else 0.0)
    subs = list(rng.choice(list(SUBSCRIPTIONS), size=int(rng.integers(0, 4)), replace=False))
    if c.persona in ("lifestyle_creep", "comfortable_spender") and len(subs) < 2:
        subs = list(SUBSCRIPTIONS)[:2]
    kirana = str(rng.choice(KIRANA_STORES))
    mobile = str(rng.choice(["Jio", "Airtel", "Vi"]))
    mobile_cycle = int(rng.choice([1, 3], p=[0.4, 0.6]))
    mobile_price = float(rng.choice([399, 599, 799]))
    broadband_m = str(rng.choice(["JioFiber", "Airtel Xstream", "ACT Fibernet"]))
    lender = str(rng.choice(["HDFC Bank", "ICICI Bank", "SBI", "Bajaj Finance", "Axis Bank"]))
    loan_type = str(rng.choice(["Home Loan EMI", "Personal Loan EMI", "Vehicle Loan EMI"],
                               p=[0.4, 0.35, 0.25]))
    school_fees = (c.age_band in ("31-40", "41-50")) and rng.random() < 0.55
    creep_g = rng.uniform(0.03, 0.05) if c.persona == "lifestyle_creep" else 0.0
    cv = rng.uniform(*P["cv"])
    tilt = P["tilt"]
    bonus_month = int(rng.choice([10, 11])) if (occ == "Salaried" and rng.random() < 0.5) else None
    hike = rng.uniform(1.04, 1.12)

    shock_type, shock_idx = None, None
    if c.persona == "shock_event":
        shock_type = str(rng.choice(["medical", "job_loss", "salary_delay"], p=[0.4, 0.35, 0.25]))
        shock_idx = int(rng.integers(5, 10))   # month index 5..9 (Mar..Jul 2025)
    job_loss_len = int(rng.integers(2, 4))

    balance = float(np.round(income * rng.uniform(*P["buf"]), 0))
    floor = cfg["borrowing_floor"]
    repay_schedule: dict[int, list[float]] = {}
    txns: list[dict] = []

    def add(t, ttype, cat, sub, merchant, amount, method, ie, recurring, loc=None):
        txns_month.append(dict(
            date=t, customer_id=c.customer_id, transaction_type=ttype, category=cat,
            subcategory=sub, merchant=merchant, amount=float(np.round(amount, 2)),
            payment_method=method, income_expense=ie, recurring_flag=int(recurring),
            location=loc or ("Online" if merchant in ONLINE_MERCHANTS else c.city),
        ))

    for mi, m in enumerate(months):
        txns_month: list[dict] = []
        cal_m = m.month
        cur_salary = income * (hike if (m >= pd.Timestamp("2025-04-01")) else 1.0)

        # ---------------- Income ----------------
        month_income = 0.0
        if occ == "Salaried":
            paid = True
            if shock_type == "job_loss" and shock_idx <= mi < shock_idx + job_loss_len:
                paid = False
            if shock_type == "job_loss" and mi >= shock_idx + job_loss_len:
                cur_salary *= 0.88   # new job at lower pay
            if shock_type == "salary_delay" and mi == shock_idx:
                paid = False
            if paid:
                n_pay = 2 if (shock_type == "salary_delay" and mi == shock_idx + 1) else 1
                for k in range(n_pay):
                    add(ts(rng, m, salary_day + 3 * k, (9, 12)), "Credit", "Salary", "Monthly Salary",
                        "Employer Payroll", np.round(cur_salary, 0), "NEFT", "Income", 1)
                month_income += cur_salary * n_pay
            if bonus_month == cal_m:
                b = cur_salary * rng.uniform(0.3, 1.0)
                add(ts(rng, m, int(rng.integers(10, 25)), (9, 12)), "Credit", "Salary", "Festival Bonus",
                    "Employer Payroll", np.round(b, 0), "NEFT", "Income", 0)
                month_income += b
        elif occ == "Freelancer/Gig":
            shape = 1 / cv ** 2
            total = income * rng.gamma(shape, 1 / shape)
            k = int(rng.integers(1, 4))
            parts = rng.dirichlet(np.ones(k)) * total
            for p in parts:
                if p < 500:
                    continue
                add(ts(rng, m, int(rng.integers(1, 29)), (10, 20)), "Credit", "Freelance Income",
                    "Client Payment", str(rng.choice(["Client - Upwork", "Client - Direct Transfer",
                                                       "Client - Fiverr", "Client - Toptal"])),
                    np.round(p, 0), str(rng.choice(["NEFT", "IMPS", "UPI"])), "Income", 0)
                month_income += p
        else:  # Student
            fam = income * rng.uniform(0.6, 0.8)
            add(ts(rng, m, int(rng.integers(1, 6)), (10, 21)), "Credit", "Family Support",
                "Family Transfer", "Family Transfer", np.round(fam, -2), "UPI", "Income", 1)
            month_income += fam
            if rng.random() < 0.8:
                pt = (income - fam) * rng.uniform(0.6, 1.4)
                add(ts(rng, m, int(rng.integers(5, 28)), (10, 20)), "Credit", "Part-time Income",
                    "Internship Stipend", "Internship Stipend", np.round(pt, -1), "IMPS", "Income", 0)
                month_income += pt
        if cal_m in (12, 3, 6, 9) and balance > 5000:
            intr = max(balance, 0) * 0.027 / 4
            add(ts(rng, m, calendar.monthrange(m.year, m.month)[1], (1, 3)), "Credit", "Interest",
                "Savings Interest", "Bank Interest Credit", np.round(intr, 2), "Bank Credit", "Income", 1)

        # ---------------- Fixed obligations ----------------
        fixed = 0.0
        if rent:
            add(ts(rng, m, int(rng.integers(1, 6)), (8, 21)), "Debit", "Housing", "Rent",
                "Rent - Landlord", rent, str(rng.choice(["UPI", "NEFT", "IMPS"], p=[0.5, 0.3, 0.2])),
                "Expense", 1)
            fixed += rent
        if emi_amt:
            add(ts(rng, m, emi_day, (5, 8)), "Debit", "Loan EMI", loan_type, lender, emi_amt,
                "Auto-Debit (NACH)", "Expense", 1)
            fixed += emi_amt
        elec_base = (900 if occ == "Student" else 1400) * (1 + 0.4 * (income > 80000))
        elec = elec_base * (1.45 if cal_m in (4, 5, 6) else 1.0) * rng.uniform(0.8, 1.2)
        add(ts(rng, m, int(rng.integers(8, 16))), "Debit", "Utilities", "Electricity",
            "Electricity Board", elec, str(rng.choice(["UPI", "Net Banking"], p=[0.7, 0.3])), "Expense", 1)
        fixed += elec
        if mi % mobile_cycle == 0:   # monthly postpaid or 84-day prepaid pack
            mob = (299 if occ == "Student" else mobile_price) * mobile_cycle * (0.85 if mobile_cycle == 3 else 1)
            add(ts(rng, m, int(rng.integers(1, 28))), "Debit", "Utilities", "Mobile Recharge", mobile,
                round(mob), "UPI", "Expense", 1, loc="Online")
            fixed += mob
        if has_broadband:
            add(ts(rng, m, int(rng.integers(1, 10))), "Debit", "Utilities", "Broadband", broadband_m,
                799, "UPI Autopay", "Expense", 1, loc="Online")
            fixed += 799
        if has_gas and mi % 2 == gas_phase:
            add(ts(rng, m, int(rng.integers(5, 25))), "Debit", "Utilities", "Cooking Gas",
                "Indane Gas", 903, "UPI", "Expense", 1)
            fixed += 903
        if insurance:
            add(ts(rng, m, 1, (5, 8)), "Debit", "Insurance", "Health & Term Premium",
                str(rng.choice(["Star Health", "HDFC Life", "LIC"])), insurance, "Auto-Debit (NACH)",
                "Expense", 1, loc="Online")
            fixed += insurance
        for s in subs:
            add(ts(rng, m, int(rng.integers(1, 28))), "Debit", "Subscriptions", "OTT & Music", s,
                SUBSCRIPTIONS[s], str(rng.choice(["Credit Card", "UPI Autopay"])), "Expense", 1)
            fixed += SUBSCRIPTIONS[s]
        if school_fees and cal_m in (4, 6):
            sf = income * rng.uniform(0.5, 0.9)
            add(ts(rng, m, int(rng.integers(1, 15))), "Debit", "Education", "School Fees",
                "School Fee Payment", sf, "Net Banking", "Expense", 1)
            fixed += sf
        for amt in repay_schedule.pop(mi, []):
            add(ts(rng, m, int(rng.integers(3, 12)), (8, 12)), "Debit", "Debt Repayment",
                "Short-term Loan Repayment", "Credit Line Repayment", amt, "Auto-Debit (NACH)",
                "Expense", 1, loc="Online")
            fixed += amt
        if sip_amt and not (shock_type == "job_loss" and shock_idx <= mi < shock_idx + job_loss_len):
            add(ts(rng, m, sip_day, (6, 9)), "Debit", "Investments", "Mutual Fund SIP",
                str(rng.choice(["Groww", "Zerodha Coin", "Kuvera"])), sip_amt, "Auto-Debit (NACH)",
                "Investment", 1, loc="Online")

        # ---------------- Variable spending ----------------
        ratio = exp_ratio * (1 + creep_g) ** mi
        target = income * ratio * SEASON[cal_m]
        var_budget = max(target - fixed, income * 0.15)
        if shock_type == "job_loss" and shock_idx <= mi < shock_idx + job_loss_len:
            var_budget *= 0.65
        if occ == "Freelancer/Gig":
            var_budget *= float(np.clip(0.75 + 0.25 * month_income / income, 0.7, 1.2))
        var_budget *= rng.uniform(0.9, 1.1)

        budg = dict(BUDGET_W)
        pres = dict(PRESENCE)
        for cat in DISCRETIONARY_TILT:
            budg[cat] *= tilt
            pres[cat] = min(1.0, pres[cat] * tilt ** 0.5)
        if cal_m in TRAVEL_MONTHS:
            budg["Travel"] *= TRAVEL_MONTHS[cal_m]
            pres["Travel"] = min(1.0, pres["Travel"] * TRAVEL_MONTHS[cal_m] * 1.6)
        if cal_m in (10, 11):
            budg["Gifts & Festivals"], pres["Gifts & Festivals"] = 0.10, 0.85
            budg["Shopping"] *= 1.3
        if occ == "Student":
            budg["Travel"] *= 0.4
            budg["Food Delivery"] *= 1.5

        # which categories are used this month, then a noisy budget split among them
        active = [k for k in budg if budg[k] > 0 and rng.random() < pres[k]]
        bw = np.array([budg[k] for k in active])
        bw = rng.dirichlet(bw / bw.sum() * 40)
        for cat, share in zip(active, bw):
            cat_budget = var_budget * share
            # number of transactions follows a realistic ticket size, capped to keep volume sane
            n = int(np.clip(round(cat_budget / TICKET[cat] * rng.uniform(0.8, 1.2)), 1, CAP[cat]))
            parts = rng.dirichlet(np.ones(n) * 3.0) * cat_budget
            for amt in parts:
                if cat == "Cash Withdrawal":
                    amt = max(500, np.round(amt, -2))
                amt = max(amt, 40.0)
                sub = str(rng.choice(list(VARIABLE[cat])))
                merchant = str(rng.choice(VARIABLE[cat][sub]))
                if merchant == "Neighbourhood Kirana":
                    merchant = kirana
                disc = cat in DISCRETIONARY_TILT or cat == "Gifts & Festivals"
                day = weekend_weighted_day(rng, m, disc)
                add(ts(rng, m, day), "Debit", cat, sub, merchant, amt,
                    pay_method(rng, cat, amt, occ), "Expense", 0)

        # ---------------- Shocks ----------------
        if shock_type == "medical" and mi == shock_idx:
            add(ts(rng, m, int(rng.integers(5, 25))), "Debit", "Healthcare", "Hospitalisation",
                str(rng.choice(["Apollo Hospitals", "Fortis Hospital", "City Hospital"])),
                income * rng.uniform(1.8, 4.0), str(rng.choice(["Credit Card", "Net Banking", "UPI"])),
                "Expense", 0)
        if shock_type == "medical" and shock_idx < mi <= shock_idx + 2:
            add(ts(rng, m, int(rng.integers(1, 28))), "Debit", "Healthcare", "Pharmacy", "Apollo Pharmacy",
                income * rng.uniform(0.05, 0.12), "UPI", "Expense", 0)

        # ---------------- Post in time order with running balance ----------------
        txns_month.sort(key=lambda r: (r["date"], r["transaction_type"] != "Credit"))
        posted = []
        last_date = m
        for r in txns_month:
            if r["transaction_type"] == "Debit" and balance - r["amount"] < floor:
                need = floor - (balance - r["amount"])
                borrow = float(np.ceil((need + rng.uniform(2000, 8000)) / 1000) * 1000)
                src = rng.choice(["Credit Card Cash Advance", "Instant Loan App", "Borrowed from Family"],
                                 p=[0.35, 0.40, 0.25])
                merchant = {"Credit Card Cash Advance": "Credit Card", "Instant Loan App":
                            str(rng.choice(["KreditBee", "MoneyView", "Navi"])),
                            "Borrowed from Family": "Family Transfer"}[src]
                balance += borrow
                posted.append(dict(
                    date=max(last_date, r["date"] - pd.Timedelta(minutes=int(rng.integers(5, 90)))),
                    customer_id=c.customer_id, transaction_type="Credit", category="Borrowing",
                    subcategory=str(src), merchant=merchant, amount=borrow, payment_method="IMPS",
                    income_expense="Borrowing", recurring_flag=0, location="Online",
                    account_balance=np.round(balance, 2)))
                if src != "Borrowed from Family":
                    rate = 1.06 if src == "Instant Loan App" else 1.04
                    inst = float(np.round(borrow * rate / 3, 0))
                    for k in (1, 2, 3):
                        repay_schedule.setdefault(mi + k, []).append(inst)
            balance += r["amount"] if r["transaction_type"] == "Credit" else -r["amount"]
            r["account_balance"] = np.round(balance, 2)
            posted.append(r)
            last_date = r["date"]
        txns.extend(posted)
    return txns


# --------------------------------------------------------------------------------------
# Dirty-data injection
# --------------------------------------------------------------------------------------
def inject_issues(df: pd.DataFrame, cfg: dict, rng) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = cfg["dirty_data"]
    df = df.copy()
    df["amount"] = df["amount"].astype(object)
    df["date"] = df["date"].dt.strftime("%Y-%m-%d %H:%M:%S").astype(object)
    log = []
    n = len(df)

    def pick(rate, mask=None):
        idx = df.index if mask is None else df.index[mask]
        k = int(round(rate * n))
        return rng.choice(idx, size=min(k, len(idx)), replace=False)

    taken: set = set()

    def fresh(rate, mask=None):
        """rows not already modified by another *amount/date* issue"""
        rows = [i for i in pick(rate * 1.3, mask) if i not in taken][: int(round(rate * n))]
        taken.update(rows)
        return rows

    for i in pick(d["missing_category"]):
        log.append((df.at[i, "transaction_id"], "missing_category", df.at[i, "category"]))
        df.at[i, "category"] = np.nan
    for i in pick(d["missing_merchant"]):
        log.append((df.at[i, "transaction_id"], "missing_merchant", df.at[i, "merchant"]))
        df.at[i, "merchant"] = np.nan
    for i in pick(d["missing_payment_method"]):
        log.append((df.at[i, "transaction_id"], "missing_payment_method", df.at[i, "payment_method"]))
        df.at[i, "payment_method"] = np.nan

    def variant(s):
        s = str(s)
        return str(rng.choice([s.lower(), s.upper(), s.replace(" ", "_").lower(), f"  {s} ", s.replace("&", "and")]))

    for i in pick(d["category_case_variants"], df["category"].notna()):
        orig = df.at[i, "category"]
        v = variant(orig)
        if v != orig:
            log.append((df.at[i, "transaction_id"], "category_variant", orig))
            df.at[i, "category"] = v
    pm_alias = {"UPI": ["upi", "UPI ", "Upi", "BHIM UPI"], "Credit Card": ["credit card", "CC", "Credit-Card"],
                "Debit Card": ["debit card", "DC", "Debit-Card"], "Net Banking": ["netbanking", "Net-Banking"],
                "Auto-Debit (NACH)": ["NACH", "auto debit"], "NEFT": ["neft"], "IMPS": ["imps"],
                "UPI Autopay": ["upi autopay", "UPI-Autopay"], "ATM/Cash": ["Cash", "ATM"],
                "Bank Credit": ["bank credit"]}
    for i in pick(d["payment_method_variants"], df["payment_method"].notna()):
        orig = df.at[i, "payment_method"]
        df.at[i, "payment_method"] = str(rng.choice(pm_alias.get(orig, [orig.lower()])))
        log.append((df.at[i, "transaction_id"], "payment_method_variant", orig))
    for i in pick(d["merchant_whitespace"], df["merchant"].notna()):
        orig = df.at[i, "merchant"]
        df.at[i, "merchant"] = str(rng.choice([f" {orig}", f"{orig}  ", orig.upper()]))
        log.append((df.at[i, "transaction_id"], "merchant_formatting", orig))

    debit = (df["transaction_type"] == "Debit").values
    for i in fresh(d["negative_amount_sign_error"], debit):
        log.append((df.at[i, "transaction_id"], "negative_amount", df.at[i, "amount"]))
        df.at[i, "amount"] = -float(df.at[i, "amount"])
    for i in fresh(d["paise_unit_error"]):
        log.append((df.at[i, "transaction_id"], "paise_unit_error", df.at[i, "amount"]))
        df.at[i, "amount"] = float(df.at[i, "amount"]) * 100
    for i in fresh(d["amount_as_text"]):
        log.append((df.at[i, "transaction_id"], "amount_as_text", df.at[i, "amount"]))
        df.at[i, "amount"] = f"₹{float(df.at[i, 'amount']):,.2f}"

    date_rows = set()
    for i in pick(d["mixed_date_format"]):
        orig = df.at[i, "date"]
        t = pd.Timestamp(orig)
        df.at[i, "date"] = t.strftime(str(rng.choice(["%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%Y/%m/%d %H:%M"])))
        log.append((df.at[i, "transaction_id"], "mixed_date_format", orig))
        date_rows.add(i)
    for i in [r for r in pick(d["year_typo_future_date"] * 2) if r not in date_rows][: int(round(d["year_typo_future_date"] * n))]:
        orig = df.at[i, "date"]
        y = orig[:4]
        df.at[i, "date"] = y[:2] + y[3] + y[2] + orig[4:]   # 2025 -> 2052, 2024 -> 2042
        log.append((df.at[i, "transaction_id"], "future_date_year_typo", orig))

    # Duplicates (appended at the end, then shuffled into place)
    dup_idx = pick(d["exact_duplicates"])
    dups = df.loc[dup_idx].copy()
    for tid in dups["transaction_id"]:
        log.append((tid, "exact_duplicate", ""))
    near_idx = pick(d["near_duplicates"], (df["transaction_type"] == "Debit").values)
    near = df.loc[near_idx].copy()
    near_ids = [f"TXN{9000000 + k:07d}" for k in range(len(near))]
    for orig_id, new_id in zip(near["transaction_id"], near_ids):
        log.append((new_id, "near_duplicate_reposted", orig_id))
    near["transaction_id"] = near_ids

    out = pd.concat([df, dups, near]).sample(frac=1, random_state=int(rng.integers(1e6))).reset_index(drop=True)
    log_df = pd.DataFrame(log, columns=["transaction_id", "issue_type", "original_value"])
    return out, log_df


# --------------------------------------------------------------------------------------
def main() -> None:
    cfg = load_config()
    rng = np.random.default_rng(cfg["seed"])
    months = month_list(cfg["start_date"], cfg["n_months"])

    customers = make_customers(cfg, rng)
    all_tx = []
    for _, c in customers.iterrows():
        all_tx.extend(simulate_customer(c, months, cfg, rng))

    # stable sort keeps each customer's posting order for same-minute transactions
    tx = pd.DataFrame(all_tx).sort_values(["date", "customer_id"], kind="mergesort").reset_index(drop=True)
    tx.insert(0, "transaction_id", [f"TXN{i:07d}" for i in range(1, len(tx) + 1)])
    # denormalised customer fields requested in the brief
    tx = tx.merge(customers[["customer_id", "declared_monthly_income", "financial_goal"]],
                  on="customer_id", how="left").rename(columns={"declared_monthly_income": "monthly_income"})
    cols = ["transaction_id", "customer_id", "date", "transaction_type", "category", "subcategory",
            "merchant", "amount", "payment_method", "income_expense", "account_balance",
            "recurring_flag", "location", "monthly_income", "financial_goal"]
    tx = tx[cols]

    raw_dir = ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    # ground truth (kept out of the analysis; used only to grade the cleaning step)
    tx.to_csv(raw_dir / "_ground_truth_transactions.csv", index=False)

    dirty, log = inject_issues(tx, cfg, rng)
    dirty.to_csv(raw_dir / "transactions_raw.csv", index=False)
    log.to_csv(raw_dir / "injected_issues_log.csv", index=False)

    cust_public = customers.drop(columns=["persona"])
    cust_public.to_csv(raw_dir / "customers_raw.csv", index=False)
    customers[["customer_id", "persona"]].to_csv(raw_dir / "_hidden_personas.csv", index=False)

    print(f"Customers: {len(customers)}  |  clean transactions: {len(tx):,}  |  raw rows: {len(dirty):,}")
    print(f"Injected issues: {len(log):,}")
    print(log["issue_type"].value_counts().to_string())


if __name__ == "__main__":
    main()
