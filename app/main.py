from fastapi import FastAPI, Depends
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import Query
from typing import Optional, List
from fastapi import HTTPException
from sqlalchemy import case
from datetime import date



from .database import SessionLocal, engine, Base
from .models import Transaction
from .schemas import TransactionCreate, TransactionOut

app = FastAPI(title="Personal Finance Simulator")

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def root():
    return {"message": "Finance simulator is running"}

@app.get("/health/live")
def live():
    return {"status": "ok"}

@app.post("/transactions", response_model=TransactionOut)
def add_transaction(txn: TransactionCreate, db: Session = Depends(get_db)):
    row = Transaction(amount=txn.amount, category=txn.category, date=txn.date)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

@app.get("/transactions", response_model=List[TransactionOut])
def list_transactions(
    month: Optional[str] = Query(default=None, description="Filter by YYYY-MM, e.g. 2025-01"),
    category: Optional[str] = Query(default=None, description="Filter by category, e.g. rent"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Transaction)

    if month:
        # matches YYYY-MM prefix
        q = q.filter(Transaction.date.like(f"{month}%"))

    if category:
        q = q.filter(Transaction.category == category)

    rows = q.order_by(Transaction.date.desc()).offset(offset).limit(limit).all()
    return rows

from sqlalchemy import case

@app.get("/cashflow/monthly")
def monthly_cashflow(db: Session = Depends(get_db)):
    month_col = func.substr(Transaction.date, 1, 7)

    inflow_expr = func.sum(
        case((Transaction.amount >= 0, Transaction.amount), else_=0.0)
    ).label("inflow")

    outflow_expr = func.sum(
        case((Transaction.amount < 0, -Transaction.amount), else_=0.0)
    ).label("outflow")

    rows = (
        db.query(month_col.label("month"), inflow_expr, outflow_expr)
        .group_by(month_col)
        .order_by(month_col)
        .all()
    )

    result = {}
    for month, inflow, outflow in rows:
        inflow_f = float(inflow or 0.0)
        outflow_f = float(outflow or 0.0)
        result[month] = {
            "inflow": inflow_f,
            "outflow": outflow_f,
            "net": inflow_f - outflow_f
        }

    return result


    return {
        month: {"inflow": float(inflow), "outflow": float(outflow)}
        for month, inflow, outflow in rows
    }

@app.delete("/transactions/reset")
def reset_transactions(db: Session = Depends(get_db)):
    db.query(Transaction).delete()
    db.commit()
    return {"message": "All transactions deleted"}

@app.get("/transactions/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    row = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return row

@app.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    row = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete(row)
    db.commit()
    return {"message": "Deleted", "id": transaction_id}

import re

def parse_end_month(end_month: str) -> tuple[int, int]:
    s = (end_month or "").strip()
    s = s.replace("/", "-").replace(".", "-")

    # Accept YYYYMM (e.g., 202503)
    if re.fullmatch(r"\d{6}", s):
        y = int(s[:4])
        m = int(s[4:])
        return y, m

    # Accept YYYY-M or YYYY-MM
    parts = s.split("-")
    if len(parts) != 2:
        raise ValueError("end_month must be in YYYY-MM (e.g., 2025-03)")

    y = int(parts[0])
    m = int(parts[1])

    if m < 1 or m > 12:
        raise ValueError("Month must be between 1 and 12")

    return y, m

def month_add(year: int, month: int, delta: int) -> tuple[int, int]:
    # Add delta months to (year, month)
    total = year * 12 + (month - 1) + delta
    new_year = total // 12
    new_month = (total % 12) + 1
    return new_year, new_month

def month_str(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"

def safe_div(a: float, b: float) -> float:
    return a / b if b != 0 else 0.0

@app.get("/health/financial")
def financial_health(
    end_month: str = Query(..., description="End month in YYYY-MM (e.g., 2025-03). Analyzes end_month and previous 2 months."),
    db: Session = Depends(get_db),
):
    # Build last 3 months list: [m-2, m-1, m]
    end_y, end_m = parse_end_month(end_month)
    months = [
        month_str(*month_add(end_y, end_m, -2)),
        month_str(*month_add(end_y, end_m, -1)),
        month_str(end_y, end_m),
    ]

    # ---------- 1) Monthly cashflow aggregation in SQL ----------
    month_col = func.substr(Transaction.date, 1, 7)

    inflow_expr = func.sum(
        case((Transaction.amount >= 0, Transaction.amount), else_=0.0)
    ).label("inflow")

    outflow_expr = func.sum(
        case((Transaction.amount < 0, -Transaction.amount), else_=0.0)
    ).label("outflow")

    monthly_rows = (
        db.query(month_col.label("month"), inflow_expr, outflow_expr)
        .filter(month_col.in_(months))
        .group_by(month_col)
        .all()
    )

    # Normalize into a dict with missing months as zeros
    monthly = {m: {"inflow": 0.0, "outflow": 0.0, "net": 0.0} for m in months}
    for m, inflow, outflow in monthly_rows:
        inflow_f = float(inflow or 0.0)
        outflow_f = float(outflow or 0.0)
        monthly[m] = {
            "inflow": inflow_f,
            "outflow": outflow_f,
            "net": inflow_f - outflow_f,
        }

    # ---------- 2) Category breakdown over the 3 months ----------
    # Sum absolute spend for negative amounts by category
    spend_rows = (
        db.query(Transaction.category, func.sum(-Transaction.amount).label("spend"))
        .filter(month_col.in_(months))
        .filter(Transaction.amount < 0)
        .group_by(Transaction.category)
        .order_by(func.sum(-Transaction.amount).desc())
        .all()
    )

    total_spend = sum(float(r.spend or 0.0) for r in spend_rows)
    category_shares = {
        cat: safe_div(float(spend), total_spend) for cat, spend in spend_rows
    }

    # ---------- 3) Compute health metrics (trend + stability) ----------
    inflows = [monthly[m]["inflow"] for m in months]
    outflows = [monthly[m]["outflow"] for m in months]
    nets = [monthly[m]["net"] for m in months]

    avg_inflow = sum(inflows) / 3.0
    avg_outflow = sum(outflows) / 3.0
    avg_net = sum(nets) / 3.0
    avg_savings_rate = safe_div(avg_net, avg_inflow)  # net / inflow

    # Volatility (simple): average absolute deviation from avg_net
    avg_abs_dev = sum(abs(n - avg_net) for n in nets) / 3.0
    volatility_ratio = safe_div(avg_abs_dev, avg_inflow)  # normalized by income

    # Trend: compare last month net vs first month net
    trend_delta = nets[-1] - nets[0]

    # Expense concentration: top category share
    top_category = None
    top_share = 0.0
    if spend_rows:
        top_category = spend_rows[0][0]
        top_share = category_shares.get(top_category, 0.0)

    # ---------- 4) Build an explainable score (0–100) ----------
    # Savings score (0–50): 20%+ is great
    savings_score = min(50.0, max(0.0, (avg_savings_rate / 0.20) * 50.0))

    # Stability score (0–25): lower volatility is better; 10% normalized volatility is ok
    stability_score = 25.0 * max(0.0, 1.0 - (volatility_ratio / 0.10))
    stability_score = max(0.0, min(25.0, stability_score))

    # Trend score (0–15): improving net adds points
    trend_score = 0.0
    if trend_delta > 0:
        trend_score = min(15.0, (trend_delta / (avg_inflow + 1e-9)) * 100.0)  # scaled
        trend_score = max(5.0, min(15.0, trend_score))
    else:
        trend_score = max(0.0, 5.0 + (trend_delta / (avg_inflow + 1e-9)) * 50.0)  # can drop toward 0
        trend_score = max(0.0, min(15.0, trend_score))

    # Concentration score (0–10): too much spend in one category is risky
    # If top category is >50% of spend, you lose points
    concentration_score = 10.0 * max(0.0, 1.0 - max(0.0, (top_share - 0.50) / 0.50))
    concentration_score = max(0.0, min(10.0, concentration_score))

    score = round(savings_score + stability_score + trend_score + concentration_score)

    score_breakdown = {
        "savings": round(savings_score, 2),
        "stability": round(stability_score, 2),
        "trend": round(trend_score, 2),
        "concentration": round(concentration_score, 2),
    }

    # ---------- 5) Insights + flags ----------
    insights = []
    flags = []

    if avg_inflow <= 0:
        flags.append("No income detected in the last 3 months; health metrics may be unreliable.")
    else:
        insights.append(f"Average savings rate over last 3 months: {avg_savings_rate*100:.1f}%.")

    if avg_savings_rate < 0:
        flags.append("You are spending more than you earn on average (negative net cashflow).")
    elif avg_savings_rate < 0.10:
        insights.append("Savings rate is low (<10%). Aim for 15–20% if possible.")
    elif avg_savings_rate >= 0.20:
        insights.append("Strong savings rate (≥20%). Keep it up.")

    if volatility_ratio > 0.10:
        insights.append("Your net cashflow is volatile month-to-month. Consider smoothing large discretionary expenses.")
    else:
        insights.append("Your cashflow looks fairly stable over the last 3 months.")

    if top_category and top_share >= 0.50:
        insights.append(f"Spending is concentrated in '{top_category}' ({top_share*100:.1f}% of expenses). Consider reducing or budgeting it.")
    elif top_category:
        insights.append(f"Top expense category is '{top_category}' ({top_share*100:.1f}% of expenses).")

    # Trend commentary
    if trend_delta > 0:
        insights.append(f"Net cashflow improved by {trend_delta:.2f} from {months[0]} to {months[-1]}.")
    elif trend_delta < 0:
        insights.append(f"Net cashflow declined by {abs(trend_delta):.2f} from {months[0]} to {months[-1]}.")
    else:
        insights.append("Net cashflow is flat across the 3-month window.")

    return {
        "window": {"months": months, "end_month": end_month},
        "score": score,
        "score_breakdown": score_breakdown,
        "summary": {
            "avg_inflow": round(avg_inflow, 2),
            "avg_outflow": round(avg_outflow, 2),
            "avg_net": round(avg_net, 2),
            "avg_savings_rate": round(avg_savings_rate, 4),
            "volatility_ratio": round(volatility_ratio, 4),
            "trend_delta_net": round(trend_delta, 2),
        },
        "monthly": {m: {k: round(v, 2) for k, v in monthly[m].items()} for m in months},
        "category_shares": {k: round(v, 4) for k, v in category_shares.items()},
        "insights": insights,
        "flags": flags,
    }
# --- Alerts / risk flags ---
# 1) Negative net months
    neg_months = [m for m in months if monthly[m]["net"] < 0]
    if len(neg_months) >= 2:
        flags.append("Two or more months have negative net cashflow (spending exceeds income).")
    elif len(neg_months) == 1:
        flags.append(f"One month has negative net cashflow: {neg_months[0]}.")

    # 2) Volatility alert
    if volatility_ratio >= 0.20:
        flags.append("High cashflow volatility over the 3-month window.")

    # 3) Income drop alert (last vs first)
    if inflows[0] > 0:
        income_drop_pct = (inflows[0] - inflows[-1]) / inflows[0]
        if income_drop_pct >= 0.15:
            flags.append(f"Income dropped by {income_drop_pct*100:.1f}% from {months[0]} to {months[-1]}.")

    # 4) Rent-to-income ratio (if rent exists)
    rent_spend = 0.0
    for cat, spend in spend_rows:
        if cat == "rent":
            rent_spend = float(spend or 0.0)

    if avg_inflow > 0 and rent_spend > 0:
        avg_monthly_rent = rent_spend / 3.0
        rent_ratio = avg_monthly_rent / avg_inflow
        if rent_ratio >= 0.40:
            flags.append(f"Rent is {rent_ratio*100:.1f}% of average monthly income (high). Aim for <35–40% if possible.")

