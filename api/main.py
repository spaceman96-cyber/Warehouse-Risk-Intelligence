# api/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import pandas as pd
import uuid
import io
import os
import sys
import hashlib
import math
from .services.scoring_service import recompute_scores

from sqlalchemy.orm import Session
from sqlalchemy import func, select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .db import engine, get_db
from .models import SKUMaster, Adjustment, Investigation
from .db import Base
import hashlib
from sqlalchemy.exc import IntegrityError

# Create tables (simple MVP). Later: Alembic migrations.
from sqlalchemy.exc import OperationalError
import time

from risk_engine import compute_all  # risk_engine/__init__.py

app = FastAPI(
    title="Warehouse Risk Intelligence API",
    description="WRI MVP v0.1 — Reduce Inventory Variance in 90 Days.",
    version="0.1.0",
)

@app.on_event("startup")
def on_startup():
    for _ in range(30):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except OperationalError:
            time.sleep(1)
    raise RuntimeError("DB not ready after 30s")

# ------------------------------------------------------------
# Import risk engine (project root on path)
# ------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:5173",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------
# Agent routes
# ------------------------------------------------------------
from .routes.duncan import router as duncan_router
app.include_router(duncan_router)

# -----------------------------
# Pydantic models
# -----------------------------
class InvestigationCreate(BaseModel):
    title: str
    severity: str = "med"
    owner: Optional[str] = None
    sku_code: Optional[str] = None
    zone: Optional[str] = None
    user_ref: Optional[str] = None
    notes: Optional[str] = None

class InvestigationUpdate(BaseModel):
    status: Optional[str] = None
    severity: Optional[str] = None
    owner: Optional[str] = None
    root_cause_tag: Optional[str] = None
    summary: Optional[str] = None

# -----------------------------
# Helpers: DB -> pandas
# -----------------------------
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()
def make_row_hash_from_fields(ts, sku, qty, user, zone, loc, typ) -> str:
    # stable canonical string (avoid None/NaN inconsistencies)
    s = "|".join([
        str(ts or ""),
        str(sku or "").strip().upper(),
        str(qty if qty is not None else ""),
        str(user or "").strip(),
        str(zone or "").strip().upper(),
        str(loc or "").strip().upper(),
        str(typ or "").strip(),
    ])
    return hashlib.sha1(s.encode("utf-8")).hexdigest()
def _score_window_from_db(db: Session) -> tuple[pd.DataFrame, pd.DataFrame, Optional[datetime]]:
    """
    Pull:
      - sku_master: all rows
      - adjustments: only last 30d relative to max timestamp (because engine uses 30/7 windows)
    """
    max_ts = db.execute(select(func.max(Adjustment.timestamp))).scalar_one_or_none()
    if not max_ts:
        return pd.DataFrame(), pd.DataFrame(), None

    since = max_ts - timedelta(days=30)

    sku_rows = db.execute(select(SKUMaster)).scalars().all()
    adj_rows = db.execute(select(Adjustment).where(Adjustment.timestamp >= since)).scalars().all()

    sku_df = pd.DataFrame([{
        "sku_code": r.sku_code,
        "sku_name": r.sku_name,
        "category": r.category,
        "abc_class": r.abc_class,
        "unit_cost": r.unit_cost,
        "value_band": r.value_band,
    } for r in sku_rows])

    adj_df = pd.DataFrame([{
        "timestamp": r.timestamp,
        "sku_code": r.sku_code,
        "qty_delta": r.qty_delta,
        "user_ref": r.user_ref,
        "zone": r.zone,
        "location_code": r.location_code,
        "adjustment_type": r.adjustment_type,
    } for r in adj_rows])

    return adj_df, sku_df, max_ts

def _require_data(adj_df: pd.DataFrame, sku_df: pd.DataFrame):
    if adj_df.empty:
        raise HTTPException(status_code=400, detail="No adjustments loaded yet. Upload /api/ingest/adjustments")
    if sku_df.empty:
        raise HTTPException(status_code=400, detail="No SKU master loaded yet. Upload /api/ingest/sku_master")

def make_row_hash(r):
    parts = [
        str(r["timestamp"]),
        str(r["sku_code"]),
        str(r["qty_delta"]),
        str(r["user_ref"]),
        str(r.get("zone", "UNKNOWN")),
        str(r.get("location_code", "")),
        str(r.get("adjustment_type", "")),
    ]
    s = "|".join(parts).encode("utf-8", errors="ignore")
    return hashlib.sha1(s).hexdigest()
# -----------------------------
# Health
# -----------------------------
@app.get("/health", tags=["System"])
def health(db: Session = Depends(get_db)):
    max_ts = db.execute(select(func.max(Adjustment.timestamp))).scalar_one_or_none()
    return {
        "status": "ok",
        "version": "0.1.0",
        "has_adjustments": bool(max_ts),
        "latest_adjustment_ts": max_ts.isoformat() if max_ts else None,
    }

# -----------------------------
# Ingest: SKU master (upsert)
# -----------------------------
@app.post("/api/ingest/sku_master", tags=["Ingest"])
async def ingest_sku_master(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files accepted.")

    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"CSV parse error: {e}")

    if "sku_code" not in df.columns:
        raise HTTPException(status_code=422, detail="Missing required column: sku_code")

    df["sku_code"] = df["sku_code"].astype(str).str.upper().str.strip()
    df["sku_name"] = df.get("sku_name", "").astype(str)
    df["category"] = df.get("category", "").astype(str)
    df["abc_class"] = df.get("abc_class", "").astype(str).str.upper().str.strip()
    df["value_band"] = df.get("value_band", "").astype(str)
    df["unit_cost"] = pd.to_numeric(df.get("unit_cost", 0), errors="coerce").fillna(0.0)

    # Upsert row-by-row (fine for MVP). Later: bulk upsert.
    upserted = 0
    for _, r in df.iterrows():
        code = r["sku_code"]
        obj = db.get(SKUMaster, code)
        if not obj:
            obj = SKUMaster(sku_code=code)
            db.add(obj)

        obj.sku_name = r["sku_name"]
        obj.category = r["category"]
        obj.abc_class = r["abc_class"]
        obj.value_band = r["value_band"]
        obj.unit_cost = float(r["unit_cost"])
        upserted += 1

    db.commit()

    return {
        "status": "saved",
        "rows_ingested": int(len(df)),
        "rows_upserted": int(upserted),
        "filename": file.filename,
        "columns": list(df.columns),
    }

# -----------------------------
# Ingest: adjustments (append)
# -----------------------------
@app.post("/api/ingest/adjustments", tags=["Ingest"])
async def ingest_adjustments(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files accepted.")

    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"CSV parse error: {e}")

    required = {"timestamp", "sku_code", "qty_delta", "user_ref"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required columns: {sorted(list(missing))}")

    # --- normalize + validate ---
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if df["timestamp"].isna().any():
        bad = int(df["timestamp"].isna().sum())
        raise HTTPException(status_code=422, detail=f"{bad} rows have invalid timestamp format")

    df["sku_code"] = df["sku_code"].astype(str).str.upper().str.strip()
    df["user_ref"] = df["user_ref"].astype(str).str.strip()

    df["qty_delta"] = pd.to_numeric(df["qty_delta"], errors="coerce")
    if df["qty_delta"].isna().any():
        bad = int(df["qty_delta"].isna().sum())
        raise HTTPException(status_code=422, detail=f"{bad} rows have invalid qty_delta (not a number)")

    # optional cols (preserve None properly)
    if "zone" in df.columns:
        df["zone"] = df["zone"].astype(str).str.upper().str.strip()
        df.loc[df["zone"].isin(["", "NAN", "NONE"]), "zone"] = "UNKNOWN"
    else:
        df["zone"] = "UNKNOWN"

    if "location_code" in df.columns:
        df["location_code"] = df["location_code"].where(pd.notna(df["location_code"]), None)
        df["location_code"] = df["location_code"].apply(
            lambda x: str(x).upper().strip() if x is not None and str(x).strip() != "" else None
        )
    else:
        df["location_code"] = None

    if "adjustment_type" in df.columns:
        df["adjustment_type"] = df["adjustment_type"].where(pd.notna(df["adjustment_type"]), None)
        df["adjustment_type"] = df["adjustment_type"].apply(
            lambda x: str(x).strip() if x is not None and str(x).strip() != "" else None
        )
    else:
        df["adjustment_type"] = None

    rows_ingested_raw = int(len(df))

    # --- compute row_hash ---
    df["row_hash"] = df.apply(
        lambda r: make_row_hash_from_fields(
            r["timestamp"].to_pydatetime(),
            r["sku_code"],
            float(r["qty_delta"]),
            r["user_ref"],
            r["zone"],
            r["location_code"],
            r["adjustment_type"],
        ),
        axis=1,
    )

    # ✅ dedupe within the same file
    df = df.drop_duplicates(subset=["row_hash"], keep="first")
    rows_after_infile_dedupe = int(len(df))

    # build payload
    payload = [{
        "timestamp": r["timestamp"].to_pydatetime() if hasattr(r["timestamp"], "to_pydatetime") else r["timestamp"],
        "sku_code": r["sku_code"],
        "qty_delta": float(r["qty_delta"]),
        "user_ref": r["user_ref"],
        "zone": r["zone"],
        "location_code": r["location_code"],
        "adjustment_type": r["adjustment_type"],
        "row_hash": r["row_hash"],
    } for r in df.to_dict(orient="records")]

    before = db.execute(select(func.count()).select_from(Adjustment)).scalar_one()

    if payload:
        stmt = pg_insert(Adjustment).values(payload)
        stmt = stmt.on_conflict_do_nothing(index_elements=["row_hash"])
        db.execute(stmt)

    db.commit()

    after = db.execute(select(func.count()).select_from(Adjustment)).scalar_one()

    rows_inserted = int(after - before)
    # counts BOTH: duplicates inside file + duplicates already in DB
    rows_skipped = int(rows_ingested_raw - rows_inserted)

    return {
        "status": "saved",
        "rows_ingested": rows_ingested_raw,
        "rows_after_infile_dedupe": rows_after_infile_dedupe,
        "rows_inserted": rows_inserted,
        "rows_skipped": rows_skipped,
        "total_rows": int(after),
        "filename": file.filename,
        "columns": list(df.columns),
    }
# -----------------------------
# Scores endpoints (computed from DB)
# -----------------------------
@app.get("/api/scores/sku", tags=["Risk Scores"])
def get_sku_scores(
    category: Optional[str] = Query(None),
    min_score: int = Query(0),
    limit: int = Query(30),
    sort_by: str = Query("risk_score"),
    db: Session = Depends(get_db),
):
    sku_scores, _, _, _, _, score_date = recompute_scores(db)
    df = sku_scores.copy()

    if category and "category" in df.columns:
        df = df[df["category"].astype(str).str.lower() == category.lower()]

    df = df[df["risk_score"] >= min_score]

    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=False)
    else:
        df = df.sort_values("risk_score", ascending=False)

    return {"score_date": str(score_date), "total": int(len(df)), "results": df.head(limit).to_dict("records")}

@app.get("/api/scores/sku/{sku_code}", tags=["Risk Scores"])
def get_sku_detail(sku_code: str, db: Session = Depends(get_db)):
    sku_scores, _, _, recs, _, score_date = recompute_scores(db)

    code = sku_code.upper().strip()
    row = sku_scores[sku_scores["sku_code"] == code]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"SKU {sku_code} not found")

    rec_row = recs[recs["sku_code"] == code] if "sku_code" in recs.columns else pd.DataFrame()
    in_recs = not rec_row.empty
    priority = int(rec_row["priority"].values[0]) if in_recs else None

    result = row.to_dict("records")[0]
    result["score_date"] = str(score_date)
    result["in_cycle_count_recommendations"] = in_recs
    result["recommendation_priority"] = priority
    return result

@app.get("/api/scores/zone", tags=["Risk Scores"])
def get_zone_scores(db: Session = Depends(get_db)):
    _, zone_scores, _, _, _, score_date = recompute_scores(db)
    return {"score_date": str(score_date), "results": zone_scores.to_dict("records")}

@app.get("/api/scores/user", tags=["Risk Scores"])
def get_user_scores(min_score: int = Query(0), db: Session = Depends(get_db)):
    _, _, user_scores, _, _, score_date = recompute_scores(db)
    df = user_scores[user_scores["risk_score"] >= min_score].copy().sort_values("risk_score", ascending=False)
    return {"score_date": str(score_date), "total": int(len(df)), "results": df.to_dict("records")}

@app.get("/api/recommendations", tags=["Recommendations"])
def get_recommendations(db: Session = Depends(get_db)):
    _, _, _, recs, _, score_date = recompute_scores(db)
    return {"rec_date": str(score_date), "total": int(len(recs)), "results": recs.to_dict("records")}

@app.get("/api/alerts/spikes", tags=["Alerts"])
def get_spike_alerts(db: Session = Depends(get_db)):
    _, _, _, _, spikes, score_date = recompute_scores(db)
    return {"score_date": str(score_date), "total_spiked": int(len(spikes)), "results": spikes.to_dict("records")}

# -----------------------------
# Investigations (DB-backed)
# -----------------------------
@app.post("/api/investigations", tags=["Investigations"], status_code=201)
def create_investigation(payload: InvestigationCreate, db: Session = Depends(get_db)):
    inv_id = str(uuid.uuid4())

    inv = Investigation(
        id=inv_id,
        title=payload.title,
        status="open",
        severity=payload.severity,
        owner=payload.owner,
        sku_code=(payload.sku_code.upper().strip() if payload.sku_code else None),
        zone=(payload.zone.upper().strip() if payload.zone else None),
        user_ref=(payload.user_ref.strip() if payload.user_ref else None),
        notes=payload.notes,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)

    return {
        "id": inv.id,
        "title": inv.title,
        "status": inv.status,
        "severity": inv.severity,
        "owner": inv.owner,
        "opened_at": inv.opened_at.isoformat() if inv.opened_at else None,
        "closed_at": inv.closed_at.isoformat() if inv.closed_at else None,
        "root_cause_tag": inv.root_cause_tag,
        "summary": inv.summary,
        "notes": inv.notes,
        "links": (
            ([{"type":"sku","key":inv.sku_code}] if inv.sku_code else [])
            + ([{"type":"zone","key":inv.zone}] if inv.zone else [])
            + ([{"type":"user","key":inv.user_ref}] if inv.user_ref else [])
        ),
    }

@app.get("/api/investigations", tags=["Investigations"])
def list_investigations(status: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = select(Investigation)
    if status:
        q = q.where(Investigation.status == status)

    rows = db.execute(q.order_by(Investigation.opened_at.desc())).scalars().all()

    def to_dict(inv: Investigation):
        return {
            "id": inv.id,
            "title": inv.title,
            "status": inv.status,
            "severity": inv.severity,
            "owner": inv.owner,
            "opened_at": inv.opened_at.isoformat() if inv.opened_at else None,
            "closed_at": inv.closed_at.isoformat() if inv.closed_at else None,
            "root_cause_tag": inv.root_cause_tag,
            "summary": inv.summary,
            "notes": inv.notes,
            "links": (
                ([{"type":"sku","key":inv.sku_code}] if inv.sku_code else [])
                + ([{"type":"zone","key":inv.zone}] if inv.zone else [])
                + ([{"type":"user","key":inv.user_ref}] if inv.user_ref else [])
            ),
        }

    return {"total": len(rows), "results": [to_dict(r) for r in rows]}

@app.get("/api/investigations/{inv_id}", tags=["Investigations"])
def get_investigation(inv_id: str, db: Session = Depends(get_db)):
    inv = db.get(Investigation, inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return {
        "id": inv.id,
        "title": inv.title,
        "status": inv.status,
        "severity": inv.severity,
        "owner": inv.owner,
        "opened_at": inv.opened_at.isoformat() if inv.opened_at else None,
        "closed_at": inv.closed_at.isoformat() if inv.closed_at else None,
        "root_cause_tag": inv.root_cause_tag,
        "summary": inv.summary,
        "notes": inv.notes,
        "links": (
            ([{"type":"sku","key":inv.sku_code}] if inv.sku_code else [])
            + ([{"type":"zone","key":inv.zone}] if inv.zone else [])
            + ([{"type":"user","key":inv.user_ref}] if inv.user_ref else [])
        ),
    }

@app.put("/api/investigations/{inv_id}", tags=["Investigations"])
def update_investigation(inv_id: str, payload: InvestigationUpdate, db: Session = Depends(get_db)):
    inv = db.get(Investigation, inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    if payload.status:
        valid = {"open", "in_progress", "blocked", "closed"}
        if payload.status not in valid:
            raise HTTPException(status_code=422, detail=f"Status must be one of {valid}")
        inv.status = payload.status
        if payload.status == "closed":
            inv.closed_at = datetime.utcnow()

    if payload.severity is not None:
        inv.severity = payload.severity
    if payload.owner is not None:
        inv.owner = payload.owner
    if payload.root_cause_tag is not None:
        inv.root_cause_tag = payload.root_cause_tag
    if payload.summary is not None:
        inv.summary = payload.summary

    db.commit()
    db.refresh(inv)

    return {
        "id": inv.id,
        "title": inv.title,
        "status": inv.status,
        "severity": inv.severity,
        "owner": inv.owner,
        "opened_at": inv.opened_at.isoformat() if inv.opened_at else None,
        "closed_at": inv.closed_at.isoformat() if inv.closed_at else None,
        "root_cause_tag": inv.root_cause_tag,
        "summary": inv.summary,
        "notes": inv.notes,
        "links": (
            ([{"type":"sku","key":inv.sku_code}] if inv.sku_code else [])
            + ([{"type":"zone","key":inv.zone}] if inv.zone else [])
            + ([{"type":"user","key":inv.user_ref}] if inv.user_ref else [])
        ),
    }
