# **Personal Finance Simulator API**

**FastAPI Backend — Financial Analytics & Health Scoring System**

---

## **Introduction**

The Personal Finance Simulator is a production-style FastAPI backend that allows users to store financial transactions, compute monthly cashflow analytics, and evaluate financial health over a rolling three-month window.

The project is designed to mirror real-world backend systems by emphasizing:

- Clean REST API design
- Robust request validation and normalization
- Database-driven aggregation and analytics
- Explainable financial health scoring (not a black box)
- Separation of system health and business logic

This project demonstrates backend engineering, data modeling, and analytical reasoning in a cohesive system.

---

## **Features**

### **Transaction Management**

Users can:

- Add income and expense transactions
- Retrieve transactions with filtering and pagination
- Fetch or delete individual transactions
- Reset all transactions for development/testing

### **Monthly Cashflow Analytics**

The system computes:

- Monthly inflow
- Monthly outflow
- Net cashflow per month

All aggregation is performed at the database level for scalability.

### **Financial Health Analysis (3-Month Window)**

The system provides:

- A normalized financial health score (0–100)
- Component-level score breakdown
- Monthly financial summaries
- Expense category concentration analysis
- Human-readable insights
- Risk flags highlighting potential financial issues

---

## **System Architecture**

+------------------------------------+
| FastAPI App |
| - Route definitions |
| - Request validation |
| - Response formatting |
+-------------------+----------------+
|
v
+------------------------------------+
| Financial Analytics |
| - Monthly cashflow aggregation |
| - Rolling 3-month health scoring |
| - Trend and volatility analysis |
+-------------------+----------------+
|
v
+------------------------------------+
| SQLAlchemy ORM Layer |
| - Transaction model |
| - Database sessions |
| - Query abstraction |
+-------------------+----------------+
|
v
+------------------------------------+
| SQLite DB |
| - Persistent transaction storage |
+------------------------------------+

---

## **Project Structure**

app/
init.py
main.py # API routes, analytics, financial health logic
database.py # SQLAlchemy engine, session, Base
models.py # ORM models
schemas.py # Pydantic request/response schemas
requirements.txt
README.md


---

## **Tech Stack**

| Component        | Technology |
|------------------|------------|
| Language         | Python 3.9+ |
| Web Framework   | FastAPI |
| ORM              | SQLAlchemy |
| Database         | SQLite |
| Validation       | Pydantic |
| Server           | Uvicorn |

---

## **API Endpoints**

### **Root**
#### `GET /`
Basic root endpoint for sanity checks.

---

### **System Health**
#### `GET /health/live`

Operational liveness check used to confirm the API is running.

Example response:
```json
{ "status": "ok",
  "time": "2026-01-12T17:12:33.000Z" }
This endpoint is intentionally separate from financial health to reflect production systems where infrastructure monitoring and business logic are decoupled.

Transactions
Add Transaction
POST /transactions
json

{ "amount": 2500,
  "category": "income",
  "date": "2025-01-01" }

Rules:
- amount > 0 → income
- amount < 0 → expense
- Dates are normalized internally

List Transactions
GET /transactions

Optional query parameters:
month=YYYY-MM
category=rent
limit (default: 50)
offset (default: 0)

Get Transaction
GET /transactions/{transaction_id}
Retrieve a transaction by ID.

Delete Transaction
DELETE /transactions/{transaction_id}
Deletes a single transaction.

Reset Transactions
DELETE /transactions/reset
Deletes all stored transactions (development/testing helper).

Cashflow Analytics
Monthly Cashflow
GET /cashflow/monthly
Returns aggregated cashflow per month:

{ "2025-01": { "inflow": 2500, "outflow": 920, "net": 1580 },
  "2025-02": { "inflow": 2600, "outflow": 1100, "net": 1500 } }

Financial Health System
Endpoint
GET /health/financial?end_month=YYYY-MM
Analyzes a rolling three-month window ending at end_month.

Supported formats:
YYYY-MM
YYYY/MM
YYYYMM

Financial Health Methodology
The financial health score is a weighted composition of four explainable components:

1. Savings
Average savings rate:
(net cashflow) / (inflow)

2. Stability
Measures volatility of net cashflow across the three-month window.

3. Trend
Tracks improvement or decline in net cashflow from the first to the last month.

4. Expense Concentration
Evaluates whether spending is overly concentrated in a single category (e.g., rent consuming >50% of expenses).

**Each component contributes independently to the final score, which is returned alongside a detailed breakdown.**

Output Structure
The financial health response includes:

score (0–100)

score_breakdown

summary (averages, volatility, trend)

monthly cashflow metrics

category_shares

insights

flags

This design ensures transparency and interpretability.

Non-Functional Requirements
Category	How the System Meets It
Performance	SQL-level aggregation
Reliability	Input validation & error handling
Maintainability	Modular architecture
Scalability	ORM + query-based analytics
Usability	Clear endpoints + Swagger UI

Testing
The system is tested manually using:

Swagger UI (/docs)

Multiple transaction scenarios

Edge cases (negative cashflow, volatility spikes, income drops)

All endpoints behave as expected under test conditions.

Known Issues
python
Copy code
None — all features operate as expected.
Future Enhancements

Planned extensions include:
Scenario simulation (e.g., rent +10%, income −15%)
Recurring transaction detection
Migration to PostgreSQL
Authentication and rate limiting
Public deployment with CI/CD

Author
Ali Fadoo
