"""SQLAlchemy models for metadata and lineage."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class PipelineRun(Base):
    """Tracks each execution of the ingestion pipeline."""
    __tablename__ = "pipeline_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String, nullable=False, default="running")  # running, success, failed
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    config = Column(JSON, nullable=True)

    dq_results = relationship("DataQualityResult", back_populates="run", cascade="all, delete-orphan")


class DataQualityResult(Base):
    """Data quality metrics for a specific pipeline run."""
    __tablename__ = "data_quality_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("pipeline_runs.id"), nullable=False)
    rule_name = Column(String, nullable=False)
    status = Column(String, nullable=False)  # pass, fail
    pass_rate = Column(Float, nullable=True)
    details = Column(JSON, nullable=True)

    run = relationship("PipelineRun", back_populates="dq_results")


class IngestionEvent(Base):
    """Tracks individual FHIR bundles or files ingested."""
    __tablename__ = "ingestion_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("pipeline_runs.id"), nullable=False)
    resource_type = Column(String, nullable=False)
    count = Column(Integer, nullable=False, default=0)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)


class LineageMapping(Base):
    """Lineage mapping from Business Domain down to FHIR Resource."""
    __tablename__ = "lineage_mappings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    business_domain = Column(String, nullable=False)   # e.g., "Clinical"
    business_entity = Column(String, nullable=False)   # e.g., "Lab Results"
    business_attribute = Column(String, nullable=False)# e.g., "HbA1c Value"
    fhir_resource = Column(String, nullable=False)     # e.g., "Observation"
    fhir_element = Column(String, nullable=False)      # e.g., "valueQuantity"
    description = Column(Text, nullable=True)
