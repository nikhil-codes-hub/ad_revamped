#!/usr/bin/env python3
"""
Demonstrate the complete conflict detection and resolution workflow.

This script simulates the scenario where:
1. User extracts child pattern (/PaxList/Pax)
2. User then extracts parent pattern (/PaxList) - triggers conflict
3. System detects conflict and shows warning
4. User chooses REPLACE strategy
5. System deletes child pattern and keeps parent pattern
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.workspace_db import get_workspace_session
from app.services.conflict_detector import create_conflict_detector
from app.models.schemas import ConflictResolution
from app.models.database import Pattern

def demo_workflow():
    """Demonstrate the conflict detection workflow."""

    workspace = "testDup"
    db = get_workspace_session(workspace)

    try:
        print("=" * 70)
        print("CONFLICT DETECTION & RESOLUTION WORKFLOW DEMONSTRATION")
        print("=" * 70)
        print(f"\nWorkspace: {workspace}\n")

        # Setup parameters
        spec_version = "21.3"
        message_root = "AirShoppingRS"
        airline_code = "AS"

        # ===== SCENARIO =====
        print("SCENARIO:")
        print("  1. User previously extracted: /PaxList/Pax (child pattern)")
        print("  2. User now wants to extract: /PaxList (parent pattern)")
        print("  3. System should detect parent-child conflict")
        print("  4. User chooses REPLACE strategy")
        print("  5. System deletes child pattern /PaxList/Pax\n")

        # ===== STEP 1: Show current state =====
        print("[Step 1] CURRENT PATTERNS:")
        patterns = db.query(Pattern).filter(
            Pattern.spec_version == spec_version,
            Pattern.message_root == message_root,
            Pattern.airline_code == airline_code,
            Pattern.superseded_by.is_(None)  # Active patterns only
        ).order_by(Pattern.id).all()

        if not patterns:
            print("  No patterns found!\n")
            return

        print(f"  Found {len(patterns)} active pattern(s):\n")
        for p in patterns:
            path_display = p.section_path.replace(message_root + "/", "")
            print(f"    ID {p.id}: {path_display}")
        print()

        # Find the child and parent patterns
        child_pattern = next((p for p in patterns if "Pax" in p.section_path and "/Pax" in p.section_path), None)
        parent_pattern = next((p for p in patterns if "PaxList" in p.section_path and "PaxList/Pax" not in p.section_path), None)

        if not child_pattern:
            print("  ⚠️  No child pattern (/PaxList/Pax) found - cannot demo conflict!")
            return

        # ===== STEP 2: Simulate extracting parent pattern =====
        print("[Step 2] EXTRACTING PARENT PATTERN:")
        extracting_path = "AirShoppingRS/Response/DataLists/PaxList"
        print(f"  Path to extract: {extracting_path}\n")

        # ===== STEP 3: Pre-flight conflict check =====
        print("[Step 3] PRE-FLIGHT CONFLICT CHECK:")
        detector = create_conflict_detector(db)

        # If parent pattern already exists, exclude it from the check
        # (simulating the user clicking the extract button again)
        if parent_pattern:
            print(f"  Note: Parent pattern already exists (ID {parent_pattern.id})")
            print(f"        For demo purposes, checking what WOULD have happened\n")
            # We'll proceed with the conflict check anyway to show what should have happened

        conflict_result = detector.check_conflicts(
            extracting_paths=[extracting_path],
            spec_version=spec_version,
            message_root=message_root,
            airline_code=airline_code
        )

        if conflict_result.has_conflicts:
            print(f"  ✓ Conflict detected!")
            print(f"  Conflicts found: {len(conflict_result.conflicts)}\n")

            for i, conflict in enumerate(conflict_result.conflicts, 1):
                print(f"  --- Conflict #{i} ---")
                print(f"  Type: {conflict.conflict_type}")
                print(f"  Recommendation: {conflict.recommendation}")
                print(f"  Impact: {conflict.impact_description}")
                print(f"\n  Existing patterns that conflict:")
                for pattern_info in conflict.existing_patterns:
                    path_display = pattern_info.section_path.replace(message_root + "/", "")
                    print(f"    • ID {pattern_info.id}: {path_display}")
                print()
        else:
            if parent_pattern:
                print("  No conflicts detected (parent pattern already exists)")
                print("  This is expected - conflict would have been detected BEFORE extraction\n")
            else:
                print("  ⚠️  No conflicts detected - unexpected!\n")
                return

        # ===== STEP 4: User chooses resolution strategy =====
        print("[Step 4] USER CHOOSES RESOLUTION STRATEGY:")
        print("  Available strategies:")
        print("    • REPLACE    - Delete old child patterns, keep new parent")
        print("    • KEEP_BOTH  - Keep both (may cause ambiguous matches)")
        print("    • MERGE      - Mark old patterns as superseded")
        print()
        print("  User selection: REPLACE\n")

        # ===== STEP 5: Apply resolution =====
        if conflict_result.has_conflicts and child_pattern:
            print("[Step 5] APPLYING REPLACE RESOLUTION:")
            print(f"  Deleting conflicting pattern(s)...\n")

            resolution_result = detector.resolve_conflicts(
                conflicts=conflict_result.conflicts,
                resolution_strategy=ConflictResolution.REPLACE
            )

            print(f"  Results:")
            print(f"    Patterns deleted: {resolution_result['patterns_deleted']}")
            print(f"    Patterns superseded: {resolution_result['patterns_superseded']}\n")

            db.commit()

            # ===== STEP 6: Show final state =====
            print("[Step 6] FINAL STATE:")
            final_patterns = db.query(Pattern).filter(
                Pattern.spec_version == spec_version,
                Pattern.message_root == message_root,
                Pattern.airline_code == airline_code,
                Pattern.superseded_by.is_(None)
            ).order_by(Pattern.id).all()

            print(f"  Active patterns remaining: {len(final_patterns)}\n")
            for p in final_patterns:
                path_display = p.section_path.replace(message_root + "/", "")
                print(f"    ID {p.id}: {path_display}")

            # Verify expected outcome
            print("\n[Verification]")
            child_exists = any(p.id == child_pattern.id for p in final_patterns)
            if not child_exists:
                print("  ✓ SUCCESS: Child pattern was deleted as expected")
            else:
                print("  ✗ ERROR: Child pattern still exists")

            if parent_pattern:
                parent_exists = any(p.id == parent_pattern.id for p in final_patterns)
                if parent_exists:
                    print("  ✓ SUCCESS: Parent pattern still exists")
                else:
                    print("  ✗ ERROR: Parent pattern was deleted (unexpected)")

        print("\n" + "=" * 70)
        print("DEMONSTRATION COMPLETE")
        print("=" * 70)
        print("\nThis workflow demonstrates how conflict detection prevents")
        print("users from accidentally creating overlapping patterns.")

    finally:
        db.close()


if __name__ == "__main__":
    demo_workflow()
