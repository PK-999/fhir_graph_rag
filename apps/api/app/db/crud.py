"""CRUD operations for pipeline tracking and lineage."""

from datetime import datetime

from apps.api.app.db.models import DataQualityResult, IngestionEvent, LineageMapping, PipelineRun
from sqlalchemy.orm import Session


def create_pipeline_run(session: Session, config: dict) -> PipelineRun:
    """Create a new pipeline run."""
    run = PipelineRun(status="running", config=config)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run

def complete_pipeline_run(session: Session, run_id: str, status: str = "success") -> None:
    """Mark a pipeline run as complete."""
    run = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if run:
        run.status = status
        run.end_time = datetime.utcnow()
        session.commit()

def add_dq_results(session: Session, run_id: str, dq_data: dict) -> None:
    """Add data quality results for a run."""
    for rule_name, rule_data in dq_data.get("rules", {}).items():
        result = DataQualityResult(
            run_id=run_id,
            rule_name=rule_name,
            status=rule_data.get("status", "unknown"),
            pass_rate=rule_data.get("pass_rate"),
            details=rule_data.get("details", {})
        )
        session.add(result)
    session.commit()

def add_ingestion_events(session: Session, run_id: str, counts: dict[str, int]) -> None:
    """Add ingestion event counts for a run."""
    for res_type, count in counts.items():
        event = IngestionEvent(
            run_id=run_id,
            resource_type=res_type,
            count=count
        )
        session.add(event)
    session.commit()

def get_lineage(session: Session) -> list[LineageMapping]:
    """Retrieve all lineage mappings."""
    return session.query(LineageMapping).all()
