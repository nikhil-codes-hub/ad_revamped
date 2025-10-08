# Workspace Database Architecture

## Overview

AssistedDiscovery now uses **workspace-based SQLite databases** instead of centralized MySQL. This makes the system:
- ✅ **Portable**: No MySQL installation required
- ✅ **User-friendly**: Each workspace is self-contained
- ✅ **Isolated**: Projects/airlines don't interfere with each other
- ✅ **Shareable**: Send `.db` file to colleagues

## Architecture

```
frontend/streamlit_ui/data/workspaces/
├── default.db          # Default workspace
├── SQ.db               # Singapore Airlines workspace
├── LATAM.db            # LATAM Airlines workspace
└── workspaces.json     # Workspace list configuration
```

### Each Workspace Database Contains:

**Discovery & Extraction:**
- `runs` - All Discovery/Identify runs
- `node_facts` - Extracted node facts from XML
- `node_relationships` - LLM-discovered relationships
- `association_facts` - Node associations

**Pattern Management:**
- `patterns` - Discovered patterns
- `pattern_matches` - Pattern matching results
- `node_configurations` - BA-managed extraction rules

**Configuration:**
- `ndc_target_paths` - Target extraction paths
- `ndc_path_aliases` - Cross-version path aliases
- `reference_types` - Reference type glossary

## Database Schema

### 1. Core Entities

#### `runs`
```sql
id TEXT PRIMARY KEY              -- UUID run identifier
kind TEXT                         -- 'discovery' or 'identify'
status TEXT                       -- 'started', 'completed', 'failed'
spec_version TEXT                 -- NDC version (18.1, 21.3)
message_root TEXT                 -- Message type (OrderViewRS, etc.)
airline_code TEXT                 -- Airline (SQ, AF, etc.)
filename TEXT                     -- Uploaded file name
started_at TIMESTAMP
finished_at TIMESTAMP
metadata_json TEXT                -- Additional run data
```

#### `node_facts`
```sql
id INTEGER PRIMARY KEY
run_id TEXT                       -- References runs.id
spec_version TEXT
message_root TEXT
section_path TEXT                 -- XML path where found
node_type TEXT                    -- Node type name
node_ordinal INTEGER              -- Position in section
fact_json TEXT                    -- Structured fact data (JSON)
pii_masked BOOLEAN                -- PII masking applied?
```

#### `node_relationships`
```sql
id INTEGER PRIMARY KEY
run_id TEXT
source_node_fact_id INTEGER       -- Source node
target_node_fact_id INTEGER       -- Target node (NULL if broken)
reference_type TEXT               -- 'pax_reference', 'segment_reference'
reference_field TEXT              -- Field containing reference
reference_value TEXT              -- Actual reference value
is_valid BOOLEAN                  -- Does reference resolve?
was_expected BOOLEAN              -- Was in BA config?
confidence REAL                   -- LLM confidence (0.0-1.0)
discovered_by TEXT                -- 'llm' or 'config'
model_used TEXT                   -- LLM model name
```

### 2. Pattern System

#### `patterns`
```sql
id INTEGER PRIMARY KEY
spec_version TEXT
message_root TEXT
airline_code TEXT                 -- NULL = applies to all
section_path TEXT
selector_xpath TEXT               -- XPath for matching
decision_rule TEXT                -- Rule definition (JSON)
description TEXT                  -- Human-readable description
signature_hash TEXT UNIQUE        -- SHA-256 deduplication
times_seen INTEGER                -- How many times discovered
examples TEXT                     -- Example nodes (JSON)
```

#### `pattern_matches`
```sql
id INTEGER PRIMARY KEY
run_id TEXT
node_fact_id INTEGER
pattern_id INTEGER
confidence REAL                   -- Match confidence
verdict TEXT                      -- 'match', 'no_match', 'uncertain'
match_metadata TEXT               -- Additional match details
```

### 3. BA Configuration

#### `node_configurations`
```sql
id INTEGER PRIMARY KEY
spec_version TEXT
message_root TEXT
airline_code TEXT                 -- NULL = applies to all
node_type TEXT                    -- Node to extract
section_path TEXT                 -- Where to find it
enabled BOOLEAN                   -- Should extract?
expected_references TEXT          -- Expected refs (JSON array)
ba_remarks TEXT                   -- BA notes
created_by TEXT                   -- Who configured this
```

#### `reference_types`
```sql
id INTEGER PRIMARY KEY
reference_type TEXT UNIQUE        -- 'pax_reference', etc.
display_name TEXT                 -- Human-readable name
description TEXT                  -- What this represents
example TEXT                      -- Example usage
category TEXT                     -- passenger, segment, etc.
is_active BOOLEAN
```

## Usage

### Backend (Python)

```python
from app.services.workspace_db import get_workspace_session

# Get session for SQ workspace
db = get_workspace_session(workspace="SQ")

# Query runs
runs = db.query(Run).filter(Run.kind == "discovery").all()

# Query node facts
facts = db.query(NodeFact).filter(NodeFact.run_id == run_id).all()

# Clean up
db.close()
```

### Context Manager (Recommended)

```python
from app.services.workspace_db import workspace_session

with workspace_session("SQ") as db:
    # Automatically commits on success, rolls back on error
    run = Run(id=run_id, kind="discovery", ...)
    db.add(run)
    # Automatically committed when block exits
```

### Frontend (Streamlit)

```python
from utils.workspace_schema import get_workspace_db

# Get workspace database
db = get_workspace_db(workspace="SQ")

# Execute query
runs = db.execute_query("SELECT * FROM runs WHERE status = 'completed'")

# Insert data
run_id = db.insert("runs", {
    "id": "abc123",
    "kind": "discovery",
    "status": "started"
})
```

## Migration from MySQL

If you have existing MySQL data and want to migrate:

1. **Export MySQL data** to SQLite:
```bash
# Install mysql2sqlite
pip install mysql-to-sqlite3

# Export
mysql2sqlite3 -f assisted_discovery.db \
  -d assisted_discovery \
  -u assisted_discovery \
  -p assisted_discovery_2025_secure
```

2. **Move to workspace directory**:
```bash
mv assisted_discovery.db frontend/streamlit_ui/data/workspaces/default.db
```

## Workspace Management

### Add New Workspace

**Via UI:**
1. In Streamlit sidebar, expand "⚙️ Manage Workspaces"
2. Enter workspace name (e.g., "BA", "EK")
3. Click "➕ Add"
4. New empty database is created automatically

**Via Code:**
```python
from app.services.workspace_db import get_workspace_session

# Access will auto-create database
db = get_workspace_session("BA")
```

### Delete Workspace

**Via UI:**
1. Select workspace in dropdown
2. Expand "⚙️ Manage Workspaces"
3. Click "🗑️ Delete"
4. Database file is removed

**Manual:**
```bash
rm frontend/streamlit_ui/data/workspaces/BA.db
```

### List All Workspaces

```python
from app.services.workspace_db import list_workspaces

workspaces = list_workspaces()
# Returns: ['AFKL', 'default', 'LATAM', 'LH', 'SQ', 'VY']
```

## Benefits

### 1. No Installation Required
Users don't need to:
- Install MySQL
- Configure database connections
- Manage database users/passwords
- Run migration scripts

### 2. Portable
- Send `.db` file to colleague
- They can analyze immediately
- No setup needed

### 3. Isolated
- Each airline/project has own database
- No cross-contamination
- Easy cleanup (delete file)

### 4. Fast
- SQLite is fast for single-user access
- No network overhead
- Indexes on all foreign keys

### 5. Easy Backup
```bash
# Backup
cp SQ.db SQ_backup_2025-01-08.db

# Restore
cp SQ_backup_2025-01-08.db SQ.db
```

## Development Mode

For development, you can still use MySQL:

```python
# app/core/config.py
DATABASE_MODE = "mysql"  # or "workspace"

if DATABASE_MODE == "mysql":
    from app.services.database import SessionLocal
else:
    from app.services.workspace_db import get_workspace_session
```

## Performance Considerations

### SQLite is Great For:
✅ Single-user access (Streamlit)
✅ Read-heavy workloads
✅ < 1GB databases
✅ < 1000 requests/second
✅ Portable deployments

### MySQL is Better For:
❌ Multi-user concurrent writes
❌ Very large datasets (> 10GB)
❌ High-throughput production systems
❌ Distributed deployments

**For AssistedDiscovery:** SQLite is perfect! ✅

## File Size Estimates

Typical workspace database sizes:
- Small project (10 runs, 100 facts): ~100 KB
- Medium project (100 runs, 1000 facts): ~1-5 MB
- Large project (1000 runs, 10000 facts): ~10-50 MB

## Troubleshooting

### "Database is locked"
SQLite allows only one writer at a time.

**Solution:** Close other connections to the database.

### "No such table: xyz"
Schema not initialized.

**Solution:** Database auto-initializes on first access. Try reloading.

### "Unable to open database file"
Permissions issue.

**Solution:**
```bash
chmod 644 frontend/streamlit_ui/data/workspaces/*.db
```

## Future Enhancements

🚧 **Planned:**
- Export workspace to Excel/CSV
- Import workspace from backup
- Merge workspaces
- Workspace templates
- Cloud sync (Google Drive, Dropbox)
