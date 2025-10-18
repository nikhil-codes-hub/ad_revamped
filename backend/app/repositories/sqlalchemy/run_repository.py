"""SQLAlchemy implementation of IRunRepository."""

from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.database import Run, RunKind, RunStatus
from app.repositories.interfaces import IRunRepository


class SQLAlchemyRunRepository:
    """SQLAlchemy implementation for Run entity."""

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def create(self, run: Run) -> Run:
        """
        Create a new run.

        Args:
            run: Run entity to create

        Returns:
            Created run

        Note:
            Does not commit - let UnitOfWork handle transaction management
        """
        self.session.add(run)
        return run

    def get_by_id(self, run_id: str) -> Optional[Run]:
        """
        Get run by ID.

        Args:
            run_id: Unique run identifier

        Returns:
            Run if found, None otherwise
        """
        return self.session.query(Run).filter(Run.id == run_id).first()

    def update_status(self, run_id: str, status: RunStatus,
                     error_details: Optional[str] = None) -> None:
        """
        Update run status.

        Args:
            run_id: Run identifier
            status: New status
            error_details: Optional error message
        """
        run = self.get_by_id(run_id)
        if run:
            run.status = status
            run.finished_at = datetime.utcnow()
            if error_details:
                run.error_details = error_details

    def update_version_info(self, run_id: str, spec_version: str,
                           message_root: str,
                           airline_code: Optional[str] = None,
                           airline_name: Optional[str] = None) -> None:
        """
        Update run with detected version information.

        Args:
            run_id: Run identifier
            spec_version: NDC spec version (e.g., "17.2")
            message_root: Message type (e.g., "OrderViewRS")
            airline_code: Optional airline code
            airline_name: Optional airline name
        """
        run = self.get_by_id(run_id)
        if run:
            run.spec_version = spec_version
            run.message_root = message_root
            if airline_code:
                run.airline_code = airline_code
            if airline_name:
                run.airline_name = airline_name
            run.status = RunStatus.IN_PROGRESS

    def list_recent(self, limit: int = 10,
                   kind: Optional[RunKind] = None) -> List[Run]:
        """
        List recent runs.

        Args:
            limit: Maximum number of runs to return
            kind: Optional filter by run kind

        Returns:
            List of recent runs, ordered by started_at descending
        """
        query = self.session.query(Run)
        if kind:
            query = query.filter(Run.kind == kind)
        return query.order_by(Run.started_at.desc()).limit(limit).all()
