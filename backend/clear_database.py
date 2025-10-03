"""Clear all data from the database."""

from app.services.database import get_db_session
from app.models.database import Pattern, PatternMatch, NodeFact, Run

def clear_all_data():
    """Clear all patterns, matches, node facts, and runs from database."""
    db = next(get_db_session())

    try:
        # Delete in order to respect foreign key constraints
        print("Deleting pattern matches...")
        deleted_matches = db.query(PatternMatch).delete()
        print(f"  Deleted {deleted_matches} pattern matches")

        print("Deleting patterns...")
        deleted_patterns = db.query(Pattern).delete()
        print(f"  Deleted {deleted_patterns} patterns")

        print("Deleting node facts...")
        deleted_node_facts = db.query(NodeFact).delete()
        print(f"  Deleted {deleted_node_facts} node facts")

        print("Deleting runs...")
        deleted_runs = db.query(Run).delete()
        print(f"  Deleted {deleted_runs} runs")

        db.commit()
        print("\n✅ All data cleared successfully!")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error clearing data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clear_all_data()
