#!/usr/bin/env python3
"""
Test conflict resolution (REPLACE strategy) for workspace testDup
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.workspace_db import get_workspace_session
from app.services.conflict_detector import create_conflict_detector
from app.models.schemas import ConflictResolution

def test_replace_resolution():
    """Test REPLACE resolution strategy."""

    workspace = "testDup"
    db = get_workspace_session(workspace)

    try:
        # Create conflict detector
        detector = create_conflict_detector(db)

        # Check for conflicts first
        extracting_paths = ["AirShoppingRS/Response/DataLists/PaxList"]
        spec_version = "21.3"
        message_root = "AirShoppingRS"
        airline_code = "AS"

        print("=" * 70)
        print("Testing REPLACE Resolution Strategy")
        print("=" * 70)
        print(f"\nWorkspace: {workspace}")

        # Step 1: Detect conflicts
        print("\n[Step 1] Detecting conflicts...")
        result = detector.check_conflicts(
            extracting_paths=extracting_paths,
            spec_version=spec_version,
            message_root=message_root,
            airline_code=airline_code
        )

        if not result.has_conflicts:
            print("  No conflicts found. Nothing to resolve.")
            return

        print(f"  Found {len(result.conflicts)} conflict(s)")
        for conflict in result.conflicts:
            print(f"    - {conflict.conflict_type}: {len(conflict.existing_patterns)} pattern(s)")

        # Step 2: Show patterns before resolution
        print("\n[Step 2] Patterns before resolution:")
        from app.models.database import Pattern
        patterns_before = db.query(Pattern).filter(
            Pattern.spec_version == spec_version,
            Pattern.message_root == message_root,
            Pattern.airline_code == airline_code
        ).order_by(Pattern.id).all()

        print(f"  Total patterns: {len(patterns_before)}")
        for p in patterns_before:
            print(f"    ID {p.id}: {p.section_path} (superseded_by={p.superseded_by})")

        # Step 3: Apply REPLACE resolution
        print("\n[Step 3] Applying REPLACE resolution...")
        resolution_result = detector.resolve_conflicts(
            conflicts=result.conflicts,
            resolution_strategy=ConflictResolution.REPLACE
        )

        print(f"  Resolution result: {resolution_result}")

        # Step 4: Show patterns after resolution
        print("\n[Step 4] Patterns after resolution:")
        db.commit()  # Ensure we see the changes
        patterns_after = db.query(Pattern).filter(
            Pattern.spec_version == spec_version,
            Pattern.message_root == message_root,
            Pattern.airline_code == airline_code
        ).order_by(Pattern.id).all()

        print(f"  Total patterns: {len(patterns_after)}")
        for p in patterns_after:
            print(f"    ID {p.id}: {p.section_path} (superseded_by={p.superseded_by})")

        # Step 5: Verify expected outcome
        print("\n[Step 5] Verification:")
        child_pattern = next((p for p in patterns_after if p.id == 1), None)
        if child_pattern is None:
            print("  ✓ Child pattern (ID 1, /PaxList/Pax) was DELETED as expected")
        else:
            print(f"  ✗ Child pattern still exists: {child_pattern.section_path}")

        parent_pattern = next((p for p in patterns_after if p.id == 4), None)
        if parent_pattern:
            print(f"  ✓ Parent pattern (ID 4, /PaxList) still exists")
        else:
            print(f"  ✗ Parent pattern was deleted (unexpected)")

        print("\n" + "=" * 70)
        print("REPLACE strategy test completed!")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    test_replace_resolution()
