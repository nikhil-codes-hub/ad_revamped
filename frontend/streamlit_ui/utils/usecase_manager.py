"""
Use Case Manager for GENIe Application
Manages user-specific database schemas and use case selection
"""

import os
import sqlite3
import streamlit as st
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import tempfile

from core.database.sql_db_utils import SQLDatabaseUtils
from core.database.schema_migration import SchemaMigration
from core.common.logging_manager import get_logger, log_user_action, log_error, get_logging_manager, reset_logging_manager

logger = get_logger(__name__)

@dataclass
class UseCase:
    """Data class for use case information"""
    id: str
    name: str
    description: str
    database_name: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    custom: bool = False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UseCase':
        """Create UseCase from dictionary"""
        return cls(**data)

class UseCaseManager:
    """Manages user-specific database schemas and use case selection"""
    
    def __init__(self, base_db_dir: Optional[Path] = None):
        """
        Initialize UseCaseManager
        
        Args:
            base_db_dir: Base directory for database files. If None, uses default.
        """
        if base_db_dir is None:
            self.base_db_dir = Path(__file__).parent.parent / "database" / "data"
        else:
            self.base_db_dir = Path(base_db_dir)
        
        # Use case storage in the GenieApp directory (sibling to logs)
        # Reset logging manager to ensure we get the updated directory structure
        reset_logging_manager()
        self.log_manager = get_logging_manager()
        log_dir = Path(self.log_manager.get_log_directory())
        # Get parent directory (GenieApp) and add usecases subdirectory
        genie_app_dir = log_dir.parent
        self.usecase_storage_dir = genie_app_dir / "usecases"
        self.usecase_storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.base_db_dir.mkdir(parents=True, exist_ok=True)
        
        # Session state keys
        self.SELECTED_USE_CASE_KEY = "selected_use_case"
        self.DB_UTILS_KEY = "current_db_utils"
        
        # Load use cases from filesystem
        self.use_cases = self._load_use_cases_from_filesystem()
        
        logger.info(f"UseCaseManager initialized:")
        logger.info(f"  Database directory: {self.base_db_dir}")
        logger.info(f"  Use case storage: {self.usecase_storage_dir}")
        logger.info(f"  Loaded {len(self.use_cases)} use cases")
    
    def _load_use_cases_from_filesystem(self) -> List[UseCase]:
        """Load use cases from filesystem, creating default ones if none exist"""
        use_cases = []
        
        # Check if use cases exist on filesystem
        usecase_files = list(self.usecase_storage_dir.glob("*.json"))
        
        if usecase_files:
            # Load existing use cases from files
            logger.info(f"Loading {len(usecase_files)} use cases from filesystem")
            
            for usecase_file in usecase_files:
                try:
                    with open(usecase_file, 'r') as f:
                        data = json.load(f)
                        use_case = UseCase.from_dict(data)
                        use_cases.append(use_case)
                        logger.debug(f"Loaded use case: {use_case.name}")
                except Exception as e:
                    log_error(f"Failed to load use case from {usecase_file}: {str(e)}")
        else:
            # Create default use cases and save them to filesystem
            logger.info("No use cases found on filesystem, creating defaults")
            use_cases = self._create_default_use_cases()
            
            # Save defaults to filesystem
            for use_case in use_cases:
                self._save_use_case_to_filesystem(use_case)
        
        return sorted(use_cases, key=lambda x: (x.custom, x.name))
    
    def _create_default_use_cases(self) -> List[UseCase]:
        """Create default use cases"""
        now = datetime.now().isoformat()
        
        return [
            UseCase(
                id="demo_analysis",
                name="Demo Analysis",
                description="Demo workspace for XML pattern analysis",
                database_name="demo_analysis.db",
                created_at=now,
                updated_at=now,
                custom=False
            )
        ]
    
    def _save_use_case_to_filesystem(self, use_case: UseCase) -> bool:
        """Save a use case to filesystem"""
        try:
            file_path = self.usecase_storage_dir / f"{use_case.id}.json"
            
            with open(file_path, 'w') as f:
                json.dump(use_case.to_dict(), f, indent=2)
            
            logger.info(f"Saved use case to: {file_path}")
            return True
            
        except Exception as e:
            log_error(f"Failed to save use case {use_case.id}: {str(e)}")
            return False
    
    def _delete_use_case_from_filesystem(self, use_case_id: str) -> bool:
        """Delete a use case from filesystem"""
        try:
            file_path = self.usecase_storage_dir / f"{use_case_id}.json"
            
            if file_path.exists():
                os.remove(file_path)
                logger.info(f"Deleted use case file: {file_path}")
                return True
            else:
                logger.warning(f"Use case file not found: {file_path}")
                return False
                
        except Exception as e:
            log_error(f"Failed to delete use case {use_case_id}: {str(e)}")
            return False
    
    def add_new_use_case(self, name: str, description: str) -> Optional[UseCase]:
        """
        Add a new custom use case
        
        Args:
            name: Display name for the use case
            description: Description of the use case
            
        Returns:
            UseCase object if successful, None otherwise
        """
        try:
            # Generate ID from name
            use_case_id = name.lower().replace(' ', '_').replace('-', '_')
            use_case_id = ''.join(c for c in use_case_id if c.isalnum() or c == '_')
            
            # Ensure unique ID
            existing_ids = [uc.id for uc in self.use_cases]
            counter = 1
            original_id = use_case_id
            while use_case_id in existing_ids:
                use_case_id = f"{original_id}_{counter}"
                counter += 1
            
            # Generate database name
            database_name = f"{use_case_id}.db"
            
            # Create use case
            now = datetime.now().isoformat()
            use_case = UseCase(
                id=use_case_id,
                name=name,
                description=description,
                database_name=database_name,
                created_at=now,
                updated_at=now,
                custom=True
            )
            
            # Save to filesystem
            if self._save_use_case_to_filesystem(use_case):
                # Add to memory
                self.use_cases.append(use_case)
                self.use_cases.sort(key=lambda x: (x.custom, x.name))
                
                log_user_action(f"Created new use case: {name}")
                logger.info(f"Successfully created use case: {use_case.name} ({use_case.id})")
                
                return use_case
            else:
                return None
                
        except Exception as e:
            log_error(f"Failed to create use case '{name}': {str(e)}")
            return None
    
    def delete_use_case(self, use_case_id: str) -> bool:
        """
        Delete a use case (only custom ones can be deleted)
        
        Args:
            use_case_id: ID of use case to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        use_case = self.get_use_case_by_id(use_case_id)
        if not use_case:
            log_error(f"Use case not found: {use_case_id}")
            return False
        
        if not use_case.custom:
            log_error(f"Cannot delete built-in use case: {use_case_id}")
            return False
        
        try:
            # Delete from filesystem
            if self._delete_use_case_from_filesystem(use_case_id):
                # Remove from memory
                self.use_cases = [uc for uc in self.use_cases if uc.id != use_case_id]
                
                # Delete associated database
                db_path = self.base_db_dir / use_case.database_name
                if db_path.exists():
                    os.remove(db_path)
                    logger.info(f"Deleted database: {db_path}")
                
                # Clear session state if this was the current use case
                current = self.get_current_use_case()
                if current and current.id == use_case_id:
                    if self.SELECTED_USE_CASE_KEY in st.session_state:
                        del st.session_state[self.SELECTED_USE_CASE_KEY]
                    if self.DB_UTILS_KEY in st.session_state:
                        del st.session_state[self.DB_UTILS_KEY]
                
                log_user_action(f"Deleted use case: {use_case.name}")
                logger.info(f"Successfully deleted use case: {use_case.name} ({use_case_id})")
                return True
            else:
                return False
                
        except Exception as e:
            log_error(f"Failed to delete use case {use_case_id}: {str(e)}")
            return False
    
    def get_available_use_cases(self) -> List[UseCase]:
        """Get list of available use cases"""
        return self.use_cases
    
    def get_use_case_by_id(self, use_case_id: str) -> Optional[UseCase]:
        """Get use case by ID"""
        for use_case in self.use_cases:
            if use_case.id == use_case_id:
                return use_case
        return None
    
    def get_current_use_case(self) -> Optional[UseCase]:
        """Get currently selected use case from session state"""
        if self.SELECTED_USE_CASE_KEY in st.session_state:
            use_case_id = st.session_state[self.SELECTED_USE_CASE_KEY]
            return self.get_use_case_by_id(use_case_id)
        return None
    
    def set_current_use_case(self, use_case_id: str) -> bool:
        """
        Set the current use case and initialize its database
        
        Args:
            use_case_id: ID of the use case to set
            
        Returns:
            bool: True if successful, False otherwise
        """
        use_case = self.get_use_case_by_id(use_case_id)
        if not use_case:
            log_error(f"Use case not found: {use_case_id}")
            return False
        
        try:
            # Initialize database for this use case
            db_utils = self._initialize_use_case_database(use_case)
            if db_utils is None:
                return False
            
            # Update session state
            st.session_state[self.SELECTED_USE_CASE_KEY] = use_case_id
            st.session_state[self.DB_UTILS_KEY] = db_utils
            
            log_user_action(f"Use case switched to: {use_case.name}")
            logger.info(f"Use case set to: {use_case.name} (Database: {use_case.database_name})")
            
            return True
            
        except Exception as e:
            log_error(f"Failed to set use case {use_case_id}: {str(e)}")
            return False
    
    def get_current_db_utils(self) -> Optional[SQLDatabaseUtils]:
        """Get database utils for current use case"""
        if self.DB_UTILS_KEY in st.session_state:
            return st.session_state[self.DB_UTILS_KEY]
        return None
    
    def _initialize_use_case_database(self, use_case: UseCase) -> Optional[SQLDatabaseUtils]:
        """
        Initialize database for a specific use case
        
        Args:
            use_case: UseCase object to initialize
            
        Returns:
            SQLDatabaseUtils instance or None if failed
        """
        try:
            db_path = self.base_db_dir / use_case.database_name
            
            # Check if database exists
            if db_path.exists():
                logger.info(f"Loading existing database: {db_path}")
                # Database exists, create utils and verify schema
                db_utils = SQLDatabaseUtils(
                    db_name=use_case.database_name,
                    base_dir=str(self.base_db_dir)
                )
                
                # Verify schema is valid
                if self._verify_database_schema(db_utils):
                    return db_utils
                else:
                    logger.warning(f"Database schema invalid for {use_case.database_name}, recreating...")
                    # Remove invalid database and recreate
                    os.remove(db_path)
            
            # Create new database
            logger.info(f"Creating new database: {db_path}")
            return self._create_new_database(use_case)
            
        except Exception as e:
            log_error(f"Failed to initialize database for {use_case.name}: {str(e)}")
            return None
    
    def _create_new_database(self, use_case: UseCase) -> Optional[SQLDatabaseUtils]:
        """
        Create a new database for the use case
        
        Args:
            use_case: UseCase to create database for
            
        Returns:
            SQLDatabaseUtils instance or None if failed
        """
        try:
            new_db_path = self.base_db_dir / use_case.database_name
            
            # Always create database from schema definition (not template copy)
            # This ensures we get all required tables including apiversion
            self._create_database_from_schema(new_db_path)
            
            # Initialize database utils
            db_utils = SQLDatabaseUtils(
                db_name=use_case.database_name,
                base_dir=str(self.base_db_dir)
            )
            
            # Verify the schema was created correctly
            if not self._verify_database_schema(db_utils):
                logger.error(f"Database schema verification failed for {use_case.name}")
                return None
            
            # Run any necessary migrations
            self._setup_database_for_use_case(db_utils, use_case)
            
            logger.info(f"Successfully created database: {new_db_path}")
            return db_utils
            
        except Exception as e:
            log_error(f"Failed to create database for {use_case.name}: {str(e)}")
            return None
    
    def _copy_database_schema(self, source_path: Path, target_path: Path):
        """Copy database schema from source to target"""
        # Read schema from source database
        source_conn = sqlite3.connect(str(source_path))
        
        # Get schema SQL, excluding system tables like sqlite_sequence
        cursor = source_conn.cursor()
        cursor.execute("""
            SELECT sql FROM sqlite_master 
            WHERE type='table' AND sql IS NOT NULL 
            AND name NOT LIKE 'sqlite_%'
        """)
        create_statements = cursor.fetchall()
        source_conn.close()
        
        # Create target database with schema
        target_conn = sqlite3.connect(str(target_path))
        target_cursor = target_conn.cursor()
        
        # Execute create statements
        for (sql,) in create_statements:
            if sql:  # Additional safety check
                target_cursor.execute(sql)
        
        target_conn.commit()
        target_conn.close()
    
    def _create_database_from_schema(self, db_path: Path):
        """Create database from SQL schema file"""
        schema_file = self.base_db_dir / "API table.sql"
        
        if schema_file.exists():
            with open(schema_file, 'r') as f:
                schema_sql = f.read()
            
            conn = sqlite3.connect(str(db_path))
            conn.executescript(schema_sql)
            conn.commit()
            conn.close()
        else:
            # Create minimal schema if no schema file exists
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Create basic tables
            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS api (
                    api_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_name TEXT NOT NULL UNIQUE
                );
                
                CREATE TABLE IF NOT EXISTS apiversion (
                    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_id INTEGER,
                    version_number TEXT NOT NULL,
                    FOREIGN KEY (api_id) REFERENCES api (api_id)
                );
                
                CREATE TABLE IF NOT EXISTS api_section (
                    section_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_id INTEGER,
                    section_name TEXT NOT NULL,
                    section_display_name TEXT,
                    FOREIGN KEY (api_id) REFERENCES api (api_id)
                );
                
                CREATE TABLE IF NOT EXISTS pattern_details (
                    pattern_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_name TEXT NOT NULL UNIQUE,
                    pattern_description TEXT,
                    pattern_prompt TEXT
                );
                
                CREATE TABLE IF NOT EXISTS section_pattern_mapping (
                    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_id INTEGER,
                    section_id INTEGER,
                    api_id INTEGER,
                    FOREIGN KEY (pattern_id) REFERENCES pattern_details (pattern_id),
                    FOREIGN KEY (section_id) REFERENCES api_section (section_id),
                    FOREIGN KEY (api_id) REFERENCES api (api_id)
                );
            """)
            
            conn.commit()
            conn.close()
    
    def _setup_database_for_use_case(self, db_utils: SQLDatabaseUtils, use_case: UseCase):
        """Setup database with use case specific data"""
        try:
            # Run schema migration to latest version
            try:
                migration = SchemaMigration(db_path=str(self.base_db_dir / use_case.database_name))
                migration.migrate_to_specification_support()
                logger.info(f"Schema migration completed for {use_case.name}")
            except Exception as migration_error:
                # Log but don't fail - database is still functional
                logger.warning(f"Schema migration failed for {use_case.name}: {str(migration_error)}")
            
            # Add use case specific initial data if needed
            try:
                self._add_initial_data_for_use_case(db_utils, use_case)
            except Exception as data_error:
                # Log but don't fail - this is just initial sample data
                logger.warning(f"Failed to add initial data for {use_case.name}: {str(data_error)}")
            
        except Exception as e:
            log_error(f"Failed to setup database for {use_case.name}: {str(e)}")
    
    def _add_initial_data_for_use_case(self, db_utils: SQLDatabaseUtils, use_case: UseCase):
        """Add initial data specific to the use case"""
        try:
            # No initial data is added to new workspaces
            # Users can add APIs, sections, and patterns as needed per workspace
            logger.info(f"Database created for {use_case.name} without initial data")
            
        except Exception as e:
            log_error(f"Failed to setup initial data for {use_case.name}: {str(e)}")
    
    def _verify_database_schema(self, db_utils: SQLDatabaseUtils) -> bool:
        """Verify that database has required tables and can execute basic queries"""
        try:
            required_tables = ['api', 'apiversion', 'api_section', 'pattern_details', 'section_pattern_mapping']
            
            # Check if all required tables exist
            for table in required_tables:
                result = db_utils.execute_query(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                )
                if not result:
                    logger.warning(f"Required table missing: {table}")
                    return False
            
            # Test that we can run a basic query that the app uses
            try:
                # Test the get_all_patterns query to make sure schema is compatible
                test_query = """
                    SELECT a.api_name, COALESCE(av.version_number, 'N/A') as api_version, 
                           aps.section_name, pd.pattern_description, pd.pattern_prompt
                    FROM api a
                    LEFT JOIN apiversion av ON a.api_id = av.api_id
                    LEFT JOIN api_section aps ON a.api_id = aps.api_id
                    LEFT JOIN section_pattern_mapping spm ON aps.section_id = spm.section_id AND aps.api_id = spm.api_id
                    LEFT JOIN pattern_details pd ON spm.pattern_id = pd.pattern_id
                    LIMIT 1
                """
                db_utils.execute_query(test_query)
                logger.info("Database schema verification passed")
                return True
                
            except Exception as query_error:
                logger.warning(f"Database schema incompatible - query test failed: {str(query_error)}")
                return False
            
        except Exception as e:
            log_error(f"Database schema verification failed: {str(e)}")
            return False
    
    def render_use_case_selector(self, key: str = "use_case_selector") -> Optional[str]:
        """
        Render Streamlit dropdown for use case selection
        
        Args:
            key: Streamlit widget key
            
        Returns:
            Selected use case ID or None
        """
        use_cases = self.get_available_use_cases()
        current_use_case = self.get_current_use_case()
        
        # Create options for selectbox with empty option
        options = [""] + [f"{uc.name} - {uc.description}" for uc in use_cases]
        use_case_ids = [None] + [uc.id for uc in use_cases]
        
        # Find current selection index
        current_index = 0  # Default to empty selection
        if current_use_case:
            try:
                # Add 1 to account for the empty option at index 0
                current_index = use_case_ids.index(current_use_case.id)
            except ValueError:
                current_index = 0
        
        # Render selectbox
        selected_option = st.selectbox(
            "Select Discovery Workspace",
            options,
            index=current_index,
            key=key,
            help="Choose the specific discovery workspace for your analysis. Each workspace maintains its own database and patterns.",
            placeholder="Choose a workspace..."
        )
        
        
        # Workspace management controls
        st.markdown("---")
        
        # Add New Discovery Workspace section with highlighting
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(34, 197, 94, 0.1), rgba(16, 185, 129, 0.1));
            border-radius: 8px;
            padding: 4px;
            margin: 8px 0;
            border-left: 4px solid #22c55e;
        ">
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("➕ Add New Discovery Workspace", expanded=False):
            new_name = st.text_input("Workspace Name", placeholder="e.g., Emirates Analysis", key=f"new_name_{key}")
            new_desc = st.text_area("Description", placeholder="Brief description of this discovery workspace", key=f"new_desc_{key}")
            
            col_add, col_cancel = st.columns([1, 1])
            with col_add:
                if st.button("✨ Create Workspace", key=f"create_usecase_{key}", type="primary", use_container_width=True):
                    if new_name and new_desc:
                        with st.spinner("Creating discovery workspace..."):
                            new_use_case = self.add_new_use_case(new_name, new_desc)
                            if new_use_case:
                                st.success(f"✅ Created: {new_name}")
                                st.rerun()
                            else:
                                st.error("❌ Failed to create discovery workspace")
                    else:
                        st.error("Please fill in both name and description")
        
        # Delete Discovery Workspace section (only for custom workspaces)
        custom_workspaces = [uc for uc in use_cases if uc.custom]
        if custom_workspaces:
            # Delete workspace highlighting
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, rgba(239, 68, 68, 0.1), rgba(220, 38, 38, 0.1));
                border-radius: 8px;
                padding: 4px;
                margin: 8px 0;
                border-left: 4px solid #ef4444;
            ">
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("🗑️ Delete Custom Discovery Workspace", expanded=False):
                st.warning("⚠️ This will permanently delete the workspace and all its data!")
                
                # Create options for deletion (only custom workspaces)
                delete_options = [f"{uc.name} - {uc.description}" for uc in custom_workspaces]
                delete_ids = [uc.id for uc in custom_workspaces]
                
                selected_delete = st.selectbox(
                    "Select workspace to delete",
                    [""] + delete_options,
                    key=f"delete_select_{key}",
                    help="Only custom workspaces can be deleted. Built-in workspaces are protected."
                )
                
                if selected_delete and selected_delete != "":
                    delete_index = delete_options.index(selected_delete)
                    workspace_to_delete = custom_workspaces[delete_index]
                    
                    st.error(f"You are about to delete: **{workspace_to_delete.name}**")
                    confirm_text = st.text_input(
                        f"Type 'DELETE {workspace_to_delete.name}' to confirm:",
                        key=f"delete_confirm_{key}",
                        placeholder=f"DELETE {workspace_to_delete.name}"
                    )
                    
                    col_del, col_cancel = st.columns([1, 1])
                    with col_del:
                        if st.button("🗑️ Delete Forever", key=f"delete_usecase_{key}", type="primary", use_container_width=True):
                            if confirm_text == f"DELETE {workspace_to_delete.name}":
                                with st.spinner("Deleting workspace..."):
                                    if self.delete_use_case(workspace_to_delete.id):
                                        st.success(f"✅ Deleted: {workspace_to_delete.name}")
                                        st.rerun()
                                    else:
                                        st.error("❌ Failed to delete workspace")
                            else:
                                st.error("❌ Confirmation text doesn't match. Please type exactly as shown.")
        
        # Import/Export functionality has been moved to the management tabs in Discovery page
        # No longer displayed in sidebar to reduce clutter
        
        # Get selected use case ID
        if selected_option and selected_option != "":
            selected_index = options.index(selected_option)
            selected_id = use_case_ids[selected_index]
            
            # Update current use case if changed
            if not current_use_case or current_use_case.id != selected_id:
                if self.set_current_use_case(selected_id):
                    # Adjust index for use_cases array (subtract 1 for empty option)
                    use_case_index = selected_index - 1
                    st.success(f"✅ Switched to: {use_cases[use_case_index].name}")
                    st.rerun()
                else:
                    # Adjust index for use_cases array (subtract 1 for empty option)
                    use_case_index = selected_index - 1
                    st.error(f"❌ Failed to switch to: {use_cases[use_case_index].name}")
                    return None
            
            return selected_id
        
        return None
    
    def get_database_info(self) -> Dict[str, any]:
        """Get information about current database"""
        current_use_case = self.get_current_use_case()
        db_utils = self.get_current_db_utils()
        
        info = {
            "use_case": current_use_case.name if current_use_case else "None",
            "database_file": current_use_case.database_name if current_use_case else "None",
            "database_path": str(self.base_db_dir / current_use_case.database_name) if current_use_case else "None",
            "database_exists": False,
            "table_count": 0,
            "record_counts": {}
        }
        
        if current_use_case and db_utils:
            db_path = self.base_db_dir / current_use_case.database_name
            info["database_exists"] = db_path.exists()
            
            if info["database_exists"]:
                try:
                    # Get table count
                    tables = db_utils.execute_query(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                    info["table_count"] = len(tables)
                    
                    # Get record counts for main tables
                    main_tables = ['api', 'pattern_details', 'api_section', 'section_pattern_mapping']
                    for table in main_tables:
                        try:
                            count = db_utils.execute_query(f"SELECT COUNT(*) FROM {table}")[0][0]
                            info["record_counts"][table] = count
                        except:
                            info["record_counts"][table] = 0
                            
                except Exception as e:
                    log_error(f"Failed to get database info: {str(e)}")
        
        return info
    
    def reset_use_case_database(self, use_case_id: str) -> bool:
        """
        Reset (delete and recreate) database for a specific use case
        
        Args:
            use_case_id: ID of the use case to reset
            
        Returns:
            bool: True if successful, False otherwise
        """
        use_case = self.get_use_case_by_id(use_case_id)
        if not use_case:
            log_error(f"Use case not found: {use_case_id}")
            return False
        
        try:
            db_path = self.base_db_dir / use_case.database_name
            
            # Remove existing database if it exists
            if db_path.exists():
                os.remove(db_path)
                logger.info(f"Removed corrupted database: {db_path}")
            
            # Create new database
            db_utils = self._create_new_database(use_case)
            if db_utils:
                logger.info(f"Successfully reset database for {use_case.name}")
                
                # Update session state if this is the current use case
                current = self.get_current_use_case()
                if current and current.id == use_case_id:
                    st.session_state[self.DB_UTILS_KEY] = db_utils
                
                return True
            else:
                log_error(f"Failed to recreate database for {use_case.name}")
                return False
                
        except Exception as e:
            log_error(f"Failed to reset database for {use_case.name}: {str(e)}")
            return False
    
    def export_workspace_patterns(self, use_case_id: str = None) -> Optional[bytes]:
        """
        Export patterns from a workspace to JSON format
        
        Args:
            use_case_id: ID of the use case to export. If None, uses current use case
            
        Returns:
            JSON bytes data or None if failed
        """
        try:
            # Get use case
            if use_case_id:
                use_case = self.get_use_case_by_id(use_case_id)
            else:
                use_case = self.get_current_use_case()
            
            if not use_case:
                log_error("No use case found for export")
                return None
            
            # Get database utils
            if use_case_id and use_case_id != (self.get_current_use_case() and self.get_current_use_case().id):
                # Initialize database for non-current use case
                db_utils = self._initialize_use_case_database(use_case)
            else:
                db_utils = self.get_current_db_utils()
            
            if not db_utils:
                log_error(f"Could not access database for {use_case.name}")
                return None
            
            # Extract all patterns from the workspace
            patterns_data = self._extract_patterns_from_database(db_utils, use_case)
            
            if not patterns_data:
                log_error(f"No patterns found in workspace: {use_case.name}")
                return None
            
            # Create export structure
            export_data = {
                "export_info": {
                    "workspace_name": use_case.name,
                    "workspace_id": use_case.id,
                    "export_timestamp": datetime.now().isoformat(),
                    "export_version": "1.0",
                    "pattern_count": len(patterns_data)
                },
                "patterns": patterns_data
            }
            
            # Convert to JSON bytes
            json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
            json_bytes = json_str.encode('utf-8')
            
            log_user_action(f"Exported {len(patterns_data)} patterns from workspace: {use_case.name}")
            logger.info(f"Successfully exported {len(patterns_data)} patterns from {use_case.name}")
            
            return json_bytes
            
        except Exception as e:
            log_error(f"Failed to export patterns from workspace: {str(e)}")
            return None
    
    def import_workspace_patterns(self, json_data: bytes, use_case_id: str = None, merge_mode: str = "add") -> bool:
        """
        Import patterns into a workspace from JSON data
        
        Args:
            json_data: JSON bytes data containing patterns
            use_case_id: ID of the use case to import into. If None, uses current use case
            merge_mode: How to handle existing patterns ("add", "replace", "skip_existing")
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get use case
            if use_case_id:
                use_case = self.get_use_case_by_id(use_case_id)
            else:
                use_case = self.get_current_use_case()
            
            if not use_case:
                log_error("No use case found for import")
                return False
            
            # Get database utils
            if use_case_id and use_case_id != (self.get_current_use_case() and self.get_current_use_case().id):
                # Initialize database for non-current use case
                db_utils = self._initialize_use_case_database(use_case)
            else:
                db_utils = self.get_current_db_utils()
            
            if not db_utils:
                log_error(f"Could not access database for {use_case.name}")
                return False
            
            # Parse JSON data
            try:
                json_str = json_data.decode('utf-8')
                import_data = json.loads(json_str)
            except Exception as e:
                log_error(f"Invalid JSON format: {str(e)}")
                return False
            
            # Validate import data structure
            if not self._validate_import_data(import_data):
                log_error("Invalid import data structure")
                return False
            
            patterns_data = import_data.get("patterns", [])
            if not patterns_data:
                log_error("No patterns found in import data")
                return False
            
            # Import patterns into database
            imported_count = self._import_patterns_to_database(db_utils, patterns_data, use_case, merge_mode)
            
            if imported_count > 0:
                log_user_action(f"Imported {imported_count} patterns into workspace: {use_case.name}")
                logger.info(f"Successfully imported {imported_count} patterns into {use_case.name}")
                return True
            else:
                log_error("No patterns were imported")
                return False
            
        except Exception as e:
            log_error(f"Failed to import patterns into workspace: {str(e)}")
            return False
    
    def _extract_patterns_from_database(self, db_utils: SQLDatabaseUtils, use_case: UseCase) -> List[Dict]:
        """Extract all patterns from the database"""
        try:
            # Get all patterns with their relationships
            query = """
                SELECT 
                    a.api_name,
                    COALESCE(av.version_number, 'N/A') as api_version,
                    aps.section_name,
                    aps.section_display_name,
                    pd.pattern_name,
                    pd.pattern_description,
                    pd.pattern_prompt,
                    pd.created_at,
                    pd.updated_at
                FROM api a
                LEFT JOIN apiversion av ON a.api_id = av.api_id
                LEFT JOIN api_section aps ON a.api_id = aps.api_id
                LEFT JOIN section_pattern_mapping spm ON aps.section_id = spm.section_id AND aps.api_id = spm.api_id
                LEFT JOIN pattern_details pd ON spm.pattern_id = pd.pattern_id
                WHERE pd.pattern_name IS NOT NULL
                ORDER BY a.api_name, aps.section_name, pd.pattern_name
            """
            
            results = db_utils.execute_query(query)
            
            patterns = []
            for row in results:
                pattern = {
                    "api_name": row[0],
                    "api_version": row[1],
                    "section_name": row[2],
                    "section_display_name": row[3],
                    "pattern_name": row[4],
                    "pattern_description": row[5],
                    "pattern_prompt": row[6],
                    "created_at": row[7],
                    "updated_at": row[8]
                }
                patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to extract patterns from database: {str(e)}")
            return []
    
    def _import_patterns_to_database(self, db_utils: SQLDatabaseUtils, patterns_data: List[Dict], use_case: UseCase, merge_mode: str) -> int:
        """Import patterns into the database"""
        try:
            imported_count = 0
            
            for pattern_data in patterns_data:
                try:
                    # Ensure API exists
                    api_name = pattern_data.get("api_name", "Imported API")
                    api_id = self._ensure_api_exists(db_utils, api_name)
                    
                    # Ensure API version exists
                    api_version = pattern_data.get("api_version", "1.0")
                    if api_version != "N/A":
                        self._ensure_api_version_exists(db_utils, api_id, api_version)
                    
                    # Ensure section exists
                    section_name = pattern_data.get("section_name", "imported_section")
                    section_display_name = pattern_data.get("section_display_name", section_name)
                    section_id = self._ensure_section_exists(db_utils, api_id, section_name, section_display_name)
                    
                    # Handle pattern based on merge mode
                    pattern_name = pattern_data.get("pattern_name")
                    if not pattern_name:
                        continue
                    
                    # Check if pattern already exists
                    existing_pattern = db_utils.execute_query(
                        "SELECT pattern_id FROM pattern_details WHERE pattern_name = ?",
                        (pattern_name,)
                    )
                    
                    if existing_pattern and merge_mode == "skip_existing":
                        continue
                    
                    # Insert or update pattern
                    pattern_description = pattern_data.get("pattern_description", "")
                    pattern_prompt = pattern_data.get("pattern_prompt", "")
                    
                    if existing_pattern and merge_mode == "replace":
                        # Update existing pattern
                        pattern_id = existing_pattern[0][0]
                        db_utils.execute_query(
                            "UPDATE pattern_details SET pattern_description = ?, pattern_prompt = ?, updated_at = ? WHERE pattern_id = ?",
                            (pattern_description, pattern_prompt, datetime.now().isoformat(), pattern_id)
                        )
                    else:
                        # Insert new pattern
                        db_utils.insert_data(
                            "pattern_details",
                            (pattern_name, pattern_description, pattern_prompt),
                            columns=["pattern_name", "pattern_description", "pattern_prompt"]
                        )
                        
                        # Get the inserted pattern ID
                        pattern_result = db_utils.execute_query(
                            "SELECT pattern_id FROM pattern_details WHERE pattern_name = ?",
                            (pattern_name,)
                        )
                        pattern_id = pattern_result[0][0]
                    
                    # Ensure mapping exists
                    self._ensure_pattern_mapping_exists(db_utils, pattern_id, section_id, api_id)
                    
                    imported_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to import pattern {pattern_data.get('pattern_name', 'Unknown')}: {str(e)}")
                    continue
            
            return imported_count
            
        except Exception as e:
            logger.error(f"Failed to import patterns to database: {str(e)}")
            return 0
    
    def _validate_import_data(self, import_data: Dict) -> bool:
        """Validate the structure of import data"""
        try:
            # Check required top-level keys
            if not isinstance(import_data, dict):
                return False
            
            if "patterns" not in import_data:
                return False
            
            patterns = import_data["patterns"]
            if not isinstance(patterns, list):
                return False
            
            # Check that we have at least one valid pattern
            for pattern in patterns:
                if not isinstance(pattern, dict):
                    continue
                
                if "pattern_name" in pattern:
                    return True
            
            return False
            
        except Exception:
            return False
    
    def _ensure_api_exists(self, db_utils: SQLDatabaseUtils, api_name: str) -> int:
        """Ensure API exists and return its ID"""
        try:
            # Check if API exists
            result = db_utils.execute_query("SELECT api_id FROM api WHERE api_name = ?", (api_name,))
            
            if result:
                return result[0][0]
            else:
                # Insert new API
                db_utils.insert_data("api", (api_name,), columns=["api_name"])
                result = db_utils.execute_query("SELECT api_id FROM api WHERE api_name = ?", (api_name,))
                return result[0][0]
                
        except Exception as e:
            logger.error(f"Failed to ensure API exists: {str(e)}")
            raise
    
    def _ensure_api_version_exists(self, db_utils: SQLDatabaseUtils, api_id: int, version_number: str):
        """Ensure API version exists"""
        try:
            # Check if version exists
            result = db_utils.execute_query(
                "SELECT version_id FROM apiversion WHERE api_id = ? AND version_number = ?",
                (api_id, version_number)
            )
            
            if not result:
                # Insert new version
                db_utils.insert_data(
                    "apiversion",
                    (api_id, version_number),
                    columns=["api_id", "version_number"]
                )
                
        except Exception as e:
            logger.error(f"Failed to ensure API version exists: {str(e)}")
            raise
    
    def _ensure_section_exists(self, db_utils: SQLDatabaseUtils, api_id: int, section_name: str, section_display_name: str) -> int:
        """Ensure section exists and return its ID"""
        try:
            # Check if section exists
            result = db_utils.execute_query(
                "SELECT section_id FROM api_section WHERE api_id = ? AND section_name = ?",
                (api_id, section_name)
            )
            
            if result:
                return result[0][0]
            else:
                # Insert new section
                db_utils.insert_data(
                    "api_section",
                    (api_id, section_name, section_display_name),
                    columns=["api_id", "section_name", "section_display_name"]
                )
                result = db_utils.execute_query(
                    "SELECT section_id FROM api_section WHERE api_id = ? AND section_name = ?",
                    (api_id, section_name)
                )
                return result[0][0]
                
        except Exception as e:
            logger.error(f"Failed to ensure section exists: {str(e)}")
            raise
    
    def _ensure_pattern_mapping_exists(self, db_utils: SQLDatabaseUtils, pattern_id: int, section_id: int, api_id: int):
        """Ensure pattern mapping exists"""
        try:
            # Check if mapping exists
            result = db_utils.execute_query(
                "SELECT mapping_id FROM section_pattern_mapping WHERE pattern_id = ? AND section_id = ? AND api_id = ?",
                (pattern_id, section_id, api_id)
            )
            
            if not result:
                # Insert new mapping
                db_utils.insert_data(
                    "section_pattern_mapping",
                    (pattern_id, section_id, api_id),
                    columns=["pattern_id", "section_id", "api_id"]
                )
                
        except Exception as e:
            logger.error(f"Failed to ensure pattern mapping exists: {str(e)}")
            raise