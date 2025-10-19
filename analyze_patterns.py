"""Analyze all patterns for child structure deduplication issues."""
import requests
import json
from collections import defaultdict, Counter

# Fetch patterns from API
response = requests.get("http://localhost:8000/api/v1/patterns/?workspace=default&limit=100")
patterns = response.json()

print('📊 Pattern Analysis - Child Structure Deduplication Check')
print('=' * 80)

# Group by node_type to find duplicates
by_node_type = defaultdict(list)
for p in patterns:
    node_type = p.get('decision_rule', {}).get('node_type', 'Unknown')
    by_node_type[node_type].append(p)

print(f'\nTotal patterns: {len(patterns)}')
print(f'Unique node types: {len(by_node_type)}')
print()

# Analyze each pattern for child structure issues
issues = []
for node_type, pattern_list in sorted(by_node_type.items()):
    for p in pattern_list:
        child_struct = p.get('decision_rule', {}).get('child_structure', {})

        if child_struct.get('has_children') and child_struct.get('child_structures'):
            child_structures = child_struct['child_structures']

            # Check for duplicate child types
            child_types = [cs['node_type'] for cs in child_structures]
            unique_child_types = set(child_types)

            if len(child_types) != len(unique_child_types):
                # Found duplicates!
                dupes = {k: v for k, v in Counter(child_types).items() if v > 1}
                issues.append({
                    'pattern_id': p['id'],
                    'node_type': node_type,
                    'hash': p['signature_hash'],
                    'times_seen': p['times_seen'],
                    'duplicate_child_types': dupes,
                    'total_children': len(child_types),
                    'unique_children': len(unique_child_types)
                })

if issues:
    print('⚠️  ISSUES FOUND - Patterns with duplicate child structures:')
    print()
    for issue in issues:
        print(f"Pattern ID {issue['pattern_id']}: {issue['node_type']}")
        print(f"  Hash: {issue['hash']}")
        print(f"  Times seen: {issue['times_seen']}")
        print(f"  Total child structures: {issue['total_children']}")
        print(f"  Unique child types: {issue['unique_children']}")
        print(f"  Duplicates: {issue['duplicate_child_types']}")
        print()
else:
    print('✅ NO ISSUES - All patterns have properly deduplicated child structures!')
    print()

# Show summary of all patterns
print('\n' + '=' * 80)
print('Pattern Summary by Node Type:')
print('-' * 80)

for node_type, pattern_list in sorted(by_node_type.items()):
    print(f'\n{node_type}: {len(pattern_list)} pattern(s)')
    for p in pattern_list:
        child_struct = p.get('decision_rule', {}).get('child_structure', {})
        print(f"  Pattern ID {p['id']} (hash: {p['signature_hash'][:12]}..., seen: {p['times_seen']}x)")

        if child_struct.get('child_structures'):
            child_structures = child_struct['child_structures']
            unique_types = list(set(cs['node_type'] for cs in child_structures))
            print(f"    Child types ({len(unique_types)}): {unique_types}")

            # Show detailed child structure
            for cs in child_structures:
                attrs = cs.get('required_attributes', [])
                refs = cs.get('reference_fields', [])
                print(f"      - {cs['node_type']}: attrs={len(attrs)}, refs={len(refs)}")
        elif child_struct.get('has_children'):
            print(f"    Has children but no child_structures defined")
        else:
            print(f"    No children")

print('\n' + '=' * 80)
print('Summary:')
print(f'  Total patterns analyzed: {len(patterns)}')
print(f'  Patterns with duplicate child structures: {len(issues)}')
if issues:
    print(f'  ⚠️  ACTION REQUIRED: {len(issues)} patterns need regeneration with fixed logic')
else:
    print(f'  ✅ All patterns are correctly deduplicated!')
