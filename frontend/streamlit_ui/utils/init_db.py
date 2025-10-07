"""
Initialize SQLite database for AssistedDiscovery pattern storage.

Creates the necessary tables for:
- Workspace management (APIs, versions)
- Pattern storage (patterns, sections, mappings)
- Shared patterns (default library)
"""

import sqlite3
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database(db_path: str = None):
    """
    Initialize the SQLite database with all required tables.

    Args:
        db_path: Path to database file. If None, uses default location.
    """
    if db_path is None:
        # Default location: frontend/streamlit_ui/data/api_analysis.db
        db_path = Path(__file__).parent.parent / "data" / "api_analysis.db"
    else:
        db_path = Path(db_path)

    # Create data directory if it doesn't exist
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Initializing database at: {db_path}")

    # Connect to database (creates file if it doesn't exist)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Create API table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api (
                api_id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_name TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        logger.info("✓ Created api table")

        # Create API Version table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS apiversion (
                version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_id INTEGER,
                version_number TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (api_id) REFERENCES api (api_id),
                UNIQUE(api_id, version_number)
            )
        """)
        logger.info("✓ Created apiversion table")

        # Create API Section table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_section (
                section_id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_id INTEGER NOT NULL,
                section_name TEXT NOT NULL,
                section_display_name TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (api_id) REFERENCES api(api_id),
                UNIQUE(api_id, section_name)
            )
        """)
        logger.info("✓ Created api_section table")

        # Create Pattern Details table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pattern_details (
                pattern_id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_name TEXT NOT NULL,
                pattern_description TEXT,
                pattern_prompt TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(pattern_name, pattern_description)
            )
        """)
        logger.info("✓ Created pattern_details table")

        # Create Section-Pattern Mapping table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS section_pattern_mapping (
                mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_id INTEGER NOT NULL,
                section_id INTEGER NOT NULL,
                api_id INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pattern_id) REFERENCES pattern_details(pattern_id),
                FOREIGN KEY (section_id) REFERENCES api_section(section_id),
                FOREIGN KEY (api_id) REFERENCES api(api_id),
                UNIQUE(pattern_id, section_id, api_id)
            )
        """)
        logger.info("✓ Created section_pattern_mapping table")

        # Create schema version table for tracking migrations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
        """)
        logger.info("✓ Created schema_version table")

        # Insert initial schema version if not exists
        cursor.execute("""
            INSERT OR IGNORE INTO schema_version (version, description)
            VALUES (0, 'Initial schema for pattern storage')
        """)

        # Commit all changes
        conn.commit()
        logger.info(f"✓ Database initialized successfully at: {db_path}")

        # Verify tables were created
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"✓ Tables created: {', '.join(tables)}")

        return True

    except Exception as e:
        logger.error(f"✗ Failed to initialize database: {e}")
        conn.rollback()
        return False

    finally:
        cursor.close()
        conn.close()


def add_default_apis(db_path: str = None):
    """
    Add default APIs to the database for common airlines.

    Args:
        db_path: Path to database file. If None, uses default location.
    """
    if db_path is None:
        db_path = Path(__file__).parent.parent / "data" / "api_analysis.db"
    else:
        db_path = Path(db_path)

    if not db_path.exists():
        logger.error(f"Database does not exist at: {db_path}. Run init_database() first.")
        return False

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Add common airline APIs
        default_apis = [
            ('LATAM', ),
            ('LH', ),
            ('LHG', ),
            ('AFKL', ),
            ('SQ', ),
            ('VY', ),
        ]

        for api in default_apis:
            try:
                cursor.execute("INSERT OR IGNORE INTO api (api_name) VALUES (?)", api)
                logger.info(f"✓ Added API: {api[0]}")
            except sqlite3.IntegrityError:
                logger.info(f"  API {api[0]} already exists")

        conn.commit()
        logger.info("✓ Default APIs added successfully")
        return True

    except Exception as e:
        logger.error(f"✗ Failed to add default APIs: {e}")
        conn.rollback()
        return False

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    # Initialize database
    success = init_database()

    if success:
        # Add default APIs
        add_default_apis()
        print("\n✓ Database setup complete!")
        print("  Location: frontend/streamlit_ui/data/api_analysis.db")
    else:
        print("\n✗ Database setup failed. Check logs for details.")
