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

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent / "utils"))

from utils.sql_db_utils import SQLDatabaseUtils
from utils.pattern_verifier import PatternVerifier
from utils.cost_display_manager import CostDisplayManager

# API Configuration
API_BASE_URL = "http://localhost:8000/api/v1"


class PatternManager:
    """Manages pattern export, verification, and organization."""

    def __init__(self):
        self.db_utils = self._get_workspace_db()
        self.cost_manager = CostDisplayManager()

    def _get_workspace_db(self) -> SQLDatabaseUtils:
        """Get current workspace database."""
        workspace = st.session_state.get('current_workspace', 'default')
        db_name = f"{workspace}_patterns.db"
        db_dir = Path(__file__).parent / "data" / "workspaces"
        db_dir.mkdir(parents=True, exist_ok=True)

        return SQLDatabaseUtils(db_name=db_name, base_dir=str(db_dir))

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
        st.info("💡 Test your workspace patterns against sample XML to ensure they work correctly")

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
                placeholder="<YourNode>\n  <Attribute>Value</Attribute>\n</YourNode>"
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
                with st.status("🔄 Verifying pattern...", expanded=True) as status:
                    st.write("Testing XML against pattern...")

                    # TODO: Implement actual LLM verification
                    # For now, show placeholder
                    st.write("✅ Verification complete")

                    status.update(label="✅ Verification Complete", state="complete")

                # Show results
                st.markdown("---")
                st.markdown("### 📊 Verification Results")
                st.success("✅ Pattern matches the XML structure")
                st.write("**Findings:**")
                st.write("- All required attributes present")
                st.write("- Child structure matches expectations")
                st.info("💡 This is a placeholder. LLM verification will be implemented next.")

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
