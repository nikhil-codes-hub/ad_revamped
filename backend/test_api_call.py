#!/usr/bin/env python3
"""Test the preflight-check API endpoint."""

import requests

# Test parameters
params = {
    "workspace": "TestDup2",
    "spec_version": "21.3",
    "message_root": "AirShoppingRS",
    "airline_code": "AS",
    "node_paths": ["AirShoppingRS/Response/DataLists/PaxList"]
}

print("Testing preflight-check API endpoint...")
print(f"Params: {params}\n")

try:
    response = requests.post(
        "http://localhost:8000/api/v1/runs/preflight-check",
        params=params,
        timeout=30
    )

    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}\n")

    if response.status_code == 200:
        result = response.json()
        print(f"Has Conflicts: {result.get('has_conflicts')}")
        print(f"Can Proceed: {result.get('can_proceed')}")
        print(f"Warning: {result.get('warning_message')}")

        if result.get('conflicts'):
            print(f"\nConflicts found: {len(result['conflicts'])}")
            for conflict in result['conflicts']:
                print(f"  - Type: {conflict['conflict_type']}")
                print(f"    Path: {conflict['extracting_path']}")
                print(f"    Existing: {len(conflict['existing_patterns'])} pattern(s)")
    else:
        print(f"Error: {response.text}")

except Exception as e:
    print(f"Exception: {e}")
