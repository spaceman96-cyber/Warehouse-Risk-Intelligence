# api/services/scoring_service.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Tuple

import pandas as pd
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from ..models import SKUMaster, Adjustment

# compute_all is in project root risk_engine/__init__.py (added to sys.path in api/main.py)
# Import here as well, so routers/services can recompute without touching api/main.py.
import os, sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from risk_engine import compute_all


def _score_window_from_db(db: Session) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[datetime]]:
    """Pull sku_master (all) + adjustments (last 30d relative to max timestamp)."""
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


def _require_data(adj_df: pd.DataFrame, sku_df: pd.DataFrame) -> None:
    if adj_df.empty:
        raise HTTPException(status_code=400, detail="No adjustments loaded yet. Upload /api/ingest/adjustments")
    if sku_df.empty:
        raise HTTPException(status_code=400, detail="No SKU master loaded yet. Upload /api/ingest/sku_master")


def recompute_scores(db: Session):
    adj_df, sku_df, max_ts = _score_window_from_db(db)
    _require_data(adj_df, sku_df)

    score_date = max_ts.date()
    out = compute_all(adj=adj_df, sku=sku_df, score_date=score_date)
    return (
        out["sku_scores"],
        out["zone_scores"],
        out["user_scores"],
        out["recommendations"],
        out["spikes"],
        out["score_date"],
    )
