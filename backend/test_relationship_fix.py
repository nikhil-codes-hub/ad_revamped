"""
Test script to verify the indirect relationship fix.

This script will:
1. Re-run Discovery on AirShoppingRS.xml to regenerate patterns with expected_relationships
2. Run Identify on the same file to verify no penalty is applied for expected broken relationships
"""
import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.services.discovery_workflow import create_discovery_workflow
from app.services.identify_workflow import IdentifyWorkflow
from app.models.database import Pattern

# Test with Test10 workspace
WORKSPACE = "Test10"
XML_FILE = "../resources/Alaska/AirShoppingRS.xml"

def test_relationship_fix():
    """Test the indirect relationship fix."""
    print("=" * 80)
    print("Testing Indirect Relationship Fix")
    print("=" * 80)

    # Connect to Test6 database
    db_path = f"data/workspaces/{WORKSPACE}.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Step 1: Check if AirShoppingRS.xml exists
        if not os.path.exists(XML_FILE):
            print(f"❌ XML file not found: {XML_FILE}")
            return

        print(f"✅ Found XML file: {XML_FILE}")

        # Step 2: Run Discovery to regenerate patterns with expected_relationships
        print("\n" + "=" * 80)
        print("STEP 1: Running Discovery to regenerate patterns")
        print("=" * 80)

        discovery = create_discovery_workflow(session)
        discovery_result = discovery.run_discovery(
            xml_file_path=XML_FILE,
            skip_pattern_generation=False,
            conflict_resolution='replace'
        )

        print(f"\n✅ Discovery completed:")
        print(f"   - Run ID: {discovery_result['run_id']}")
        print(f"   - Status: {discovery_result['status']}")
        print(f"   - NodeFacts extracted: {discovery_result['node_facts_extracted']}")
        print(f"   - Patterns created: {discovery_result.get('pattern_generation', {}).get('patterns_created', 0)}")
        print(f"   - Patterns updated: {discovery_result.get('pattern_generation', {}).get('patterns_updated', 0)}")

        # Step 3: Check if DatedMarketingSegmentList pattern has expected_relationships
        print("\n" + "=" * 80)
        print("STEP 2: Verifying Pattern has expected_relationships")
        print("=" * 80)

        pattern = session.query(Pattern).filter(
            Pattern.section_path == "AirShoppingRS/Response/DataLists/DatedMarketingSegmentList",
            Pattern.spec_version == "21.3"
        ).first()

        if pattern:
            decision_rule = pattern.decision_rule
            expected_rels = decision_rule.get('expected_relationships', [])

            print(f"\n✅ Found DatedMarketingSegmentList pattern (ID: {pattern.id})")
            print(f"   - Expected relationships count: {len(expected_rels)}")

            if expected_rels:
                print("\n   Expected Relationships:")
                for rel in expected_rels:
                    status = "✅ Valid" if rel['is_valid'] else "❌ Broken (Expected)"
                    print(f"     {status} -> {rel['target_node_type']} ({rel['reference_type']})")
            else:
                print("   ⚠️  WARNING: Pattern has NO expected_relationships!")
        else:
            print("❌ Pattern not found!")
            return

        # Step 4: Run Identify to verify no penalty for expected broken relationships
        print("\n" + "=" * 80)
        print("STEP 3: Running Identify to test penalty logic")
        print("=" * 80)

        identify = IdentifyWorkflow(session)
        identify_result = identify.run_identify(
            xml_file_path=XML_FILE
        )

        print(f"\n✅ Identify completed:")
        print(f"   - Run ID: {identify_result['run_id']}")
        print(f"   - Status: {identify_result['status']}")

        # Check pattern matches for DatedMarketingSegmentList
        matches = identify_result.get('pattern_matches', [])
        dms_matches = [m for m in matches if 'DatedMarketingSegmentList' in m.get('section_path', '')]

        if dms_matches:
            print(f"\n   DatedMarketingSegmentList matches:")
            for match in dms_matches:
                confidence = match.get('confidence', 0)
                verdict = match.get('verdict', 'unknown')
                print(f"     - Confidence: {confidence:.2f} ({verdict})")

                # Check if confidence is close to 1.0 (no penalty)
                if confidence >= 0.95:
                    print("     ✅ SUCCESS: No penalty applied for expected broken relationship!")
                elif confidence >= 0.70 and confidence < 0.95:
                    print("     ⚠️  PARTIAL: Some penalty applied, but less than before")
                else:
                    print(f"     ❌ FAILURE: Still applying full penalty (confidence: {confidence:.2f})")
        else:
            print("   ⚠️  No matches found for DatedMarketingSegmentList")

        print("\n" + "=" * 80)
        print("Test Complete!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    test_relationship_fix()
