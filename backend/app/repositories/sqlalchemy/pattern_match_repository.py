"""SQLAlchemy implementation of IPatternMatchRepository."""

from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.database import PatternMatch
from app.repositories.interfaces import IPatternMatchRepository


class SQLAlchemyPatternMatchRepository:
    """SQLAlchemy implementation for PatternMatch entity."""

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def create(self, pattern_match: PatternMatch) -> PatternMatch:
        """
        Store a pattern match result.

        Args:
            pattern_match: PatternMatch entity to create

        Returns:
            Created pattern match

        Note:
            Does not commit - let UnitOfWork handle transaction management
        """
        self.session.add(pattern_match)
        return pattern_match

    def list_by_run(self, run_id: str) -> List[PatternMatch]:
        """
        List all pattern matches for a run.

        Args:
            run_id: Run identifier

        Returns:
            List of pattern matches for the run
        """
        return self.session.query(PatternMatch).filter(
            PatternMatch.run_id == run_id
        ).all()

    def get_match_statistics(self, run_id: str) -> Dict[str, Any]:
        """
        Get aggregated match statistics for a run.

        Args:
            run_id: Run identifier

        Returns:
            Dictionary with statistics (match_rate, verdict counts, etc.)
        """
        matches = self.list_by_run(run_id)

        if not matches:
            return {
                'total_matches': 0,
                'verdict_counts': {},
                'avg_confidence': 0.0,
                'high_confidence_count': 0
            }

        # Count verdicts
        verdict_counts: Dict[str, int] = {}
        high_confidence_count = 0
        total_confidence = 0.0

        for match in matches:
            # Count by verdict
            verdict = match.verdict or 'UNKNOWN'
            verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

            # Count high confidence matches (≥0.85)
            if match.confidence and match.confidence >= 0.85:
                high_confidence_count += 1

            # Sum confidence for average
            total_confidence += match.confidence or 0.0

        avg_confidence = total_confidence / len(matches) if matches else 0.0

        return {
            'total_matches': len(matches),
            'verdict_counts': verdict_counts,
            'avg_confidence': avg_confidence,
            'high_confidence_count': high_confidence_count,
            'match_rate': (high_confidence_count / len(matches) * 100) if matches else 0.0
        }
