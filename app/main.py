from fastapi import FastAPI, Depends
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import Query
from typing import Optional, List
from fastapi import HTTPException


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

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

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
