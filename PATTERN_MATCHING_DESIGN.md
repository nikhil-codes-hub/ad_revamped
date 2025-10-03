# Pattern Matching Design - AssistedDiscovery

**Date:** 2025-10-02
**Status:** Design documented, implementation pending (Phase 2 & 3)

---

## Core Concepts

### NodeFacts vs Patterns

#### NodeFact (Currently Implemented ✅)
- **What it is:** Concrete data instance extracted from ONE specific XML file
- **Contains:** Actual values (e.g., "PAX1", "ADT", "****" for masked PII)
- **Purpose:** Store what was found in a specific XML
- **Quantity:** One per occurrence in each XML file
- **Used for:** Viewing extracted data, auditing, debugging
- **Storage:** `node_facts` table

**Example NodeFact:**
```json
{
  "id": 123,
  "run_id": "abc-123",
  "node_type": "PassengerList",
  "node_ordinal": 1,
  "section_path": "/OrderViewRS/Response/DataLists/PassengerList",
  "fact_json": {
    "node_type": "PassengerList",
    "attributes": {
      "child_count": 4,
      "summary": "List of 4 passengers"
    },
    "business_intelligence": {
      "type_breakdown": {"ADT": 2, "CHD": 1, "INF": 1},
      "passenger_counts": {"adults": 2, "children": 1, "infants": 1}
    },
    "children": [
      {
        "node_type": "Passenger",
        "ordinal": 1,
        "attributes": {
          "id": "PAX1",
          "type": "ADT",
          "name": "****"
        },
        "references": {
          "contact_info": ["CI1PAX1"],
          "infant": ["PAX1.1"]
        }
      }
      // ... more children
    ]
  }
}
```

#### Pattern (NOT YET IMPLEMENTED ❌)
- **What it is:** Abstract schema/template that describes the STRUCTURE of similar NodeFacts
- **Contains:** Structure rules, not actual values (e.g., "must have id", "must have type")
- **Purpose:** Define what to look for when matching future XMLs
- **Quantity:** One per unique structure type
- **Used for:** Matching future XMLs, pattern recognition, coverage analysis
- **Storage:** `ndc_patterns` table

**Example Pattern:**
```json
{
  "id": 456,
  "spec_version": "17.2",
  "message_root": "OrderViewRS",
  "section_path": "/OrderViewRS/Response/DataLists/PassengerList",
  "selector_xpath": "./PassengerList",
  "decision_rule": {
    "node_type": "PassengerList",
    "must_have_attributes": ["child_count"],
    "must_have_children": [
      {
        "node_type": "Passenger",
        "must_have_attributes": ["id", "type"],
        "optional_attributes": ["name"],
        "must_have_references": ["contact_info"],
        "optional_references": ["infant", "parent"]
      }
    ],
    "business_intelligence_schema": {
      "type_breakdown": "object",
      "passenger_counts": {
        "adults": "integer",
        "children": "integer",
        "infants": "integer"
      }
    },
    "reference_patterns": [
      {
        "type": "infant_parent",
        "from": "Passenger[type=ADT]",
        "to": "Passenger[type=INF]",
        "via": "references.infant"
      },
      {
        "type": "contact_reference",
        "from": "Passenger",
        "to": "ContactInfo",
        "via": "references.contact_info"
      }
    ]
  },
  "signature_hash": "PAXLIST_17_2_STANDARD_A1B2C3",
  "times_seen": 15,
  "created_by_model": "gpt-4o",
  "examples": [
    {
      "node_fact_id": 123,
      "snippet": "<PassengerList>...</PassengerList>"
    }
  ]
}
```

---

## Pattern Generation Process (Phase 2 - NOT IMPLEMENTED)

### Overview
Convert collected NodeFacts into reusable Pattern templates for future matching.

### Flow

```
Step 1: Collect Similar NodeFacts
- NodeFact #1 (Iberia 17.2): PassengerList with 4 passengers
- NodeFact #2 (Qantas 17.2): PassengerList with 2 passengers
- NodeFact #3 (LATAM 19.2): PassengerList with 3 passengers

Step 2: Group by Version + Section Path
- Group 1: 17.2 OrderViewRS /DataLists/PassengerList (2 NodeFacts)
- Group 2: 19.2 OrderViewRS /DataLists/PassengerList (1 NodeFact)

Step 3: Analyze Common Structure (per group)
- All have: child_count attribute
- All have: Passenger children with id, type, name
- All have: references.contact_info
- Some have: references.infant (conditional pattern: when type=INF)

Step 4: Generate Decision Rule
decision_rule = {
  "must_have_attributes": ["child_count"],
  "must_have_children": [{
    "node_type": "Passenger",
    "must_have": ["id", "type"],
    "conditional": {
      "if type=INF": "must_have references.parent OR parent must have references.infant"
    }
  }]
}

Step 5: Calculate Signature Hash
hash(section_path + structure + version)
= SHA256("/DataLists/PassengerList" + JSON.stringify(decision_rule) + "17.2")
= "PAXLIST_17_2_STANDARD_A1B2C3"

Step 6: Store Pattern
- Insert into ndc_patterns table
- Set times_seen = count of NodeFacts that match this pattern
- Link example NodeFacts via pattern_id
```

### Implementation Tasks (Phase 2)
- [ ] Create pattern signature generator service
- [ ] Implement structure analysis algorithm
- [ ] Build decision rule generator
- [ ] Create pattern deduplication logic
- [ ] Implement pattern storage and updates
- [ ] Add pattern confidence scoring
- [ ] Update Discovery workflow to trigger pattern generation

---

## Pattern Identification Process (Phase 3 - NOT IMPLEMENTED)

### Overview
When a new XML is uploaded for "Identify", match its NodeFacts against saved Patterns.

### Critical: Version-Filtered Matching

**✅ CORRECT APPROACH (with version filtering):**
```
New XML arrives
→ Detect version (e.g., 17.2 OrderViewRS)
→ Extract NodeFacts
→ Generate temporary signatures
→ Query patterns WHERE spec_version='17.2' AND message_root='OrderViewRS'
→ Compare signatures only within same version
→ Accurate matches ✓
```

**❌ WRONG APPROACH (without version filtering):**
```
New XML arrives
→ Extract NodeFacts
→ Compare against ALL patterns (all versions)
→ Might match wrong version patterns
→ FALSE POSITIVES ❌
```

### Detailed Identify Flow

**Example: New XML - OVRS_NewAirline_17_2.xml**

```sql
-- Step 1: Detect version
Detected: 17.2 / OrderViewRS

-- Step 2: Extract NodeFacts (same as Discovery)
Extracted:
- PassengerList (path: /OrderViewRS/.../PassengerList)
- BaggageAllowanceList (path: /OrderViewRS/.../BaggageAllowanceList)
- ContactInfoList (path: /OrderViewRS/.../ContactInfoList)

-- Step 3: Generate temporary signatures (don't save yet)
PassengerList → temp_signature = "PAXLIST_17_2_STD_A1B2"
BaggageList → temp_signature = "BAGGAGELIST_17_2_STD_C3D4"
ContactList → temp_signature = "CONTACTLIST_17_2_STD_E5F6"

-- Step 4: Query patterns (VERSION-FILTERED!)
SELECT * FROM ndc_patterns
WHERE spec_version = '17.2'
  AND message_root = 'OrderViewRS'
  AND signature_hash IN ('PAXLIST_17_2_STD_A1B2', 'BAGGAGELIST_17_2_STD_C3D4', 'CONTACTLIST_17_2_STD_E5F6')

-- Step 5: Calculate confidence scores
For each NodeFact:
  - Exact hash match → 100% confidence
  - Partial structure match → 70-95% confidence (similarity algorithm)
  - No match → 0% confidence (NEW pattern)

-- Step 6: Match results
✓ MATCH: PassengerList → Pattern #456 (confidence: 98%, times_seen: 25)
✓ MATCH: BaggageList → Pattern #789 (confidence: 95%, times_seen: 18)
✗ NO MATCH: ContactList → NEW pattern discovered!

-- Step 7: Store pattern_matches
INSERT INTO pattern_matches (pattern_id, node_fact_id, confidence_score, verdict, matched_at)
VALUES
  (456, <paxlist_nodefact_id>, 0.98, 'MATCH', NOW()),
  (789, <baggage_nodefact_id>, 0.95, 'MATCH', NOW()),
  (NULL, <contact_nodefact_id>, 0.0, 'NEW_PATTERN', NOW())

-- Step 8: Update pattern statistics
UPDATE ndc_patterns
SET times_seen = times_seen + 1, last_seen_at = NOW()
WHERE id IN (456, 789)
```

### Match Verdicts

| Verdict | Confidence | Meaning |
|---------|-----------|---------|
| `EXACT_MATCH` | 100% | Signature hash matches exactly |
| `HIGH_MATCH` | 90-99% | Structure very similar, minor differences |
| `PARTIAL_MATCH` | 70-89% | Core structure matches, some variations |
| `LOW_MATCH` | 50-69% | Similar but significant differences |
| `NO_MATCH` | 0-49% | Different structure |
| `NEW_PATTERN` | 0% | No similar pattern found in database |

### Edge Case: Cross-Version Pattern Detection (Optional)

For research/analysis, you might want to find similar patterns across versions:

```sql
-- Find similar patterns in other versions (optional, not primary flow)
SELECT
  p.*,
  SIMILARITY(p.decision_rule, <current_decision_rule>) as similarity_score
FROM ndc_patterns p
WHERE section_path LIKE '%PassengerList%'
  AND spec_version != '17.2'
ORDER BY similarity_score DESC
LIMIT 10

-- Use case: "This 17.2 PassengerList is 85% similar to 18.1 PassengerList pattern"
-- Useful for: migration analysis, pattern evolution tracking
```

### Implementation Tasks (Phase 3)
- [ ] Create identify workflow service
- [ ] Implement version-filtered pattern matching
- [ ] Build confidence scoring algorithm
- [ ] Create pattern similarity calculator (for partial matches)
- [ ] Implement pattern_matches storage
- [ ] Update pattern statistics (times_seen, last_seen_at)
- [ ] Create gap analysis (NEW_PATTERN identification)
- [ ] Build identify API endpoint

---

## Key Design Decisions

### Why Version Filtering is Critical

1. **Schema Differences Between Versions:**
   - 17.2/18.1: Uses `PassengerList`, `Passenger`, `InfantRef`, `ContactInfoRef`
   - 21.3: Uses `PaxList`, `Pax`, `PaxRefID` (different reference structure)
   - Comparing across versions would give false positives

2. **Performance:**
   - Database index on (spec_version, message_root, signature_hash)
   - Filtering reduces search space from 1000s to 10s of patterns

3. **Accuracy:**
   - Same-version patterns have 95%+ match accuracy
   - Cross-version matching drops to 60-70% accuracy (too many false positives)

### Pattern Signature Algorithm

```python
def generate_signature(node_fact: dict, spec_version: str) -> str:
    """
    Generate unique signature hash for a NodeFact structure.

    Signature components:
    1. Section path (normalized)
    2. Node type
    3. Required attributes (sorted)
    4. Child structure (recursive)
    5. Reference patterns
    6. Spec version
    """
    components = [
        normalize_path(node_fact['section_path']),
        node_fact['node_type'],
        sorted(get_required_attributes(node_fact)),
        get_child_structure_fingerprint(node_fact.get('children', [])),
        get_reference_patterns(node_fact),
        spec_version
    ]

    signature_string = json.dumps(components, sort_keys=True)
    return hashlib.sha256(signature_string.encode()).hexdigest()[:16]
```

### Similarity Scoring (for partial matches)

```python
def calculate_similarity(pattern1: dict, pattern2: dict) -> float:
    """
    Calculate structural similarity between two patterns.

    Scoring:
    - Exact match → 1.0
    - Same must_have fields → +0.3
    - Same optional fields → +0.2
    - Same child structure → +0.3
    - Same reference patterns → +0.2
    """
    score = 0.0

    # Compare required attributes
    required1 = set(pattern1['decision_rule'].get('must_have_attributes', []))
    required2 = set(pattern2['decision_rule'].get('must_have_attributes', []))
    if required1 == required2:
        score += 0.3
    elif required1 & required2:  # Intersection exists
        score += 0.3 * (len(required1 & required2) / len(required1 | required2))

    # Compare optional attributes
    optional1 = set(pattern1['decision_rule'].get('optional_attributes', []))
    optional2 = set(pattern2['decision_rule'].get('optional_attributes', []))
    if optional1 == optional2:
        score += 0.2
    elif optional1 & optional2:
        score += 0.2 * (len(optional1 & optional2) / len(optional1 | optional2))

    # Compare child structure (recursive)
    child_similarity = compare_child_structures(
        pattern1['decision_rule'].get('must_have_children', []),
        pattern2['decision_rule'].get('must_have_children', [])
    )
    score += 0.3 * child_similarity

    # Compare reference patterns
    ref_similarity = compare_reference_patterns(
        pattern1['decision_rule'].get('reference_patterns', []),
        pattern2['decision_rule'].get('reference_patterns', [])
    )
    score += 0.2 * ref_similarity

    return score
```

---

## Database Schema Reference

### ndc_patterns table
```sql
CREATE TABLE ndc_patterns (
    id INT PRIMARY KEY AUTO_INCREMENT,
    spec_version VARCHAR(10) NOT NULL,
    message_root VARCHAR(50) NOT NULL,
    section_path VARCHAR(500) NOT NULL,
    selector_xpath TEXT,
    decision_rule JSON NOT NULL,
    signature_hash VARCHAR(64) NOT NULL,
    times_seen INT DEFAULT 1,
    created_by_model VARCHAR(50),
    examples JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP,
    INDEX idx_version_hash (spec_version, message_root, signature_hash)
);
```

### pattern_matches table
```sql
CREATE TABLE pattern_matches (
    id INT PRIMARY KEY AUTO_INCREMENT,
    pattern_id INT,
    node_fact_id INT NOT NULL,
    confidence_score DECIMAL(5,4) NOT NULL,
    verdict ENUM('EXACT_MATCH', 'HIGH_MATCH', 'PARTIAL_MATCH', 'LOW_MATCH', 'NO_MATCH', 'NEW_PATTERN'),
    matched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pattern_id) REFERENCES ndc_patterns(id),
    FOREIGN KEY (node_fact_id) REFERENCES node_facts(id)
);
```

---

## Current Implementation Status

### Phase 1: Extraction & Storage ✅ COMPLETE
- [x] XML streaming parser
- [x] Version detection
- [x] NodeFacts extraction (LLM + templates)
- [x] Business intelligence enrichment
- [x] PII masking
- [x] Database storage
- [x] Streamlit UI for viewing NodeFacts

### Phase 2: Pattern Generation ❌ NOT IMPLEMENTED
- [ ] Pattern signature generator
- [ ] Structure analysis algorithm
- [ ] Decision rule generator
- [ ] Pattern deduplication
- [ ] Pattern storage service
- [ ] Integration with Discovery workflow

### Phase 3: Pattern Identification ❌ NOT IMPLEMENTED
- [ ] Identify workflow
- [ ] Version-filtered pattern matching
- [ ] Confidence scoring
- [ ] Similarity algorithm
- [ ] Gap analysis (NEW_PATTERN detection)
- [ ] Pattern statistics updates
- [ ] Identify API endpoint

---

## Next Steps (Tomorrow's Tasks)

1. **Implement Pattern Signature Generator:**
   - Create `/backend/app/services/pattern_generator.py`
   - Implement signature hash algorithm
   - Build decision rule extraction logic

2. **Implement Pattern Discovery Service:**
   - Analyze existing NodeFacts
   - Group by version + section path
   - Generate patterns from groups
   - Store in ndc_patterns table

3. **Update Discovery Workflow:**
   - After storing NodeFacts, trigger pattern generation
   - Update existing patterns (times_seen increment)
   - Store new patterns when discovered

4. **Implement Identify Workflow:**
   - Create `/backend/app/services/identify_workflow.py`
   - Extract NodeFacts from new XML
   - Match against patterns (version-filtered)
   - Store pattern_matches
   - Generate gap analysis report

5. **Update Streamlit UI:**
   - Add "Identify" page
   - Show pattern matches with confidence scores
   - Display gap analysis (unmatched patterns)
   - Show pattern coverage statistics

---

## Questions to Resolve Tomorrow

1. Should we auto-generate patterns during Discovery, or require explicit "Generate Patterns" action?
2. What's the minimum `times_seen` threshold before a pattern is considered "stable"?
3. How to handle pattern evolution (when structure changes slightly over time)?
4. Should we support manual pattern editing/curation?
5. How to visualize pattern relationships in the UI?

---

**End of Document**
