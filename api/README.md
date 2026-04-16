# WRI Backend — Setup & Run Guide

## Project Structure
```
wri/
├── main.py                        ← FastAPI app (this file)
├── risk_engine.py                 ← Risk scoring logic
├── generate_wri_data.py           ← Synthetic data generator
├── adjustment_log.csv             ← Generated adjustment data
├── sku_master.csv                 ← Generated SKU master
└── requirements.txt
```

## Requirements
```
fastapi
uvicorn
pandas
numpy
python-multipart
```

Install:
```bash
pip install fastapi uvicorn pandas numpy python-multipart
```

## Run
```bash
# From the wri/ directory
uvicorn main:app --reload --port 8000
```

## API Docs (auto-generated)
```
http://localhost:8000/docs       ← Swagger UI  (use this for demo)
http://localhost:8000/redoc      ← ReDoc
```

---

## Endpoints

| Method | URL | What it does |
|--------|-----|--------------|
| GET | /health | System check |
| GET | /api/scores/sku | All SKU risk scores |
| GET | /api/scores/sku/{sku_code} | Single SKU detail |
| GET | /api/scores/zone | Zone risk scores |
| GET | /api/scores/user | User anomaly scores |
| GET | /api/recommendations | Top 15 SKUs to count tomorrow |
| GET | /api/alerts/spikes | Spike alerts |
| POST | /api/ingest/adjustments | Upload adjustment CSV |
| POST | /api/investigations | Open investigation case |
| GET | /api/investigations | List all cases |
| PUT | /api/investigations/{id} | Update case |

---

## Example Calls

### Get high-risk SKUs only
```bash
curl "http://localhost:8000/api/scores/sku?min_score=60"
```

### Get SKU detail
```bash
curl "http://localhost:8000/api/scores/sku/SKU-007"
```

### Get cycle count recommendations
```bash
curl "http://localhost:8000/api/recommendations"
```

### Open an investigation
```bash
curl -X POST "http://localhost:8000/api/investigations" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "SKU-007 chronic shrinkage investigation",
    "severity": "high",
    "owner": "warehouse_manager",
    "sku_code": "SKU-007",
    "notes": "Consistent -5 to -15 unit shortfall every week"
  }'
```

### Upload a new CSV
```bash
curl -X POST "http://localhost:8000/api/ingest/adjustments" \
  -F "file=@adjustment_log.csv"
```

---

## For Demo Purposes

1. Run `python generate_wri_data.py` first to create the CSVs
2. Start the API with `uvicorn main:app --reload --port 8000`
3. Open `http://localhost:8000/docs` — this is your interactive demo
4. Show co-founders: SKU scores → Zone scores → Recommendations → Open an investigation live

The Swagger UI at /docs lets you click through every endpoint without writing any code.
That's your demo interface until the React dashboard is built.
