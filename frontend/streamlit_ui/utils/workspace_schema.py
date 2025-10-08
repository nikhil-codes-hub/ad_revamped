"""
Complete SQLite Schema for Workspace Databases

Each workspace gets a full SQLite database with all tables needed for
Discovery, Identify, Pattern Management, and Node Management.

Replaces MySQL dependency - fully portable and self-contained.
"""

import sqlite3
from pathlib import Path
from typing import Optional


class WorkspaceDatabase:
    """Manages SQLite database for a workspace."""

    def __init__(self, workspace_name: str = "default"):
        self.workspace_name = workspace_name
        self.db_dir = Path(__file__).parent.parent / "data" / "workspaces"
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.db_dir / f"{workspace_name}.db"
        self._init_schema()

    def connect(self):
        """Get database connection."""
        return sqlite3.connect(str(self.db_path), timeout=30)

    def _init_schema(self):
        """Initialize complete schema if not exists."""
        conn = self.connect()
        cursor = conn.cursor()

        try:
            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys = ON")

            # Table 1: NDC Target Paths
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ndc_target_paths (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spec_version TEXT NOT NULL,
                    message_root TEXT NOT NULL,
                    path_local TEXT NOT NULL,
                    extractor_key TEXT NOT NULL,
                    is_required BOOLEAN DEFAULT 0,
                    importance TEXT DEFAULT 'medium',
                    constraints_json TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Table 2: NDC Path Aliases
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ndc_path_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_spec_version TEXT NOT NULL,
                    from_message_root TEXT NOT NULL,
                    from_path_local TEXT NOT NULL,
                    to_spec_version TEXT NOT NULL,
                    to_message_root TEXT NOT NULL,
                    to_path_local TEXT NOT NULL,
                    is_bidirectional BOOLEAN DEFAULT 0,
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Table 3: Runs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    status TEXT DEFAULT 'started',
                    spec_version TEXT,
                    message_root TEXT,
                    airline_code TEXT,
                    airline_name TEXT,
                    filename TEXT,
                    file_size_bytes INTEGER,
                    file_hash TEXT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    finished_at TIMESTAMP,
                    metadata_json TEXT,
                    error_details TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_kind ON runs(kind)")

            # Table 4: Node Facts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS node_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    spec_version TEXT NOT NULL,
                    message_root TEXT NOT NULL,
                    section_path TEXT NOT NULL,
                    node_type TEXT NOT NULL,
                    node_ordinal INTEGER NOT NULL,
                    fact_json TEXT NOT NULL,
                    pii_masked BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodefacts_run ON node_facts(run_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodefacts_type ON node_facts(node_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodefacts_section ON node_facts(section_path)")

            # Table 5: Association Facts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS association_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    rel_type TEXT NOT NULL,
                    from_node_fact_id INTEGER NOT NULL,
                    to_node_fact_id INTEGER NOT NULL,
                    from_node_type TEXT NOT NULL,
                    to_node_type TEXT NOT NULL,
                    ref_key TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
                    FOREIGN KEY (from_node_fact_id) REFERENCES node_facts(id) ON DELETE CASCADE,
                    FOREIGN KEY (to_node_fact_id) REFERENCES node_facts(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_assoc_run ON association_facts(run_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_assoc_from ON association_facts(from_node_fact_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_assoc_to ON association_facts(to_node_fact_id)")

            # Table 6: Node Relationships (LLM-discovered)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS node_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    source_node_fact_id INTEGER NOT NULL,
                    source_node_type TEXT NOT NULL,
                    source_section_path TEXT NOT NULL,
                    target_node_fact_id INTEGER,
                    target_node_type TEXT NOT NULL,
                    target_section_path TEXT NOT NULL,
                    reference_type TEXT NOT NULL,
                    reference_field TEXT,
                    reference_value TEXT,
                    is_valid BOOLEAN DEFAULT 1,
                    was_expected BOOLEAN DEFAULT 0,
                    confidence REAL DEFAULT 1.0,
                    discovered_by TEXT DEFAULT 'llm',
                    model_used TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
                    FOREIGN KEY (source_node_fact_id) REFERENCES node_facts(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_node_fact_id) REFERENCES node_facts(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_noderel_run ON node_relationships(run_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_noderel_source ON node_relationships(source_node_fact_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_noderel_target ON node_relationships(target_node_fact_id)")

            # Table 7: Patterns
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spec_version TEXT NOT NULL,
                    message_root TEXT NOT NULL,
                    airline_code TEXT,
                    section_path TEXT NOT NULL,
                    selector_xpath TEXT NOT NULL,
                    decision_rule TEXT NOT NULL,
                    description TEXT,
                    signature_hash TEXT UNIQUE NOT NULL,
                    times_seen INTEGER DEFAULT 1,
                    created_by_model TEXT,
                    examples TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_version ON patterns(spec_version, message_root)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_airline ON patterns(airline_code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_hash ON patterns(signature_hash)")

            # Table 8: Pattern Matches
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pattern_matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    node_fact_id INTEGER NOT NULL,
                    pattern_id INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    verdict TEXT NOT NULL,
                    match_metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
                    FOREIGN KEY (node_fact_id) REFERENCES node_facts(id) ON DELETE CASCADE,
                    FOREIGN KEY (pattern_id) REFERENCES patterns(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_run ON pattern_matches(run_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_node ON pattern_matches(node_fact_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_pattern ON pattern_matches(pattern_id)")

            # Table 9: Node Configurations (BA-managed)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS node_configurations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spec_version TEXT NOT NULL,
                    message_root TEXT NOT NULL,
                    airline_code TEXT,
                    node_type TEXT NOT NULL,
                    section_path TEXT NOT NULL,
                    enabled BOOLEAN DEFAULT 1,
                    expected_references TEXT,
                    ba_remarks TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodeconfig_version ON node_configurations(spec_version, message_root)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodeconfig_airline ON node_configurations(airline_code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodeconfig_type ON node_configurations(node_type)")

            # Table 10: Reference Types Glossary
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reference_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference_type TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    example TEXT,
                    category TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT
                )
            """)

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def execute_query(self, query: str, params: Optional[tuple] = None):
        """Execute a query and return results."""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            results = cursor.fetchall()
            conn.commit()
            return results
        finally:
            cursor.close()
            conn.close()

    def insert(self, table: str, data: dict) -> int:
        """Insert data into a table and return the ID."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute(query, tuple(data.values()))
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()


def get_workspace_db(workspace_name: str = "default") -> WorkspaceDatabase:
    """Get or create a workspace database."""
    return WorkspaceDatabase(workspace_name)
