# Testing Checklist - Relationship Fix & AI Explanation Improvements

## ⚠️ CRITICAL: Restart Backend Before Testing

**The code changes will NOT take effect until you restart the backend!**

```bash
# Stop current backend (Ctrl+C)
# Then restart:
cd backend
python -m uvicorn app.main:app --reload
```

---

## 📋 Test Scenario 1: Expected Broken Relationships (No Penalty)

### Setup
- **Workspace:** Create new workspace (e.g., `Test_Validation_Fix`)
- **XML File:** `resources/Alaska/AirShoppingRS.xml`

### Steps

**1. Run Discovery**
- [ ] Upload AirShoppingRS.xml to new workspace
- [ ] Conflict resolution: `replace`
- [ ] Wait for completion (should take ~3-5 minutes with relationship analysis)

**2. Verify Pattern Has Expected Relationships**
```bash
cd backend
sqlite3 data/workspaces/Test_Validation_Fix.db
```
```sql
SELECT json_extract(decision_rule, '$.expected_relationships')
FROM patterns
WHERE section_path='AirShoppingRS/Response/DataLists/DatedMarketingSegmentList'
LIMIT 1;
```

**Expected Output:**
```json
[
  {
    "target_section_path": "/AirShoppingRS/Response/DataLists/DatedOperatingLegList",
    "target_node_type": "DatedOperatingLegList",
    "reference_type": "segment_reference",
    "is_valid": false,  // ⭐ Key: Expected broken relationship!
    "confidence": 0.9
  },
  {
    "target_section_path": "/AirShoppingRS/Response/DataLists/DatedOperatingSegmentList",
    "target_node_type": "DatedOperatingSegmentList",
    "reference_type": "segment_reference",
    "is_valid": true,
    "confidence": 1.0
  },
  ...
]
```

**3. Run Identify**
- [ ] Upload the **same** AirShoppingRS.xml file
- [ ] Wait for completion

**4. Check Confidence Score**
```sql
SELECT pm.confidence, pm.verdict, nf.node_type
FROM pattern_matches pm
JOIN node_facts nf ON pm.node_fact_id = nf.id
WHERE nf.node_type='DatedMarketingSegmentList'
ORDER BY pm.created_at DESC LIMIT 1;
```

**Expected Output:**
```
0.95|EXACT_MATCH|DatedMarketingSegmentList
```
OR
```
1.0|EXACT_MATCH|DatedMarketingSegmentList
```

**NOT:**
```
0.7|PARTIAL_MATCH|DatedMarketingSegmentList  ❌ FAIL
```

**5. Test Detailed AI Explanation**
- [ ] Navigate to Identify results page in UI
- [ ] Find DatedMarketingSegmentList in the matches table
- [ ] Click "Detailed AI Explanation" button
- [ ] Wait for LLM response

**Expected Output:**
```
The Problem: No quality issues detected - the DatedMarketingSegmentList data is complete and valid, matching the expected NDC 21.3 schema structure perfectly.

Impact: Having complete and accurate marketing segment information ensures reliable flight segment tracking, proper linking to operating segments, and accurate passenger itinerary management.

Action: No action required - continue processing as normal. The data meets all quality standards for this airline and message type.
```

**NOT Expected:**
```
The Problem: The XML appears truncated... ❌ FAIL
```

---

## 📋 Test Scenario 2: Dynamic Few-Shot Examples

### Test Case 2A: No Quality Issues

- [ ] Use DatedOperatingLegList (should be complete)
- [ ] Click "Detailed AI Explanation"
- [ ] Verify response says "No quality issues detected"
- [ ] Verify it does NOT mention truncation or incomplete data

### Test Case 2B: Missing Required Attributes

To test this, you'd need an XML file with actual quality issues. If you have one:

- [ ] Upload XML with missing required fields
- [ ] Run Discovery + Identify
- [ ] Click "Detailed AI Explanation" for an element with issues
- [ ] Verify the response follows Problem/Impact/Action format
- [ ] Verify it includes specific field names and percentages

---

## 📋 Test Scenario 3: Backward Compatibility

### Test Old Patterns (Without expected_relationships)

**1. Use an old workspace** (e.g., Test6 or Test8)
- [ ] Run Identify on AirShoppingRS.xml
- [ ] Check if old patterns still work

**Expected Behavior:**
- Old patterns (without `expected_relationships`) should still match
- They'll use the old penalty logic (backward compatible)
- No errors should occur

---

## 📋 Test Scenario 4: Relationship Mismatch Detection

### Create a Mismatch Scenario

This would require:
1. Pattern expects relationship to be valid
2. Actual data has broken relationship (or vice versa)

**How to test:**
- Manually edit a pattern in database to have different expected_relationships
- Then run Identify
- Should see penalty applied for the mismatch

```sql
-- Manually change expected_relationships for testing
UPDATE patterns
SET decision_rule = json_set(
  decision_rule,
  '$.expected_relationships[0].is_valid',
  1  -- Change from false to true
)
WHERE section_path='AirShoppingRS/Response/DataLists/DatedMarketingSegmentList';
```

Then run Identify and verify mismatch is detected.

---

## ✅ Success Criteria Summary

| Aspect | Before Fix | After Fix |
|--------|-----------|-----------|
| **Pattern has expected_relationships** | ❌ Empty array | ✅ Populated with is_valid status |
| **DatedMarketingSegmentList confidence** | 0.70 (30% penalty) | ~0.95-1.00 (no penalty) |
| **Detailed AI Explanation** | "XML appears truncated..." | "No quality issues detected..." |
| **Few-shot examples** | ❌ None | ✅ Dynamic, contextual examples |
| **Logs show relationship validation** | "broken relationship" penalty | "No penalty" or "0 mismatches" |

---

## 🐛 Troubleshooting

### Issue: Still seeing 0.70 confidence

**Possible causes:**
1. ❌ Backend not restarted (most common!)
2. ❌ Using old patterns from before the fix
3. ❌ Different quality issue (not relationship-related)

**Solution:**
1. Restart backend
2. Delete old patterns and re-run Discovery
3. Check logs for actual penalty reason

### Issue: Pattern doesn't have expected_relationships

**Possible causes:**
1. ❌ Pattern was generated before the fix
2. ❌ No relationships were detected during Discovery

**Solution:**
1. Re-run Discovery on a fresh workspace
2. Check relationship analysis logs
3. Verify node_relationships table has entries

### Issue: Detailed AI Explanation still mentions truncation

**Possible causes:**
1. ❌ Backend not restarted
2. ❌ Using cached explanation (old response)

**Solution:**
1. Restart backend
2. Delete pattern_matches table entries to clear cache
3. Re-run Identify

---

## 📊 Quick Verification Commands

**Check if backend has latest code:**
```bash
cd backend
grep -n "expected_relationships" app/services/pattern_generator.py
# Should show multiple lines
```

**Check database for expected_relationships:**
```bash
sqlite3 data/workspaces/YOUR_WORKSPACE.db
```
```sql
SELECT COUNT(*) FROM patterns
WHERE json_extract(decision_rule, '$.expected_relationships') IS NOT NULL;
# Should be > 0 after running Discovery with the fix
```

**Check logs for "No penalty" message:**
```bash
tail -100 ~/Library/Logs/AssistedDiscovery/assisted_discovery.log | grep -i "penalty\|mismatch"
```

---

## 📝 Report Template

After testing, report results:

```
✅ Test Scenario 1: PASS/FAIL
   - Pattern has expected_relationships: YES/NO
   - DatedMarketingSegmentList confidence: X.XX
   - Detailed AI Explanation: CORRECT/INCORRECT

✅ Test Scenario 2A: PASS/FAIL
   - No truncation warnings: YES/NO

✅ Test Scenario 3: PASS/FAIL
   - Backward compatibility: WORKING/BROKEN

Issues found:
- [Describe any issues]

Next steps:
- [What needs to be fixed]
```

---

**Last Updated:** 2025-11-05
**Version:** 1.0
