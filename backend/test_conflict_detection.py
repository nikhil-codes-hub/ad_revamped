#!/usr/bin/env python3
"""
Test conflict detection for workspace testDup
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.workspace_db import get_workspace_session
from app.services.conflict_detector import create_conflict_detector

def test_conflict_detection():
    """Test if conflict detection works for testDup workspace."""

    workspace = "testDup"
    db = get_workspace_session(workspace)

    try:
        # Create conflict detector
        detector = create_conflict_detector(db)

        # Simulate extracting /PaxList when /PaxList/Pax already exists
        extracting_paths = ["AirShoppingRS/Response/DataLists/PaxList"]
        spec_version = "21.3"
        message_root = "AirShoppingRS"
        airline_code = "AS"

        print("=" * 70)
        print("Testing Conflict Detection")
        print("=" * 70)
        print(f"\nWorkspace: {workspace}")
        print(f"Spec Version: {spec_version}")
        print(f"Message Root: {message_root}")
        print(f"Airline Code: {airline_code}")
        print(f"Extracting Paths: {extracting_paths}")

        # Check for conflicts
        print("\nRunning conflict detection...")
        result = detector.check_conflicts(
            extracting_paths=extracting_paths,
            spec_version=spec_version,
            message_root=message_root,
            airline_code=airline_code
        )

        print(f"\nHas Conflicts: {result.has_conflicts}")
        print(f"Can Proceed: {result.can_proceed}")

        if result.has_conflicts:
            print(f"\nFound {len(result.conflicts)} conflict(s):")
            for i, conflict in enumerate(result.conflicts, 1):
                print(f"\n--- Conflict {i} ---")
                print(f"Type: {conflict.conflict_type}")
                print(f"Extracting Path: {conflict.extracting_path}")
                print(f"Recommendation: {conflict.recommendation}")
                print(f"Impact: {conflict.impact_description}")
                print(f"\nExisting Patterns ({len(conflict.existing_patterns)}):")
                for pattern in conflict.existing_patterns:
                    print(f"  - ID {pattern.id}: {pattern.section_path} (seen {pattern.times_seen}x, created {pattern.created_at})")
        else:
            print("\nNo conflicts found")

        if result.warning_message:
            print(f"\nWarning: {result.warning_message}")

        print("\n" + "=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    test_conflict_detection()
