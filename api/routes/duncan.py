# api/routes/duncan.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
import json
from typing import Optional
from datetime import date

from ..db import get_db
from ..services.scoring_service import recompute_scores
from services.agents.duncan_agent import DuncanAgent

router = APIRouter(prefix="/api/agent/duncan", tags=["Agents"])


def save_agent_run(
    db: Session,
    *,
    agent_name: str,
    score_date: Optional[date],
    auto_open: bool,
    max_to_open: Optional[int],
    opened: int,
    skipped: int,
    created_ids: list[str],
    status: str = "success",
    error: Optional[str] = None,
):
    db.execute(
        text(
            """
            INSERT INTO agent_runs (
                agent_name, score_date, auto_open, max_to_open,
                opened, skipped, created_ids, status, error
            )
            VALUES (
                :agent_name, :score_date, :auto_open, :max_to_open,
                :opened, :skipped, (:created_ids)::jsonb, :status, :error
            )
            """
        ),
        {
            "agent_name": agent_name,
            "score_date": score_date,
            "auto_open": auto_open,
            "max_to_open": max_to_open,
            "opened": opened,
            "skipped": skipped,
            "created_ids": json.dumps(created_ids),
            "status": status,
            "error": error,
        },
    )
    db.flush()  # ✅ not commit


@router.get("/suggestions")
def duncan_suggestions(
    max_spikes: int = Query(5, ge=0, le=50),
    max_top_skus: int = Query(8, ge=0, le=50),
    max_users: int = Query(5, ge=0, le=50),
    max_zones: int = Query(3, ge=0, le=50),
    db: Session = Depends(get_db),
):
    sku_scores, zone_scores, user_scores, recommendations, spikes, score_date = recompute_scores(db)
    agent = DuncanAgent(score_date=score_date)

    cases = agent.build_cases(
        sku_scores=sku_scores,
        zone_scores=zone_scores,
        user_scores=user_scores,
        recommendations=recommendations,
        spikes=spikes,
        max_spikes=max_spikes,
        max_top_skus=max_top_skus,
        max_users=max_users,
        max_zones=max_zones,
    )
    return {"score_date": str(score_date), "count": len(cases), "cases": [c.to_dict() for c in cases]}


class DuncanRunPayload(BaseModel):
    auto_open: bool = False
    max_to_open: int = 5
    min_confidence: int = 75

    max_spikes: int = 5
    max_top_skus: int = 8
    max_users: int = 5
    max_zones: int = 3


@router.get("/runs")
def duncan_runs(db: Session = Depends(get_db), limit: int = Query(50, ge=1, le=200)):
    rows = db.execute(
        text(
            """
            SELECT id, agent_name, score_date, auto_open, max_to_open,
                   opened, skipped, created_ids, status, error, created_at
            FROM agent_runs
            WHERE agent_name = 'duncan'
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()
    return {"runs": [dict(r) for r in rows]}


@router.post("/run")
def duncan_run(payload: DuncanRunPayload, db: Session = Depends(get_db)):
    try:
        sku_scores, zone_scores, user_scores, recommendations, spikes, score_date = recompute_scores(db)
        agent = DuncanAgent(score_date=score_date)

        cases = agent.build_cases(
            sku_scores=sku_scores,
            zone_scores=zone_scores,
            user_scores=user_scores,
            recommendations=recommendations,
            spikes=spikes,
            max_spikes=payload.max_spikes,
            max_top_skus=payload.max_top_skus,
            max_users=payload.max_users,
            max_zones=payload.max_zones,
        )

        opened_result = {"opened": 0, "skipped": 0, "created_ids": []}

        if payload.auto_open:
            opened = agent.open_investigations(
                db,
                cases,
                max_to_open=payload.max_to_open,
                min_confidence=payload.min_confidence,
            ) or {}
            opened_result = {
                "opened": int(opened.get("opened", 0)),
                "skipped": int(opened.get("skipped", 0)),
                "created_ids": list(opened.get("created_ids", [])),
            }

        save_agent_run(
            db,
            agent_name="duncan",
            score_date=score_date,
            auto_open=payload.auto_open,
            max_to_open=payload.max_to_open if payload.auto_open else None,
            opened=opened_result["opened"],
            skipped=opened_result["skipped"],
            created_ids=opened_result["created_ids"],
            status="success",
            error=None,
        )

        db.commit()  # ✅ single commit for everything

        return {
            "score_date": str(score_date),
            "cases": [c.to_dict() for c in cases],
            "auto_open": payload.auto_open,
            "opened": opened_result if payload.auto_open else None,
        }

    except Exception as e:
        db.rollback()

        # log failure (best effort)
        try:
            save_agent_run(
                db,
                agent_name="duncan",
                score_date=None,
                auto_open=payload.auto_open,
                max_to_open=payload.max_to_open if payload.auto_open else None,
                opened=0,
                skipped=0,
                created_ids=[],
                status="error",
                error=str(e),
            )
            db.commit()
        except Exception:
            db.rollback()

        raise