"""
WRI Synthetic Data Generator — MVP v0.1
========================================
Generates two CSVs:
  1. sku_master.csv       — 30 SKUs across 5 categories
  2. adjustment_log.csv   — ~1,000 adjustment events over 90 days

5 anomaly patterns baked in:
  P1 — SKU-007: chronic small negative adjustments (slow shrinkage)
  P2 — Zone C:  3x adjustment frequency vs other zones (location problem)
  P3 — USER-07: 60% of adjustments in last 30min of shift (suspicious timing)
  P4 — SKU-019: normal for 60 days, then spike in days 61-90
  P5 — Beverages category: small qty but high dollar value loss

Run:
    pip install pandas numpy faker
    python generate_wri_data.py

Outputs: sku_master.csv, adjustment_log.csv
"""

import pandas as pd
import numpy as np
import random
import uuid
from datetime import datetime, timedelta
import os

# ── Reproducibility ──────────────────────────────────────────
random.seed(42)
np.random.seed(42)

# ── Config ───────────────────────────────────────────────────
START_DATE      = datetime(2024, 1, 1)
END_DATE        = datetime(2024, 3, 31)   # 90 days
TOTAL_DAYS      = (END_DATE - START_DATE).days
TARGET_ROWS     = 1000

ZONES           = ["A", "B", "C", "D", "E"]
SHIFTS          = ["Morning", "Afternoon", "Night"]
SHIFT_HOURS     = {"Morning": (6, 14), "Afternoon": (14, 22), "Night": (22, 30)}
USERS           = [f"USER-{str(i).zfill(2)}" for i in range(1, 11)]  # USER-01 to USER-10
ADJ_TYPES       = ["CycleCount", "Damage", "Returns", "Unknown"]
REASON_CODES    = ["QTY_MISMATCH", "DAMAGED_GOODS", "PUTAWAY_ERROR",
                   "PICKING_ERROR", "RECEIVING_DISCREPANCY", "SYSTEM_ERROR", "OTHER"]

CATEGORIES = {
    "Beverages":     {"count": 8,  "unit_cost_range": (6.0,  15.0),  "movement_range": (1800, 3000)},
    "Snacks":        {"count": 7,  "unit_cost_range": (1.5,  5.0),   "movement_range": (2000, 4000)},
    "Personal Care": {"count": 6,  "unit_cost_range": (3.0,  12.0),  "movement_range": (800,  2000)},
    "Household":     {"count": 5,  "unit_cost_range": (2.0,  8.0),   "movement_range": (600,  1800)},
    "Frozen":        {"count": 4,  "unit_cost_range": (8.0,  25.0),  "movement_range": (400,  1200)},
}

# ── Helpers ───────────────────────────────────────────────────

def bins_for_zone(zone: str, n: int = 6) -> list:
    return [f"{zone}-{str(row).zfill(2)}-{str(col).zfill(2)}"
            for row in range(1, n+1) for col in range(1, 4)]

ALL_BINS = {z: bins_for_zone(z) for z in ZONES}

def random_ts(day_offset: int, shift: str) -> datetime:
    h_start, h_end = SHIFT_HOURS[shift]
    hour   = random.randint(h_start, h_end - 1) % 24
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return START_DATE + timedelta(days=day_offset, hours=hour,
                                  minutes=minute, seconds=second)

def random_ts_endshift(day_offset: int, shift: str) -> datetime:
    """USER-07 anomaly: timestamps clustered in last 30 min of shift."""
    _, h_end = SHIFT_HOURS[shift]
    hour   = (h_end - 1) % 24
    minute = random.randint(30, 59)
    second = random.randint(0, 59)
    return START_DATE + timedelta(days=day_offset, hours=hour,
                                  minutes=minute, seconds=second)

def abc_class(movement: int) -> str:
    if movement >= 2000: return "A"
    if movement >= 1000: return "B"
    return "C"

def value_band(cost: float) -> str:
    if cost >= 10: return "high"
    if cost >= 4:  return "med"
    return "low"

# ── 1. SKU MASTER ─────────────────────────────────────────────

def build_sku_master() -> pd.DataFrame:
    rows = []
    sku_num = 1
    for category, cfg in CATEGORIES.items():
        for _ in range(cfg["count"]):
            sku_code    = f"SKU-{str(sku_num).zfill(3)}"
            cost        = round(random.uniform(*cfg["unit_cost_range"]), 2)
            movement    = random.randint(*cfg["movement_range"])
            rows.append({
                "sku_code":             sku_code,
                "sku_name":             f"{category} Product {sku_num:03d}",
                "category":             category,
                "uom":                  "EA",
                "unit_cost":            cost,
                "value_band":           value_band(cost),
                "abc_class":            abc_class(movement),
                "avg_monthly_movement": movement,
            })
            sku_num += 1
    df = pd.DataFrame(rows)
    # Force specific SKUs for anomaly patterns
    df.loc[df.sku_code == "SKU-007", "category"]   = "Snacks"         # P1
    df.loc[df.sku_code == "SKU-007", "unit_cost"]   = 2.5
    df.loc[df.sku_code == "SKU-019", "category"]    = "Personal Care"  # P4
    df.loc[df.sku_code == "SKU-019", "unit_cost"]   = 9.0
    # Make Beverages high-value for P5
    df.loc[df.category == "Beverages", "unit_cost"] = df.loc[
        df.category == "Beverages", "unit_cost"].apply(lambda x: max(x, 10.0))
    df.loc[df.category == "Beverages", "value_band"] = "high"
    return df

# ── 2. ADJUSTMENT LOG ─────────────────────────────────────────

def build_adjustment_log(sku_master: pd.DataFrame) -> pd.DataFrame:
    all_skus        = sku_master.sku_code.tolist()
    beverage_skus   = sku_master[sku_master.category == "Beverages"].sku_code.tolist()
    normal_skus     = [s for s in all_skus if s not in ["SKU-007", "SKU-019"]]

    rows = []

    # ── NORMAL baseline ──────────────────────────────────────
    # ~700 normal rows spread across all zones / users
    for _ in range(700):
        day    = random.randint(0, TOTAL_DAYS - 1)
        shift  = random.choice(SHIFTS)
        zone   = random.choice(["A", "B", "D", "E"])   # Zone C less here; boosted in P2
        sku    = random.choice(normal_skus)
        user   = random.choice([u for u in USERS if u != "USER-07"])
        qty    = random.choice([-1,-1,-1,-2,-3,1,2,3,4,-4,-5,5])
        sys_q  = random.randint(50, 500)
        loc    = random.choice(ALL_BINS[zone])
        rows.append({
            "adjustment_id":    str(uuid.uuid4()),
            "timestamp":        random_ts(day, shift),
            "sku_code":         sku,
            "location_code":    loc,
            "zone":             zone,
            "qty_delta":        qty,
            "adjustment_type":  random.choice(ADJ_TYPES),
            "reason_code":      random.choice(REASON_CODES),
            "user_ref":         user,
            "shift":            shift,
            "system_qty_before":sys_q,
            "physical_qty_found": sys_q + qty,
            "doc_ref":          f"ADJ-{random.randint(10000,99999)}",
            "remarks":          random.choice([
                "Qty mismatch after cycle count",
                "Putaway error corrected",
                "Damaged goods removed",
                "Receiving discrepancy",
                "",
            ]),
            "anomaly_pattern":  "NORMAL",
        })

    # ── P1: SKU-007 chronic small negatives ─────────────────
    # Every 5-7 days, -5 to -15 units. Same SKU, different locations.
    day = 0
    while day < TOTAL_DAYS:
        shift = random.choice(SHIFTS)
        zone  = random.choice(ZONES)
        loc   = random.choice(ALL_BINS[zone])
        qty   = random.randint(-15, -5)
        sys_q = random.randint(100, 300)
        rows.append({
            "adjustment_id":    str(uuid.uuid4()),
            "timestamp":        random_ts(day, shift),
            "sku_code":         "SKU-007",
            "location_code":    loc,
            "zone":             zone,
            "qty_delta":        qty,
            "adjustment_type":  "CycleCount",
            "reason_code":      "QTY_MISMATCH",
            "user_ref":         random.choice(USERS),
            "shift":            shift,
            "system_qty_before":sys_q,
            "physical_qty_found": sys_q + qty,
            "doc_ref":          f"CC-{random.randint(1000,9999)}",
            "remarks":          "Consistent shortfall — cause unknown",
            "anomaly_pattern":  "P1_CHRONIC_SHRINKAGE",
        })
        day += random.randint(5, 7)

    # ── P2: Zone C 3x frequency ──────────────────────────────
    for _ in range(120):
        day   = random.randint(0, TOTAL_DAYS - 1)
        shift = random.choice(SHIFTS)
        sku   = random.choice(all_skus)
        loc   = random.choice(ALL_BINS["C"])
        qty   = random.choice([-2,-3,-4,-5,-6,1,2,3])
        sys_q = random.randint(30, 200)
        rows.append({
            "adjustment_id":    str(uuid.uuid4()),
            "timestamp":        random_ts(day, shift),
            "sku_code":         sku,
            "location_code":    loc,
            "zone":             "C",
            "qty_delta":        qty,
            "adjustment_type":  random.choice(ADJ_TYPES),
            "reason_code":      random.choice(REASON_CODES),
            "user_ref":         random.choice(USERS),
            "shift":            shift,
            "system_qty_before":sys_q,
            "physical_qty_found": sys_q + qty,
            "doc_ref":          f"ADJ-{random.randint(10000,99999)}",
            "remarks":          "Zone C location discrepancy",
            "anomaly_pattern":  "P2_ZONE_C_VOLATILE",
        })

    # ── P3: USER-07 end-of-shift clustering ─────────────────
    for _ in range(80):
        day   = random.randint(0, TOTAL_DAYS - 1)
        shift = random.choice(SHIFTS)
        zone  = random.choice(ZONES)
        sku   = random.choice(all_skus)
        loc   = random.choice(ALL_BINS[zone])
        qty   = random.choice([-3,-4,-5,-6,-7,-8])
        sys_q = random.randint(50, 400)
        # 60% end of shift, 40% normal
        ts = (random_ts_endshift(day, shift)
              if random.random() < 0.60
              else random_ts(day, shift))
        rows.append({
            "adjustment_id":    str(uuid.uuid4()),
            "timestamp":        ts,
            "sku_code":         sku,
            "location_code":    loc,
            "zone":             zone,
            "qty_delta":        qty,
            "adjustment_type":  "Unknown",
            "reason_code":      "OTHER",
            "user_ref":         "USER-07",
            "shift":            shift,
            "system_qty_before":sys_q,
            "physical_qty_found": sys_q + qty,
            "doc_ref":          f"ADJ-{random.randint(10000,99999)}",
            "remarks":          "",
            "anomaly_pattern":  "P3_USER07_ENDSHIFT",
        })

    # ── P4: SKU-019 spike after day 60 ──────────────────────
    # Days 0-60: quiet (3 small events)
    for _ in range(3):
        day   = random.randint(0, 59)
        shift = random.choice(SHIFTS)
        zone  = random.choice(ZONES)
        loc   = random.choice(ALL_BINS[zone])
        sys_q = random.randint(200, 600)
        rows.append({
            "adjustment_id":    str(uuid.uuid4()),
            "timestamp":        random_ts(day, shift),
            "sku_code":         "SKU-019",
            "location_code":    loc,
            "zone":             zone,
            "qty_delta":        random.choice([-1, -2, 1]),
            "adjustment_type":  "CycleCount",
            "reason_code":      "QTY_MISMATCH",
            "user_ref":         random.choice(USERS),
            "shift":            shift,
            "system_qty_before":sys_q,
            "physical_qty_found": sys_q + random.choice([-1,-2,1]),
            "doc_ref":          f"CC-{random.randint(1000,9999)}",
            "remarks":          "Normal count",
            "anomaly_pattern":  "P4_PRE_SPIKE_NORMAL",
        })
    # Days 61-90: spike (8 large adjustments)
    for _ in range(8):
        day   = random.randint(61, TOTAL_DAYS - 1)
        shift = random.choice(SHIFTS)
        zone  = random.choice(ZONES)
        loc   = random.choice(ALL_BINS[zone])
        qty   = random.randint(-40, -20)
        sys_q = random.randint(200, 600)
        rows.append({
            "adjustment_id":    str(uuid.uuid4()),
            "timestamp":        random_ts(day, shift),
            "sku_code":         "SKU-019",
            "location_code":    loc,
            "zone":             zone,
            "qty_delta":        qty,
            "adjustment_type":  "Unknown",
            "reason_code":      "QTY_MISMATCH",
            "user_ref":         random.choice(USERS),
            "shift":            shift,
            "system_qty_before":sys_q,
            "physical_qty_found": sys_q + qty,
            "doc_ref":          f"ADJ-{random.randint(10000,99999)}",
            "remarks":          "Large variance — investigation required",
            "anomaly_pattern":  "P4_SPIKE",
        })

    # ── P5: Beverages — small qty, high dollar value ─────────
    for _ in range(40):
        day   = random.randint(0, TOTAL_DAYS - 1)
        shift = random.choice(SHIFTS)
        zone  = random.choice(ZONES)
        sku   = random.choice(beverage_skus)
        loc   = random.choice(ALL_BINS[zone])
        qty   = random.choice([-1, -2, -3])   # small qty
        sys_q = random.randint(80, 300)
        rows.append({
            "adjustment_id":    str(uuid.uuid4()),
            "timestamp":        random_ts(day, shift),
            "sku_code":         sku,
            "location_code":    loc,
            "zone":             zone,
            "qty_delta":        qty,
            "adjustment_type":  "Damage",
            "reason_code":      "DAMAGED_GOODS",
            "user_ref":         random.choice(USERS),
            "shift":            shift,
            "system_qty_before":sys_q,
            "physical_qty_found": sys_q + qty,
            "doc_ref":          f"DMG-{random.randint(1000,9999)}",
            "remarks":          "Beverage damage — small qty high value",
            "anomaly_pattern":  "P5_HIGH_VALUE_LOSS",
        })

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Add human-readable date cols
    df["date"]  = df["timestamp"].dt.date
    df["hour"]  = df["timestamp"].dt.hour

    # Enrich with unit cost from sku_master
    cost_map = sku_master.set_index("sku_code")["unit_cost"].to_dict()
    df["unit_cost"]     = df["sku_code"].map(cost_map)
    df["value_impact"]  = (df["qty_delta"] * df["unit_cost"]).round(2)

    return df

# ── MAIN ──────────────────────────────────────────────────────

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    os.makedirs(DATA_DIR, exist_ok=True)
    print("Building SKU master...")
    sku_master = build_sku_master()
    sku_master.to_csv(os.path.join(DATA_DIR, "sku_master.csv"), index=False)
    print(f"  ✓ sku_master.csv — {len(sku_master)} rows")

    print("Building adjustment log...")
    adj_log = build_adjustment_log(sku_master)
    adj_log.to_csv(os.path.join(DATA_DIR, "adjustment_log.csv"), index=False)
    print(f"  ✓ adjustment_log.csv — {len(adj_log)} rows")

    print("\n── Anomaly pattern summary ──")
    print(adj_log.anomaly_pattern.value_counts().to_string())

    print("\n── Zone distribution ──")
    print(adj_log.zone.value_counts().sort_index().to_string())

    print("\n── USER-07 shift timing (should be skewed late) ──")
    u7 = adj_log[adj_log.user_ref == "USER-07"]
    print(f"  Total USER-07 rows: {len(u7)}")
    print(f"  End-of-shift (min>=30): {(u7['timestamp'].dt.minute >= 30).sum()}")

    print("\n── SKU-019 timeline ──")
    s19 = adj_log[adj_log.sku_code == "SKU-019"].copy()
    s19["day"] = (s19["timestamp"] - datetime(2024,1,1)).dt.days
    print(f"  Days 0-60:  {(s19.day <= 60).sum()} events")
    print(f"  Days 61-90: {(s19.day > 60).sum()} events  ← spike")

    print("\nDone. Load CSVs into PostgreSQL with COPY or pandas to_sql.")
