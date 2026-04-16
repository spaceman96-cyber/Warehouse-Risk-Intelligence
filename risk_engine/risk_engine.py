# risk_engine/risk_engine.py
"""
WRI Risk Scoring Engine — v1
API-first: consumes DataFrames (adj + sku) and returns score DataFrames.
"""

from __future__ import annotations

import warnings
from datetime import date, timedelta
from typing import Optional, Tuple, Dict

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

LOOKBACK_30 = 30
LOOKBACK_7 = 7
TOP_N_RECS = 15

W_FREQ = 0.35
W_DRIFT = 0.30
W_VALUE = 0.20
W_ZONE = 0.15


def _ensure_required_cols(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{name} missing required columns: {sorted(list(missing))}")


def prepare_adjustments(adj: pd.DataFrame) -> pd.DataFrame:
    """
    Required: timestamp, sku_code, qty_delta, user_ref
    Optional: zone, location_code, adjustment_type
    """
    adj = adj.copy()
    _ensure_required_cols(adj, {"timestamp", "sku_code", "qty_delta", "user_ref"}, "adjustments")

    adj["timestamp"] = pd.to_datetime(adj["timestamp"], errors="coerce")
    if adj["timestamp"].isna().any():
        bad = int(adj["timestamp"].isna().sum())
        raise ValueError(f"adjustments has {bad} rows with invalid timestamp")

    adj["sku_code"] = adj["sku_code"].astype(str).str.upper().str.strip()
    adj["user_ref"] = adj["user_ref"].astype(str).str.strip()

    if "zone" in adj.columns:
        adj["zone"] = adj["zone"].astype(str).str.upper().str.strip()
    else:
        adj["zone"] = "UNKNOWN"

    if "location_code" in adj.columns:
        adj["location_code"] = adj["location_code"].astype(str).str.upper().str.strip()

    adj["qty_delta"] = pd.to_numeric(adj["qty_delta"], errors="coerce")
    if adj["qty_delta"].isna().any():
        bad = int(adj["qty_delta"].isna().sum())
        raise ValueError(f"adjustments has {bad} rows with invalid qty_delta (not a number)")

    adj["date"] = adj["timestamp"].dt.date
    adj["abs_qty"] = adj["qty_delta"].abs()
    adj["is_neg"] = adj["qty_delta"] < 0

    return adj


def prepare_sku_master(sku: pd.DataFrame) -> pd.DataFrame:
    """
    Required: sku_code
    Recommended: sku_name, category, abc_class, unit_cost, value_band
    """
    sku = sku.copy()
    _ensure_required_cols(sku, {"sku_code"}, "sku_master")

    sku["sku_code"] = sku["sku_code"].astype(str).str.upper().str.strip()

    for col, default in [
        ("sku_name", ""),
        ("category", ""),
        ("abc_class", ""),
        ("unit_cost", 0.0),
        ("value_band", ""),
    ]:
        if col not in sku.columns:
            sku[col] = default

    sku["category"] = sku["category"].astype(str).str.strip()
    sku["abc_class"] = sku["abc_class"].astype(str).str.upper().str.strip()
    sku["value_band"] = sku["value_band"].astype(str).str.strip()
    sku["unit_cost"] = pd.to_numeric(sku["unit_cost"], errors="coerce").fillna(0.0)

    return sku


def normalize(series: pd.Series) -> pd.Series:
    mn, mx = series.min(), series.max()
    if pd.isna(mn) or pd.isna(mx) or mx == mn:
        return pd.Series(0.0, index=series.index)
    return ((series - mn) / (mx - mn) * 100).round(2)


def window(adj: pd.DataFrame, score_date: date, days: int) -> pd.DataFrame:
    cutoff = score_date - timedelta(days=days)
    return adj[adj["date"] >= cutoff].copy()


def freq_score(adj: pd.DataFrame, score_date: date, lookback_30: int) -> pd.Series:
    w = window(adj, score_date, lookback_30)
    return w.groupby("sku_code").size().rename("freq_30d")


def drift_score(adj: pd.DataFrame, score_date: date, lookback_30: int, lookback_7: int) -> pd.Series:
    w30 = window(adj, score_date, lookback_30)
    w7 = window(adj, score_date, lookback_7)

    avg30 = w30.groupby("sku_code")["abs_qty"].mean().rename("avg30")
    avg7 = w7.groupby("sku_code")["abs_qty"].mean().rename("avg7")

    drift = pd.concat([avg30, avg7], axis=1).fillna(0)
    drift["ratio"] = drift.apply(lambda r: (r["avg7"] / r["avg30"]) if r["avg30"] > 0 else 1.0, axis=1)
    return drift["ratio"]


def value_score(adj: pd.DataFrame, sku: pd.DataFrame, score_date: date, lookback_30: int) -> pd.Series:
    w = window(adj, score_date, lookback_30)
    cost_map = sku.set_index("sku_code")["unit_cost"].to_dict()

    w = w.copy()
    w["unit_cost"] = w["sku_code"].map(cost_map).fillna(0.0)
    w["dollar_loss"] = w["abs_qty"] * w["unit_cost"]

    return w.groupby("sku_code")["dollar_loss"].sum().rename("dollar_loss_30d")


def zone_risk_score(adj: pd.DataFrame, score_date: date, lookback_30: int) -> pd.Series:
    w = window(adj, score_date, lookback_30)
    zone_freq = w.groupby("zone").size().rename("zone_freq")
    zone_abs = w.groupby("zone")["abs_qty"].mean().rename("zone_avg_abs")
    z = pd.concat([zone_freq, zone_abs], axis=1).fillna(0)
    z["raw"] = (z["zone_freq"] * 0.6) + (z["zone_avg_abs"] * 0.4)
    return z["raw"]


def user_anomaly_score(adj: pd.DataFrame, score_date: date, lookback_30: int) -> pd.DataFrame:
    w = window(adj, score_date, lookback_30)

    total = w.groupby("user_ref").size().rename("total")
    neg_count = w[w["is_neg"]].groupby("user_ref").size().rename("neg_count")

    # Keep your v1 heuristic exactly (minute >= 30)
    endshift = w[w["timestamp"].dt.minute >= 30].groupby("user_ref").size().rename("endshift_count")

    u = pd.concat([total, neg_count, endshift], axis=1).fillna(0)

    u["neg_ratio"] = (u["neg_count"] / u["total"].replace(0, np.nan)).fillna(0)
    u["endshift_ratio"] = (u["endshift_count"] / u["total"].replace(0, np.nan)).fillna(0)

    u["freq_score"] = normalize(u["total"])
    u["neg_score"] = normalize(u["neg_ratio"])
    u["endshift_score"] = normalize(u["endshift_ratio"])

    u["user_risk_score"] = (
        (u["freq_score"] * 0.30)
        + (u["neg_score"] * 0.35)
        + (u["endshift_score"] * 0.35)
    ).round(2)

    u["risk_score"] = normalize(u["user_risk_score"]).round(0).astype(int)

    out = u[["total", "neg_ratio", "endshift_ratio", "risk_score"]].copy()
    out.columns = ["adj_count_30d", "neg_ratio", "endshift_ratio", "risk_score"]
    out.index.name = "user_ref"
    return out.reset_index().sort_values("risk_score", ascending=False)


def sku_risk_score(
    adj: pd.DataFrame,
    sku: pd.DataFrame,
    score_date: date,
    lookback_30: int,
    lookback_7: int,
) -> pd.DataFrame:
    all_skus = sku["sku_code"].tolist()

    freq = freq_score(adj, score_date, lookback_30).reindex(all_skus).fillna(0)
    drift = drift_score(adj, score_date, lookback_30, lookback_7).reindex(all_skus).fillna(1.0)
    value = value_score(adj, sku, score_date, lookback_30).reindex(all_skus).fillna(0.0)

    w30 = window(adj, score_date, lookback_30)
    sku_zone = (
        w30.groupby(["sku_code", "zone"])
        .size()
        .reset_index(name="cnt")
        .sort_values("cnt", ascending=False)
        .drop_duplicates("sku_code")
        .set_index("sku_code")["zone"]
    )

    zone_raw = zone_risk_score(adj, score_date, lookback_30)
    zone_norm = normalize(zone_raw)
    sku_zone_score = sku_zone.map(zone_norm).reindex(all_skus).fillna(0.0)

    freq_n = normalize(freq)
    drift_n = normalize(drift)
    value_n = normalize(value)
    zone_n = sku_zone_score

    composite = (W_FREQ * freq_n) + (W_DRIFT * drift_n) + (W_VALUE * value_n) + (W_ZONE * zone_n)

    sku_meta = sku.set_index("sku_code")[["sku_name", "category", "unit_cost", "abc_class", "value_band"]]

    result = pd.DataFrame(
        {
            "sku_code": all_skus,
            "freq_30d": freq.values,
            "drift_ratio_7d": drift.round(3).values,
            "dollar_loss_30d": value.round(2).values,
            "zone": sku_zone.reindex(all_skus).values,
            "freq_score": freq_n.round(2).values,
            "drift_score": drift_n.round(2).values,
            "value_score": value_n.round(2).values,
            "zone_score": zone_n.round(2).values,
            "risk_score": composite.round(0).astype(int).values,
        }
    ).set_index("sku_code")

    result = result.join(sku_meta)
    result = result.sort_values("risk_score", ascending=False)
    result.index.name = "sku_code"
    return result.reset_index()


def zone_risk_output(adj: pd.DataFrame, score_date: date, lookback_30: int) -> pd.DataFrame:
    w = window(adj, score_date, lookback_30)

    zone_freq = w.groupby("zone").size().rename("adj_count_30d")
    zone_neg = w[w["is_neg"]].groupby("zone").size().rename("neg_count")
    zone_abs = w.groupby("zone")["abs_qty"].mean().rename("avg_abs_qty")
    zone_skus = w.groupby("zone")["sku_code"].nunique().rename("unique_skus_affected")

    z = pd.concat([zone_freq, zone_neg, zone_abs, zone_skus], axis=1).fillna(0)
    z["neg_ratio"] = (z["neg_count"] / z["adj_count_30d"].replace(0, np.nan)).fillna(0).round(3)

    raw = zone_risk_score(adj, score_date, lookback_30)
    z["risk_score"] = normalize(raw).round(0).astype(int)

    z.index.name = "zone"
    return z.reset_index().sort_values("risk_score", ascending=False)


def build_recommendations(sku_scores: pd.DataFrame, score_date: date, top_n_recs: int) -> pd.DataFrame:
    top = sku_scores.head(top_n_recs).copy()
    top["priority"] = range(1, len(top) + 1)
    top["rec_date"] = score_date
    top["status"] = "proposed"

    def reason(row):
        parts = []
        if float(row.get("drift_ratio_7d", 1.0)) > 1.5:
            parts.append(f"Drift ↑ {row['drift_ratio_7d']:.1f}x vs 30d avg")
        if float(row.get("freq_30d", 0)) >= 5:
            parts.append(f"{int(row['freq_30d'])} adjustments in 30d")
        if float(row.get("dollar_loss_30d", 0.0)) > 100:
            parts.append(f"${row['dollar_loss_30d']:.0f} at risk")
        if str(row.get("value_band", "")).lower() == "high":
            parts.append("High-value SKU")
        return " | ".join(parts) if parts else "Elevated composite risk"

    top["reason"] = top.apply(reason, axis=1)

    return top[
        ["priority", "rec_date", "sku_code", "sku_name", "category", "zone", "risk_score", "reason", "status"]
    ]


def detect_spikes(adj: pd.DataFrame, score_date: date, lookback_30: int, lookback_7: int) -> pd.DataFrame:
    w30 = window(adj, score_date, lookback_30)
    w7 = window(adj, score_date, lookback_7)

    daily_avg_30 = (w30.groupby("sku_code").size() / float(lookback_30)).rename("daily_avg_30d")
    count_7 = w7.groupby("sku_code").size().rename("count_7d")
    daily_avg_7 = (count_7 / float(lookback_7)).rename("daily_avg_7d")

    spikes = pd.concat([daily_avg_30, daily_avg_7, count_7], axis=1).dropna()
    spikes = spikes[spikes["daily_avg_30d"] > 0]
    spikes["spike_ratio"] = (spikes["daily_avg_7d"] / spikes["daily_avg_30d"]).round(2)

    spikes = spikes[spikes["spike_ratio"] > 2.0].sort_values("spike_ratio", ascending=False)
    spikes.index.name = "sku_code"
    return spikes.reset_index()


def compute_all(
    adj: pd.DataFrame,
    sku: pd.DataFrame,
    score_date: Optional[date] = None,
    lookback_30: int = LOOKBACK_30,
    lookback_7: int = LOOKBACK_7,
    top_n_recs: int = TOP_N_RECS,
) -> Dict[str, object]:
    adj_p = prepare_adjustments(adj)
    sku_p = prepare_sku_master(sku)

    score_date_final = score_date or pd.to_datetime(adj_p["timestamp"]).dt.date.max()

    sku_scores = sku_risk_score(adj_p, sku_p, score_date_final, lookback_30, lookback_7)
    zone_scores = zone_risk_output(adj_p, score_date_final, lookback_30)
    user_scores = user_anomaly_score(adj_p, score_date_final, lookback_30)
    recs = build_recommendations(sku_scores, score_date_final, top_n_recs)
    spikes = detect_spikes(adj_p, score_date_final, lookback_30, lookback_7)

    return {
        "score_date": score_date_final,
        "sku_scores": sku_scores,
        "zone_scores": zone_scores,
        "user_scores": user_scores,
        "recommendations": recs,
        "spikes": spikes,
    }