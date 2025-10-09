# Hardcoding Analysis Report

## Summary
Analysis performed to identify hardcoded values that could affect testing with different XMLs or airline data.

**Status**: ⚠️ **REVIEW REQUIRED** - Several hardcoded values found

---

## 🔴 CRITICAL FINDINGS (Require Review)

### 1. **Hardcoded Workspace List** (Frontend)
**File**: `frontend/streamlit_ui/app_core.py:31`

```python
return ["default", "LATAM", "LH", "SQ", "VY", "AFKL"]
```

**Impact**:
- Users can only select from these predefined workspaces on first load
- Can be extended via UI, but starts with airline-specific workspaces

**Recommendation**:
- ✅ **OK for testing** - Users can add new workspaces via Config page
- This is just the default list if no workspaces.json exists
- Already dynamic - users can create their own workspaces

---

### 2. **Hardcoded NDC Version Fallback Logic** (Backend)
**Files**:
- `backend/app/services/discovery_workflow.py:404-407`
- `backend/app/services/xml_parser.py:153-206`

**Hardcoded Version Priority**:
```python
('21.3', 'OrderViewRS'),  # Most modern
('18.1', 'OrderViewRS'),  # Very common
('17.2', 'OrderViewRS'),  # Legacy but common
('19.2', 'OrderViewRS'),  # Alternative
```

**Hardcoded Fallbacks**:
- Default to `17.2` if no version detected
- Namespace `2017.2` → maps to `17.2`
- Version `5.000` with `2017.2` namespace → maps to `17.2`
- `21` version attribute → maps to `21.3`

**Impact**:
- System makes assumptions about NDC versions when not explicit
- Could misclassify newer/different NDC versions

**Recommendation**:
- ⚠️ **REVIEW NEEDED** - Ensure fallback logic covers user test XMLs
- If users test with NDC 22.1, 23.1, or other versions, may default to 17.2
- **Suggestion**: Add logging to warn when version detection falls back to defaults

---

### 3. **Hardcoded IATA Prefix Normalization** (Backend)
**Files**:
- `backend/app/services/discovery_workflow.py:121-122, 150-157`
- `backend/app/services/pattern_generator.py:35-37`

```python
normalized_path = section_path.replace('IATA_OrderViewRS/', 'OrderViewRS/')
normalized_path = normalized_path.replace('/IATA_OrderViewRS/', '/OrderViewRS/')
```

**Impact**:
- Assumes all XMLs either have `IATA_` prefix or don't
- Hardcoded to `OrderViewRS` message type
- Different message types may not be normalized correctly

**Recommendation**:
- ⚠️ **REVIEW NEEDED** - Only handles OrderViewRS
- If users test AirShoppingRS, ServiceListRS, OfferPriceRS, etc., normalization may not work
- **Suggestion**: Make normalization generic for all message types

---

### 4. **Hardcoded Example Data in API Docs** (Backend)
**Files**:
- `backend/app/api/v1/endpoints/node_facts.py:123-125`
- `backend/app/api/v1/endpoints/patterns.py:174-176`
- `backend/app/api/v1/endpoints/llm_test.py:130, 164`

**Examples**:
```python
spec_version="17.2",
message_root="OrderViewRS",
section_path="/OrderViewRS/Response/DataLists/PassengerList"
```

**Impact**:
- ✅ **NO IMPACT** - These are just API documentation examples
- Do not affect runtime behavior

---

## 🟡 MODERATE FINDINGS (Documentation Only)

### 5. **Hardcoded Examples in Comments/Docs**
**Files**: Multiple files with examples like `SQ`, `AF`, `VY` in comments

**Impact**:
- ✅ **NO IMPACT** - Documentation only, not runtime code

---

## 🟢 NO ISSUES FOUND

### 1. **No Hardcoded File Paths** ✅
- No hardcoded XML file paths
- No hardcoded upload directories
- All file handling is dynamic

### 2. **No Hardcoded Database Values** ✅
- No hardcoded connection strings in code
- All database config comes from .env

### 3. **No Hardcoded Airline Logic** ✅
- Airline codes are extracted from XML, not hardcoded
- Pattern matching is dynamic

---

## 📋 RECOMMENDATIONS FOR TESTING

### Immediate Actions:

1. **Test with Different Message Types**
   - If users test with `AirShoppingRS`, `ServiceListRS`, `OfferPriceRS`, etc.
   - Current normalization is hardcoded to `OrderViewRS`
   - **Action**: Update normalization to be generic

2. **Test with Different NDC Versions**
   - If users test with NDC 22.1, 23.1, or custom versions
   - May default to `17.2`
   - **Action**: Add logging for version detection fallbacks

3. **Monitor Version Detection**
   - Add logging when version fallback logic is triggered
   - Helps debug misclassifications

### Code Changes Needed:

**Priority 1 - Make IATA Prefix Normalization Generic**:
```python
# Instead of hardcoding OrderViewRS:
def normalize_iata_prefix(path: str, message_root: str) -> str:
    """Remove IATA_ prefix from message root in paths."""
    iata_variant = f"IATA_{message_root}"
    path = path.replace(f'{iata_variant}/', f'{message_root}/')
    path = path.replace(f'/{iata_variant}/', f'/{message_root}/')
    return path
```

**Priority 2 - Add Version Detection Logging**:
```python
# In xml_parser.py when falling back:
if detected_version == '17.2' and not explicitly_set:
    logger.warning(f"NDC version not detected, defaulting to 17.2 for {message_root}")
```

---

## ✅ TESTING CHECKLIST

Before releasing to users, verify:

- [ ] Test with non-OrderViewRS messages (AirShoppingRS, etc.)
- [ ] Test with NDC versions beyond 21.3 (if applicable)
- [ ] Test with XMLs that have IATA_ prefix
- [ ] Test with XMLs that don't have IATA_ prefix
- [ ] Test with different airlines (not just VY, SQ, LATAM)
- [ ] Test with custom workspace names
- [ ] Verify version detection logs for fallback warnings

---

## 🎯 CONCLUSION

**Overall Assessment**: System is mostly dynamic, with a few strategic hardcoded values for common scenarios.

**Safe to Release?**: ⚠️ **WITH CAVEATS**

The application will work for most NDC XMLs, but:
1. Works best with `OrderViewRS` messages
2. Works best with NDC versions 17.2-21.3
3. Other message types and versions will work, but may have normalization issues

**Recommended Before Release**:
1. Make IATA prefix normalization generic (15 min fix)
2. Add version detection logging (5 min fix)
3. Test with at least one non-OrderViewRS XML (10 min test)

---

**Generated**: 2025-01-09
**Analyst**: Claude Code
