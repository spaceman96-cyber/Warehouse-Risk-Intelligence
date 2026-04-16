# Warehouse Risk Intelligence (WRI) 📦

Warehouse Risk Intelligence (WRI) is an AI-powered warehouse analytics platform that helps operations teams identify inventory discrepancies, adjustment risk, and anomaly patterns across SKUs, warehouse zones, and users.

The system combines a FastAPI backend, a React dashboard, PostgreSQL storage, and a custom risk scoring engine to surface the highest-risk inventory issues and drive targeted cycle count actions.

---

## Overview

WRI is designed to reduce inventory variance by turning raw warehouse adjustment logs into actionable risk insights.

It supports:

- SKU-level risk scoring
- Zone-level risk scoring
- User-level anomaly scoring
- Cycle count recommendations
- Spike detection
- Investigation tracking
- CSV-based data ingestion
- Real-time dashboard visualisation

This repository contains the application stack for the WRI MVP, including backend API, frontend dashboard, database schema, risk engine, and Docker deployment files.

---

## Core Features

### Risk Scoring Engine

The custom risk engine computes risk scores using historical warehouse adjustment activity.

It evaluates:

- **Frequency risk** — how often a SKU is adjusted
- **Drift risk** — changes in adjustment behavior over recent time windows
- **Value-at-risk** — estimated dollar exposure using SKU unit cost
- **Zone risk** — warehouse zones with elevated adjustment intensity
- **User anomaly risk** — unusual adjustment patterns by operator

### Dashboard

The React dashboard presents:

- Top risky SKUs
- High-risk warehouse zones
- User anomaly rankings
- Recommendation lists
- Spike alerts
- Investigation management

### Data Ingestion

The API supports CSV ingestion for:

- SKU master data
- Warehouse adjustment logs

### Investigations

Users can create and update investigations tied to:

- SKU
- zone
- user
- severity
- notes
- root cause summary

### Deployment

The stack includes:

- FastAPI backend
- React/Vite frontend
- PostgreSQL database
- nginx reverse proxy
- Docker Compose orchestration

---

## Tech Stack

### Backend

- FastAPI
- SQLAlchemy
- PostgreSQL
- Pandas
- Pydantic

### Frontend

- React
- Vite
- Recharts

### Infrastructure

- Docker
- Docker Compose
- nginx

---

## Project Structure

```text
warehouse-risk-intelligence/
├── api/                  # FastAPI backend
│   ├── routes/           # API routes
│   ├── services/         # Backend services
│   ├── models.py         # SQLAlchemy models
│   ├── db.py             # DB connection / session handling
│   └── main.py           # FastAPI app entrypoint
├── wri-dashboard/        # React + Vite frontend
│   ├── src/
│   ├── public/
│   └── package.json
├── risk_engine/          # Risk scoring engine
│   └── risk_engine.py
├── schema/               # SQL / seed / schema-related files
├── nginx/                # nginx config
├── data/                 # sample CSV data
├── docker-compose.yml
├── Dockerfile.backend
└── Dockerfile.frontend
```

---

## Running the Project

### Option 1: Run with Docker (Recommended)

Run everything:

```bash
docker compose up --build
```

After startup:

- Frontend → `http://localhost:8080`
- Backend → `http://localhost:8000`
- Health check → `http://localhost:8000/health`

---

### Option 2: Run Locally

#### 1. Start PostgreSQL

Make sure PostgreSQL is running locally.

Create the database:

```sql
CREATE DATABASE wri;
```

#### 2. Run Backend

```bash
cd api

python -m venv venv

# Mac / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

pip install -r requirements.txt
uvicorn main:app --reload
```

Backend will run at:

```text
http://localhost:8000
```

#### 3. Run Frontend

```bash
cd wri-dashboard

npm install
npm run dev
```

Frontend will run at:

```text
http://localhost:5173
```

#### 4. Configure Environment Variables

Create `wri-dashboard/.env`:

```env
VITE_API_BASE=http://localhost:8000
```

If needed, create `api/.env`:

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/wri
```

---

## Workflow

1. Upload SKU master CSV
2. Upload warehouse adjustment CSV
3. The backend validates and stores the data
4. The risk engine computes fresh scores
5. The dashboard displays:
   - SKU risk
   - Zone risk
   - User anomalies
   - Recommendations
   - Spike alerts

---

## Sample Data

Sample CSV files are available in:

- `data/`
- `schema/`

Use these to test ingestion and scoring flows locally.

---

## Use Cases

- Warehouse inventory auditing
- Cycle count prioritisation
- Shrinkage detection
- Operational risk monitoring
- Warehouse analytics

---

## Disclaimer

This repository contains an MVP / demonstration version of the system.

Production implementations should integrate with real WMS / ERP systems and include authentication, role-based access control, and stronger validation.

---

## Author
R. Rajasekar
Built as part of the Warehouse Risk Intelligence (WRI) project for warehouse analytics and risk detection.