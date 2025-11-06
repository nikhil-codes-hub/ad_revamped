"""Quick test to verify expected_relationships are stored in patterns."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Pattern

WORKSPACE = "Test7"

def quick_test():
    db_path = f"data/workspaces/{WORKSPACE}.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Check DatedMarketingSegmentList pattern
        pattern = session.query(Pattern).filter(
            Pattern.section_path == "AirShoppingRS/Response/DataLists/DatedMarketingSegmentList"
        ).first()

        if pattern:
            print(f"✅ Found pattern (ID: {pattern.id})")
            print(f"   Spec: {pattern.spec_version}/{pattern.message_root}")
            print(f"   Times seen: {pattern.times_seen}")

            decision_rule = pattern.decision_rule
            expected_rels = decision_rule.get('expected_relationships', [])

            print(f"\n   Expected relationships: {len(expected_rels)}")
            if expected_rels:
                for rel in expected_rels:
                    status = "✅ Valid" if rel['is_valid'] else "❌ Broken"
                    print(f"     {status} -> {rel['target_section_path']}")
                    print(f"        Type: {rel['reference_type']}, Confidence: {rel.get('confidence', 1.0)}")
            else:
                print("   ❌ NO expected_relationships in decision_rule!")
        else:
            print("❌ Pattern not found!")
    finally:
        session.close()

if __name__ == "__main__":
    quick_test()
