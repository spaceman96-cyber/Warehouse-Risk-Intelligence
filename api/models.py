# api/models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Index, UniqueConstraint
from sqlalchemy.sql import func
from .db import Base

class IngestFile(Base):
    __tablename__ = "ingest_files"

    id = Column(Integer, primary_key=True)
    file_type = Column(String(32), nullable=False)   # "sku_master" or "adjustments"
    filename = Column(String(256), nullable=False)
    sha256 = Column(String(64), nullable=False, unique=True)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("sha256", name="uq_ingest_files_sha256"),
    )

class SKUMaster(Base):
    __tablename__ = "sku_master"

    sku_code   = Column(String, primary_key=True, index=True)
    sku_name   = Column(String, default="")
    category   = Column(String, default="")
    abc_class  = Column(String, default="")
    unit_cost  = Column(Float, default=0.0)
    value_band = Column(String, default="")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Adjustment(Base):
    __tablename__ = "adjustments"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    sku_code = Column(String, nullable=False)
    qty_delta = Column(Float, nullable=False)
    user_ref = Column(String, nullable=False)

    zone = Column(String, nullable=True)
    location_code = Column(String, nullable=True)
    adjustment_type = Column(String, nullable=True)

    row_hash = Column(String(64), nullable=False, unique=True)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("row_hash", name="uq_adjustments_row_hash"),)
Index("idx_adj_sku_ts", Adjustment.sku_code, Adjustment.timestamp)

class Investigation(Base):
    __tablename__ = "investigations"

    id            = Column(String, primary_key=True, index=True)  # uuid
    title         = Column(String, nullable=False)

    status        = Column(String, default="open")       # open / in_progress / blocked / closed
    severity      = Column(String, default="med")        # low / med / high
    owner         = Column(String, default=None)

    sku_code      = Column(String, default=None, index=True)
    zone          = Column(String, default=None, index=True)
    user_ref      = Column(String, default=None, index=True)

    notes         = Column(Text, default=None)
    root_cause_tag= Column(String, default=None)
    summary       = Column(Text, default=None)

    opened_at     = Column(DateTime(timezone=True), server_default=func.now())
    closed_at     = Column(DateTime(timezone=True), default=None)