# Relationship Discovery Logic

## Overview

AssistedDiscovery uses a hybrid approach to discover and validate relationships between XML nodes. It combines:
- **BA-configured expected references** (known business logic)
- **LLM-powered auto-discovery** (finding unknown references)
- **Validation across all instances** (checking if references are valid or broken)

This document explains the complete relationship discovery workflow.

---

## High-Level Process Flow

```
1. Extract NodeFacts from XML
   ↓
2. Group NodeFacts by Section Path
   ↓
3. For each Source Node Type:
   ├─ Get BA-configured expected references
   ├─ For each Target Node Type:
   │  ├─ Use LLM to discover references
   │  ├─ Validate discovered references across all instances
   │  └─ Classify: Expected/Unexpected, Valid/Broken
   └─ Save relationships to database
```

---

## Detailed Workflow

### Step 1: Group NodeFacts by Section

**Location**: `relationship_analyzer.py:146-153`

```python
def _group_by_section(self, node_facts: List[NodeFact]) -> Dict[str, List[NodeFact]]:
    groups = {}
    for fact in node_facts:
        if fact.section_path not in groups:
            groups[fact.section_path] = []
        groups[fact.section_path].append(fact)
    return groups
```

**Purpose**: Organize extracted nodes by their type for efficient processing.

**Example**:
```python
{
  "OrderViewRS/Response/DataLists/PassengerList": [Passenger1, Passenger2, Passenger3],
  "OrderViewRS/Response/DataLists/SegmentList": [Segment1, Segment2],
  "OrderViewRS/Response/DataLists/FareList": [Fare1, Fare2, Fare3]
}
```

---

### Step 2: Get Expected References from BA Configuration

**Location**: `relationship_analyzer.py:155-165`

```python
def _get_expected_references(self, section_path: str, sample_fact: NodeFact) -> List[str]:
    config = self.db.query(NodeConfiguration).filter(
        NodeConfiguration.section_path == section_path,
        NodeConfiguration.spec_version == sample_fact.spec_version,
        NodeConfiguration.message_root == sample_fact.message_root
    ).first()

    if config and config.expected_references:
        return config.expected_references
    return []
```

**Purpose**: Retrieve Business Analyst-configured expected references for this node type.

**Example Configuration**:
```python
NodeConfiguration(
    section_path="OrderViewRS/Response/DataLists/PassengerList",
    expected_references=["segment_reference", "fare_reference", "infant_parent"]
)
```

**What it means**: BA expects `PassengerList` to reference `SegmentList`, `FareList`, and potentially other passengers (infants).

---

### Step 3: LLM-Based Reference Discovery

**Location**: `relationship_analyzer.py:217-283`

#### 3.1 Extract XML Snippets

The system extracts representative XML snippets from the node fact JSON:

```python
source_xml = self._extract_xml_snippet(source_fact.fact_json)
target_xml = self._extract_xml_snippet(target_fact.fact_json)
```

**Example XML Snippets**:

**Source (PassengerList)**:
```xml
<Passenger>
  <PaxID>PAX1</PaxID>
  <PaxRefID>PAX1</PaxRefID>
  <GivenName>John</GivenName>
  <Surname>Doe</Surname>
  <SegmentRefID>SEG1</SegmentRefID>
  <FareRefID>FARE1</FareRefID>
</Passenger>
```

**Target (SegmentList)**:
```xml
<Segment>
  <SegmentKey>SEG1</SegmentKey>
  <DepartureStation>LAX</DepartureStation>
  <ArrivalStation>JFK</ArrivalStation>
</Segment>
```

#### 3.2 Build LLM Prompt

**Location**: `relationship_analyzer.py:285-335`

```
Analyze if the SOURCE node contains references to the TARGET node.

SOURCE NODE TYPE: PassengerList
SOURCE XML SAMPLE:
```xml
<Passenger>
  <PaxRefID>PAX1</PaxRefID>
  <SegmentRefID>SEG1</SegmentRefID>
</Passenger>
```

TARGET NODE TYPE: SegmentList
TARGET XML SAMPLE:
```xml
<Segment>
  <SegmentKey>SEG1</SegmentKey>
</Segment>
```

EXPECTED REFERENCES (configured by BA): segment_reference, fare_reference

TASK:
1. Identify if SOURCE contains reference fields pointing to TARGET
2. For each reference found, determine:
   - reference_type: Semantic name (e.g., "segment_reference")
   - reference_field: XML element containing the reference (e.g., "SegmentRefID")
   - reference_value: The actual reference ID/key value
   - confidence: Your confidence level (0.0 - 1.0)
   - was_expected: Is this reference in the EXPECTED REFERENCES list?

Return ONLY valid JSON (no markdown):
{
  "has_references": true|false,
  "references": [
    {
      "reference_type": "segment_reference",
      "reference_field": "SegmentRefID",
      "reference_value": "SEG1",
      "confidence": 0.95,
      "was_expected": true
    }
  ],
  "missing_expected": [],
  "validation_notes": "SegmentRefID clearly references SegmentKey in target"
}
```

#### 3.3 LLM Response Processing

**Temperature**: `0.1` (low for consistency)
**Response Format**: `json_object` (enforces valid JSON)

**Example LLM Response**:
```json
{
  "has_references": true,
  "references": [
    {
      "reference_type": "segment_reference",
      "reference_field": "SegmentRefID",
      "reference_value": "SEG1",
      "confidence": 0.95,
      "was_expected": true
    },
    {
      "reference_type": "fare_reference",
      "reference_field": "FareRefID",
      "reference_value": "FARE1",
      "confidence": 0.90,
      "was_expected": true
    }
  ],
  "missing_expected": [],
  "validation_notes": "Both expected references found"
}
```

**What the LLM identifies**:
- ✅ **Reference exists**: `SegmentRefID` in source points to `SegmentKey` in target
- ✅ **Field name**: The XML element containing the reference value
- ✅ **Semantic type**: Business meaning of the relationship
- ✅ **Confidence**: How certain the LLM is about this reference
- ✅ **Expected status**: Whether BA predicted this reference

---

### Step 4: Validate References Across All Instances

**Location**: `relationship_analyzer.py:337-389`

The LLM analysis is done on **sample nodes only** (one source, one target) for efficiency. Now we validate across **all instances**.

#### 4.1 For Each Source Instance

```python
for source_fact in source_facts:  # All Passenger nodes
    # Extract reference value
    ref_value = self._extract_reference_value(source_fact, "SegmentRefID")
    # e.g., ref_value = "SEG1" from Passenger1

    # Find matching target
    target_fact = self._find_target_by_reference(target_facts, "SEG1")
    # Search all Segment nodes for SegmentKey == "SEG1"

    # Create relationship record
    relationships.append({
        'source_node_fact_id': source_fact.id,
        'target_node_fact_id': target_fact.id if target_fact else None,
        'reference_field': "SegmentRefID",
        'reference_value': "SEG1",
        'is_valid': target_fact is not None,  # ✅ Valid or ❌ Broken
        'was_expected': True,
        'confidence': 0.95
    })
```

#### 4.2 Reference Field Extraction Logic

**Location**: `relationship_analyzer.py:391-449`

The system uses **fuzzy matching** to handle various XML structures and naming conventions:

**Match Strategies** (in priority order):

1. **Exact Match**
   ```python
   if reference_field in fact_data:
       return fact_data[reference_field]
   # "SegmentRefID" == "SegmentRefID"
   ```

2. **Normalized Match** (case-insensitive, underscore-removed)
   ```python
   normalized_attr = attr_key.lower().replace('_', '')
   normalized_field = reference_field.lower().replace('_', '')
   if normalized_attr == normalized_field:
       return attr_value
   # "segmentrefid" == "SegmentRefID"
   # "segment_ref_id" == "SegmentRefID"
   ```

3. **Partial Match** (for complex field names)
   ```python
   if normalized_field in normalized_attr or normalized_attr in normalized_field:
       if ('id' in normalized_field or 'ref' in normalized_field):
           return attr_value
   # "legrefid" found in "operating_leg_ref_id"
   ```

4. **Nested References Section**
   ```python
   references = child.get('references', {})
   for ref_type, ref_values in references.items():
       if ref_type.lower() in reference_field.lower():
           return ref_values[0]
   ```

**Why Fuzzy Matching?**
- XML field names vary: `PaxRefID`, `pax_ref_id`, `PassengerReferenceID`
- Nested structures: References may be in `attributes`, `references`, or `child_references`
- Business flexibility: Handles airline-specific naming conventions

---

### Step 5: Relationship Classification

**Location**: `relationship_analyzer.py:127-133`

Each discovered relationship is classified into one of these categories:

#### ✅ **Expected Validated**
- BA configured this reference type
- Reference exists in XML
- Reference points to valid target (target node found)

**Example**:
```
PassengerList → SegmentList via "SegmentRefID"
Status: ✅ Expected, ✅ Valid
```

#### ❌ **Expected Missing**
- BA configured this reference type
- Reference does NOT exist in XML, OR
- Reference exists but target not found (broken reference)

**Example**:
```
PassengerList → ServiceList via "ServiceRefID"
Status: ✅ Expected, ❌ Broken (ServiceRefID = "SVC99" but no Service with ID "SVC99")
```

#### 🔍 **Unexpected Discovered**
- BA did NOT configure this reference type
- LLM discovered it automatically
- Reference is valid (target found)

**Example**:
```
PassengerList → BaggageList via "BaggageRefID"
Status: 🔍 Discovered, ✅ Valid
```

**Why This Matters**:
- **Expected Validated**: Confirms BA's understanding is correct ✅
- **Expected Missing**: Alerts BA that expected reference is broken ⚠️
- **Unexpected Discovered**: Reveals hidden relationships BA didn't know about 💡

---

### Step 6: Save Relationships to Database

**Location**: `relationship_analyzer.py:135-137`

```python
if relationships:
    self._save_relationships(relationships)
```

**Database Schema** (simplified):

```sql
CREATE TABLE node_relationships (
    id INTEGER PRIMARY KEY,
    run_id TEXT,
    source_node_fact_id INTEGER,        -- Which Passenger node
    target_node_fact_id INTEGER,        -- Which Segment node (NULL if broken)
    source_node_type TEXT,              -- "PassengerList"
    target_node_type TEXT,              -- "SegmentList"
    reference_type TEXT,                -- "segment_reference"
    reference_field TEXT,               -- "SegmentRefID"
    reference_value TEXT,               -- "SEG1"
    is_valid BOOLEAN,                   -- TRUE if target found
    was_expected BOOLEAN,               -- TRUE if BA configured
    confidence REAL,                    -- 0.0 - 1.0
    discovered_by TEXT,                 -- "llm"
    model_used TEXT                     -- "gpt-4o"
);
```

---

## Statistics Tracking

**Location**: `relationship_analyzer.py:76-84, 139-143`

The system tracks comprehensive statistics:

```python
stats = {
    'total_comparisons': 12,           # PassengerList vs 12 other node types
    'relationships_found': 8,           # 8 relationships discovered
    'valid_relationships': 6,           # 6 references point to existing targets
    'broken_relationships': 2,          # 2 references point to missing targets
    'expected_validated': 4,            # 4 BA-expected references found valid
    'expected_missing': 1,              # 1 BA-expected reference is broken
    'unexpected_discovered': 2          # 2 new references LLM discovered
}
```

**Example Output**:
```
✅ 6 Valid Relationships
❌ 2 Broken Relationships
📋 4 Expected References Validated
⚠️ 1 Expected Reference Missing
🔍 2 Unexpected Relationships Discovered
```

---

## Example: Complete Flow

### Input: XML with Passengers and Segments

```xml
<OrderViewRS>
  <Response>
    <DataLists>
      <PassengerList>
        <Passenger>
          <PaxID>PAX1</PaxID>
          <GivenName>John</GivenName>
          <SegmentRefID>SEG1</SegmentRefID>
        </Passenger>
        <Passenger>
          <PaxID>PAX2</PaxID>
          <GivenName>Jane</GivenName>
          <SegmentRefID>SEG999</SegmentRefID>  <!-- Broken reference -->
        </Passenger>
      </PassengerList>

      <SegmentList>
        <Segment>
          <SegmentKey>SEG1</SegmentKey>
          <DepartureStation>LAX</DepartureStation>
        </Segment>
      </SegmentList>
    </DataLists>
  </Response>
</OrderViewRS>
```

### BA Configuration

```python
NodeConfiguration(
    section_path="PassengerList",
    expected_references=["segment_reference"]
)
```

### Discovery Process

**Step 1**: Extract NodeFacts
- 2 Passenger nodes
- 1 Segment node

**Step 2**: LLM Analysis
```
Source: PassengerList sample (PAX1)
Target: SegmentList sample (SEG1)
Expected: ["segment_reference"]

LLM discovers:
- reference_type: "segment_reference"
- reference_field: "SegmentRefID"
- was_expected: true
- confidence: 0.95
```

**Step 3**: Validate All Instances

**Passenger 1 (PAX1)**:
- SegmentRefID = "SEG1"
- Search SegmentList for SegmentKey = "SEG1"
- ✅ **Found**: Valid reference

**Passenger 2 (PAX2)**:
- SegmentRefID = "SEG999"
- Search SegmentList for SegmentKey = "SEG999"
- ❌ **Not Found**: Broken reference

### Output Relationships

```python
[
    {
        'source': 'Passenger[PAX1]',
        'target': 'Segment[SEG1]',
        'reference_type': 'segment_reference',
        'reference_field': 'SegmentRefID',
        'reference_value': 'SEG1',
        'is_valid': True,           # ✅
        'was_expected': True        # 📋
    },
    {
        'source': 'Passenger[PAX2]',
        'target': None,
        'reference_type': 'segment_reference',
        'reference_field': 'SegmentRefID',
        'reference_value': 'SEG999',
        'is_valid': False,          # ❌ Broken
        'was_expected': True        # 📋
    }
]
```

### Statistics

```
Total Comparisons: 1 (PassengerList → SegmentList)
Relationships Found: 2
Valid Relationships: 1 ✅
Broken Relationships: 1 ❌
Expected Validated: 2 (both instances checked)
Expected Missing: 0
Unexpected Discovered: 0
```

---

## Key Design Principles

### 1. **Hybrid Intelligence**
- **BA Knowledge**: Leverage domain expertise (expected_references)
- **AI Discovery**: Find relationships BA didn't know about
- **Best of Both**: Validate BA assumptions + discover unknowns

### 2. **Sample + Validate Pattern**
- **LLM analyzes samples** (1 source + 1 target) for efficiency
- **Validation checks all instances** for accuracy
- **Cost-effective**: Minimize expensive LLM calls

### 3. **Fuzzy Field Matching**
- Handle variations: `PaxRefID`, `pax_ref_id`, `PassengerReferenceID`
- Search nested structures: `attributes`, `references`, `children`
- Airline-agnostic: Works with different XML schemas

### 4. **Broken Reference Detection**
- **Valid**: Reference points to existing target ✅
- **Broken**: Reference value exists but target not found ❌
- **Critical for data quality**: Identifies XML integrity issues

### 5. **Confidence Scoring**
- LLM provides confidence (0.0 - 1.0) for each discovery
- Helps prioritize validation efforts
- Distinguishes certain vs uncertain relationships

### 6. **Comprehensive Statistics**
- Track expected vs unexpected
- Track valid vs broken
- Provide actionable insights for BAs

---

## Performance Considerations

### Optimization Strategies

1. **Sample-Based LLM Analysis**
   - Only send 1 source + 1 target to LLM
   - Reduces API calls by ~90%
   - Cost: Minimal accuracy loss (validated across all instances)

2. **Cached Configurations**
   - Expected references loaded once per section
   - Reused for all instances

3. **Batch Relationship Insertion**
   - Collect all relationships in memory
   - Single bulk database insert
   - Faster than per-relationship inserts

4. **Skip Self-Comparisons**
   ```python
   if source_path == target_path:
       continue
   ```
   - PassengerList doesn't reference itself

### Typical Performance

**Small XML** (5 node types, 50 total nodes):
- LLM Calls: ~10 (5 × 2 node type pairs)
- Validation: ~100 instance checks
- Time: ~30 seconds

**Large XML** (20 node types, 500 total nodes):
- LLM Calls: ~190 (20 × 19 / 2 pairs)
- Validation: ~5,000 instance checks
- Time: ~5 minutes

---

## Error Handling

### LLM Failures

```python
try:
    response = self.llm_client.chat.completions.create(...)
    result = json.loads(response.choices[0].message.content)
except Exception as e:
    logger.error("LLM reference discovery failed", error=str(e))
    return None  # Skip this source-target pair
```

**Fallback Strategy**: If LLM fails for a node pair, relationships are simply not discovered for that pair. Other pairs continue processing.

### Reference Value Not Found

```python
ref_value = self._extract_reference_value(source_fact, reference_field)
if not ref_value:
    continue  # Skip this instance, no reference to validate
```

**Behavior**: If reference field doesn't exist in source node, that instance is skipped (not counted as broken).

### Target Not Found (Broken Reference)

```python
target_fact = self._find_target_by_reference(target_facts, ref_value)
relationships.append({
    'target_node_fact_id': target_fact.id if target_fact else None,
    'is_valid': target_fact is not None
})
```

**Behavior**: Relationship is stored as `is_valid=False`, allowing BA to see broken references.

---

## Configuration: Expected References

### Where to Configure

**Node Configuration Manager** → **Manage Configurations** → **Expected References**

### Format

```python
expected_references = [
    "segment_reference",
    "fare_reference",
    "service_reference",
    "infant_parent"
]
```

### Naming Convention

Use semantic names that describe the business relationship:
- ✅ `segment_reference` (clear: Passenger → Segment)
- ✅ `infant_parent` (clear: Infant → Parent Passenger)
- ❌ `pax_ref_id` (implementation detail, not semantic)
- ❌ `ref1` (meaningless)

### When to Configure

**Before Discovery**:
- Configure expected references for known business logic
- System will validate these during discovery

**After Discovery**:
- Review "Unexpected Discovered" relationships
- Add valuable ones to expected_references for future runs

---

## UI Display

### Discovery Results Page

**Expected & Validated** ✅📋:
```
PassengerList → SegmentList via "SegmentRefID"
Status: Expected & Valid
Confidence: 95%
```

**Expected but Missing** ❌📋:
```
PassengerList → ServiceList via "ServiceRefID"
Status: Expected but Broken (target not found)
Confidence: 90%
Value: "SVC999"
```

**Unexpected Discovery** ✅🔍:
```
PassengerList → BaggageList via "BaggageRefID"
Status: Discovered & Valid
Confidence: 85%
Note: This reference was not configured but LLM found it
```

### Relationship Summary Statistics

```
📊 Relationship Analysis Results

✅ Valid Relationships: 15
❌ Broken Relationships: 3
📋 Expected Validated: 12
⚠️ Expected Missing: 2
🔍 Unexpected Discovered: 4

Total Comparisons: 20 node type pairs analyzed
```

---

## Future Enhancements

### Potential Improvements

1. **Multi-hop Relationships**
   - Passenger → Segment → Flight
   - Currently: Direct relationships only

2. **Reference Type Taxonomy**
   - Categorize references: ownership, lookup, hierarchy
   - Better semantic understanding

3. **Pattern Learning**
   - Learn field naming patterns across airlines
   - Improve fuzzy matching accuracy

4. **Confidence Thresholds**
   - Filter low-confidence discoveries
   - User-configurable minimum confidence

5. **Relationship Validation Rules**
   - Cardinality checks (1:1, 1:N, N:M)
   - Business rule validation (e.g., infant must reference adult)

---

## Troubleshooting

### No Relationships Discovered

**Possible Causes**:
1. LLM not configured (check .env: AZURE_OPENAI_KEY)
2. No reference fields in XML (nodes are independent)
3. LLM confidence too low (check logs for confidence scores)

**Solution**: Check backend logs for LLM responses and errors.

### Too Many False Positives

**Symptom**: LLM discovers relationships that don't make sense

**Cause**: LLM over-interpreting similar field names

**Solution**:
- Add expected_references to guide LLM
- Review confidence scores (ignore < 0.7)

### Broken References Not Detected

**Symptom**: Known broken reference shows as valid

**Cause**: Fuzzy matching too aggressive (matched wrong field)

**Solution**: Check `reference_field` in relationship details - may be matching unintended field.

---

## API Endpoints

### Get Relationships for Run

```http
GET /api/v1/relationships/?run_id={run_id}&workspace={workspace}
```

**Response**:
```json
[
  {
    "id": 123,
    "source_node_type": "PassengerList",
    "target_node_type": "SegmentList",
    "reference_type": "segment_reference",
    "reference_field": "SegmentRefID",
    "reference_value": "SEG1",
    "is_valid": true,
    "was_expected": true,
    "confidence": 0.95
  }
]
```

### Get Relationship Summary

```http
GET /api/v1/relationships/run/{run_id}/summary?workspace={workspace}
```

**Response**:
```json
{
  "total_relationships": 18,
  "valid_count": 15,
  "broken_count": 3,
  "expected_validated": 12,
  "expected_missing": 2,
  "unexpected_discovered": 4,
  "by_type": {
    "segment_reference": 8,
    "fare_reference": 6,
    "service_reference": 4
  }
}
```

---

## Summary

**Relationship Discovery** is a core feature that:

✅ **Validates Business Logic**: Confirms BA-expected references exist
✅ **Discovers Hidden Relationships**: LLM finds references BA didn't know about
✅ **Detects Data Quality Issues**: Identifies broken references
✅ **Provides Confidence Scores**: Distinguishes certain from uncertain discoveries
✅ **Handles XML Variations**: Fuzzy matching works across airline schemas
✅ **Scales Efficiently**: Sample-based LLM + instance validation

**Key Insight**: The hybrid approach (BA knowledge + AI discovery) provides both **precision** (validate known references) and **recall** (discover unknown references), making it more powerful than either approach alone.

---

**Document Version**: 1.0
**Last Updated**: 2025-10-09
**Author**: AssistedDiscovery Development Team
