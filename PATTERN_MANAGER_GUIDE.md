# Pattern Manager - Hybrid Approach Guide

## Overview

Pattern Manager is a **hybrid system** that combines backend automation with frontend organization:

- **Backend** (FastAPI): Automatically discovers and generates patterns during Discovery runs
- **Frontend** (Streamlit): Exports, verifies, and organizes patterns in workspaces

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     DISCOVERY WORKFLOW                           │
│                                                                  │
│  Upload XML → Backend Extracts NodeFacts → Generate Patterns    │
│                                                                  │
│  Patterns stored in: backend/database (PostgreSQL)              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    PATTERN MANAGER                              │
│                                                                  │
│  📤 EXPORT TAB                                                  │
│     - View all backend patterns                                 │
│     - Filter by Version/Airline/Message                         │
│     - Select patterns to export                                 │
│     - Export to Workspace SQLite DB                             │
│                                                                  │
│  ✅ VERIFY TAB                                                  │
│     - Select workspace pattern                                  │
│     - Paste test XML                                            │
│     - LLM verifies pattern validity                             │
│     - Shows match/mismatch details                              │
│                                                                  │
│  📚 MANAGE TAB                                                  │
│     - View all workspace patterns                               │
│     - Export to CSV                                             │
│     - Clear workspace                                           │
│     - Organize by airline/version                               │
└─────────────────────────────────────────────────────────────────┘
```

## Workspaces

Workspaces allow you to organize patterns by:
- **Airline**: LATAM, LH, SQ, VY, AFKL
- **Project**: default (multi-airline), custom names
- **Purpose**: Testing, Production, Development

Each workspace has its own SQLite database:
```
frontend/streamlit_ui/data/workspaces/
├── default_patterns.db
├── LATAM_patterns.db
├── LH_patterns.db
└── ...
```

## Usage Workflow

### 1. Run Discovery (Backend-Driven)

```
🔬 Discovery Page
  └─ Upload NDC XML
  └─ Select nodes to extract (Node Manager)
  └─ Click "Start Discovery"
  └─ Backend generates patterns automatically
  └─ View patterns in Discovery Results
```

**What happens:**
- Backend extracts NodeFacts
- Generates decision rules
- Analyzes relationships
- Stores patterns in PostgreSQL

### 2. Export Patterns to Workspace

```
🎨 Pattern Manager → 📤 Export Tab
  └─ Backend shows all patterns
  └─ Filter by Version/Airline/Message
  └─ Select patterns (or "Select All")
  └─ Click "Export to Workspace"
  └─ Patterns saved to workspace SQLite DB
```

**What happens:**
- Backend patterns → Workspace SQLite
- Converts decision rules → Validation prompts
- Creates API/Version/Section mappings
- Ready for verification

### 3. Verify Patterns (Optional but Recommended)

```
🎨 Pattern Manager → ✅ Verify Tab
  └─ Select pattern from workspace
  └─ Paste sample XML
  └─ Click "Verify Pattern"
  └─ LLM tests if XML matches pattern
  └─ Shows validation results
```

**Why verify?**
- Ensure patterns work correctly
- Catch edge cases
- Validate before using in Identify
- Document pattern behavior

### 4. Organize Workspace

```
🎨 Pattern Manager → 📚 Manage Tab
  └─ View all workspace patterns
  └─ Export to CSV for documentation
  └─ Clear workspace if needed
  └─ Switch workspaces in sidebar
```

### 5. Use Patterns in Identify

```
🎯 Identify Page
  └─ Upload XML to identify
  └─ Backend uses patterns to match
  └─ Shows matches with confidence scores
  └─ (Backend uses PostgreSQL patterns, not workspace)
```

**Note:** Identify uses backend patterns, not workspace patterns. Workspace is for organization and verification only.

## Database Schema

### Backend (PostgreSQL)
```sql
patterns
├── id
├── spec_version
├── message_root
├── airline_code
├── section_path
├── decision_rule (JSON)
├── times_seen
└── ...
```

### Workspace (SQLite per workspace)
```sql
api
├── api_id
├── api_name (LATAM, LH, etc.)

apiversion
├── version_id
├── api_id
├── version_number (21.3, 17.2, etc.)

api_section
├── section_id
├── api_id
├── section_name
├── section_display_name

pattern_details
├── pattern_id
├── pattern_name
├── pattern_description
├── pattern_prompt (validation rules)

section_pattern_mapping
├── mapping_id
├── pattern_id
├── section_id
├── api_id
```

## Key Features

### ✅ What's Implemented
- ✅ Backend pattern generation (automatic)
- ✅ Pattern Manager with 3 tabs
- ✅ Workspace selector (sidebar)
- ✅ Export backend → workspace
- ✅ Workspace SQLite databases
- ✅ Cost display placeholder
- ✅ Pattern filtering
- ✅ Pattern organization

### 🚧 Coming Soon
- 🚧 LLM verification implementation
- 🚧 Token cost tracking
- 🚧 Pattern versioning
- 🚧 Workspace sharing/export
- 🚧 Pattern diff/comparison
- 🚧 Auto-suggestions

## Files Created/Modified

### New Files
```
frontend/streamlit_ui/
├── pattern_manager.py          # Pattern Manager main module
├── utils/
│   ├── init_db.py              # SQLite DB initialization
│   ├── pattern_verifier.py     # From backup (verify logic)
│   ├── pattern_saver.py        # From backup (save logic)
│   ├── sql_db_utils.py         # SQLite operations
│   ├── cost_display_manager.py # Token cost tracking
│   └── ...
└── data/
    ├── api_analysis.db         # Initial DB (not used directly)
    └── workspaces/             # Per-workspace DBs
        ├── default_patterns.db
        ├── LATAM_patterns.db
        └── ...
```

### Modified Files
```
frontend/streamlit_ui/
└── main.py                     # Added Pattern Manager navigation,
                                # workspace selector, cost display
```

## Benefits of Hybrid Approach

### For Business Analysts
- ✅ Automated pattern discovery (no manual extraction)
- ✅ Organized workspace per airline/project
- ✅ Verify patterns before deployment
- ✅ Export patterns for documentation

### For Developers
- ✅ Keep existing backend logic (no breaking changes)
- ✅ Backend patterns remain source of truth
- ✅ Workspace for experimentation
- ✅ Easy to extend with new features

### System Advantages
- ✅ Backend handles heavy lifting (LLM extraction)
- ✅ Frontend handles organization (user-friendly)
- ✅ No backend changes needed
- ✅ Workspace isolation (test without affecting production)

## Usage Tips

1. **Always run Discovery first** - Backend generates patterns
2. **Export selectively** - Filter patterns before exporting
3. **Use workspaces wisely** - One per airline or project
4. **Verify critical patterns** - Especially for production use
5. **Document in workspace** - Use Manage tab to export CSVs

## Troubleshooting

### Backend patterns not showing?
- Check backend is running: `http://localhost:8000/health`
- Run Discovery to generate patterns first
- Check Pattern Explorer for backend patterns

### Export fails?
- Check workspace DB exists: `frontend/streamlit_ui/data/workspaces/`
- Run `python3 utils/init_db.py` to recreate DB
- Check for UNIQUE constraint errors (pattern already exists)

### Workspace empty after switch?
- Each workspace has separate DB
- Export patterns to new workspace
- Check correct workspace selected in sidebar

## Next Steps

1. ✅ Test Export functionality
2. 🚧 Implement LLM verification
3. 🚧 Add real token cost tracking
4. 🚧 Add workspace import/export
5. 🚧 Add pattern comparison tools
