# services/agents/duncan_agent.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import hashlib

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select

from api.models import Investigation


@dataclass
class DuncanCase:
    title: str
    severity: str  # low/med/high
    confidence: int  # 0-100
    hypothesis: str
    evidence: Dict[str, Any]
    checklist: List[str]
    sku_code: Optional[str] = None
    zone: Optional[str] = None
    user_ref: Optional[str] = None
    dedupe_key: Optional[str] = None
    source: str = "duncan_agent"
    created_at: str = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "severity": self.severity,
            "confidence": self.confidence,
            "hypothesis": self.hypothesis,
            "evidence": self.evidence,
            "checklist": self.checklist,
            "sku_code": self.sku_code,
            "zone": self.zone,
            "user_ref": self.user_ref,
            "dedupe_key": self.dedupe_key,
            "source": self.source,
            "created_at": self.created_at,
        }


class DuncanAgent:
    """Rule-based reasoning layer that converts WRI signals into investigations.

    MVP goals:
    - Explainable cases (title/hypothesis/evidence/checklist)
    - Confidence score (0-100) for trust + gating
    - Stable dedupe keys to avoid investigation spam
    """

    def __init__(self, score_date):
        self.score_date = score_date

    # -------------------------
    # Confidence scoring
    # -------------------------
    @staticmethod
    def _clamp(n: float, lo: float = 0.0, hi: float = 100.0) -> int:
        return int(max(lo, min(hi, round(n))))

    @staticmethod
    def _combine_weighted(parts: List[Tuple[float, float]]) -> int:
        # parts: [(value0_100, weight), ...] ignore missing (None)
        total_w = sum(w for v, w in parts if v is not None)
        if total_w <= 0:
            return 0
        score = sum(v * w for v, w in parts if v is not None) / total_w
        return DuncanAgent._clamp(score)

    @staticmethod
    def confidence_from_signals(
        *,
        sku_risk: Optional[float] = None,
        spike_ratio: Optional[float] = None,
        user_risk: Optional[float] = None,
        zone_risk: Optional[float] = None,
        value_band: Optional[str] = None,
    ) -> int:
        # Normalize spike ratio (>2 means spike). Map 2..6 to 60..95.
        spike_score = None
        if spike_ratio is not None:
            if spike_ratio < 2.0:
                spike_score = 40.0
            else:
                spike_score = 60.0 + (min(spike_ratio, 6.0) - 2.0) * (35.0 / 4.0)

        # Base weighted blend. (Sku risk is strongest.)
        base = DuncanAgent._combine_weighted([
            (sku_risk, 0.45),
            (spike_score, 0.25),
            (user_risk, 0.20),
            (zone_risk, 0.10),
        ])

        # Small boost for high-value SKUs (but do not exceed 100).
        vb = (value_band or "").lower().strip()
        if vb in {"high", "a"}:
            base = min(100, base + 5)
        return int(base)

    # -------------------------
    # Dedupe keys
    # -------------------------
    @staticmethod
    def make_dedupe_key(kind: str, sku_code: Optional[str], zone: Optional[str], user_ref: Optional[str], score_date) -> str:
        raw = f"{kind}|{sku_code or ''}|{zone or ''}|{user_ref or ''}|{score_date}"
        return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()

    # -------------------------
    # Case builders
    # -------------------------
    def build_cases(
        self,
        *,
        sku_scores: pd.DataFrame,
        zone_scores: pd.DataFrame,
        user_scores: pd.DataFrame,
        recommendations: pd.DataFrame,
        spikes: pd.DataFrame,
        max_spikes: int = 5,
        max_top_skus: int = 8,
        max_users: int = 5,
        max_zones: int = 3,
    ) -> List[DuncanCase]:
        cases: List[DuncanCase] = []

        # Helpful lookup for sku meta (name/value band)
        sku_lookup = {}
        if not sku_scores.empty:
            for _, r in sku_scores.iterrows():
                sku_lookup[str(r.get("sku_code"))] = r.to_dict()

        # 1) Spike cases (highest urgency)
        if not spikes.empty:
            for _, r in spikes.head(max_spikes).iterrows():
                sku = str(r.get("sku_code"))
                spike_ratio = float(r.get("spike_ratio", 0) or 0)
                meta = sku_lookup.get(sku, {})
                sku_risk = meta.get("risk_score")
                zone = meta.get("zone")
                value_band = meta.get("value_band")
                conf = self.confidence_from_signals(
                    sku_risk=float(sku_risk) if sku_risk is not None else None,
                    spike_ratio=spike_ratio,
                    zone_risk=None,
                    user_risk=None,
                    value_band=value_band,
                )

                severity = "high" if conf >= 80 else "med"
                title = f"Spike detected: {sku} (x{spike_ratio:.2f})"
                hypothesis = "Sudden increase in adjustments suggests process break (mis-slotting, mis-pick, or rapid shrinkage)."  # explainable, not accusatory
                evidence = {
                    "sku_code": sku,
                    "spike_ratio": spike_ratio,
                    "daily_avg_30d": float(r.get("daily_avg_30d", 0) or 0),
                    "daily_avg_7d": float(r.get("daily_avg_7d", 0) or 0),
                    "count_7d": int(r.get("count_7d", 0) or 0),
                    "sku_risk_score": sku_risk,
                    "zone": zone,
                    "sku_name": meta.get("sku_name"),
                    "value_band": value_band,
                }
                checklist = [
                    "Verify slotting / bin location for this SKU (mis-slotting is common after replenishment).",
                    "Check last 48h receiving/replenishment records for this SKU.",
                    "Review top users touching this SKU (negative adjustments + end-of-shift clustering).",
                    "If physical variance confirmed, trigger targeted cycle count for this SKU + neighboring bins.",
                ]
                dedupe = self.make_dedupe_key("spike", sku, zone, None, self.score_date)
                cases.append(DuncanCase(
                    title=title,
                    severity=severity,
                    confidence=conf,
                    hypothesis=hypothesis,
                    evidence=evidence,
                    checklist=checklist,
                    sku_code=sku,
                    zone=zone,
                    dedupe_key=dedupe,
                ))

        # 2) Top SKU recommendations → investigation cases
        if not recommendations.empty:
            for _, r in recommendations.head(max_top_skus).iterrows():
                sku = str(r.get("sku_code"))
                meta = sku_lookup.get(sku, {})
                sku_risk = float(r.get("risk_score", meta.get("risk_score", 0)) or 0)
                zone = r.get("zone") or meta.get("zone")
                value_band = meta.get("value_band")
                conf = self.confidence_from_signals(
                    sku_risk=sku_risk,
                    spike_ratio=None,
                    zone_risk=None,
                    user_risk=None,
                    value_band=value_band,
                )
                severity = "high" if conf >= 85 else ("med" if conf >= 65 else "low")
                title = f"Investigate high-risk SKU: {sku}"
                hypothesis = "Composite risk score indicates repeated variance signals (frequency, drift, value impact, and zone exposure)." 
                evidence = {
                    "sku_code": sku,
                    "sku_name": meta.get("sku_name") or r.get("sku_name"),
                    "category": meta.get("category") or r.get("category"),
                    "zone": zone,
                    "risk_score": sku_risk,
                    "reason": r.get("reason"),
                    "drift_ratio_7d": meta.get("drift_ratio_7d"),
                    "dollar_loss_30d": meta.get("dollar_loss_30d"),
                    "value_band": value_band,
                }
                checklist = [
                    "Run targeted cycle count for this SKU in its primary zone.",
                    "Compare 7d vs 30d adjustment mix (manual vs system, negative vs positive).",
                    "Inspect receiving + putaway accuracy for the last replenishment wave.",
                ]
                dedupe = self.make_dedupe_key("sku", sku, str(zone) if zone else None, None, self.score_date)
                cases.append(DuncanCase(
                    title=title,
                    severity=severity,
                    confidence=conf,
                    hypothesis=hypothesis,
                    evidence=evidence,
                    checklist=checklist,
                    sku_code=sku,
                    zone=str(zone) if zone else None,
                    dedupe_key=dedupe,
                ))

        # 3) Risky users
        if not user_scores.empty:
            for _, r in user_scores.head(max_users).iterrows():
                user = str(r.get("user_ref"))
                user_risk = float(r.get("risk_score", 0) or 0)
                conf = self.confidence_from_signals(
                    sku_risk=None,
                    spike_ratio=None,
                    user_risk=user_risk,
                    zone_risk=None,
                    value_band=None,
                )
                severity = "med" if conf >= 70 else "low"
                title = f"User anomaly: {user}"
                hypothesis = "User shows unusual adjustment signature (high negative ratio and/or end-of-shift clustering)." 
                evidence = {
                    "user_ref": user,
                    "risk_score": user_risk,
                    "adj_count_30d": int(r.get("adj_count_30d", 0) or 0),
                    "neg_ratio": float(r.get("neg_ratio", 0) or 0),
                    "endshift_ratio": float(r.get("endshift_ratio", 0) or 0),
                }
                checklist = [
                    "Review top SKUs adjusted by this user in last 7 days.",
                    "Check for repeated negative adjustments after replenishment windows.",
                    "Confirm whether this user is assigned to exception handling / damaged goods (context matters).",
                ]
                dedupe = self.make_dedupe_key("user", None, None, user, self.score_date)
                cases.append(DuncanCase(
                    title=title,
                    severity=severity,
                    confidence=conf,
                    hypothesis=hypothesis,
                    evidence=evidence,
                    checklist=checklist,
                    user_ref=user,
                    dedupe_key=dedupe,
                ))

        # 4) Risky zones (hotspots)
        if not zone_scores.empty:
            for _, r in zone_scores.head(max_zones).iterrows():
                zone = str(r.get("zone"))
                zone_risk = float(r.get("risk_score", 0) or 0)
                conf = self.confidence_from_signals(
                    sku_risk=None,
                    spike_ratio=None,
                    user_risk=None,
                    zone_risk=zone_risk,
                    value_band=None,
                )
                severity = "med" if conf >= 70 else "low"
                title = f"Zone hotspot: {zone}"
                hypothesis = "Zone shows elevated variance frequency and negative adjustment mix — could indicate process bottleneck or layout issues." 
                evidence = {
                    "zone": zone,
                    "risk_score": zone_risk,
                    "adj_count_30d": int(r.get("adj_count_30d", 0) or 0),
                    "neg_ratio": float(r.get("neg_ratio", 0) or 0),
                    "avg_abs_qty": float(r.get("avg_abs_qty", 0) or 0),
                    "unique_skus_affected": int(r.get("unique_skus_affected", 0) or 0),
                }
                checklist = [
                    "Run zone walk-through: check bin labels, overflow locations, and congestion points.",
                    "Target cycle counts for top 5 SKUs in this zone.",
                    "Validate replenishment/putaway SOP adherence for this zone.",
                ]
                dedupe = self.make_dedupe_key("zone", None, zone, None, self.score_date)
                cases.append(DuncanCase(
                    title=title,
                    severity=severity,
                    confidence=conf,
                    hypothesis=hypothesis,
                    evidence=evidence,
                    checklist=checklist,
                    zone=zone,
                    dedupe_key=dedupe,
                ))

        # Sort by severity then confidence (high first)
        sev_rank = {"high": 3, "med": 2, "low": 1}
        cases.sort(key=lambda c: (sev_rank.get(c.severity, 0), c.confidence), reverse=True)
        return cases

    # -------------------------
    # Persistence: open investigations
    # -------------------------
    @staticmethod
    def _existing_dedupe_keys(db: Session) -> set[str]:
        # Look for keys embedded in notes: "duncan_dedupe_key=<key>"
        rows = db.execute(
            select(Investigation.notes).where(Investigation.status.in_(["open", "in_progress"]))
        ).all()
        keys = set()
        for (notes,) in rows:
            if not notes:
                continue
            for line in str(notes).splitlines():
                if line.startswith("duncan_dedupe_key="):
                    keys.add(line.split("=", 1)[1].strip())
        return keys

    # services/agents/duncan_agent.py
from sqlalchemy import text
import json

class DuncanAgent:
    # ... your existing code ...

    def open_investigations(self, db, cases, max_to_open=5, min_confidence=75):
        opened = 0
        skipped = 0
        created_ids = []
        existing_ids = []

        stmt = text("""
            INSERT INTO investigations (
                title, status, severity, confidence, source, dedupe_key,
                evidence, checklist, hypothesis, sku_code, zone, user_ref,
                opened_at, updated_at
            )
            VALUES (
                :title, 'open', :severity, :confidence, :source, :dedupe_key,
                (:evidence)::jsonb, (:checklist)::jsonb, :hypothesis, :sku_code, :zone, :user_ref,
                now(), now()
            )
            ON CONFLICT (dedupe_key) DO UPDATE
            SET updated_at = now()
            RETURNING id, (xmax = 0) AS inserted;
        """)

        for c in cases:
            if opened >= max_to_open:
                break

            conf = int(getattr(c, "confidence", 0) or 0)
            if conf < min_confidence:
                skipped += 1
                continue

            params = {
                "title": c.title,
                "severity": c.severity,
                "confidence": conf,
                "source": "duncan_agent",
                "dedupe_key": c.dedupe_key,
                "evidence": json.dumps(getattr(c, "evidence", {}) or {}),
                "checklist": json.dumps(getattr(c, "checklist", []) or []),
                "hypothesis": getattr(c, "hypothesis", None),
                "sku_code": getattr(c, "sku_code", None),
                "zone": getattr(c, "zone", None),
                "user_ref": getattr(c, "user_ref", None),
            }

            row = db.execute(stmt, params).fetchone()
            inv_id = str(row[0])
            inserted = bool(row[1])

            if inserted:
                opened += 1
                created_ids.append(inv_id)
            else:
                existing_ids.append(inv_id)

        db.commit()

        return {
            "opened": opened,
            "skipped": skipped,
            "created_ids": created_ids,
            "existing_ids": existing_ids,
        }
    @staticmethod
    def _case_notes(c: DuncanCase) -> str:
        # Store structured metadata in notes without DB migration.
        lines = [
            f"source=duncan_agent",
            f"duncan_dedupe_key={c.dedupe_key}",
            f"confidence={c.confidence}",
            f"score_date={c.evidence.get('score_date', '') or ''}",
            "---",
            "hypothesis:",
            c.hypothesis,
            "---",
            "evidence:",
        ]
        for k, v in c.evidence.items():
            lines.append(f"- {k}: {v}")
        lines.append("---")
        lines.append("checklist:")
        for item in c.checklist:
            lines.append(f"- {item}")
        return "\n".join(lines)

    @staticmethod
    def _new_uuid() -> str:
        # Avoid importing uuid at module import time in some environments
        import uuid
        return str(uuid.uuid4())
