"""
AssistedDiscovery Streamlit UI

Clean table-based interface with sidebar navigation.
"""

import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import json
from streamlit_tree_select import tree_select

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"
HEALTH_URL = "http://localhost:8000/health"


workspace_config_file = Path(__file__).parent / "data" / "workspaces" / "workspaces.json"


def load_workspaces() -> List[str]:
    """Load workspaces from disk or return defaults."""
    if workspace_config_file.exists():
        try:
            return json.loads(workspace_config_file.read_text())
        except Exception:
            pass
    return ["default", "LATAM", "LH", "SQ", "VY", "AFKL"]


def save_workspaces(workspaces: List[str]) -> None:
    """Persist workspace list to disk."""
    workspace_config_file.parent.mkdir(parents=True, exist_ok=True)
    workspace_config_file.write_text(json.dumps(workspaces, indent=2))


def check_api_health() -> bool:
    """Check if the FastAPI backend is running."""
    try:
        response = requests.get(HEALTH_URL, timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def build_node_tree(nodes: List[Dict]) -> List[Dict]:
    """
    Convert flat node list to hierarchical tree structure for streamlit-tree-select.

    Args:
        nodes: List of node dicts with 'section_path', 'node_type', 'enabled', etc.

    Returns:
        List of tree nodes in format: {"label": str, "value": str, "children": []}
    """
    if not nodes:
        return []

    # Build a dictionary mapping section_path to node (with temporary children list)
    path_to_node = {}
    for node in nodes:
        path = node['section_path']
        path_to_node[path] = {
            "label": node['node_type'],
            "value": path,
            "_children": []  # Temporary field
        }

    # Build tree hierarchy
    root_nodes = []
    for path in sorted(path_to_node.keys()):  # Sort to ensure parents come before children
        parts = path.split('/')
        if len(parts) == 1:
            # This is a root node
            root_nodes.append(path_to_node[path])
        else:
            # Find parent and add as child
            parent_path = '/'.join(parts[:-1])
            if parent_path in path_to_node:
                path_to_node[parent_path]['_children'].append(path_to_node[path])

    # Convert _children to children (only if non-empty) and remove the field
    def finalize_tree(node_list):
        for node in node_list:
            children = node.pop('_children', [])
            if children:
                finalize_tree(children)  # Recursively finalize children
                node['children'] = children
            # If no children, don't add the field at all
        return node_list

    return finalize_tree(root_nodes)


def flatten_tree_values(nodes: List[Dict[str, Any]]) -> List[str]:
    """Return a flat list of all node values found in a tree-select node structure."""
    values: List[str] = []
    for node in nodes:
        value = node.get('value')
        if value:
            values.append(value)
        children = node.get('children') or []
        if children:
            values.extend(flatten_tree_values(children))
    return values


def _path_ancestors(path: str) -> List[str]:
    parts = path.split('/')
    return ['/'.join(parts[:i]) for i in range(1, len(parts)) if parts[:i]]


def filter_raw_paths(raw_paths: List[str], previous_raw: Optional[List[str]] = None,
                     previous_effective: Optional[List[str]] = None) -> List[str]:
    """Remove auto-selected descendants when parent is newly chosen."""
    unique_paths = list(dict.fromkeys(raw_paths or []))
    prev_selected = set(previous_raw or []) | set(previous_effective or [])
    raw_set = set(unique_paths)

    filtered = []
    for path in unique_paths:
        has_parent_selected = any(parent in raw_set for parent in _path_ancestors(path))
        if has_parent_selected and path not in prev_selected:
            continue  # Skip descendants implicitly checked via parent
        filtered.append(path)

    return filtered


def compute_effective_paths(raw_paths: List[str],
                            previous_effective: Optional[List[str]] = None,
                            previous_raw: Optional[List[str]] = None) -> List[str]:
    """Compute effective enabled paths based on filtered raw selections and prior state."""

    filtered_raw = filter_raw_paths(raw_paths, previous_raw, previous_effective)
    prev_paths = previous_effective or []

    raw_set = set(filtered_raw)
    prev_set = set(prev_paths)
    final_set = set(prev_paths)

    # Remove entries explicitly unchecked (no descendants selected)
    removed_paths = prev_set - raw_set
    for path in removed_paths:
        has_descendant = any(desc == path or desc.startswith(f"{path}/") for desc in raw_set)
        if not has_descendant:
            final_set.discard(path)

    # Add newly checked nodes
    final_set.update(raw_set)

    # When child selected without parent previously, ensure parent stays disabled
    for path in list(final_set):
        for parent in _path_ancestors(path):
            if parent in final_set and parent not in prev_set and parent not in raw_set:
                final_set.discard(parent)

    ordered: List[str] = []

    for path in prev_paths:
        if path in final_set and path not in ordered:
            ordered.append(path)

    for path in filtered_raw:
        if path in final_set and path not in ordered:
            ordered.append(path)

    # Add any remaining (e.g., parents restored due to descendants) by depth
    for path in sorted(final_set, key=lambda p: (p.count('/'), p)):
        if path not in ordered:
            ordered.append(path)

    return ordered


def merge_existing_configs(result: Dict[str, Any], workspace: Optional[str] = None) -> Dict[str, Any]:
    """Merge existing node configurations from API into analyzed nodes."""
    if not result or 'spec_version' not in result or 'message_root' not in result:
        return result

    configs_data = get_node_configurations(
        spec_version=result.get('spec_version'),
        message_root=result.get('message_root'),
        airline_code=result.get('airline_code'),
        workspace=workspace
    )

    if not configs_data or not configs_data.get('configurations'):
        return result

    config_map = {}
    for cfg in configs_data['configurations']:
        section_path = cfg.get('section_path')
        if section_path:
            config_map[section_path] = cfg

    for node in result.get('nodes', []):
        cfg = config_map.get(node.get('section_path'))
        if not cfg:
            continue

        config_id = cfg.get('config_id') or cfg.get('id')
        if config_id:
            node['config_id'] = config_id

        if 'enabled' in cfg:
            node['enabled'] = cfg['enabled']
        if 'expected_references' in cfg:
            node['expected_references'] = cfg['expected_references'] or []
        if 'ba_remarks' in cfg:
            node['ba_remarks'] = cfg['ba_remarks'] or ''

    return result


def upload_file_for_run(file, run_kind: str, workspace: str = "default", target_version: Optional[str] = None, target_message_root: Optional[str] = None, target_airline_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Upload file and create a new run."""
    try:
        files = {"file": (file.name, file.getvalue(), "application/xml")}
        params = {
            "kind": run_kind,
            "workspace": workspace
        }

        # Add optional filters for identify runs
        if target_version:
            params["target_version"] = target_version
        if target_message_root:
            params["target_message_root"] = target_message_root
        if target_airline_code:
            params["target_airline_code"] = target_airline_code

        response = requests.post(
            f"{API_BASE_URL}/runs/",
            files=files,
            params=params,
            timeout=300
        )

        if response.status_code == 200:
            return response.json()
        else:
            # Try to extract detailed error message from response
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', response.text)
            except:
                error_detail = response.text

            st.error(f"❌ **Upload Failed** (Status {response.status_code})")
            st.error(f"{error_detail}")

            # Show helpful hints based on error content
            if "API" in str(error_detail) or "LLM" in str(error_detail):
                st.info("💡 **Troubleshooting Tips:**\n"
                       "- Check your `.env` file has correct API keys\n"
                       "- Verify AZURE_OPENAI_KEY or OPENAI_API_KEY is set\n"
                       "- Check AZURE_OPENAI_ENDPOINT is correct\n"
                       "- Review backend logs for detailed error messages")
            elif "XML" in str(error_detail):
                st.info("💡 **Troubleshooting Tips:**\n"
                       "- Verify the XML file is well-formed\n"
                       "- Check if the file is a valid NDC OrderViewRS\n"
                       "- Try opening the XML in a validator first")

            return None

    except requests.exceptions.Timeout:
        st.error(f"❌ **Request Timeout**: The server took too long to respond")
        st.info("💡 The XML file might be too large. Try with a smaller file.")
        return None

    except requests.exceptions.ConnectionError as e:
        st.error(f"❌ **Connection Error**: Cannot reach the backend server")
        st.error(f"Details: {str(e)}")
        st.info("💡 Make sure the backend is running: `uvicorn app.main:app --reload`")
        return None

    except requests.exceptions.RequestException as e:
        st.error(f"❌ **Request Error**: {str(e)}")
        return None


def get_runs(kind: Optional[str] = None, limit: int = 50, workspace: str = "default") -> List[Dict[str, Any]]:
    """Get list of runs."""
    try:
        params = {
            "limit": limit,
            "workspace": workspace
        }
        if kind:
            params["kind"] = kind

        response = requests.get(
            f"{API_BASE_URL}/runs/",
            params=params,
            timeout=15
        )
        if response.status_code == 200:
            return response.json()
        return []
    except requests.exceptions.RequestException:
        return []


def get_run_status(run_id: str, workspace: str = "default") -> Optional[Dict[str, Any]]:
    """Get status of a specific run."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/runs/{run_id}",
            params={"workspace": workspace},
            timeout=15
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def get_node_facts(run_id: str, limit: int = 100, workspace: str = "default") -> List[Dict[str, Any]]:
    """Get node facts for a run."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/node_facts/",
            params={"run_id": run_id, "limit": limit, "workspace": workspace},
            timeout=15
        )
        if response.status_code == 200:
            return response.json()
        return []
    except requests.exceptions.RequestException:
        return []


def get_identify_matches(run_id: str, limit: int = 100) -> Optional[Dict[str, Any]]:
    """Get pattern matching results for an identify run."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/identify/{run_id}/matches",
            params={"limit": limit},
            timeout=15
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def get_gap_analysis(run_id: str) -> Optional[Dict[str, Any]]:
    """Get gap analysis for an identify run."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/identify/{run_id}/gap-analysis",
            timeout=15
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def get_detailed_explanation(match_id: int) -> Optional[Dict[str, Any]]:
    """Generate detailed LLM explanation for a pattern match."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/identify/matches/{match_id}/explain",
            timeout=30  # LLM calls may take longer
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error generating explanation: {str(e)}")
        return None


def get_patterns(limit: int = 100, run_id: Optional[str] = None, workspace: str = "default") -> List[Dict[str, Any]]:
    """Get all patterns, optionally filtered by run_id."""
    try:
        params = {"limit": limit, "workspace": workspace}
        if run_id:
            params["run_id"] = run_id

        response = requests.get(
            f"{API_BASE_URL}/patterns/",
            params=params,
            timeout=15
        )
        if response.status_code == 200:
            return response.json()
        return []
    except requests.exceptions.RequestException:
        return []


def detect_version_and_airline(file) -> Optional[Dict[str, Any]]:
    """Fast detection of NDC version and airline from XML."""
    try:
        files = {"file": (file.name, file.getvalue(), "application/xml")}
        response = requests.post(
            f"{API_BASE_URL}/node-configs/analyze",
            files=files,
            timeout=15
        )
        if response.status_code == 200:
            result = response.json()
            # Return only version and airline info
            return {
                'spec_version': result.get('spec_version'),
                'message_root': result.get('message_root'),
                'airline_code': result.get('airline_code')
            }
        return None
    except requests.exceptions.RequestException:
        return None


def analyze_xml_for_nodes(file, workspace: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Upload XML and analyze its structure for node configuration."""
    try:
        files = {"file": (file.name, file.getvalue(), "application/xml")}
        response = requests.post(
            f"{API_BASE_URL}/node-configs/analyze",
            files=files,
            params={"workspace": workspace} if workspace else None,
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def get_node_configurations(spec_version: Optional[str] = None,
                            message_root: Optional[str] = None,
                            airline_code: Optional[str] = None,
                            workspace: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get node configurations with optional filtering."""
    try:
        params = {"limit": 500}
        if spec_version:
            params["spec_version"] = spec_version
        if message_root:
            params["message_root"] = message_root
        if airline_code:
            params["airline_code"] = airline_code
        if workspace:
            params["workspace"] = workspace

        response = requests.get(
            f"{API_BASE_URL}/node-configs/",
            params=params,
            timeout=15
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def bulk_update_node_configurations(configurations: List[Dict[str, Any]], workspace: Optional[str] = None) -> bool:
    """Bulk update node configurations."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/node-configs/bulk-update",
            json=configurations,
            params={"workspace": workspace} if workspace else None,
            timeout=30
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def get_relationships(run_id: Optional[str] = None,
                     reference_type: Optional[str] = None,
                     is_valid: Optional[bool] = None) -> Optional[List[Dict[str, Any]]]:
    """Get discovered relationships with optional filtering."""
    try:
        params = {"limit": 500}
        if run_id:
            params["run_id"] = run_id
        if reference_type:
            params["reference_type"] = reference_type
        if is_valid is not None:
            params["is_valid"] = is_valid

        response = requests.get(
            f"{API_BASE_URL}/relationships/",
            params=params,
            timeout=15
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def get_relationship_summary(run_id: str, workspace: str = "default") -> Optional[Dict[str, Any]]:
    """Get comprehensive relationship summary for a run."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/relationships/run/{run_id}/summary",
            params={"workspace": workspace},
            timeout=15
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def copy_configurations_to_versions(
    source_spec_version: str,
    source_message_root: str,
    target_versions: List[str],
    source_airline_code: Optional[str] = None,
    target_airline_code: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Copy configurations from one version to multiple other versions."""
    try:
        # Build query parameters (FastAPI will parse List[str] from query params)
        params = {
            "source_spec_version": source_spec_version,
            "source_message_root": source_message_root,
        }

        # Add target_versions as multiple query params (e.g., ?target_versions=17.2&target_versions=19.2)
        query_string = f"source_spec_version={source_spec_version}&source_message_root={source_message_root}"
        for version in target_versions:
            query_string += f"&target_versions={version}"

        if source_airline_code:
            query_string += f"&source_airline_code={source_airline_code}"
        if target_airline_code:
            query_string += f"&target_airline_code={target_airline_code}"

        response = requests.post(
            f"{API_BASE_URL}/node-configs/copy-to-versions?{query_string}",
            timeout=30
        )

        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Request failed: {str(e)}")
        return None


# ========== PAGE FUNCTIONS ==========

def show_discovery_page():
    """Discovery page - run discovery and view results."""
    st.header("🔬 Discovery Mode")
    st.write("Upload XML files to learn and extract patterns")

    current_workspace = st.session_state.get('current_workspace', 'default')

    # Initialize session state
    if 'discovery_selected_run' not in st.session_state:
        st.session_state.discovery_selected_run = None

    # Upload section
    st.subheader("📤 Upload XML for Discovery")
    uploaded_file = st.file_uploader("Choose an NDC XML file", type=['xml'], key="discovery_upload")

    if uploaded_file:
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.write(f"**Filename:** {uploaded_file.name}")
            st.write(f"**Size:** {uploaded_file.size:,} bytes")
        with col2:
            if st.button("📋 Show Configured Nodes", help="View configured nodes for this XML", use_container_width=True):
                # Detect version and airline from XML
                with st.spinner("Analyzing XML..."):
                    detect_result = detect_version_and_airline(uploaded_file)

                if detect_result:
                    st.session_state.discovery_detect_result = detect_result
                    st.rerun()
        with col3:
            if 'discovery_detect_result' in st.session_state:
                if st.button("🔄 Clear", help="Clear detection and upload new file", use_container_width=True):
                    del st.session_state.discovery_detect_result
                    st.rerun()

        # Show configured nodes table if detection was done
        if 'discovery_detect_result' in st.session_state:
            detect_result = st.session_state.discovery_detect_result

            st.divider()
            st.subheader("⚙️ Configured Nodes for This File")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Version", detect_result.get('spec_version', 'Unknown'))
            with col2:
                st.metric("Message", detect_result.get('message_root', 'Unknown'))
            with col3:
                st.metric("Airline", detect_result.get('airline_code', 'Global'))

            # Fetch configured nodes for this version/message/airline
            configs_data = get_node_configurations(
                spec_version=detect_result.get('spec_version'),
                message_root=detect_result.get('message_root'),
                airline_code=detect_result.get('airline_code'),
                workspace=current_workspace
            )

            if configs_data and configs_data.get('configurations'):
                configs = configs_data['configurations']
                enabled_configs = [c for c in configs if c.get('enabled')]

                st.info(f"✅ Found {len(enabled_configs)} enabled node(s) configured for extraction")

                # Build tree structure from configurations
                # Convert configs to node format for tree building
                nodes_for_tree = [
                    {
                        'section_path': cfg['section_path'],
                        'node_type': cfg['node_type'],
                        'enabled': cfg.get('enabled', False)
                    }
                    for cfg in configs
                ]

                if nodes_for_tree:
                    tree_data = build_node_tree(nodes_for_tree)

                    # Get list of enabled node paths for checked display
                    enabled_paths = [cfg['section_path'] for cfg in configs if cfg.get('enabled')]

                    col1, col2 = st.columns([1, 1])

                    with col1:
                        st.write("**🌳 Node Hierarchy**")
                        st.caption(f"✅ Checked = Enabled ({len(enabled_paths)} nodes)")
                        st.caption("ℹ️ View-only. Edit in Node Manager →")

                        # Display tree with enabled nodes checked (read-only display)
                        tree_select(
                            tree_data,
                            checked=enabled_paths,
                            only_leaf_checkboxes=False,
                            expand_on_click=True,
                            no_cascade=True,
                            expanded=[node['value'] for node in tree_data if node.get('value')],
                            disabled=True,
                            key="discovery_config_tree"
                        )

                    with col2:
                        st.write("**📋 Enabled Node Details**")

                        if enabled_configs:
                            st.caption(f"Showing {len(enabled_configs)} enabled nodes")

                            for cfg in enabled_configs[:10]:  # Show first 10
                                with st.expander(f"**{cfg['node_type']}**", expanded=False):
                                    st.write(f"**Path:** `{cfg['section_path']}`")

                                    if cfg.get('expected_references'):
                                        st.write(f"**Expected References:**")
                                        for ref in cfg['expected_references']:
                                            st.write(f"  • `{ref}`")

                                    if cfg.get('ba_remarks'):
                                        st.write(f"**BA Remarks:** {cfg['ba_remarks']}")

                            if len(enabled_configs) > 10:
                                st.caption(f"...and {len(enabled_configs) - 10} more")
                        else:
                            st.info("No nodes enabled")
                else:
                    st.warning("⚠️ No nodes are configured. Please configure nodes in the Node Manager.")
            else:
                st.warning(f"⚠️ No configurations found for {detect_result.get('spec_version')}/{detect_result.get('message_root')}/{detect_result.get('airline_code', 'Global')}")
                st.info("💡 Go to **Node Manager** to configure nodes for this version/airline.")

            st.divider()

        # Start Discovery button
        col1, col2, col3 = st.columns(3)
        with col2:
            if st.button("🚀 Start Discovery", type="primary", key="start_discovery", use_container_width=True):
                import time
                progress_bar = st.progress(0)
                status_text = st.empty()

                # Step 1: Upload
                status_text.text("📤 Uploading XML file to backend...")
                progress_bar.progress(5)
                time.sleep(0.3)

                status_text.text("🔍 Analysing XML, detecting root and version...")
                progress_bar.progress(10)
                time.sleep(0.2)

                status_text.text("🔍 Detecting NDC version...")
                progress_bar.progress(10)
                time.sleep(0.2)

                status_text.text("🔍 Analyzing relationships..")
                progress_bar.progress(30)
                
                time.sleep(5.0)

                status_text.text("🔍 Extracting patterns, please wait!...")
                progress_bar.progress(30)
                time.sleep(5.0)

                # Step 2: Start processing
                result = upload_file_for_run(uploaded_file, "discovery", workspace=current_workspace)

                if result:
                    # Check if there was an error during processing
                    if result.get('error_details'):
                        status_text.empty()
                        progress_bar.empty()

                        st.error(f"❌ **Discovery Failed**")
                        st.error(f"**Error:** {result['error_details']}")

                        # Show helpful hints based on error content
                        error_detail = result['error_details']
                        if "LLM" in error_detail or "API" in error_detail:
                            st.info("💡 **LLM/API Error - Troubleshooting:**\n"
                                   "- Check backend logs for detailed error messages\n"
                                   "- Verify `.env` file has correct API keys:\n"
                                   "  - AZURE_OPENAI_KEY + AZURE_OPENAI_ENDPOINT (for Azure)\n"
                                   "  - OPENAI_API_KEY (for OpenAI)\n"
                                   "- Test your API credentials independently\n"
                                   "- Check if you have exceeded rate limits")
                        elif "XML" in error_detail:
                            st.info("💡 **XML Parsing Error - Troubleshooting:**\n"
                                   "- Verify the XML file is well-formed\n"
                                   "- Check if the file is valid NDC OrderViewRS format\n"
                                   "- Try validating the XML with an online validator\n"
                                   "- Look for unclosed tags or special characters")
                        else:
                            st.info("💡 **Troubleshooting:**\n"
                                   "- Check backend logs for full error details\n"
                                   "- Run: `tail -f backend_logs.txt` or check console output\n"
                                   "- Contact support with the Run ID above")

                        st.info(f"📋 **Run ID:** `{result['id']}` (check logs with this ID)")

                    else:
                        # Step 3: Processing events
                        status_text.text("📋 Parsing XML structure...")
                        progress_bar.progress(30)
                        time.sleep(0.2)

                        status_text.text("🤖 LLM extracting NodeFacts...")
                        progress_bar.progress(50)
                        time.sleep(0.3)

                        status_text.text("🧠 Applying business intelligence...")
                        progress_bar.progress(70)
                        time.sleep(0.2)

                        status_text.text("🏗️ Generating patterns...")
                        progress_bar.progress(85)
                        time.sleep(0.2)

                        status_text.text("💾 Saving to database...")
                        progress_bar.progress(95)
                        time.sleep(0.2)

                        status_text.text("✅ Discovery completed!")
                        progress_bar.progress(100)

                        st.success(f"✅ Discovery completed! Run ID: {result['id']}")

                        # Show warning if no node configurations were found
                        if result.get('warning'):
                            st.warning(f"⚠️ {result['warning']}")

                        st.session_state.discovery_selected_run = result['id']
                        st.rerun()

    st.divider()

    # Show results from current session
    if st.session_state.discovery_selected_run:
        run_id = st.session_state.discovery_selected_run
        st.success(f"📊 Discovery Results (Run: {run_id[:12]}...)")
        show_discovery_run_details(run_id, current_workspace)
    else:
        st.info("👆 Upload an XML file above to see discovery results")



def show_discovery_run_details(run_id: str, workspace: str = "default"):
    """Show detailed view of a discovery run."""
    run_details = get_run_status(run_id, workspace)

    if not run_details:
        st.error("Failed to load run details")
        return

    # Summary metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Status", run_details["status"])
    with col2:
        st.metric("Version", run_details["spec_version"])
    with col3:
        airline_display = run_details.get("airline_code", "N/A")
        if run_details.get("airline_name"):
            airline_display = f"{run_details['airline_code']}"
        st.metric("Airline", airline_display)
    with col4:
        st.metric("NodeFacts", run_details.get("node_facts_count", 0))
    with col5:
        st.metric("Duration", f"{run_details.get('duration_seconds', 0)}s")

    st.divider()

    # Patterns generated section
    st.subheader("📚 Patterns Generated")
    patterns = get_patterns(limit=200, run_id=run_id, workspace=workspace)

    if patterns:
        col1, col2 = st.columns([3, 1])

        with col1:
            st.success(f"✅ {len(patterns)} pattern(s) extracted and saved from this discovery run")

        with col2:
            if st.button("View in Pattern Explorer", type="secondary"):
                st.session_state.page = "📚 Pattern Explorer"
                st.rerun()

        # Quick preview of patterns
        pattern_preview = []
        for p in patterns[:10]:  # Show top 10
            decision_rule = p.get('decision_rule', {})
            pattern_preview.append({
                "Node Type": decision_rule.get('node_type', 'Unknown'),
                "Version": p.get('spec_version', 'N/A'),
                "Airline": p.get('airline_code', 'N/A'),
                "Section Path": p['section_path'],
                "Must-Have Attrs": len(decision_rule.get('must_have_attributes', [])),
                "Has Children": "✓" if decision_rule.get('child_structure', {}).get('has_children') else "",
            })

        df_patterns = pd.DataFrame(pattern_preview)
        st.dataframe(df_patterns, use_container_width=True, hide_index=True)

        if len(patterns) > 10:
            st.info(f"Showing 10 of {len(patterns)} patterns. View all in Pattern Explorer →")
    else:
        st.info("No patterns generated yet. Patterns are created during the pattern generation phase.")

    st.divider()

    # Relationships section
    st.subheader("🔗 Discovered Relationships")
    rel_summary = get_relationship_summary(run_id, workspace)

    if rel_summary and rel_summary.get('statistics', {}).get('total_relationships', 0) > 0:
        stats = rel_summary['statistics']

        # Display metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total", stats['total_relationships'])
        with col2:
            st.metric("✅ Valid", stats['valid_relationships'])
        with col3:
            st.metric("❌ Broken", stats['broken_relationships'])
        with col4:
            st.metric("Expected", stats['expected_relationships'])
        with col5:
            st.metric("🔍 Discovered", stats['discovered_relationships'])

        # Validation rate
        if stats['total_relationships'] > 0:
            validation_rate = stats.get('validation_rate', 0)
            if validation_rate >= 90:
                st.success(f"✅ {validation_rate}% of relationships are valid")
            elif validation_rate >= 70:
                st.warning(f"⚠️ {validation_rate}% of relationships are valid")
            else:
                st.error(f"❌ Only {validation_rate}% of relationships are valid")

        # Reference type breakdown
        st.write("**Reference Types Breakdown:**")
        ref_types = rel_summary.get('reference_types', {})

        if ref_types:
            type_data = []
            for ref_type, counts in ref_types.items():
                type_data.append({
                    "Reference Type": ref_type,
                    "Total": counts['total'],
                    "Valid": counts['valid'],
                    "Broken": counts['broken'],
                    "Expected": counts['expected'],
                    "Discovered": counts['discovered']
                })

            df_types = pd.DataFrame(type_data)
            st.dataframe(df_types, use_container_width=True, hide_index=True)

        # Broken references table
        broken_refs = rel_summary.get('broken_references', [])
        if broken_refs:
            st.warning(f"⚠️ {len(broken_refs)} broken reference(s) found")

            with st.expander("View Broken References", expanded=False):
                broken_data = []
                for br in broken_refs:
                    status = "Expected" if br.get('was_expected') else "Discovered"
                    broken_data.append({
                        "Source": br['source'],
                        "→ Target": br['target'],
                        "Type": br['reference_type'],
                        "Field": br.get('reference_field', 'N/A'),
                        "Value": br.get('reference_value', 'N/A'),
                        "Status": status
                    })

                df_broken = pd.DataFrame(broken_data)
                st.dataframe(df_broken, use_container_width=True, hide_index=True)

        # Unexpected discoveries table
        discoveries = rel_summary.get('unexpected_discoveries', [])
        if discoveries:
            st.info(f"🔍 {len(discoveries)} unexpected relationship(s) discovered by LLM")

            with st.expander("View Unexpected Discoveries", expanded=False):
                disc_data = []
                for d in discoveries:
                    status = "✅ Valid" if d.get('is_valid') else "❌ Broken"
                    conf = d.get('confidence')
                    conf_str = f"{conf:.0%}" if conf is not None else "N/A"

                    disc_data.append({
                        "Source": d['source'],
                        "→ Target": d['target'],
                        "Type": d['reference_type'],
                        "Field": d.get('reference_field', 'N/A'),
                        "Confidence": conf_str,
                        "Status": status
                    })

                df_disc = pd.DataFrame(disc_data)
                st.dataframe(df_disc, use_container_width=True, hide_index=True)

        # Full relationships table
        with st.expander("📊 All Relationships", expanded=False):
            all_rels = get_relationships(run_id=run_id)

            if all_rels:
                rel_data = []
                for r in all_rels:
                    status_icon = "✅" if r.get('is_valid') else "❌"
                    origin_icon = "📋" if r.get('was_expected') else "🔍"
                    conf = r.get('confidence')
                    conf_str = f"{conf:.0%}" if conf is not None else "N/A"

                    rel_data.append({
                        "": f"{status_icon} {origin_icon}",
                        "Source": r['source_node_type'],
                        "→ Target": r['target_node_type'],
                        "Type": r['reference_type'],
                        "Field": r.get('reference_field', 'N/A'),
                        "Value": r.get('reference_value', 'N/A'),
                        "Confidence": conf_str
                    })

                df_all = pd.DataFrame(rel_data)
                st.dataframe(df_all, use_container_width=True, hide_index=True)

                st.caption("Legend: ✅ Valid | ❌ Broken | 📋 Expected | 🔍 Discovered")
            else:
                st.info("No relationship details available")
    else:
        st.info("No relationships analyzed yet. Relationships are discovered during the Discovery workflow.")

    st.divider()

    # NodeFacts table
    st.subheader("📋 Extracted NodeFacts")
    node_facts = get_node_facts(run_id, limit=200, workspace=workspace)

    if node_facts:
        nf_data = []
        for nf in node_facts:
            fact_json = nf.get("fact_json", {})

            # Get relationship info
            relationships = fact_json.get("relationships", [])
            ref_summary = ""
            if relationships:
                ref_types = [r.get("type", "ref") for r in relationships]
                ref_summary = f"{len(relationships)} refs: {', '.join(set(ref_types[:3]))}"

            nf_data.append({
                "Node Type": nf["node_type"],
                "Section Path": nf["section_path"],
                "Attributes": len(fact_json.get("attributes", {})),
                "Children": len(fact_json.get("children", [])),
                "References": ref_summary if ref_summary else "-",
                "Has BI": "✓" if fact_json.get("business_intelligence") else "",
                "Confidence": f"{fact_json.get('confidence', 0):.0%}"
            })

        df_nf = pd.DataFrame(nf_data)
        st.dataframe(df_nf, use_container_width=True, hide_index=True)

        # Detailed view for selected NodeFact
        st.divider()
        st.subheader("🔎 NodeFact Details")

        nf_options = {f"ID {nf['id']} - {nf['node_type']}": nf for nf in node_facts}
        selected_nf = st.selectbox("Select NodeFact:", list(nf_options.keys()))

        if selected_nf:
            nf = nf_options[selected_nf]
            fact_json = nf.get("fact_json", {})

            col1, col2 = st.columns(2)

            with col1:
                st.write("**Attributes:**")
                attrs = fact_json.get("attributes", {})
                if attrs:
                    st.json(attrs)
                else:
                    st.info("No attributes")

                st.write("**Relationships:**")
                relationships = fact_json.get("relationships", [])
                if relationships:
                    for rel in relationships:
                        ref_type = rel.get("type", "reference")
                        target_path = rel.get("target_section_path", "unknown")
                        target_type = rel.get("target_type", "unknown")
                        st.write(f"- **{ref_type}** → `{target_type}` at `{target_path}`")
                else:
                    st.info("No relationships")

            with col2:
                st.write("**Business Intelligence:**")
                bi = fact_json.get("business_intelligence", {})
                if bi:
                    st.json(bi)
                else:
                    st.info("No business intelligence")
    else:
        st.info("No NodeFacts found for this run")


def show_identify_page(current_workspace: Optional[str] = None):
    """Identify page - match patterns and view results."""
    if current_workspace is None:
        current_workspace = st.session_state.get('current_workspace', 'default')
    st.header("🎯 Identify Mode")
    st.write("Upload XML files to match against learned patterns")

    # Initialize session state to track current session's run only
    if 'identify_current_run' not in st.session_state:
        st.session_state.identify_current_run = None

    # Upload section
    with st.expander("📤 Upload XML for Identification", expanded=True):
        uploaded_file = st.file_uploader("Choose an NDC XML file", type=['xml'], key="identify_upload")

        if uploaded_file:
            # Get available patterns to populate filters
            all_patterns = get_patterns(limit=200)
            available_versions = sorted(set(p.get('spec_version', '') for p in all_patterns if p.get('spec_version')))
            available_msg_roots = sorted(set(p.get('message_root', '') for p in all_patterns if p.get('message_root')))
            available_airlines = sorted(set(p.get('airline_code', '') for p in all_patterns if p.get('airline_code')))

            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Filename:** {uploaded_file.name}")
                st.write(f"**Size:** {uploaded_file.size:,} bytes")
            with col2:
                st.write("**Match Against:**")
                target_version = st.selectbox(
                    "🏷️ NDC Version:",
                    options=["Auto-detect (from XML)"] + available_versions,
                    key="identify_target_version"
                )
                target_msg_root = st.selectbox(
                    "📋 Message Root:",
                    options=["Auto-detect (from XML)"] + available_msg_roots,
                    key="identify_target_msg_root"
                )
                target_airline = st.selectbox(
                    "✈️ Airline:",
                    options=["Auto-detect (from XML)"] + available_airlines,
                    key="identify_target_airline"
                )

            if st.button("Start Identify", type="primary", key="start_identify"):
                    import time
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    # Prepare filter parameters
                    filter_version = None if target_version == "Auto-detect (from XML)" else target_version
                    filter_msg_root = None if target_msg_root == "Auto-detect (from XML)" else target_msg_root
                    filter_airline = None if target_airline == "Auto-detect (from XML)" else target_airline

                    status_text.text("📤 Uploading XML file to backend...")
                    progress_bar.progress(5)
                    time.sleep(0.3)

                    status_text.text("🔍 Detecting NDC version...")
                    progress_bar.progress(10)
                    time.sleep(0.2)

                    result = upload_file_for_run(
                        uploaded_file,
                        "identify",
                        workspace=current_workspace,
                        target_version=filter_version,
                        target_message_root=filter_msg_root,
                        target_airline_code=filter_airline
                    )

                    if result:
                        status_text.text("📋 Parsing XML structure...")
                        progress_bar.progress(25)
                        time.sleep(0.2)

                        status_text.text("🤖 LLM extracting NodeFacts...")
                        progress_bar.progress(45)
                        time.sleep(0.3)

                        status_text.text("🎯 Matching against patterns...")
                        progress_bar.progress(70)
                        time.sleep(0.3)

                        status_text.text("📊 Calculating confidence scores...")
                        progress_bar.progress(85)
                        time.sleep(0.2)

                        status_text.text("💾 Saving match results...")
                        progress_bar.progress(95)
                        time.sleep(0.2)

                        status_text.text("✅ Identify completed!")
                        progress_bar.progress(100)

                        st.success(f"✅ Identify completed! Run ID: {result['id']}")
                        # Store the current run ID in session
                        st.session_state.identify_current_run = result['id']
                        st.rerun()

    st.divider()

    # Only show results from the current session
    if st.session_state.identify_current_run:
        run_id = st.session_state.identify_current_run
        st.success("📊 Pattern Matching Results")
        show_identify_run_details(run_id)
    else:
        st.info("👆 Upload an XML file above to see pattern matching results")


def show_identify_run_details(run_id: str):
    """Show detailed view of an identify run with pattern matches."""
    run_details = get_run_status(run_id)

    if not run_details:
        st.error("Failed to load run details")
        return

    # Show basic run info first
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("NDC Version", run_details.get("spec_version", "N/A"))
    with col2:
        airline_code = run_details.get("airline_code", "N/A")
        st.metric("Airline", airline_code)
    with col3:
        st.metric("Message Root", run_details.get("message_root", "N/A"))

    st.divider()

    # Gap Analysis
    gap_analysis = get_gap_analysis(run_id)

    if gap_analysis:
        stats = gap_analysis.get('statistics', {})
        verdict_breakdown = gap_analysis.get('verdict_breakdown', {})

        # Summary metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total NodeFacts", stats.get('total_node_facts', 0))
        with col2:
            st.metric("Match Rate", f"{stats.get('match_rate', 0):.1f}%")
        with col3:
            st.metric("High Confidence", stats.get('high_confidence_matches', 0))
        with col4:
            st.metric("New Patterns", stats.get('new_patterns', 0))
        with col5:
            st.metric("Unmatched", stats.get('unmatched_facts', 0))

        st.divider()

        # Verdict breakdown
        st.subheader("📊 Match Quality Breakdown")

        verdict_colors = {
            "EXACT_MATCH": "🟢",
            "HIGH_MATCH": "🟡",
            "PARTIAL_MATCH": "🟠",
            "LOW_MATCH": "🔵",
            "NO_MATCH": "⚪",
            "NEW_PATTERN": "🔴"
        }

        verdict_data = []
        for verdict, count in verdict_breakdown.items():
            if count > 0:
                verdict_data.append({
                    "Verdict": f"{verdict_colors.get(verdict, '⚪')} {verdict.replace('_', ' ')}",
                    "Count": count,
                    "Percentage": f"{(count / stats.get('total_node_facts', 1) * 100):.1f}%"
                })

        if verdict_data:
            df_verdict = pd.DataFrame(verdict_data)
            st.dataframe(df_verdict, use_container_width=True, hide_index=True)

    st.divider()

    # Pattern Matches table
    st.subheader("🔍 Pattern Matches")

    matches_data = get_identify_matches(run_id, limit=200)

    if matches_data and matches_data.get('matches'):
        matches = matches_data['matches']

        match_table = []
        for match in matches:
            node_fact = match.get('node_fact', {})
            pattern = match.get('pattern')

            match_table.append({
                "Node Type": node_fact.get('node_type'),
                "Section Path": node_fact.get('section_path'),
                "Explanation": match.get('quick_explanation', 'No explanation available'),
                "Pattern Airline": pattern.get('airline_code', 'N/A') if pattern else "N/A",
                "Pattern Version": pattern.get('spec_version', 'N/A') if pattern else "N/A",
                "Pattern Message": pattern.get('message_root', 'N/A') if pattern else "N/A",
                "Pattern Section": pattern['section_path'] if pattern else "N/A",
                "Times Seen": pattern['times_seen'] if pattern else 0,
                "Confidence": f"{match.get('confidence', 0):.1%}",
                "Verdict": match.get('verdict', 'UNKNOWN')
            })

        df_matches = pd.DataFrame(match_table)

        # Color code by verdict
        def highlight_verdict(row):
            verdict = row['Verdict']
            if verdict == "EXACT_MATCH":
                return ['background-color: #d4edda'] * len(row)
            elif verdict == "HIGH_MATCH":
                return ['background-color: #fff3cd'] * len(row)
            elif verdict in ["PARTIAL_MATCH", "LOW_MATCH"]:
                return ['background-color: #f8d7da'] * len(row)
            elif verdict == "NEW_PATTERN":
                return ['background-color: #f5c6cb'] * len(row)
            return [''] * len(row)

        st.dataframe(
            df_matches.style.apply(highlight_verdict, axis=1),
            use_container_width=True,
            hide_index=True
        )

        # Detailed match view
        st.divider()
        st.subheader("🔎 Match Details & Analysis")

        match_options = {f"{m['node_fact']['node_type']} @ {m['node_fact']['section_path']} - {m['verdict']} ({m.get('confidence', 0):.1%})": m for m in matches}
        selected_match = st.selectbox("Select match to analyze:", list(match_options.keys()))

        if selected_match:
            match = match_options[selected_match]
            node_fact = match.get('node_fact', {})
            pattern = match.get('pattern')
            fact_json = node_fact.get('fact_json', {})

            # Match summary
            st.write(f"**Match Verdict:** `{match['verdict']}` | **Confidence:** `{match.get('confidence', 0):.1%}`")

            # Quick explanation
            quick_explanation = match.get('quick_explanation', '')
            if quick_explanation:
                st.info(quick_explanation)

            # Detailed LLM Explanation button
            match_id = match.get('match_id')
            if match_id:
                if st.button("🤖 Get Detailed AI Explanation", key=f"explain_{match_id}"):
                    with st.spinner("Generating detailed explanation with AI..."):
                        explanation_response = get_detailed_explanation(match_id)
                        if explanation_response:
                            detailed_explanation = explanation_response.get('detailed_explanation', '')
                            is_cached = explanation_response.get('cached', False)

                            cache_label = " (cached)" if is_cached else " (newly generated)"
                            st.success(f"✨ AI Explanation{cache_label}")
                            st.markdown(detailed_explanation)
                        else:
                            st.error("Failed to generate explanation. Please try again.")

            if pattern:
                decision_rule = pattern.get('decision_rule', {})

                # Show pattern metadata
                spec_ver = pattern.get('spec_version', 'Unknown')
                msg_root = pattern.get('message_root', 'Unknown')
                times_seen = pattern.get('times_seen', 0)
                st.info(f"🎯 Matched Pattern from **{spec_ver}/{msg_root}** (seen {times_seen} times)")

                st.divider()

                # Comparison breakdown
                st.subheader("📊 Match Breakdown")

                # 1. Node Type Match
                st.write("**1️⃣ Node Type Match**")
                nf_type = fact_json.get('node_type', 'Unknown')
                pattern_type = decision_rule.get('node_type', 'Unknown')
                if nf_type == pattern_type:
                    st.success(f"✅ Both are `{nf_type}`")
                else:
                    st.error(f"❌ NodeFact: `{nf_type}` vs Pattern: `{pattern_type}`")

                # 2. Attributes Match
                st.write("**2️⃣ Attributes Match**")
                nf_attrs = set(fact_json.get('attributes', {}).keys())
                required_attrs = set(decision_rule.get('must_have_attributes', []))
                optional_attrs = set(decision_rule.get('optional_attributes', []))

                if required_attrs:
                    matched_attrs = nf_attrs & required_attrs
                    missing_attrs = required_attrs - nf_attrs
                    extra_attrs = nf_attrs - required_attrs - optional_attrs

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Required Matched", f"{len(matched_attrs)}/{len(required_attrs)}")
                        if matched_attrs:
                            st.write("✅ " + ", ".join(f"`{a}`" for a in matched_attrs))
                    with col2:
                        if missing_attrs:
                            st.metric("Missing", len(missing_attrs), delta_color="inverse")
                            st.write("❌ " + ", ".join(f"`{a}`" for a in missing_attrs))
                        else:
                            st.metric("Missing", 0)
                    with col3:
                        if extra_attrs:
                            st.metric("Extra", len(extra_attrs))
                            st.write("➕ " + ", ".join(f"`{a}`" for a in extra_attrs))
                else:
                    st.info("No required attributes for this pattern")

                # 3. Children Structure Match
                st.write("**3️⃣ Children Structure Match**")
                nf_children = fact_json.get('children', [])
                pattern_child = decision_rule.get('child_structure', {})

                pattern_has_children = pattern_child.get('has_children', False)
                nf_has_children = len(nf_children) > 0

                if pattern_has_children == nf_has_children:
                    if nf_has_children:
                        st.success(f"✅ Both have children ({len(nf_children)} children in NodeFact)")

                        # Check child types if container
                        if pattern_child.get('is_container') and isinstance(nf_children[0], dict):
                            pattern_child_types = set(pattern_child.get('child_types', []))
                            nf_child_types = set(c.get('node_type', '') for c in nf_children if isinstance(c, dict))

                            if pattern_child_types:
                                matched_types = pattern_child_types & nf_child_types
                                st.write(f"  Child types: {', '.join(f'`{t}`' for t in matched_types)}")
                    else:
                        st.success("✅ Both have no children")
                else:
                    st.warning(f"⚠️ Pattern expects children: {pattern_has_children}, NodeFact has children: {nf_has_children}")

                # 4. Relationships Match
                st.write("**4️⃣ Relationships Match**")
                nf_relationships = fact_json.get('relationships', [])
                pattern_refs = decision_rule.get('reference_patterns', [])

                if pattern_refs or nf_relationships:
                    # Build detailed relationship info
                    nf_ref_details = {}
                    for rel in nf_relationships:
                        ref_type = rel.get('type', '')
                        nf_ref_details[ref_type] = {
                            'target_type': rel.get('target_type', 'Unknown'),
                            'target_path': rel.get('target_section_path', 'Unknown')
                        }

                    pattern_ref_details = {}
                    for ref in pattern_refs:
                        ref_type = ref.get('type', '')

                        # Handle different reference pattern structures
                        if ref_type == 'child_references':
                            pattern_ref_details[ref_type] = {
                                'description': f"Children with reference fields: {', '.join(ref.get('fields', []))}",
                                'fields': ref.get('fields', [])
                            }
                        elif 'parent' in ref and 'child' in ref:
                            # Relationship type (parent/child)
                            pattern_ref_details[ref_type] = {
                                'description': f"{ref.get('parent', 'Unknown')} → {ref.get('child', 'Unknown')} ({ref.get('direction', 'unknown')})",
                                'parent': ref.get('parent'),
                                'child': ref.get('child')
                            }
                        else:
                            # Cross-reference or other type
                            pattern_ref_details[ref_type] = {
                                'description': ref.get('reference', ref_type),
                                'data': ref
                            }

                    nf_ref_types = set(nf_ref_details.keys())
                    pattern_ref_types = set(pattern_ref_details.keys())

                    matched_refs = nf_ref_types & pattern_ref_types
                    missing_refs = pattern_ref_types - nf_ref_types
                    extra_refs = nf_ref_types - pattern_ref_types

                    if matched_refs:
                        st.success(f"✅ **Matched References:**")
                        for ref in matched_refs:
                            nf_info = nf_ref_details[ref]
                            st.write(f"  - `{ref}` → {nf_info['target_type']} at `{nf_info['target_path']}`")

                    if missing_refs:
                        st.warning(f"⚠️ **Missing References (Pattern expects these):**")
                        for ref in missing_refs:
                            pattern_info = pattern_ref_details[ref]
                            st.write(f"  - `{ref}`: {pattern_info['description']}")

                    if extra_refs:
                        st.info(f"➕ **Extra References (NodeFact has these):**")
                        for ref in extra_refs:
                            nf_info = nf_ref_details[ref]
                            st.write(f"  - `{ref}` → {nf_info['target_type']} at `{nf_info['target_path']}`")

                    if not matched_refs and not missing_refs and not extra_refs:
                        st.info("Both have no relationship patterns")
                else:
                    st.info("No relationship patterns")

                st.divider()

                # Raw JSON comparison (collapsible)
                with st.expander("🔍 View Full JSON Comparison"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**NodeFact Structure:**")
                        st.json(fact_json)
                    with col2:
                        st.write("**Pattern Decision Rule:**")
                        st.json(decision_rule)
            else:
                st.warning("🆕 No pattern matched - this is a NEW pattern!")
                st.write("**NodeFact Structure:**")
                st.json(fact_json)
    else:
        st.info("No pattern matches found. Please Discover them first.")


def show_patterns_page(embedded: bool = False):
    """Render Pattern Explorer content; embed inside tabs if requested."""

    if embedded:
        st.subheader("📚 Pattern Explorer")
        st.caption("Browse and search the discovered pattern library.")
    else:
        st.header("🔍 Pattern Explorer")
        st.write("View and analyze learned patterns")

    patterns = get_patterns(limit=200)

    if patterns:
        # Patterns table
        pattern_data = []
        for pattern in patterns:
            decision_rule = pattern.get('decision_rule', {})
            pattern_data.append({
                "ID": pattern['id'],
                "Section Path": pattern['section_path'],
                "Node Type": decision_rule.get('node_type', 'Unknown'),
                "Version": pattern['spec_version'],
                "Airline": pattern.get('airline_code', 'N/A'),
                "Message": pattern['message_root'],
                "Times Seen": pattern['times_seen'],
                "Must-Have Attrs": len(decision_rule.get('must_have_attributes', [])),
                "Has Children": "✓" if decision_rule.get('child_structure', {}).get('has_children') else "",
                "Last Seen": datetime.fromisoformat(pattern["last_seen_at"]).strftime("%Y-%m-%d %H:%M") if pattern.get("last_seen_at") else "Never"
            })

        df_patterns = pd.DataFrame(pattern_data)

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Patterns", len(patterns))
        with col2:
            unique_versions = len(set(p['spec_version'] for p in patterns))
            st.metric("Versions", unique_versions)
        with col3:
            unique_types = len(set(p.get('decision_rule', {}).get('node_type', 'Unknown') for p in patterns))
            st.metric("Node Types", unique_types)
        with col4:
            total_seen = sum(p['times_seen'] for p in patterns)
            st.metric("Total Observations", total_seen)

        st.divider()

        # Filters
        st.subheader("🔧 Filters")
        col1, col2 = st.columns(2)

        with col1:
            versions = ["All"] + sorted(list(set(p['spec_version'] for p in patterns)))
            selected_version = st.selectbox("Version:", versions)

        with col2:
            node_types = ["All"] + sorted(list(set(p.get('decision_rule', {}).get('node_type', 'Unknown') for p in patterns)))
            selected_type = st.selectbox("Node Type:", node_types)

        # Apply filters
        filtered_df = df_patterns.copy()
        if selected_version != "All":
            filtered_df = filtered_df[filtered_df['Version'] == selected_version]
        if selected_type != "All":
            filtered_df = filtered_df[filtered_df['Node Type'] == selected_type]

        st.divider()
        st.subheader(f"📋 Backend Patterns ({len(filtered_df)} total)")
        st.info("💡 **Tip**: To share patterns, go to the 'Export Patterns' tab to export them to your workspace, then use 'Manage Workspace' tab to mark them as shared.")

        # Drop columns for cleaner display
        columns_to_hide = ["ID"]
        display_df = filtered_df[[col for col in filtered_df.columns if col not in columns_to_hide]]

        # Display as dataframe (read-only)
        st.dataframe(
            display_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Times Seen": st.column_config.NumberColumn("Times Seen", format="%d"),
                "Must-Have Attrs": st.column_config.NumberColumn("Must-Have Attrs", format="%d"),
            }
        )

        # Pattern details
        st.divider()
        st.subheader("🔎 Pattern Details")

        pattern_options = {f"ID {p['id']} - {p['section_path']} (seen {p['times_seen']}x)": p for p in patterns}
        selected_pattern = st.selectbox("Select pattern:", list(pattern_options.keys()))

        if selected_pattern:
            pattern = pattern_options[selected_pattern]

            col1, col2 = st.columns(2)

            with col1:
                st.write("**Pattern Info:**")
                st.write(f"- **ID:** {pattern['id']}")
                st.write(f"- **Section:** {pattern['section_path']}")
                st.write(f"- **Version:** {pattern['spec_version']}")
                st.write(f"- **Message:** {pattern['message_root']}")
                st.write(f"- **Times Seen:** {pattern['times_seen']}")

            with col2:
                st.write("**Decision Rule:**")
                st.json(pattern.get('decision_rule', {}))
    else:
        st.info("No patterns found. Run discovery on some XML files first!")


def show_config_page():
    """Render configuration utilities, including workspace management."""

    st.header("⚙️ Config")
    st.caption("Quick controls for workspaces driving the AssistedDiscovery UI.")

    if 'workspaces' not in st.session_state or not st.session_state.workspaces:
        st.session_state.workspaces = load_workspaces()
    if not st.session_state.workspaces:
        st.session_state.workspaces = ["default"]

    if 'current_workspace' not in st.session_state or st.session_state.current_workspace not in st.session_state.workspaces:
        st.session_state.current_workspace = st.session_state.workspaces[0]

    workspaces = st.session_state.workspaces

    col_active, col_add, col_delete = st.columns([2, 2, 2])
    with col_active:
        st.markdown("### Active Workspace")
        current_idx = workspaces.index(st.session_state.current_workspace)
        selected_workspace = st.selectbox(
            "Active workspace",
            options=workspaces,
            index=current_idx,
            key="config_workspace_selector",
            label_visibility="collapsed"
        )
        if selected_workspace != st.session_state.current_workspace:
            st.session_state.current_workspace = selected_workspace
            st.success(f"Active workspace set to '{selected_workspace}'.")
            st.experimental_rerun()

    with col_add:
        st.markdown("### Add Workspace")
        new_workspace = st.text_input(
            "Workspace name",
            key="config_new_workspace",
            placeholder="e.g. WestJet",
            label_visibility="collapsed"
        )
        if st.button("➕ Add", key="config_add_workspace", use_container_width=True):
            if not new_workspace or not new_workspace.strip():
                st.warning("Enter a workspace name to add.")
            else:
                candidate = new_workspace.strip()
                if candidate in st.session_state.workspaces:
                    st.warning(f"Workspace '{candidate}' already exists.")
                else:
                    st.session_state.workspaces.append(candidate)
                    save_workspaces(st.session_state.workspaces)
                    st.session_state.current_workspace = candidate
                    st.session_state.pop("config_new_workspace", None)
                    st.success(f"Workspace '{candidate}' added and activated.")
                    st.experimental_rerun()

    with col_delete:
        st.markdown("### Delete Workspace")
        deletable = [w for w in st.session_state.workspaces if w != "default"]
        if not deletable:
            st.info("Only the default workspace exists. Add another workspace to enable deletion.")
        else:
            workspace_to_delete = st.selectbox(
                "Workspace to delete",
                options=deletable,
                key="config_delete_workspace",
                label_visibility="collapsed"
            )
            st.caption("Deleting removes it from the selection list. Existing data files remain on disk.")
            if st.button("🗑️ Delete", key="config_delete_workspace_btn", use_container_width=True):
                if workspace_to_delete in st.session_state.workspaces:
                    st.session_state.workspaces.remove(workspace_to_delete)
                    if not st.session_state.workspaces:
                        st.session_state.workspaces = ["default"]
                    save_workspaces(st.session_state.workspaces)
                    if st.session_state.current_workspace == workspace_to_delete:
                        st.session_state.current_workspace = st.session_state.workspaces[0]
                    st.success(f"Workspace '{workspace_to_delete}' deleted.")
                    st.experimental_rerun()

    st.divider()


def run_pattern_manager_page():
    """Render Pattern Manager with embedded Pattern Explorer tab."""
    from pattern_manager import PatternManager

    manager = PatternManager()
    manager.render(explorer_callback=lambda: show_patterns_page(embedded=True))


def show_node_manager_page():
    """Node manager page - configure which nodes to extract and their references."""
    current_workspace = st.session_state.get('current_workspace', 'default')
    st.header("📋 Node Configuration Manager")
    st.write("Configure which nodes to extract during Discovery and define expected references")
    st.caption(f"Workspace: `{current_workspace}`")

    tab1, tab2, tab3, tab4 = st.tabs(["📤 Analyze XML", "⚙️ Manage Configurations", "📋 Copy to Versions", "🔖 Reference Types"])

    with tab1:
        st.subheader("Upload XML to Discover Nodes")
        st.write("Upload an XML file to analyze its structure and create configurations")

        col_upload, col_clear = st.columns([4, 1])

        with col_upload:
            uploaded_file = st.file_uploader("Choose XML file", type=['xml'], key="node_config_upload")

        with col_clear:
            if 'analyzed_nodes' in st.session_state:
                st.write("")  # Spacer
                st.write("")  # Spacer
                if st.button("🔄 Clear & New Upload", help="Clear current analysis and upload a new file"):
                    del st.session_state.analyzed_nodes
                    st.session_state.pop('node_checked_paths_raw', None)
                    st.session_state.pop('node_checked_paths_effective', None)
                    st.rerun()

        if uploaded_file:
            if st.button("Analyze Structure", type="primary"):
                with st.spinner("Analyzing XML structure..."):
                    result = analyze_xml_for_nodes(uploaded_file, workspace=current_workspace)

                if result:
                    airline_display = f" - Airline: {result['airline_code']}" if result.get('airline_code') else ""
                    st.success(f"✅ Discovered {result['total_nodes']} nodes in {result['spec_version']}/{result['message_root']}{airline_display}")

                    if result.get('airline_code'):
                        st.info(f"ℹ️ Showing configurations for **{result['airline_code']}** airline. "
                               f"Configurations are airline-specific - each airline has its own settings.")

                    # Store in session state for editing
                    st.session_state.analyzed_nodes = merge_existing_configs(result, workspace=current_workspace)
                    default_checked_raw = [
                        node['section_path']
                        for node in result.get('nodes', [])
                        if node.get('enabled', False)
                    ]
                    st.session_state.node_checked_paths_raw = default_checked_raw
                    st.session_state.node_checked_paths_effective = compute_effective_paths(
                        default_checked_raw,
                        previous_effective=default_checked_raw,
                        previous_raw=default_checked_raw
                    )
                    st.rerun()
                else:
                    st.error("Failed to analyze XML structure")

        # Show analyzed nodes if available
        if 'analyzed_nodes' in st.session_state:
            result = merge_existing_configs(st.session_state.analyzed_nodes, workspace=current_workspace)
            st.session_state.analyzed_nodes = result

            st.divider()

            # Show airline context prominently
            airline_display = f" for {result.get('airline_code', 'Global')}" if result.get('airline_code') else " (Global)"
            st.subheader(f"📊 Discovered Nodes{airline_display}")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Version", result['spec_version'])
            with col2:
                st.metric("Airline", result.get('airline_code', 'Global'))
            with col3:
                st.metric("Total Nodes", result['total_nodes'])
            with col4:
                st.metric("Configured", result['configured_nodes'])

            st.divider()

            # Tree-based node selection
            st.subheader("✏️ Configure Nodes")
            st.write("Select nodes from the tree to enable extraction and configure properties")

            # Build tree structure from flat nodes
            tree_data = build_node_tree(result['nodes'])

            # Create a mapping of section_path to node data for quick lookup
            node_lookup = {node['section_path']: node for node in result['nodes']}

            # Determine which nodes should be checked initially
            default_checked_raw = [
                node['section_path'] for node in result['nodes'] if node.get('enabled', False)
            ]

            stored_raw = st.session_state.get('node_checked_paths_raw')
            if stored_raw is None:
                stored_raw = [path for path in default_checked_raw if path in node_lookup]
                st.session_state.node_checked_paths_raw = stored_raw

            stored_raw = [path for path in stored_raw if path in node_lookup]
            if stored_raw != st.session_state.get('node_checked_paths_raw'):
                st.session_state.node_checked_paths_raw = stored_raw

            stored_effective = st.session_state.get('node_checked_paths_effective')
            if stored_effective is None:
                stored_effective = compute_effective_paths(
                    stored_raw,
                    previous_effective=stored_raw,
                    previous_raw=stored_raw
                )
                stored_effective = [path for path in stored_effective if path in node_lookup]
                st.session_state.node_checked_paths_effective = stored_effective

            pre_checked_display = list(dict.fromkeys([
                *stored_raw,
                *[path for path in stored_effective if path in node_lookup]
            ]))

            if not pre_checked_display and default_checked_raw:
                pre_checked_display = [path for path in default_checked_raw if path in node_lookup]
                st.session_state.node_checked_paths_raw = pre_checked_display
                stored_raw = pre_checked_display

            # Display tree selector
            col1, col2 = st.columns([1, 1])

            checked_paths = st.session_state.get('node_checked_paths_effective', [])

            with col1:
                st.write("**🌳 Node Hierarchy**")
                st.caption("Check nodes to enable extraction")

                # Tree select component
                try:
                    selected = tree_select(
                        tree_data,
                        checked=pre_checked_display,
                        only_leaf_checkboxes=False,
                        expand_on_click=True,
                        no_cascade=True,
                        expanded=[node['value'] for node in tree_data if node.get('value')],
                        key="node_manager_tree"
                    )
                except Exception as e:
                    st.error(f"Tree component error: {str(e)}")
                    st.write("Tree data:", tree_data)
                    selected = {'checked': []}

                # Get checked nodes from tree_select
                raw_checked = selected.get('checked')
                if raw_checked is None:
                    raw_checked = pre_checked_display
                raw_checked = [path for path in raw_checked if path in node_lookup]

                previous_raw = st.session_state.get('node_checked_paths_raw', stored_raw)
                previous_effective = st.session_state.get('node_checked_paths_effective')

                filtered_raw = filter_raw_paths(raw_checked, previous_raw, previous_effective)
                filtered_raw = [path for path in filtered_raw if path in node_lookup]
                st.session_state.node_checked_paths_raw = filtered_raw

                effective_checked = compute_effective_paths(filtered_raw, previous_effective, previous_raw)
                effective_checked = [path for path in effective_checked if path in node_lookup]
                st.session_state.node_checked_paths_effective = effective_checked

                checked_paths = effective_checked

            with col2:
                st.write("**⚙️ Node Properties**")

                # Show configuration form for selected nodes
                if checked_paths:
                    st.info(f"✅ {len(checked_paths)} nodes selected for extraction")

                    raw_selection = st.session_state.get('node_checked_paths_raw', [])
                    auto_enabled = [path for path in checked_paths if path not in raw_selection]
                    if auto_enabled:
                        auto_display = ", ".join(f"`{path}`" for path in auto_enabled)
                        st.caption(f"🔁 Parent selections also keep these nodes enabled: {auto_display}")

                    # Get first checked node for editing
                    selected_path = checked_paths[0] if checked_paths else None

                    if selected_path and selected_path in node_lookup:
                        selected_node = node_lookup[selected_path]

                        st.write(f"**Editing:** `{selected_node['node_type']}`")
                        st.caption(f"Path: {selected_path}")

                        # Initialize form state
                        if 'node_configs' not in st.session_state:
                            st.session_state.node_configs = {}

                        # Get current config or defaults
                        current_config = st.session_state.node_configs.get(selected_path, {
                            'expected_references': selected_node.get('expected_references', []),
                            'ba_remarks': selected_node.get('ba_remarks', '')
                        })

                        # Form for editing node properties
                        with st.form(key=f"edit_form_{selected_path}"):
                            expected_refs_str = st.text_input(
                                "Expected References",
                                value=", ".join(current_config['expected_references']),
                                help="Comma-separated: infant_parent, segment_reference, etc.",
                                placeholder="e.g., segment_reference, pax_reference"
                            )

                            ba_remarks_str = st.text_area(
                                "BA Remarks",
                                value=current_config['ba_remarks'],
                                help="Notes and instructions for this node",
                                placeholder="Add any notes or special instructions..."
                            )

                            if st.form_submit_button("💾 Update This Node"):
                                # Parse and store config
                                refs = [r.strip() for r in expected_refs_str.split(',') if r.strip()]
                                st.session_state.node_configs[selected_path] = {
                                    'expected_references': refs,
                                    'ba_remarks': ba_remarks_str
                                }
                                st.success(f"✅ Updated {selected_node['node_type']}")

                        # Show all selected nodes summary
                        if len(checked_paths) > 1:
                            st.divider()
                            st.caption(f"**Other selected nodes ({len(checked_paths) - 1}):**")
                            for path in checked_paths[1:6]:  # Show up to 5
                                if path in node_lookup:
                                    st.caption(f"• {node_lookup[path]['node_type']}")
                            if len(checked_paths) > 6:
                                st.caption(f"...and {len(checked_paths) - 6} more")
                else:
                    st.info("👈 Check nodes in the tree to configure them")
                    st.caption("**Tip:** You can select multiple nodes at once")

            # Save button
            st.divider()
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("💾 Save All Configurations", type="primary"):
                    # Prepare data for bulk update from all nodes
                    configurations = []

                    # Get configs from session state or defaults
                    node_configs = st.session_state.get('node_configs', {})

                    # Process all nodes
                    for node in result['nodes']:
                        section_path = node['section_path']

                        # Check if node is enabled (in checked_paths)
                        enabled = section_path in checked_paths

                        # Get config for this node
                        config_data = node_configs.get(section_path, {
                            'expected_references': node.get('expected_references', []),
                            'ba_remarks': node.get('ba_remarks', '')
                        })

                        config = {
                            'config_id': node.get('config_id'),
                            'spec_version': result['spec_version'],
                            'message_root': result['message_root'],
                            'airline_code': result.get('airline_code'),
                            'node_type': node['node_type'],
                            'section_path': section_path,
                            'enabled': enabled,
                            'expected_references': config_data['expected_references'],
                            'ba_remarks': config_data['ba_remarks']
                        }
                        configurations.append(config)

                    # Send to API
                    if bulk_update_node_configurations(configurations, workspace=current_workspace):
                        st.success(f"✅ Saved {len(configurations)} node configurations!")
                        st.success(f"   • {len(checked_paths)} nodes enabled for extraction")
                        st.info("💡 Configurations saved successfully. You can continue editing or upload a new XML file.")
                        # Clear session state configs after save
                        st.session_state.node_configs = {}
                    else:
                        st.error("Failed to save configurations")

            with col2:
                st.caption("💡 **Tip**: See available reference types in the 'Reference Types' tab →")

    with tab2:
        st.subheader("⚙️ Existing Configurations")

        # Filters
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            filter_version = st.text_input("Filter by Version", placeholder="e.g., 21.3")
        with col2:
            filter_message = st.text_input("Filter by Message", placeholder="e.g., OrderViewRS")
        with col3:
            filter_airline = st.text_input("Filter by Airline", placeholder="e.g., SQ")
        with col4:
            filter_node = st.text_input("Search Node Type", placeholder="e.g., Pax")

        if st.button("🔍 Load Configurations"):
            version_filter = filter_version.strip() if filter_version and filter_version.strip() else None
            message_filter = filter_message.strip() if filter_message and filter_message.strip() else None
            airline_filter = filter_airline.strip().upper() if filter_airline and filter_airline.strip() else None

            configs_data = get_node_configurations(
                spec_version=version_filter,
                message_root=message_filter,
                airline_code=airline_filter,
                workspace=current_workspace
            )

            if configs_data and configs_data['configurations']:
                st.caption(f"Showing results for Version={version_filter or 'All'}, Message={message_filter or 'All'}, Airline={airline_filter or 'All'}")
                # Display as table
                config_list = []
                for config in configs_data['configurations']:
                    config_list.append({
                        "Version": config['spec_version'],
                        "Message": config['message_root'],
                        "Airline": config['airline_code'] or "All",
                        "Node Type": config['node_type'],
                        "Section Path": config['section_path'],
                        "Enabled": "Yes" if config['enabled'] else "No",
                        "References": ", ".join(config['expected_references']) if config['expected_references'] else "-",
                        "Remarks": config['ba_remarks'] or "-"
                    })

                df_configs = pd.DataFrame(config_list)

                # Apply node type filter if specified
                if filter_node:
                    # Case-insensitive partial match on Node Type
                    df_configs = df_configs[
                        df_configs['Node Type'].str.contains(filter_node, case=False, na=False)
                    ]

                if len(df_configs) > 0:
                    st.success(f"Found {len(df_configs)} configurations")

                    # Apply color coding to Enabled column
                    def highlight_enabled(row):
                        if row['Enabled'] == 'Yes':
                            return ['background-color: #d4edda'] * len(row)  # Light green
                        else:
                            return ['background-color: #f8d7da'] * len(row)  # Light red

                    styled_df = df_configs.style.apply(highlight_enabled, axis=1)
                    st.dataframe(styled_df, use_container_width=True, hide_index=True)
                else:
                    st.warning(f"No configurations found matching node type '{filter_node}'")
            else:
                st.info(f"No configurations found in workspace `{current_workspace}`. Upload an XML in the 'Analyze XML' tab to create configurations or adjust your filters.")

    with tab3:
        st.subheader("📋 Copy Configurations to Other Versions")
        st.write("Apply your configurations from one version to multiple other NDC versions")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Source Configuration**")
            source_version = st.text_input("Source Version", value="18.1", placeholder="e.g., 18.1")
            source_message = st.text_input("Source Message Root", value="OrderViewRS", placeholder="e.g., OrderViewRS")
            source_airline = st.text_input("Source Airline (optional)", placeholder="Leave empty to auto-detect", help="Leave empty to use global configs or first available airline (e.g., SQ)")

        with col2:
            st.write("**Target Versions**")
            st.caption("Enter versions separated by commas")
            target_versions_input = st.text_area(
                "Target Versions",
                value="17.2, 19.2, 21.3, 23.1",
                placeholder="e.g., 17.2, 19.2, 21.3",
                height=100
            )
            target_airline = st.text_input("Target Airline (optional)", placeholder="Leave empty to keep same as source")

        st.divider()

        if st.button("🚀 Copy Configurations to All Versions", type="primary"):
            # Parse target versions
            target_versions = [v.strip() for v in target_versions_input.split(',') if v.strip()]

            if not target_versions:
                st.error("Please enter at least one target version")
            elif not source_version or not source_message:
                st.error("Please enter source version and message root")
            else:
                with st.spinner(f"Copying configurations from {source_version} to {len(target_versions)} versions..."):
                    result = copy_configurations_to_versions(
                        source_spec_version=source_version,
                        source_message_root=source_message,
                        target_versions=target_versions,
                        source_airline_code=source_airline if source_airline else None,
                        target_airline_code=target_airline if target_airline else None
                    )

                if result:
                    st.success(f"✅ Successfully copied configurations!")
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("Source Configs", result['source_configs'])
                    with col_b:
                        st.metric("Created", result['created'])
                    with col_c:
                        st.metric("Skipped (already exist)", result['skipped'])

                    # Show which airline was used
                    detected = result.get('detected_airline', 'Unknown')
                    airline_info = f" (Airline: {detected})"
                    st.info(f"📋 Copied from **{result['source_version']}{airline_info}** to: {', '.join(result['target_versions'])}")

                    if result.get('errors'):
                        st.warning("Some errors occurred:")
                        for error in result['errors']:
                            st.text(error)
                else:
                    st.error("Failed to copy configurations. Please check:\n- Source version and message root are correct\n- Configurations exist for the source version")

    with tab4:
        st.subheader("🔖 Reference Types Glossary")
        st.write("Manage reference types used in node configurations")

        # Add new reference type section
        with st.expander("➕ Add New Reference Type", expanded=False):
            col1, col2 = st.columns(2)

            with col1:
                new_ref_type = st.text_input("Reference Type ID*", placeholder="e.g., document_reference",
                                            help="Unique identifier (lowercase, underscores)")
                new_display_name = st.text_input("Display Name*", placeholder="e.g., Document Reference")
                new_category = st.selectbox("Category*",
                    ["passenger", "segment", "journey", "baggage", "price", "service", "order", "document", "other"])

            with col2:
                new_description = st.text_area("Description*", placeholder="Describe what this reference represents", height=100)
                new_example = st.text_input("Example", placeholder="e.g., Ticket references DocumentID:DOC123")

            if st.button("✅ Add Reference Type", type="primary"):
                if not new_ref_type or not new_display_name or not new_description:
                    st.error("Please fill in all required fields (marked with *)")
                else:
                    try:
                        response = requests.post(
                            f"{API_BASE_URL}/reference-types/",
                            params={
                                "reference_type": new_ref_type,
                                "display_name": new_display_name,
                                "description": new_description,
                                "example": new_example if new_example else None,
                                "category": new_category,
                                "created_by": "user"
                            },
                            timeout=10
                        )

                        if response.status_code == 200:
                            st.success(f"✅ Reference type '{new_ref_type}' added successfully!")
                            st.rerun()
                        else:
                            error_data = response.json()
                            st.error(f"Failed to add reference type: {error_data.get('detail', response.text)}")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

        st.divider()

        # Filter section
        col1, col2 = st.columns([3, 1])
        with col1:
            filter_category = st.selectbox("Filter by Category", ["All"] + ["passenger", "segment", "journey", "baggage", "price", "service", "order", "document", "other"])
        with col2:
            show_inactive = st.checkbox("Show Inactive", value=False)

        # Load reference types
        try:
            params = {}
            if filter_category != "All":
                params["category"] = filter_category
            if not show_inactive:
                params["is_active"] = True

            response = requests.get(
                f"{API_BASE_URL}/reference-types/",
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                ref_types = data.get('reference_types', [])

                if ref_types:
                    st.success(f"📚 Found {len(ref_types)} reference types")

                    # Group by category
                    categories = {}
                    for ref_type in ref_types:
                        cat = ref_type.get('category', 'other')
                        if cat not in categories:
                            categories[cat] = []
                        categories[cat].append(ref_type)

                    # Display by category
                    for category, items in sorted(categories.items()):
                        st.subheader(f"📂 {category.title()}")

                        for ref_type in items:
                            with st.expander(f"**{ref_type['display_name']}** (`{ref_type['reference_type']}`)", expanded=False):
                                col1, col2 = st.columns([3, 1])

                                with col1:
                                    st.write("**Description:**")
                                    st.write(ref_type['description'])

                                    if ref_type.get('example'):
                                        st.write("**Example:**")
                                        st.code(ref_type['example'])

                                    st.caption(f"Created by: {ref_type.get('created_by', 'Unknown')}")

                                with col2:
                                    status_icon = "✅" if ref_type['is_active'] else "⏸️"
                                    st.write(f"**Status:** {status_icon}")

                                    if ref_type.get('created_by') != 'system':
                                        if st.button("🗑️ Delete", key=f"del_{ref_type['id']}"):
                                            try:
                                                del_response = requests.delete(
                                                    f"{API_BASE_URL}/reference-types/{ref_type['id']}",
                                                    timeout=10
                                                )
                                                if del_response.status_code == 200:
                                                    st.success("Deleted!")
                                                    st.rerun()
                                                else:
                                                    st.error("Delete failed")
                                            except Exception as e:
                                                st.error(f"Error: {str(e)}")

                        st.divider()
                else:
                    st.info("No reference types found. Add one using the form above.")
            else:
                st.error(f"Failed to load reference types: {response.status_code}")

        except Exception as e:
            st.error(f"Error loading reference types: {str(e)}")


# ========== MAIN APP ==========

def render_sidebar() -> str:
    """Render the common sidebar controls and return the active workspace."""

    st.sidebar.subheader("🗂️ Workspace")

    if 'workspaces' not in st.session_state:
        st.session_state.workspaces = load_workspaces()

    if not st.session_state.workspaces:
        st.session_state.workspaces = ["default"]

    if 'current_workspace' not in st.session_state or st.session_state.current_workspace not in st.session_state.workspaces:
        st.session_state.current_workspace = st.session_state.workspaces[0]

    active_workspace = st.session_state.current_workspace

    st.sidebar.metric("Active Workspace", active_workspace)
    st.sidebar.caption("Manage workspaces from the ⚙️ Config page.")

    st.sidebar.divider()

    return active_workspace


def render_sidebar_footer() -> None:
    """Render shared sidebar footer information."""

    st.sidebar.subheader("💰 Token Usage")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.metric("Session", "0", help="Tokens used this session")
    with col2:
        st.metric("Total", "0", help="Total tokens used")
    st.sidebar.caption("💡 Token tracking coming soon")

    st.sidebar.divider()

    st.sidebar.subheader("System Status")
    st.sidebar.success("✅ API Connected")
    backend_patterns_count = len(get_patterns(limit=500))
    st.sidebar.metric("Backend Patterns", backend_patterns_count)
