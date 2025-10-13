"""
Pattern Manager - Export, Verify, and Organize Patterns

Hybrid approach:
- Backend generates patterns during Discovery
- Pattern Manager exports patterns to SQLite workspace
- Business analysts can verify and organize patterns
"""

import streamlit as st
import requests
from typing import Dict, List, Any, Optional
from pathlib import Path
import sys
import sqlite3

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent / "utils"))

# API Configuration
API_BASE_URL = (
    st.session_state.get("api_base_url")
    if "api_base_url" in st.session_state
    else "http://localhost:8000/api/v1"
)


class SimpleSQLDatabaseUtils:
    """Simplified SQLite database utilities."""

    def __init__(self, db_name="patterns.db", base_dir=None):
        if base_dir is None:
            base_dir = Path(__file__).parent / "data" / "workspaces"
        else:
            base_dir = Path(base_dir)

        base_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_dir / db_name

        # Initialize database schema if it doesn't exist
        self._init_schema()

    def connect(self):
        return sqlite3.connect(str(self.db_path), timeout=30)

    def _init_schema(self):
        """Initialize database schema if tables don't exist."""
        conn = self.connect()
        cursor = conn.cursor()

        try:
            # Create api table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api (
                    api_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_name TEXT NOT NULL UNIQUE,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create apiversion table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS apiversion (
                    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_id INTEGER NOT NULL,
                    version_number TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (api_id) REFERENCES api(api_id),
                    UNIQUE(api_id, version_number)
                )
            """)

            # Create api_section table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_section (
                    section_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_id INTEGER NOT NULL,
                    section_name TEXT NOT NULL,
                    section_type TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (api_id) REFERENCES api(api_id),
                    UNIQUE(api_id, section_name)
                )
            """)

            # Create pattern_details table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pattern_details (
                    pattern_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_name TEXT NOT NULL,
                    pattern_description TEXT,
                    pattern_prompt TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create section_pattern_mapping table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS section_pattern_mapping (
                    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    section_id INTEGER NOT NULL,
                    api_id INTEGER NOT NULL,
                    pattern_id INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (section_id) REFERENCES api_section(section_id),
                    FOREIGN KEY (api_id) REFERENCES api(api_id),
                    FOREIGN KEY (pattern_id) REFERENCES pattern_details(pattern_id),
                    UNIQUE(section_id, api_id, pattern_id)
                )
            """)

            # Create shared_patterns table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS shared_patterns (
                    shared_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_id INTEGER NOT NULL,
                    api_id INTEGER NOT NULL,
                    section_id INTEGER NOT NULL,
                    is_shared INTEGER DEFAULT 0,
                    shared_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    shared_by TEXT,
                    FOREIGN KEY (pattern_id) REFERENCES pattern_details(pattern_id),
                    FOREIGN KEY (api_id) REFERENCES api(api_id),
                    FOREIGN KEY (section_id) REFERENCES api_section(section_id),
                    UNIQUE(pattern_id, api_id, section_id)
                )
            """)

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def run_query(self, query, params=None):
        conn = self.connect()
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        results = cursor.fetchall()
        conn.commit()
        cursor.close()
        conn.close()
        return results

    def insert_data(self, table_name, values, columns=None):
        conn = self.connect()
        cursor = conn.cursor()
        if columns:
            columns_str = ", ".join(columns)
            placeholders = ", ".join(["?"] * len(values))
            query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
        else:
            placeholders = ", ".join(["?"] * len(values))
            query = f"INSERT INTO {table_name} VALUES ({placeholders})"
        cursor.execute(query, values)
        conn.commit()
        last_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return last_id

    def get_all_patterns(self):
        query = """
            SELECT a.api_name, COALESCE(av.version_number, 'N/A') as api_version,
                   aps.section_name, pd.pattern_description, pd.pattern_prompt,
                   pd.pattern_id, a.api_id, aps.section_id,
                   COALESCE(sp.is_shared, 0) as is_shared
            FROM api a
            LEFT JOIN apiversion av ON a.api_id = av.api_id
            JOIN api_section aps ON a.api_id = aps.api_id
            JOIN section_pattern_mapping spm ON aps.section_id = spm.section_id AND aps.api_id = spm.api_id
            JOIN pattern_details pd ON spm.pattern_id = pd.pattern_id
            LEFT JOIN shared_patterns sp ON pd.pattern_id = sp.pattern_id
                AND a.api_id = sp.api_id AND aps.section_id = sp.section_id
            GROUP BY a.api_name, av.version_number, pd.pattern_prompt
        """
        return self.run_query(query)

    def get_shared_patterns(self):
        """Get only shared patterns for export."""
        query = """
            SELECT a.api_name, av.version_number, aps.section_name,
                   pd.pattern_name, pd.pattern_description, pd.pattern_prompt,
                   sp.shared_at, sp.shared_by
            FROM shared_patterns sp
            JOIN pattern_details pd ON sp.pattern_id = pd.pattern_id
            JOIN api a ON sp.api_id = a.api_id
            LEFT JOIN apiversion av ON a.api_id = av.api_id
            JOIN api_section aps ON sp.section_id = aps.section_id
            WHERE sp.is_shared = 1
        """
        return self.run_query(query)

    def update_shared_status(self, pattern_id, api_id, section_id, is_shared, shared_by=None):
        """Update or insert shared pattern status."""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO shared_patterns
                (pattern_id, api_id, section_id, is_shared, shared_by, shared_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (pattern_id, api_id, section_id, 1 if is_shared else 0, shared_by))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def insert_api_version(self, api_id, version_number):
        return self.insert_data("apiversion", (api_id, version_number),
                              columns=["api_id", "version_number"])


class PatternManager:
    """Manages pattern export, verification, and organization."""

    def __init__(self):
        self.db_utils = self._get_workspace_db()

    def _get_workspace_db(self) -> SimpleSQLDatabaseUtils:
        """Get current workspace database."""
        workspace = st.session_state.get('current_workspace', 'default')
        db_name = f"{workspace}_patterns.db"
        db_dir = Path(__file__).parent / "data" / "workspaces"
        db_dir.mkdir(parents=True, exist_ok=True)

        return SimpleSQLDatabaseUtils(db_name=db_name, base_dir=str(db_dir))

    def render(self, explorer_callback=None):
        """Render Pattern Manager page with optional pattern manager tab."""

        if explorer_callback:
            tabs = st.tabs([
                "📋 Manage Patterns",
                "✅ Verify Patterns"
            ])

            with tabs[0]:
                explorer_callback()
            with tabs[1]:
                self._render_verify_tab()
        else:
            st.warning("⚠️ Pattern Manager callback not provided")
            self._render_verify_tab()

    def _render_export_tab(self):
        """Export  patterns to workspace."""
        st.subheader("📤 Export Patterns to Workspace")

        workspace = st.session_state.get('current_workspace', 'default')
        st.caption(f"📁 Fetching patterns from workspace: **{workspace}**")

        # Fetch backend patterns
        try:
            response = requests.get(
                f"{API_BASE_URL}/patterns/",
                params={"limit": 200, "workspace": workspace}
            )
            if response.status_code == 200:
                backend_patterns = response.json()
            else:
                st.error(f"❌ API returned status {response.status_code}: {response.text}")
                backend_patterns = []
        except Exception as e:
            st.error(f"❌ Failed to fetch backend patterns: {str(e)}")
            st.info("💡 Make sure the backend API is running at http://localhost:8000")
            return

        if not backend_patterns:
            st.info("📭 No patterns found in backend. Run Discovery first to generate patterns.")
            return

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Patterns", len(backend_patterns))
        with col2:
            unique_versions = len(set(p.get('spec_version', '') for p in backend_patterns))
            st.metric("Versions", unique_versions)
        with col3:
            unique_types = len(set(p.get('decision_rule', {}).get('node_type', 'Unknown') for p in backend_patterns))
            st.metric("Node Types", unique_types)
        with col4:
            total_seen = sum(p.get('times_seen', 0) for p in backend_patterns)
            st.metric("Total Observations", total_seen)

        st.divider()

        # Filters
        st.markdown("### 🔧 Filters")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            versions = ["All"] + sorted(set(p.get('spec_version', '') for p in backend_patterns if p.get('spec_version')))
            selected_version = st.selectbox("Version:", versions, key="export_filter_version")

        with col2:
            node_types = ["All"] + sorted(set(p.get('decision_rule', {}).get('node_type', 'Unknown') for p in backend_patterns))
            selected_type = st.selectbox("Node Type:", node_types, key="export_filter_node_type")

        with col3:
            airlines = ["All"] + sorted(set(p.get('airline_code', '') for p in backend_patterns if p.get('airline_code')))
            selected_airline = st.selectbox("Airline:", airlines, key="export_filter_airline")

        with col4:
            msg_roots = ["All"] + sorted(set(p.get('message_root', '') for p in backend_patterns if p.get('message_root')))
            selected_msg_root = st.selectbox("Message Root:", msg_roots, key="export_filter_message_root")

        # Apply filters
        filtered_patterns = backend_patterns
        if selected_version != "All":
            filtered_patterns = [p for p in filtered_patterns if p.get('spec_version') == selected_version]
        if selected_type != "All":
            filtered_patterns = [p for p in filtered_patterns if p.get('decision_rule', {}).get('node_type', 'Unknown') == selected_type]
        if selected_airline != "All":
            filtered_patterns = [p for p in filtered_patterns if p.get('airline_code') == selected_airline]
        if selected_msg_root != "All":
            filtered_patterns = [p for p in filtered_patterns if p.get('message_root') == selected_msg_root]

        st.divider()
        st.markdown(f"### ✅ Select Patterns to Export ({len(filtered_patterns)} matching)")

        # Prepare table data
        import pandas as pd

        table_rows = []
        pattern_id_map = {}  # Map row index to pattern ID

        for idx, pattern in enumerate(filtered_patterns):
            decision_rule = pattern.get('decision_rule', {})
            node_type = decision_rule.get('node_type', 'Unknown')

            pattern_id_map[idx] = pattern['id']

            table_rows.append({
                "Select": False,
                "Node Type": node_type,
                "Section Path": pattern['section_path'],
                "Version": pattern.get('spec_version', 'N/A'),
                "Airline": pattern.get('airline_code', 'N/A'),
                "Message": pattern.get('message_root', 'N/A'),
                "Times Seen": pattern.get('times_seen', 0),
                "Must-Have Attrs": len(decision_rule.get('must_have_attributes', [])),
                "Has Children": "✓" if decision_rule.get('child_structure', {}).get('has_children') else ""
            })

        df = pd.DataFrame(table_rows)

        # Data editor with checkbox column (key includes workspace to force refresh on workspace change)
        edited_df = st.data_editor(
            df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Select": st.column_config.CheckboxColumn(
                    "Select",
                    help="Select patterns to export",
                    default=False
                ),
                "Times Seen": st.column_config.NumberColumn("Times Seen", format="%d"),
                "Must-Have Attrs": st.column_config.NumberColumn("Must-Have Attrs", format="%d"),
            },
            disabled=["Node Type", "Section Path", "Version", "Airline", "Message", "Times Seen", "Must-Have Attrs", "Has Children"],
            key=f"export_patterns_table_{workspace}"
        )

        # Get selected pattern IDs
        selected_pattern_ids = [
            pattern_id_map[idx]
            for idx in range(len(edited_df))
            if edited_df.iloc[idx]["Select"]
        ]

        # Quick select options
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("✅ Select All", use_container_width=True):
                # Update all rows to selected
                for idx in range(len(df)):
                    df.at[idx, "Select"] = True
                st.rerun()
        with col2:
            if st.button("❌ Clear All", use_container_width=True):
                # Update all rows to unselected
                for idx in range(len(df)):
                    df.at[idx, "Select"] = False
                st.rerun()
        with col3:
            st.metric("Selected", len(selected_pattern_ids))

        # Export button
        st.markdown("---")
        col1, col2 = st.columns([1, 3])

        with col1:
            workspace = st.session_state.get('current_workspace', 'default')
            export_clicked = st.button(
                f"💾 Export {len(selected_pattern_ids)} Patterns",
                type="primary",
                disabled=len(selected_pattern_ids) == 0,
                use_container_width=True
            )

        with col2:
            if len(selected_pattern_ids) > 0:
                st.success(f"✅ Ready to export to workspace: **{workspace}**")
            else:
                st.info("Select patterns above to export")

        # Process export
        if export_clicked and len(selected_pattern_ids) > 0:
            with st.status("📤 Exporting patterns to workspace...", expanded=True) as status:
                st.write(f"Exporting {len(selected_pattern_ids)} patterns...")

                success_count = 0
                skip_count = 0
                error_count = 0

                for pattern_id in selected_pattern_ids:
                    pattern = next((p for p in backend_patterns if p['id'] == pattern_id), None)
                    if not pattern:
                        error_count += 1
                        continue

                    try:
                        # Save to workspace database
                        self._export_pattern_to_workspace(pattern)
                        success_count += 1
                    except Exception as e:
                        if "UNIQUE constraint" in str(e):
                            skip_count += 1
                        else:
                            error_count += 1
                            st.write(f"❌ Error exporting {pattern['section_path']}: {e}")

                st.write(f"✅ Exported: {success_count}")
                if skip_count > 0:
                    st.write(f"⏭️ Skipped (already exists): {skip_count}")
                if error_count > 0:
                    st.write(f"❌ Errors: {error_count}")

                status.update(label=f"✅ Export Complete! ({success_count} exported)", state="complete")

    def _export_pattern_to_workspace(self, pattern: Dict[str, Any]):
        """Export a backend pattern to workspace SQLite."""
        decision_rule = pattern.get('decision_rule', {})

        # Extract pattern information
        pattern_name = f"{decision_rule.get('node_type', 'Unknown')}"
        pattern_description = f"Node: {pattern['section_path']}, Version: {pattern['spec_version']}"
        pattern_prompt = self._generate_pattern_prompt(pattern)

        # Get or create API
        api_name = pattern.get('airline_code', 'GENERIC')
        api_id = self._get_or_create_api(api_name)

        # Get or create API version
        version_number = pattern['spec_version']
        self._get_or_create_version(api_id, version_number)

        # Insert pattern details
        pattern_id = self.db_utils.insert_data(
            "pattern_details",
            (pattern_name, pattern_description, pattern_prompt),
            columns=["pattern_name", "pattern_description", "pattern_prompt"]
        )

        # Create section
        section_id = self.db_utils.insert_data(
            "api_section",
            (api_id, pattern['section_path'], 'pattern'),
            columns=["api_id", "section_name", "section_type"]
        )

        # Create mapping
        self.db_utils.insert_data(
            "section_pattern_mapping",
            (pattern_id, section_id, api_id),
            columns=["pattern_id", "section_id", "api_id"]
        )

    def _generate_pattern_prompt(self, pattern: Dict[str, Any]) -> str:
        """Generate validation prompt from pattern decision rule."""
        decision_rule = pattern.get('decision_rule', {})

        prompt = f"Validate that the XML node matches:\n"
        prompt += f"- Node Type: {decision_rule.get('node_type', 'Unknown')}\n"

        if decision_rule.get('must_have_attributes'):
            prompt += f"- Must Have Attributes: {', '.join(decision_rule['must_have_attributes'])}\n"

        if decision_rule.get('child_structure', {}).get('has_children'):
            prompt += f"- Must Have Children: Yes\n"
            child_types = decision_rule.get('child_structure', {}).get('child_types', [])
            if child_types:
                prompt += f"- Expected Child Types: {', '.join(child_types)}\n"

        return prompt

    def _load_patterns_from_backend(self, workspace: str) -> List[tuple]:
        """Fetch patterns directly from backend when local cache is empty."""
        try:
            response = requests.get(
                f"{API_BASE_URL}/patterns/",
                params={"limit": 500, "workspace": workspace},
                timeout=15
            )
            if response.status_code != 200:
                return []

            backend_patterns = response.json() or []
            converted_patterns = []
            for pattern in backend_patterns:
                prompt = self._generate_pattern_prompt(pattern)
                converted_patterns.append((
                    pattern.get('message_root', 'Unknown'),  # api_name
                    pattern.get('spec_version', 'Unknown'),  # version
                    pattern.get('section_path', 'Unknown'),  # section_name
                    pattern.get('description', ''),          # pattern_desc
                    prompt,                                  # pattern_prompt
                    pattern.get('id', 0),                    # pattern_id (backend)
                    None,                                    # api_id placeholder
                    None,                                    # section_id placeholder
                    0                                        # is_shared
                ))
            return converted_patterns
        except requests.exceptions.RequestException:
            return []

    def _get_or_create_api(self, api_name: str) -> int:
        """Get or create API in workspace."""
        result = self.db_utils.run_query("SELECT api_id FROM api WHERE api_name = ?", (api_name,))
        if result:
            return result[0][0]

        return self.db_utils.insert_data("api", (api_name,), columns=["api_name"])

    def _get_or_create_version(self, api_id: int, version_number: str):
        """Get or create API version."""
        result = self.db_utils.run_query(
            "SELECT version_id FROM apiversion WHERE api_id = ? AND version_number = ?",
            (api_id, version_number)
        )
        if result:
            return result[0][0]

        return self.db_utils.insert_api_version(api_id, version_number)

    def _render_verify_tab(self):
        """Verify workspace patterns with test XML."""
        st.subheader("🔍 Verify Patterns")
        st.info("💡 Verify patterns against XML content to ensure they match as expected.")

        # Get current workspace
        workspace = st.session_state.get('current_workspace', 'default')

        # Load patterns from backend API first (primary source)
        workspace_patterns = self._load_patterns_from_backend(workspace)

        # Fallback to local workspace database if backend is unavailable
        if not workspace_patterns:
            workspace_patterns = self.db_utils.get_all_patterns()

        if not workspace_patterns:
            st.warning("📭 No patterns found. Run Discovery first to generate patterns.")
            return

        # Show pattern statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Patterns", len(workspace_patterns))
        with col2:
            unique_versions = len(set(p[1] for p in workspace_patterns))
            st.metric("Versions", unique_versions)
        with col3:
            unique_types = len(set(p[2] for p in workspace_patterns))
            st.metric("Node Types", unique_types)

        st.divider()

        # Show pattern list with selection
        st.markdown("### 🔍 Pattern Details")

        import pandas as pd

        # Build pattern table
        pattern_rows = []
        pattern_map = {}  # Map index to pattern details

        for idx, p in enumerate(workspace_patterns):
            # Unpack pattern tuple (9 columns from get_all_patterns or _load_patterns_from_backend)
            (api_name, api_version, section_name, pattern_desc, pattern_prompt,
             pattern_id, api_id, section_id, is_shared) = p

            pattern_map[idx] = {
                'api': api_name,
                'version': api_version,
                'section': section_name,
                'description': pattern_desc or '',
                'prompt': pattern_prompt,
                'pattern_id': pattern_id
            }

            pattern_rows.append({
                "API": api_name,
                "Version": api_version,
                "Node Type": section_name,
                "Description": pattern_desc[:80] + "..." if pattern_desc and len(pattern_desc) > 80 else pattern_desc or ''
            })

        df = pd.DataFrame(pattern_rows)

        # Display patterns table
        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True,
            height=min(400, len(df) * 35 + 38)
        )

        st.divider()

        # XML file upload
        st.markdown("### 📄 Upload XML File to Verify")

        uploaded_xml = st.file_uploader(
            "Upload XML file to verify against patterns",
            type=['xml'],
            help="Upload an XML file to check which patterns match",
            key="verify_xml_uploader"
        )

        if uploaded_xml is not None:
            # Read XML content
            xml_content = uploaded_xml.read().decode('utf-8')

            st.success(f"✅ Uploaded: {uploaded_xml.name}")

            # Show XML preview
            with st.expander("📄 XML Preview", expanded=False):
                st.code(xml_content[:1000] + ("..." if len(xml_content) > 1000 else ""), language='xml')

            # Pattern selection for verification
            st.markdown("### 🎯 Select Pattern to Verify")

            pattern_labels = [
                f"{pattern_map[idx]['api']} v{pattern_map[idx]['version']} - {pattern_map[idx]['section']}"
                for idx in range(len(workspace_patterns))
            ]

            selected_pattern_label = st.selectbox(
                "Choose a pattern:",
                pattern_labels,
                key="selected_pattern_verify"
            )

            selected_idx = pattern_labels.index(selected_pattern_label)
            pattern = pattern_map[selected_idx]

            # Show pattern details
            with st.expander("📋 Pattern Details", expanded=True):
                st.write(f"**API:** {pattern['api']} v{pattern['version']}")
                st.write(f"**Node Type:** {pattern['section']}")
                if pattern['description']:
                    st.write(f"**Description:** {pattern['description']}")
                st.code(pattern['prompt'], language='text')

            col1, col2 = st.columns([1, 3])

            with col1:
                verify_btn = st.button("🚀 Verify Pattern", type="primary", use_container_width=True)

            with col2:
                st.success("✅ Ready to verify pattern against uploaded XML")

            # Process verification
            if verify_btn:
                self._process_verification(pattern, xml_content)

    def _process_verification(self, pattern: Dict[str, Any], test_xml: str):
        """Process pattern verification with LLM."""
        result = None
        verification_error = None

        with st.status("🔄 Verifying pattern with AI...", expanded=True) as status:

            try:
                # Import and initialize verifier
                from utils.pattern_llm_verifier import get_verifier

                verifier = get_verifier()
                st.write("🤖 Analyzing XML against pattern...")

                # Verify pattern
                result = verifier.verify_pattern(pattern['prompt'], test_xml)

                if 'error' in result:
                    st.write(f"❌ Verification error: {result['error']}")
                    status.update(label="❌ Verification Failed", state="error")
                    return

                st.write("✅ Verification complete!")
                status.update(label="✅ AI Verification Complete", state="complete")

            except ImportError:
                verification_error = "LLM verifier not available. Check that openai package is installed."
                status.update(label="❌ Verification Failed", state="error")

            except Exception as e:
                verification_error = f"Verification failed: {str(e)}\n\nError Type: {type(e).__name__}"
                status.update(label="❌ Verification Failed", state="error")

        # Display results outside the status block to avoid nesting issues
        if verification_error:
            st.error(f"❌ {verification_error}")
        elif result:
            self._display_verification_results(result, pattern)

    def _display_verification_results(self, result: Dict[str, Any], pattern: Dict[str, Any]):
        """Display verification results."""
        st.markdown("---")
        st.markdown("### 📊 AI Verification Results")

        # Summary with match status
        is_match = result.get('is_match', False)
        confidence = result.get('confidence', 0.0)

        col1, col2, col3 = st.columns(3)
        with col1:
            if is_match:
                st.success("✅ **MATCH**")
            else:
                st.error("❌ **NO MATCH**")

        with col2:
            st.metric("Confidence", f"{confidence:.0%}")

        with col3:
            tokens_used = result.get('tokens_used', 0)
            st.metric("Tokens Used", tokens_used)

        # Summary
        summary = result.get('summary', 'No summary available')
        st.markdown("**Summary:**")
        if is_match:
            st.success(summary)
        else:
            st.warning(summary)

        # Detailed findings
        findings = result.get('findings', [])
        if findings:
            st.markdown("---")
            st.markdown("### 🔍 Detailed Findings")

            for finding in findings:
                aspect = finding.get('aspect', 'Unknown')
                expected = finding.get('expected', 'N/A')
                found = finding.get('found', 'N/A')
                match = finding.get('match', False)

                with st.expander(f"{'✅' if match else '❌'} {aspect.replace('_', ' ').title()}", expanded=not match):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**Expected:**")
                        st.code(expected, language='text')
                    with col2:
                        st.write("**Found:**")
                        st.code(found, language='text')

                    if match:
                        st.success("✅ Matches pattern requirements")
                    else:
                        st.error("❌ Does not match pattern requirements")

        # Issues
        issues = result.get('issues', [])
        if issues:
            st.markdown("---")
            st.markdown("### ⚠️ Issues Found")
            for issue in issues:
                st.warning(f"• {issue}")

        # Recommendations
        recommendations = result.get('recommendations', [])
        if recommendations:
            st.markdown("---")
            st.markdown("### 💡 Recommendations")
            for rec in recommendations:
                st.info(f"• {rec}")

    def _render_manage_tab(self):
        """Manage workspace patterns."""
        st.subheader("📚 Manage Workspace Patterns")

        workspace = st.session_state.get('current_workspace', 'default')
        st.info(f"📁 Current Workspace: **{workspace}**")

        # Initialize session state for pending changes
        if 'pending_shared_changes' not in st.session_state:
            st.session_state.pending_shared_changes = {}

        # Get workspace patterns
        workspace_patterns = self.db_utils.get_all_patterns()

        if not workspace_patterns:
            st.warning("📭 No patterns in workspace. Export patterns first.")
            return

        st.success(f"✅ {len(workspace_patterns)} patterns in workspace")

        # Display patterns table
        import pandas as pd

        pattern_rows = []
        pattern_metadata = []  # Store pattern_id, api_id, section_id for saving
        for p in workspace_patterns:
            (api_name, api_version, section_name, pattern_desc, pattern_prompt,
             pattern_id, api_id, section_id, is_shared) = p

            # Create unique key for this pattern
            pattern_key = f"{pattern_id}_{api_id}_{section_id}"

            pattern_metadata.append({
                'pattern_id': pattern_id,
                'api_id': api_id,
                'section_id': section_id,
                'key': pattern_key
            })

            # Check if there's a pending change for this pattern
            if pattern_key in st.session_state.pending_shared_changes:
                is_shared = st.session_state.pending_shared_changes[pattern_key]

            pattern_rows.append({
                "Shared Pattern": bool(is_shared),
                "API": api_name,
                "Version": api_version,
                "Section": section_name,
                "Description": pattern_desc[:50] + "..." if len(pattern_desc) > 50 else pattern_desc
            })

        df = pd.DataFrame(pattern_rows)

        # Use data editor
        edited_df = st.data_editor(
            df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Shared Pattern": st.column_config.CheckboxColumn(
                    "Shared Pattern",
                    help="Mark patterns that should be shared across workspaces"
                )
            },
            disabled=["API", "Version", "Section", "Description"],
            key="patterns_table"
        )

        # Detect changes and save to database + session state immediately
        changes_made = False
        for idx in range(len(edited_df)):
            old_shared = pattern_rows[idx]["Shared Pattern"]
            new_shared = edited_df.iloc[idx]["Shared Pattern"]

            if old_shared != new_shared:
                changes_made = True
                # Update database immediately
                metadata = pattern_metadata[idx]
                self.db_utils.update_shared_status(
                    metadata['pattern_id'],
                    metadata['api_id'],
                    metadata['section_id'],
                    new_shared,
                    shared_by=workspace
                )
                # Store in session state to persist across reruns
                st.session_state.pending_shared_changes[metadata['key']] = new_shared

        if changes_made:
            st.toast("✅ Shared pattern settings saved!", icon="✅")
            # Clear pending changes after successful save
            st.session_state.pending_shared_changes = {}

        # Workspace actions
        st.markdown("---")
        st.markdown("### 🔧 Workspace Actions")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("📊 Export All to CSV", use_container_width=True):
                csv = df.to_csv(index=False)
                st.download_button(
                    label="⬇️ Download CSV",
                    data=csv,
                    file_name=f"{workspace}_patterns.csv",
                    mime="text/csv"
                )

        with col2:
            # Export shared patterns only
            shared_count = sum(1 for row in pattern_rows if row["Shared Pattern"])
            if st.button(f"📤 Export Shared ({shared_count})", use_container_width=True, type="primary"):
                self._export_shared_patterns_action(workspace)

        with col3:
            # Import shared patterns
            if st.button("📥 Import Shared", use_container_width=True, type="primary"):
                st.session_state.show_import_dialog = True

        with col4:
            st.metric("Total", len(workspace_patterns))
            st.metric("Shared", shared_count)

        # Import dialog
        if st.session_state.get('show_import_dialog', False):
            self._render_import_dialog()

    def _export_shared_patterns_action(self, workspace: str):
        """Export shared patterns to a JSON file for sharing."""
        import json
        from datetime import datetime

        shared_patterns = self.db_utils.get_shared_patterns()

        if not shared_patterns:
            st.warning("⚠️ No shared patterns to export. Mark patterns as shared first.")
            return

        # Convert to exportable format
        export_data = {
            "metadata": {
                "exported_from": workspace,
                "exported_at": datetime.utcnow().isoformat(),
                "pattern_count": len(shared_patterns),
                "format_version": "1.0"
            },
            "patterns": []
        }

        for pattern in shared_patterns:
            (api_name, api_version, section_name, pattern_name,
             pattern_desc, pattern_prompt, shared_at, shared_by) = pattern

            export_data["patterns"].append({
                "api_name": api_name,
                "api_version": api_version,
                "section_name": section_name,
                "pattern_name": pattern_name,
                "pattern_description": pattern_desc,
                "pattern_prompt": pattern_prompt,
                "shared_at": shared_at,
                "shared_by": shared_by
            })

        # Create download button
        json_str = json.dumps(export_data, indent=2)
        filename = f"{workspace}_shared_patterns_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        st.download_button(
            label=f"⬇️ Download {len(shared_patterns)} Shared Patterns",
            data=json_str,
            file_name=filename,
            mime="application/json",
            type="primary"
        )

        st.success(f"✅ Ready to export {len(shared_patterns)} shared patterns!")

    def _render_import_dialog(self):
        """Render import dialog for shared patterns."""
        import json

        st.markdown("---")
        st.markdown("### 📥 Import Shared Patterns")

        uploaded_file = st.file_uploader(
            "Upload shared patterns JSON file",
            type=['json'],
            help="Import patterns exported from another workspace",
            key="import_file_uploader"
        )

        if uploaded_file is not None:
            try:
                # Read and parse JSON
                import_data = json.load(uploaded_file)

                # Validate format
                if "metadata" not in import_data or "patterns" not in import_data:
                    st.error("❌ Invalid file format. Missing metadata or patterns.")
                    return

                metadata = import_data["metadata"]
                patterns = import_data["patterns"]

                # Show import preview
                st.info(f"""
                **Source:** {metadata.get('exported_from', 'Unknown')}
                **Exported:** {metadata.get('exported_at', 'Unknown')}
                **Patterns:** {len(patterns)}
                """)

                # Pattern preview
                with st.expander("📋 Preview Patterns", expanded=False):
                    for idx, pattern in enumerate(patterns[:10], 1):
                        st.write(f"{idx}. **{pattern['pattern_name']}** - {pattern['section_name']} ({pattern['api_name']} v{pattern['api_version']})")
                    if len(patterns) > 10:
                        st.write(f"... and {len(patterns) - 10} more")

                # Import options
                col1, col2 = st.columns(2)

                with col1:
                    overwrite = st.checkbox(
                        "Overwrite existing patterns",
                        value=False,
                        help="If checked, existing patterns will be replaced"
                    )

                with col2:
                    mark_as_shared = st.checkbox(
                        "Mark imported patterns as shared",
                        value=True,
                        help="Automatically mark imported patterns as shared"
                    )

                # Import button
                if st.button("✅ Import Patterns", type="primary", use_container_width=True):
                    with st.status("📥 Importing patterns...", expanded=True) as status:
                        success_count = 0
                        skip_count = 0
                        error_count = 0

                        for pattern in patterns:
                            try:
                                # Create pattern structure
                                pattern_obj = {
                                    'section_path': pattern['section_name'],
                                    'spec_version': pattern['api_version'],
                                    'airline_code': pattern['api_name'],
                                    'decision_rule': {
                                        'node_type': pattern['pattern_name']
                                    }
                                }

                                # Use existing export method
                                self._export_pattern_to_workspace(pattern_obj)

                                # Mark as shared if requested
                                if mark_as_shared:
                                    # Get the pattern IDs that were just created
                                    # Note: This is a simplified approach
                                    pass

                                success_count += 1

                            except Exception as e:
                                if "UNIQUE constraint" in str(e) and not overwrite:
                                    skip_count += 1
                                else:
                                    error_count += 1
                                    st.write(f"❌ Error: {e}")

                        st.write(f"✅ Imported: {success_count}")
                        if skip_count > 0:
                            st.write(f"⏭️ Skipped (already exists): {skip_count}")
                        if error_count > 0:
                            st.write(f"❌ Errors: {error_count}")

                        status.update(label=f"✅ Import Complete! ({success_count} imported)", state="complete")

                        # Close dialog
                        st.session_state.show_import_dialog = False
                        st.rerun()

            except json.JSONDecodeError:
                st.error("❌ Invalid JSON file. Please upload a valid patterns export file.")
            except Exception as e:
                st.error(f"❌ Import failed: {str(e)}")

        # Close button
        if st.button("❌ Cancel Import", type="secondary"):
            st.session_state.show_import_dialog = False
            st.rerun()


def show_pattern_manager_page():
    """Entry point for Pattern Manager page."""
    manager = PatternManager()
    manager.render()


if __name__ == "__main__":
    show_pattern_manager_page()
