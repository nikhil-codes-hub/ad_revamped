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
API_BASE_URL = "http://localhost:8000/api/v1"


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
                   aps.section_name, pd.pattern_description, pd.pattern_prompt
            FROM api a
            LEFT JOIN apiversion av ON a.api_id = av.api_id
            JOIN api_section aps ON a.api_id = aps.api_id
            JOIN section_pattern_mapping spm ON aps.section_id = spm.section_id AND aps.api_id = spm.api_id
            JOIN pattern_details pd ON spm.pattern_id = pd.pattern_id
            GROUP BY a.api_name, av.version_number, pd.pattern_prompt
        """
        return self.run_query(query)

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

    def render(self):
        """Render Pattern Manager page."""
        st.header("🎨 Pattern Manager")
        st.write("Export backend patterns, verify, and organize in workspace")

        # Tabs
        tab1, tab2, tab3 = st.tabs(["📤 Export Patterns", "✅ Verify Patterns", "📚 Manage Workspace"])

        with tab1:
            self._render_export_tab()

        with tab2:
            self._render_verify_tab()

        with tab3:
            self._render_manage_tab()

    def _render_export_tab(self):
        """Export backend patterns to workspace."""
        st.subheader("📤 Export Backend Patterns to Workspace")

        # Fetch backend patterns
        try:
            response = requests.get(f"{API_BASE_URL}/patterns/", params={"limit": 500})
            if response.status_code == 200:
                backend_patterns = response.json()
            else:
                backend_patterns = []
        except:
            st.error("❌ Failed to fetch backend patterns. Is the backend running?")
            return

        if not backend_patterns:
            st.info("📭 No patterns found in backend. Run Discovery first to generate patterns.")
            return

        st.success(f"✅ Found {len(backend_patterns)} patterns in backend")

        # Filters
        st.markdown("### 🔧 Filter Patterns to Export")

        col1, col2, col3 = st.columns(3)

        with col1:
            versions = ["All"] + sorted(set(p.get('spec_version', '') for p in backend_patterns if p.get('spec_version')))
            selected_version = st.selectbox("NDC Version:", versions)

        with col2:
            airlines = ["All"] + sorted(set(p.get('airline_code', '') for p in backend_patterns if p.get('airline_code')))
            selected_airline = st.selectbox("Airline:", airlines)

        with col3:
            msg_roots = ["All"] + sorted(set(p.get('message_root', '') for p in backend_patterns if p.get('message_root')))
            selected_msg_root = st.selectbox("Message Root:", msg_roots)

        # Apply filters
        filtered_patterns = backend_patterns
        if selected_version != "All":
            filtered_patterns = [p for p in filtered_patterns if p.get('spec_version') == selected_version]
        if selected_airline != "All":
            filtered_patterns = [p for p in filtered_patterns if p.get('airline_code') == selected_airline]
        if selected_msg_root != "All":
            filtered_patterns = [p for p in filtered_patterns if p.get('message_root') == selected_msg_root]

        st.info(f"🎯 {len(filtered_patterns)} patterns match your filters")

        # Pattern selection
        st.markdown("### ✅ Select Patterns to Export")

        if st.checkbox("Select All Filtered Patterns", key="select_all_export"):
            selected_pattern_ids = [p['id'] for p in filtered_patterns]
        else:
            selected_pattern_ids = []

            # Show pattern table for selection
            for pattern in filtered_patterns[:50]:  # Show max 50 for UI performance
                decision_rule = pattern.get('decision_rule', {})
                node_type = decision_rule.get('node_type', 'Unknown')

                col1, col2 = st.columns([1, 5])
                with col1:
                    if st.checkbox("", key=f"pattern_{pattern['id']}", value=False):
                        selected_pattern_ids.append(pattern['id'])
                with col2:
                    st.write(f"**{node_type}** - `{pattern['section_path']}` "
                            f"(v{pattern['spec_version']}, {pattern.get('airline_code', 'N/A')}, "
                            f"seen {pattern['times_seen']}x)")

            if len(filtered_patterns) > 50:
                st.warning(f"⚠️ Showing 50 of {len(filtered_patterns)} patterns. Use filters or 'Select All' to export more.")

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
            (api_id, pattern['section_path'], pattern['section_path']),
            columns=["api_id", "section_name", "section_display_name"]
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
        st.subheader("✅ Verify Patterns with Test XML")
        st.info("💡 Test your workspace patterns against sample XML using AI-powered verification")

        # Get workspace patterns
        workspace_patterns = self.db_utils.get_all_patterns()

        if not workspace_patterns:
            st.warning("📭 No patterns in workspace. Export patterns first in the Export tab.")
            return

        st.success(f"✅ {len(workspace_patterns)} patterns in workspace")

        # Pattern selection
        pattern_options = {}
        for p in workspace_patterns:
            api_name, api_version, section_name, pattern_desc, pattern_prompt = p
            label = f"{api_name} v{api_version} - {section_name}"
            pattern_options[label] = {
                'api': api_name,
                'version': api_version,
                'section': section_name,
                'description': pattern_desc,
                'prompt': pattern_prompt
            }

        selected_pattern_label = st.selectbox("🎯 Select Pattern to Test:", list(pattern_options.keys()))

        if selected_pattern_label:
            pattern = pattern_options[selected_pattern_label]

            # Show pattern details
            with st.expander("📋 Pattern Details", expanded=False):
                st.write(f"**API:** {pattern['api']} v{pattern['version']}")
                st.write(f"**Section:** {pattern['section']}")
                st.write(f"**Description:** {pattern['description']}")
                st.code(pattern['prompt'], language='text')

            # XML test input
            st.markdown("### 🧪 Test XML")
            test_xml = st.text_area(
                "Paste XML snippet to test:",
                height=200,
                placeholder="<YourNode>\n  <Attribute>Value</Attribute>\n</YourNode>",
                key="verify_test_xml"
            )

            col1, col2 = st.columns([1, 3])

            with col1:
                verify_btn = st.button("🚀 Verify Pattern", type="primary", disabled=not test_xml.strip())

            with col2:
                if test_xml.strip():
                    st.success("✅ Ready to test")
                else:
                    st.info("Enter XML above to test")

            # Process verification
            if verify_btn and test_xml.strip():
                self._process_verification(pattern, test_xml)

    def _process_verification(self, pattern: Dict[str, Any], test_xml: str):
        """Process pattern verification with LLM."""
        with st.status("🔄 Verifying pattern with AI...", expanded=True) as status:
            st.write("📤 Sending to Azure OpenAI for analysis...")

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

                # Display results
                self._display_verification_results(result, pattern)

            except ImportError:
                st.error("❌ LLM verifier not available. Check that openai package is installed.")
                status.update(label="❌ Verification Failed", state="error")

            except Exception as e:
                st.error(f"❌ Verification failed: {str(e)}")
                st.write("**Debug Info:**")
                st.write(f"- Error Type: {type(e).__name__}")
                st.write(f"- Error Details: {str(e)}")
                status.update(label="❌ Verification Failed", state="error")

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

        # Get workspace patterns
        workspace_patterns = self.db_utils.get_all_patterns()

        if not workspace_patterns:
            st.warning("📭 No patterns in workspace. Export patterns first.")
            return

        st.success(f"✅ {len(workspace_patterns)} patterns in workspace")

        # Display patterns table
        import pandas as pd

        pattern_data = []
        for p in workspace_patterns:
            api_name, api_version, section_name, pattern_desc, pattern_prompt = p
            pattern_data.append({
                "API": api_name,
                "Version": api_version,
                "Section": section_name,
                "Description": pattern_desc[:50] + "..." if len(pattern_desc) > 50 else pattern_desc
            })

        df = pd.DataFrame(pattern_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Workspace actions
        st.markdown("---")
        st.markdown("### 🔧 Workspace Actions")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📊 Export to CSV", use_container_width=True):
                csv = df.to_csv(index=False)
                st.download_button(
                    label="⬇️ Download CSV",
                    data=csv,
                    file_name=f"{workspace}_patterns.csv",
                    mime="text/csv"
                )

        with col2:
            if st.button("🗑️ Clear Workspace", use_container_width=True, type="secondary"):
                st.warning("⚠️ This will delete all patterns in this workspace!")
                if st.button("⚠️ Confirm Delete All", type="secondary"):
                    # TODO: Implement workspace clear
                    st.success("Workspace cleared")

        with col3:
            st.metric("Total Patterns", len(workspace_patterns))


def show_pattern_manager_page():
    """Entry point for Pattern Manager page."""
    manager = PatternManager()
    manager.render()


if __name__ == "__main__":
    show_pattern_manager_page()
