"""SQLAlchemy implementation of INodeRelationshipRepository."""

from typing import List
from sqlalchemy.orm import Session
from app.models.database import NodeRelationship
from app.repositories.interfaces import INodeRelationshipRepository


class SQLAlchemyNodeRelationshipRepository:
    """SQLAlchemy implementation for NodeRelationship entity."""

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def create(self, relationship: NodeRelationship) -> NodeRelationship:
        """
        Create a new node relationship.

        Args:
            relationship: NodeRelationship entity to create

        Returns:
            Created relationship

        Note:
            Does not commit - let UnitOfWork handle transaction management
        """
        self.session.add(relationship)
        return relationship

    def create_batch(self, relationships: List[NodeRelationship]) -> List[NodeRelationship]:
        """
        Create multiple relationships efficiently (bulk insert).

        Args:
            relationships: List of NodeRelationship entities to create

        Returns:
            Created relationships

        Note:
            Uses bulk_save_objects for better performance with large batches
        """
        if not relationships:
            return []

        # Use bulk insert for performance
        self.session.bulk_save_objects(relationships)
        return relationships

    def list_by_run(self, run_id: str) -> List[NodeRelationship]:
        """
        List all relationships for a run.

        Args:
            run_id: Run identifier

        Returns:
            List of relationships discovered in the run
        """
        return self.session.query(NodeRelationship).filter(
            NodeRelationship.run_id == run_id
        ).all()

    def list_broken_for_node(self, node_fact_id: int) -> List[NodeRelationship]:
        """
        List broken relationships for a specific node fact.

        Args:
            node_fact_id: NodeFact identifier

        Returns:
            List of broken relationships where this node is the source
        """
        return self.session.query(NodeRelationship).filter(
            NodeRelationship.source_node_fact_id == node_fact_id,
            NodeRelationship.is_valid == False  # noqa: E712
        ).all()
