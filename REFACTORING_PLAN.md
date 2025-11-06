# Terminology Refactoring Plan

## Changes
- **OLD "discovery"** → **NEW "pattern_extractor"**
- **OLD "identify"** → **NEW "discovery"**

## Status
✅ Database enums updated (database.py, schemas.py)

## Remaining Work

### 1. Database Migration (CRITICAL - Do First!)
```sql
-- Update existing runs in database
UPDATE runs SET kind = 'pattern_extractor' WHERE kind = 'discovery';
UPDATE runs SET kind = 'discovery_temp' WHERE kind = 'identify';
UPDATE runs SET kind = 'discovery' WHERE kind = 'discovery_temp';
```

### 2. API Endpoints
- [ ] `backend/app/api/v1/endpoints/runs.py`
  - Update query param regex: `^(discovery|identify)$` → `^(pattern_extractor|discovery)$`
  - Update docstrings

- [ ] Rename: `backend/app/api/v1/endpoints/identify.py` → `discovery.py`
  - Update all `RunKind.IDENTIFY` → `RunKind.DISCOVERY`
  - Update docstrings

### 3. Service Files
- [ ] Rename: `backend/app/services/discovery_workflow.py` → `pattern_extractor_workflow.py`
  - Rename class: `DiscoveryWorkflow` → `PatternExtractorWorkflow`
  - Update all `RunKind.DISCOVERY` → `RunKind.PATTERN_EXTRACTOR`
  - Update function: `create_discovery_workflow` → `create_pattern_extractor_workflow`

- [ ] Rename: `backend/app/services/identify_workflow.py` → `discovery_workflow.py`
  - Rename class: `IdentifyWorkflow` → `DiscoveryWorkflow`
  - Update all `RunKind.IDENTIFY` → `RunKind.DISCOVERY`
  - Update function: `create_identify_workflow` → `create_discovery_workflow`

### 4. Frontend UI
- [ ] Rename: `frontend/streamlit_ui/pages/4_Discovery.py` → `4_Pattern_Extractor.py`
- [ ] Create: `frontend/streamlit_ui/pages/5_Discovery.py` (new)
- [ ] `frontend/streamlit_ui/app_core.py`:
  - Rename: `show_discovery_page()` → `show_pattern_extractor_page()`
  - Create: `show_discovery_page()` (new - copy from old identify logic)
  - Update all API calls: `"identify"` → `"discovery"`, `"discovery"` → `"pattern_extractor"`

### 5. Test Files
- [ ] `backend/tests/integration/test_api_discovery.py` → `test_api_pattern_extractor.py`
- [ ] Create: `backend/tests/integration/test_api_discovery.py` (new)

## Automated Script

I can create a Python script to automate most of these changes. Would you like me to:
1. Create the script
2. Apply changes manually file-by-file (slower but safer)
3. Do a partial refactoring (update critical paths only)

