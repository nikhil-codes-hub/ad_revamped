"""SQLAlchemy implementation of INodeFactRepository."""

from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.database import NodeFact
from app.repositories.interfaces import INodeFactRepository


class SQLAlchemyNodeFactRepository:
    """SQLAlchemy implementation for NodeFact entity."""

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def create(self, node_fact: NodeFact) -> NodeFact:
        """
        Create a new node fact.

        Args:
            node_fact: NodeFact entity to create

        Returns:
            Created node fact

        Note:
            Does not commit - let UnitOfWork handle transaction management
        """
        self.session.add(node_fact)
        return node_fact

    def create_batch(self, node_facts: List[NodeFact]) -> List[NodeFact]:
        """
        Create multiple node facts efficiently (bulk insert).

        Args:
            node_facts: List of NodeFact entities to create

        Returns:
            Created node facts

        Note:
            Uses bulk_save_objects for better performance with large batches
        """
        if not node_facts:
            return []

        # Use bulk insert for performance
        self.session.bulk_save_objects(node_facts)
        return node_facts

    def get_by_id(self, node_fact_id: int) -> Optional[NodeFact]:
        """
        Get node fact by ID.

        Args:
            node_fact_id: NodeFact identifier

        Returns:
            NodeFact if found, None otherwise
        """
        return self.session.query(NodeFact).filter(NodeFact.id == node_fact_id).first()

    def list_by_run(self, run_id: str) -> List[NodeFact]:
        """
        List all node facts for a run.

        Args:
            run_id: Run identifier

        Returns:
            List of node facts for the run
        """
        return self.session.query(NodeFact).filter(NodeFact.run_id == run_id).all()

    def count_by_run(self, run_id: str) -> int:
        """
        Count node facts for a run.

        Args:
            run_id: Run identifier

        Returns:
            Number of node facts in the run
        """
        return self.session.query(NodeFact).filter(NodeFact.run_id == run_id).count()
