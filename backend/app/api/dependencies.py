"""
FastAPI dependency injection for AssistedDiscovery.

Provides database sessions and repository layer access to API endpoints.
"""

from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.repositories.interfaces import IUnitOfWork
from app.repositories.sqlalchemy.unit_of_work import SQLAlchemyUnitOfWork


def get_unit_of_work(session: Session = Depends(get_db)) -> IUnitOfWork:
    """
    Dependency that provides Unit of Work for repository access.

    FastAPI will automatically inject this into endpoint functions.

    Args:
        session: SQLAlchemy session (injected by get_db dependency)

    Returns:
        Unit of Work instance providing access to all repositories

    Example:
        @router.post("/runs/")
        async def create_run(
            file_path: str,
            uow: IUnitOfWork = Depends(get_unit_of_work)
        ):
            run = Run(...)
            uow.runs.create(run)
            uow.commit()
            return {"run_id": run.id}

    Note:
        This returns the IUnitOfWork interface, not the concrete
        SQLAlchemyUnitOfWork class. This allows us to swap implementations
        (e.g., MongoDB, DynamoDB) without changing API endpoint code.
    """
    return SQLAlchemyUnitOfWork(session)
