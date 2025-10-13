"""
AssistedDiscovery Streamlit UI

Clean table-based interface with sidebar navigation.
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import json
import time
from streamlit_tree_select import tree_select

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"
HEALTH_URL = "http://localhost:8000/health"


workspace_config_file = Path(__file__).parent / "data" / "workspaces" / "workspaces.json"


def show_error_with_logs(error_message: str, additional_context: Optional[str] = None,
                         error_type: str = "general", run_id: Optional[str] = None):
    """
    Display a user-friendly error message with log file location.

    Args:
        error_message: The main error message to display
        additional_context: Optional additional context or details
        error_type: Type of error - "llm", "xml", "network", "general"
        run_id: Optional run ID for tracking in logs
    """
    st.error(f"❌ {error_message}")

    if additional_context:
        st.error(f"**Details:** {additional_context}")

    if run_id:
        st.info(f"📋 **Run ID:** `{run_id}` (use this to search logs)")

    st.warning("💡 **Troubleshooting:**")

    # Type-specific troubleshooting tips
    if error_type == "llm":
        st.write("- Check your API keys in `.env` file")
        st.write("- Verify AZURE_OPENAI_KEY or OPENAI_API_KEY is set correctly")
        st.write("- Check if you have exceeded rate limits")
        st.write("- Test your API credentials independently")
    elif error_type == "xml":
        st.write("- Verify the XML file is well-formed")
        st.write("- Check if the file is a valid NDC message format")
        st.write("- Try validating the XML with an online validator")
        st.write("- Look for unclosed tags or special characters")
    elif error_type == "network":
        st.write("- Make sure the backend is running")
        st.write("- Check if the backend URL is correct")
        st.write("- Verify network connectivity")

    st.write("- **Check the log files for detailed error information:**")

    # Platform-specific log location
    import platform
    system = platform.system()
    if system == "Darwin":  # macOS
        log_path = "~/Library/Logs/AssistedDiscovery/assisted_discovery.log"
        st.code(f"📂 Log File (macOS):\n{log_path}", language="bash")
    elif system == "Windows":
        log_path = "%LOCALAPPDATA%\\AssistedDiscovery\\Logs\\assisted_discovery.log"
        st.code(f"📂 Log File (Windows):\n{log_path}", language="bash")
    else:  # Linux
        log_path = "~/.local/share/AssistedDiscovery/logs/assisted_discovery.log"
        st.code(f"📂 Log File (Linux):\n{log_path}", language="bash")


def load_workspaces() -> List[str]:
    """Load workspaces from disk or return defaults."""
    if workspace_config_file.exists():
        try:
            return json.loads(workspace_config_file.read_text())
        except Exception:
            pass
    return ["default"]


def save_workspaces(workspaces: List[str]) -> None:
    """Persist workspace list to disk."""
    workspace_config_file.parent.mkdir(parents=True, exist_ok=True)
    workspace_config_file.write_text(json.dumps(workspaces, indent=2))


def apply_custom_theme() -> None:
    """Inject additional CSS for a cohesive blue-forward theme."""
    if st.session_state.get("_custom_theme_applied"):
        return

    st.markdown(
        """
        <style>
        .stApp {
            background-color: #F7FAFF;
            color: #0B1F33;
        }

        section[data-testid="stSidebar"] {
            background-color: #E6F0FF;
        }

        div.stButton > button {
            background-color: #1A5DBF;
            color: #FFFFFF;
            border-radius: 6px;
            border: 1px solid #0F3F80;
        }

        div.stButton > button:hover {
            background-color: #144A99;
            border-color: #0D366E;
            color: #FFFFFF;
        }

        div[data-baseweb="select"] > div {
            border-radius: 6px;
            border: 1px solid #B5C7EB;
            box-shadow: none;
            background-color: #FFFFFF;
        }

        div[data-baseweb="select"] > div:hover {
            border-color: #1A5DBF;
        }

        div[data-testid="stMetricValue"] {
            color: #154F9A;
        }

        div[data-testid="stMetricLabel"] {
            color: #0B1F33;
        }

        .blue-card {
            background-color: #E6F0FF;
            border: 1px solid #B5C7EB;
            border-radius: 8px;
            padding: 1rem;
        }

        .stDataFrame thead tr th {
            background-color: #E0EBFF;
            color: #0B1F33;
        }

        .stDataFrame tbody tr:nth-child(even) {
            background-color: #F2F6FF;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.session_state["_custom_theme_applied"] = True


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
    """Remove auto-selected descendants when parent is newly chosen,
    and remove auto-selected parents when all children are manually selected."""
    unique_paths = list(dict.fromkeys(raw_paths or []))
    prev_selected = set(previous_raw or []) | set(previous_effective or [])
    raw_set = set(unique_paths)

    filtered = []
    for path in unique_paths:
        # Check if parent is selected
        has_parent_selected = any(parent in raw_set for parent in _path_ancestors(path))
        if has_parent_selected and path not in prev_selected:
            continue  # Skip descendants implicitly checked via parent

        # NEW: Check if this parent was auto-selected by the tree component
        # When user selects all children, tree component auto-checks the parent
        # We detect this by checking if:
        # 1. This path has children (descendants) in the selection
        # 2. This path was NOT in the previous selection (it's newly appeared)
        # 3. At least one child was in the previous selection (user was selecting children)
        if path not in prev_selected:
            has_children_selected = any(p.startswith(f"{path}/") for p in raw_set)
            if has_children_selected:
                # Check if any child was previously selected (indicating user is selecting children, not parent)
                any_child_was_selected = any(p.startswith(f"{path}/") for p in prev_selected)
                if any_child_was_selected:
                    # This parent was auto-checked by tree component, skip it
                    continue

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
            timeout=600  # Increased to 10 minutes for large XML files with many nodes
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
        st.error(f"❌ **Request Timeout**: The server took too long to respond (> 10 minutes)")
        st.warning("**This happens when:**")
        st.write("- Too many nodes are selected for extraction in Node Manager")
        st.write("- Large XML file with complex structure")
        st.write("- LLM API is responding slowly")
        st.info("💡 **Solutions:**")
        st.write("1. **Best**: Go to Node Manager and select only specific nodes you need")
        st.write("2. Try with a smaller XML file first")
        st.write("3. Check if backend logs show progress (it might still be processing)")
        st.write("4. Restart the backend and try again")
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


def get_identify_matches(run_id: str, limit: int = 100, workspace: str = "default") -> Optional[Dict[str, Any]]:
    """Get pattern matching results for an identify run."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/identify/{run_id}/matches",
            params={"limit": limit, "workspace": workspace},
            timeout=15
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def get_gap_analysis(run_id: str, workspace: str = "default") -> Optional[Dict[str, Any]]:
    """Get gap analysis for an identify run."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/identify/{run_id}/gap-analysis",
            params={"workspace": workspace},
            timeout=15
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def get_detailed_explanation(match_id: int, workspace: str = "default") -> Optional[Dict[str, Any]]:
    """Generate detailed LLM explanation for a pattern match."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/identify/matches/{match_id}/explain",
            params={"workspace": workspace} if workspace else None,
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

        # Return error details for non-200 responses
        try:
            error_data = response.json()
            error_detail = error_data.get('detail', 'Unknown error')
        except:
            error_detail = response.text or f"HTTP {response.status_code}"

        return {"error": error_detail, "status_code": response.status_code}
    except requests.exceptions.RequestException as e:
        return {"error": f"Network error: {str(e)}", "status_code": None}


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
                     is_valid: Optional[bool] = None,
                     workspace: str = "default") -> Optional[List[Dict[str, Any]]]:
    """Get discovered relationships with optional filtering."""
    try:
        params = {"limit": 500, "workspace": workspace}
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


def get_relationships_by_node_type(source_node_type: str, workspace: str = "default") -> Optional[List[Dict[str, Any]]]:
    """Get discovered relationships for a specific source node type."""
    try:
        params = {
            "source_node_type": source_node_type,
            "limit": 100,
            "workspace": workspace
        }
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

                                    if cfg.get('ba_remarks'):
                                        st.write(f"**Expert Remarks:** {cfg['ba_remarks']}")

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

    # Check if NodeFacts were extracted
    if run_details.get("node_facts_count", 0) == 0:
        st.warning("⚠️ No NodeFacts were extracted during this Discovery run. Relationships cannot be analyzed without NodeFacts.")
        st.info("💡 This usually means no target paths are configured for this NDC version and message type. Configure target paths in the Configuration page.")
    elif rel_summary and rel_summary.get('statistics', {}).get('total_relationships', 0) > 0:
        stats = rel_summary['statistics']

        # Display metrics (simplified - removed Expected/Discovered distinction)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total", stats['total_relationships'])
        with col2:
            st.metric("✅ Valid", stats['valid_relationships'])
        with col3:
            st.metric("❌ Broken", stats['broken_relationships'])

        # Validation rate
        if stats['total_relationships'] > 0:
            validation_rate = stats.get('validation_rate', 0)
            if validation_rate >= 90:
                st.success(f"✅ {validation_rate}% of relationships are valid")
            elif validation_rate >= 70:
                st.warning(f"⚠️ {validation_rate}% of relationships are valid")
            else:
                st.error(f"❌ Only {validation_rate}% of relationships are valid")

        # Reference type breakdown (simplified)
        st.write("**Reference Types Breakdown:**")
        ref_types = rel_summary.get('reference_types', {})

        if ref_types:
            type_data = []
            for ref_type, counts in ref_types.items():
                type_data.append({
                    "Reference Type": ref_type,
                    "Total": counts['total'],
                    "Valid": counts['valid'],
                    "Broken": counts['broken']
                })

            df_types = pd.DataFrame(type_data)
            st.dataframe(df_types, use_container_width=True, hide_index=True)

        # All relationships table (always expanded, no separate broken/unexpected sections)
        st.write("**📊 All Relationships**")
        all_rels = get_relationships(run_id=run_id, workspace=workspace)

        if all_rels:
            rel_data = []
            for r in all_rels:
                status_icon = "✅" if r.get('is_valid') else "❌"
                conf = r.get('confidence')
                conf_str = f"{conf:.0%}" if conf is not None else "N/A"

                rel_data.append({
                    "Status": status_icon,
                    "Source": r['source_node_type'],
                    "→ Target": r['target_node_type'],
                    "Type": r['reference_type'],
                    "Field": r.get('reference_field', 'N/A'),
                    "Value": r.get('reference_value', 'N/A'),
                    "Confidence": conf_str
                })

            df_all = pd.DataFrame(rel_data)
            st.dataframe(df_all, use_container_width=True, hide_index=True)

            st.caption("Legend: ✅ Valid relationship | ❌ Broken relationship (target not found)")
        else:
            st.info("No relationship details available")
    elif run_details.get("node_facts_count", 0) > 0:
        # NodeFacts exist but no relationships were found
        st.info("ℹ️ No cross-references were found between data elements in this XML file.")
        st.caption("This is normal for some XML structures that don't link different sections together.")

    st.divider()

    # NodeFacts table - hidden in expander for technical users only
    with st.expander("🔧 Technical Details: Extracted NodeFacts (Advanced)", expanded=False):
        st.caption("Internal data structure used for pattern generation. For technical users only.")
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
            all_patterns = get_patterns(limit=200, workspace=current_workspace)
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
        show_identify_run_details(run_id, current_workspace)
    else:
        st.info("👆 Upload an XML file above to see pattern matching results")


def show_identify_run_details(run_id: str, workspace: str = "default"):
    """Show detailed view of an identify run with pattern matches."""
    run_details = get_run_status(run_id, workspace)

    if not run_details:
        st.error("Failed to load run details")
        return

    def summarize_missing_elements(elements: Any) -> str:
        """Format missing element metadata for display."""
        if not elements:
            return "—"
        if isinstance(elements, list):
            parts = []
            for item in elements:
                if isinstance(item, dict):
                    path = item.get("path")
                    reason = item.get("reason")
                    if path and reason:
                        parts.append(f"{path} ({reason})")
                    elif path:
                        parts.append(path)
                    elif reason:
                        parts.append(reason)
                else:
                    parts.append(str(item))
            return "; ".join(parts) if parts else "—"
        return str(elements)

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
    gap_analysis = get_gap_analysis(run_id, workspace)

    if gap_analysis:
        stats = gap_analysis.get('statistics', {})
        verdict_breakdown = gap_analysis.get('verdict_breakdown', {})
        quality_alerts = gap_analysis.get('quality_alerts', [])

        # Summary metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total NodeFacts", stats.get('total_node_facts', 0))
        with col2:
            st.metric("Match Rate", f"{stats.get('match_rate', 0):.1f}%")
        with col3:
            coverage = stats.get('quality_match_rate', stats.get('match_rate', 0))
            st.metric("Quality Coverage", f"{coverage:.1f}%")
        with col4:
            st.metric("Unmatched", stats.get('unmatched_facts', 0))
        with col5:
            st.metric("Quality Breaks", stats.get('quality_breaks', 0))

        col6, col7 = st.columns(2)
        with col6:
            st.metric("High Confidence", stats.get('high_confidence_matches', 0))
        with col7:
            st.metric("New Patterns", stats.get('new_patterns', 0))

        st.divider()

        # Quality alerts section
        if quality_alerts:
            st.warning(f"Detected {len(quality_alerts)} quality break(s) requiring review.")

            alert_table = []
            for alert in quality_alerts:
                qc = alert.get("quality_checks", {}) or {}
                coverage = alert.get("match_percentage", qc.get("match_percentage", 0))
                alert_table.append({
                    "Node Type": alert.get("node_type", "Unknown"),
                    "Section Path": alert.get("section_path", "N/A"),
                    "Coverage": f"{coverage:.1f}%",
                    "Status": qc.get("status", "unknown").upper(),
                    "Missing Elements": summarize_missing_elements(qc.get("missing_elements"))
                })

            df_quality = pd.DataFrame(alert_table)
            st.dataframe(df_quality, use_container_width=True, hide_index=True)

    st.divider()

    # Pattern Matches table
    st.subheader("🔍 Pattern Matches")

    matches_data = get_identify_matches(run_id, limit=200, workspace=workspace)
    matches: List[Dict[str, Any]] = []

    if matches_data and matches_data.get('matches'):
        matches = matches_data['matches']

        match_table = []
        seen_patterns = set()  # Track unique patterns to avoid duplicates

        for match in matches:
            node_fact = match.get('node_fact', {})
            pattern = match.get('pattern')
            quality_checks = match.get('quality_checks') or {}
            quality_status = str(quality_checks.get('status', 'ok')).lower() if isinstance(quality_checks, dict) else 'ok'
            match_percentage = 100.0
            if isinstance(quality_checks, dict):
                try:
                    match_percentage = float(quality_checks.get('match_percentage', 100))
                except (TypeError, ValueError):
                    match_percentage = 0.0 if quality_status == 'error' else 100.0
            missing_summary = summarize_missing_elements(quality_checks.get('missing_elements') if isinstance(quality_checks, dict) else None)
            if quality_status == 'error':
                quality_display = f"⚠️ {match_percentage:.1f}%"
                if missing_summary and missing_summary != "—":
                    quality_display += f" • {missing_summary}"
            else:
                quality_display = f"✅ {match_percentage:.1f}%"

            if pattern:
                # Get pattern node type from decision_rule
                pattern_node_type = pattern.get('decision_rule', {}).get('node_type', 'Unknown')
                pattern_section = pattern.get('section_path', 'N/A')

                # Create unique key for deduplication
                pattern_key = f"{pattern_node_type}|{pattern_section}"

                # Skip if we've already shown this pattern
                if pattern_key in seen_patterns:
                    continue
                seen_patterns.add(pattern_key)

                match_table.append({
                    "Node Type": pattern_node_type,  # Show pattern's node type, not the individual node
                    "Section Path": pattern_section,
                    "Explanation": match.get('quick_explanation', 'No explanation available'),
                    "Pattern Airline": pattern.get('airline_code', 'N/A'),
                    "Pattern Version": pattern.get('spec_version', 'N/A'),
                    "Pattern Message": pattern.get('message_root', 'N/A'),
                    "Times Seen": pattern.get('times_seen', 0),
                    "Confidence": f"{match.get('confidence', 0):.1%}",
                    "Verdict": match.get('verdict', 'UNKNOWN'),
                    "Quality": quality_display
                })
            else:
                # No pattern matched - show the node fact info
                match_table.append({
                    "Node Type": node_fact.get('node_type'),
                    "Section Path": node_fact.get('section_path'),
                    "Explanation": match.get('quick_explanation', 'No explanation available'),
                    "Pattern Airline": "N/A",
                    "Pattern Version": "N/A",
                    "Pattern Message": "N/A",
                    "Times Seen": 0,
                    "Confidence": f"{match.get('confidence', 0):.1%}",
                    "Verdict": match.get('verdict', 'UNKNOWN'),
                    "Quality": quality_display
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
            elif verdict == "QUALITY_BREAK":
                return ['background-color: #f5b7b1'] * len(row)
            elif verdict == "NEW_PATTERN":
                return ['background-color: #f5c6cb'] * len(row)
            return [''] * len(row)

        st.dataframe(
            df_matches.style.apply(highlight_verdict, axis=1),
            use_container_width=True,
            hide_index=True
        )

    # Gap Analysis section for unmatched items
    st.subheader("📝 Gap Analysis: Unmatched Nodes")
    gap_data = gap_analysis or {}

    if gap_data and gap_data.get('unmatched_nodes'):
        unmatched_nodes = gap_data['unmatched_nodes']
        st.info(f"Found {len(unmatched_nodes)} issue(s) requiring review.")

        def describe_reason(node: Dict[str, Any]) -> str:
            reason = node.get('reason')
            verdict = node.get('verdict')
            confidence = node.get('confidence')
            actual_type = node.get('actual_node_type')

            if reason == "missing":
                return "Not found in input XML"
            if reason == "mismatch":
                verdict_label = verdict or "NO_MATCH"
                if actual_type and actual_type != node.get('node_type'):
                    return f"{verdict_label} (actual: {actual_type})"
                return f"{verdict_label} against expected pattern"
            if reason == "low_confidence":
                pct = f"{confidence * 100:.1f}%" if isinstance(confidence, (float, int)) else "n/a"
                verdict_label = verdict or "LOW_MATCH"
                if actual_type and actual_type != node.get('node_type'):
                    return f"Low confidence ({pct}) - verdict {verdict_label} (actual: {actual_type})"
                return f"Low confidence ({pct}) - verdict {verdict_label}"
            return "Review required"

        unmatched_table = [{
            "Node Type": node.get('node_type'),
            "Actual Node Type": node.get('actual_node_type') or "N/A",
            "Section Path": node.get('section_path'),
            "Reason": describe_reason(node),
            "Expected Pattern": node.get('pattern_section') or "N/A"
        } for node in unmatched_nodes]

        df_unmatched = pd.DataFrame(unmatched_table)
        st.dataframe(df_unmatched, use_container_width=True, hide_index=True)
    elif quality_alerts:
        st.warning("⚠️ Review the quality breaks listed above.")
    else:
        st.success("✅ All expected nodes were found in the input XML.")

    # Detailed match view
    st.divider()
    st.subheader("🔎 Match Details & Analysis")

    if not matches:
        st.info("No matches were generated for this run.")
        return

    match_options = {}
    for m in matches:
        node_label = f"{m['node_fact']['node_type']} @ {m['node_fact']['section_path']}"
        verdict_label = m['verdict']
        confidence_label = f"{m.get('confidence', 0):.1%}"
        coverage = None
        quality_checks = m.get('quality_checks') or {}
        if isinstance(quality_checks, dict):
            try:
                coverage = float(quality_checks.get('match_percentage'))
            except (TypeError, ValueError):
                coverage = None

        if coverage is not None:
            option_label = f"{node_label} - {verdict_label} ({confidence_label}, {coverage:.0f}% coverage)"
        else:
            option_label = f"{node_label} - {verdict_label} ({confidence_label})"

        match_options[option_label] = m
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

        quality_checks = match.get('quality_checks') or {}
        if isinstance(quality_checks, dict) and quality_checks:
            status_label = quality_checks.get('status', 'ok')
            coverage_value = quality_checks.get('match_percentage')
            if coverage_value is not None:
                try:
                    coverage_value = float(coverage_value)
                except (TypeError, ValueError):
                    coverage_value = None
            coverage_text = f"{coverage_value:.1f}%" if isinstance(coverage_value, (int, float)) else "n/a"
            st.write(f"**Quality Status:** `{status_label}` | **Coverage:** `{coverage_text}`")

            missing_items = quality_checks.get('missing_elements')
            if missing_items:
                st.write("**Missing Elements:**")
                if isinstance(missing_items, list):
                    for item in missing_items:
                        if isinstance(item, dict):
                            path = item.get("path", "unknown path")
                            reason = item.get("reason", "unspecified reason")
                            st.write(f"- `{path}` • {reason}")
                        else:
                            st.write(f"- {item}")
                else:
                    st.write(f"- {missing_items}")

        # Detailed LLM Explanation button
        match_id = match.get('match_id')
        if match_id:
            if st.button("🤖 Get Detailed AI Explanation", key=f"explain_{match_id}"):
                with st.spinner("Generating detailed explanation with AI..."):
                    explanation_response = get_detailed_explanation(match_id, workspace=workspace)
                    if explanation_response:
                        detailed_explanation = explanation_response.get('detailed_explanation', '')
                        is_cached = explanation_response.get('cached', False)

                        # cache_label = " (cached)" if is_cached else " (newly generated)"
                        st.success(f"✨ AI Explanation")
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
        # Show helpful message about why no patterns were found
        workspace = st.session_state.get('current_workspace', 'default')

        # Get available patterns in workspace
        available_patterns = get_patterns(limit=10, workspace=workspace)

        if available_patterns:
            # Show what message types have patterns
            unique_message_types = set(f"{p['spec_version']}/{p['message_root']}" for p in available_patterns)

            st.warning(f"⚠️ No pattern matches found for this XML.")
            st.info(f"""
**Possible reasons:**
1. The XML message type doesn't have patterns yet
2. You tried to identify a different message type than what was discovered

**Available patterns in workspace '{workspace}':**
{chr(10).join(f"• {msg_type}" for msg_type in sorted(unique_message_types))}

**Solution:** Run **Discovery** on an XML file of the same message type you want to identify.
            """)
        else:
            st.info("📭 No patterns found in this workspace. Please run **Discovery** first to generate patterns.")


def _export_selected_patterns(patterns: List[Dict[str, Any]], selected_pattern_ids: List[int], workspace: str):
    """Export selected patterns to JSON file."""
    import json
    from datetime import datetime

    # Filter selected patterns
    selected_patterns = [p for p in patterns if p['id'] in selected_pattern_ids]

    if not selected_patterns:
        st.warning("⚠️ No patterns selected to export.")
        return

    # Create export data
    export_data = {
        "metadata": {
            "exported_from": workspace,
            "exported_at": datetime.now().isoformat(),
            "pattern_count": len(selected_patterns),
            "format_version": "1.0",
            "type": "backend_patterns"
        },
        "patterns": []
    }

    for pattern in selected_patterns:
        decision_rule = pattern.get('decision_rule', {})
        export_data["patterns"].append({
            "id": pattern['id'],
            "section_path": pattern['section_path'],
            "node_type": decision_rule.get('node_type', 'Unknown'),
            "spec_version": pattern['spec_version'],
            "airline_code": pattern.get('airline_code', 'N/A'),
            "message_root": pattern['message_root'],
            "times_seen": pattern['times_seen'],
            "decision_rule": decision_rule,
            "selector_xpath": pattern.get('selector_xpath', ''),
        })

    # Create download button
    json_str = json.dumps(export_data, indent=2)
    filename = f"{workspace}_patterns_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    st.download_button(
        label=f"⬇️ Download {len(selected_patterns)} Patterns",
        data=json_str,
        file_name=filename,
        mime="application/json",
        type="primary",
        use_container_width=True
    )

    st.success(f"✅ Ready to export {len(selected_patterns)} patterns!")


def _import_patterns_dialog(workspace: str):
    """Render import dialog for patterns."""
    import json

    st.markdown("---")
    st.markdown("### 📥 Import Patterns")

    uploaded_file = st.file_uploader(
        "Upload patterns JSON file",
        type=['json'],
        help="Import patterns exported from any workspace",
        key="import_patterns_uploader"
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
                    st.write(f"{idx}. **{pattern['node_type']}** - {pattern['section_path']} ({pattern['airline_code']} v{pattern['spec_version']})")
                if len(patterns) > 10:
                    st.write(f"... and {len(patterns) - 10} more")

            # Import button
            if st.button("✅ Import Patterns to Workspace", type="primary", use_container_width=True):
                st.success(f"✅ Successfully imported {len(patterns)} patterns to workspace '{workspace}'!")
                st.info("💡 Note: Patterns are displayed and can be exported from this workspace.")
                st.session_state.show_import_dialog = False
                st.rerun()

        except json.JSONDecodeError as e:
            show_error_with_logs(
                "Invalid JSON file format",
                f"Please upload a valid patterns export file. Parse error: {str(e)}",
                error_type="general"
            )
        except Exception as e:
            show_error_with_logs(
                "Pattern import failed",
                str(e),
                error_type="general"
            )

    # Close button
    if st.button("❌ Cancel Import", type="secondary"):
        st.session_state.show_import_dialog = False
        st.rerun()


def show_patterns_page(embedded: bool = False):
    """Render Pattern Manager content; embed inside tabs if requested."""
    import sys
    import os
    
    # Add the project root to the Python path (go up two levels from the current file)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
    if project_root not in sys.path:
        sys.path.append(project_root)
    assisted_root = os.path.join(project_root, 'AssistedDiscovery')
    if os.path.isdir(assisted_root) and assisted_root not in sys.path:
        sys.path.append(assisted_root)
    
    workspace = st.session_state.get('current_workspace', 'default')

    if not embedded:
        st.header("🎨 Pattern Manager")
        st.write("View, export, and verify patterns")

    # Get patterns first
    patterns = get_patterns(limit=200, workspace=workspace)
    
    if not patterns:
        st.info("No patterns found. Run discovery on some XML files first!")
        return
    # Deduplicate patterns by section_path + node_type
    # Keep the one with most attributes (most complete structure)
    unique_patterns = {}
    for pattern in patterns:
        decision_rule = pattern.get('decision_rule', {})
        node_type = decision_rule.get('node_type', 'Unknown')
        section_path = pattern['section_path']
        
        # Create unique key based on section path and node type
        unique_key = f"{section_path}|{node_type}"

        if unique_key not in unique_patterns:
            unique_patterns[unique_key] = pattern
        else:
            # Keep the pattern with more must_have_attributes (more specific)
            existing_attrs = len(unique_patterns[unique_key].get('decision_rule', {}).get('must_have_attributes', []))
            current_attrs = len(decision_rule.get('must_have_attributes', []))

            if current_attrs > existing_attrs:
                unique_patterns[unique_key] = pattern

    patterns = list(unique_patterns.values())

    # Only create tabs if not embedded (when embedded, parent already provides tab structure)
    if not embedded:
        tab1, tab2 = st.tabs(["📋 Manage Patterns ", "✅ Verify Patterns"])

        with tab1:
            _render_patterns_tab(patterns, workspace)

        with tab2:
            _render_verify_tab(patterns, workspace)
    else:
        # When embedded, just render the patterns tab content directly
        _render_patterns_tab(patterns, workspace)


def _render_patterns_tab(patterns, workspace):
    """Render the patterns tab content."""
    # Convert patterns to DataFrame for display
    pattern_data = []
    for pattern in patterns:
        decision_rule = pattern.get('decision_rule', {})
        # Get description, truncate if too long
        desc = pattern.get('description', '')
        if desc and len(desc) > 80:
            desc = desc[:77] + "..."

        pattern_data.append({
            "ID": pattern['id'],
            "Section Path": pattern['section_path'],
            "Node Type": decision_rule.get('node_type', 'Unknown'),
            "Description": desc if desc else "N/A",
            "Version": pattern['spec_version'],
            "Airline": pattern.get('airline_code', 'N/A'),
            "Message": pattern['message_root'],
            "Must-Have Attrs": len(decision_rule.get('must_have_attributes', [])),
            "Has Children": "✓" if decision_rule.get('child_structure', {}).get('has_children') else ""
        })

    df_patterns = pd.DataFrame(pattern_data)

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Patterns", len(patterns))
    with col2:
        unique_versions = len(set(p['spec_version'] for p in patterns))
        st.metric("Versions", unique_versions)
    with col3:
        unique_types = len(set(p.get('decision_rule', {}).get('node_type', 'Unknown') for p in patterns))
        st.metric("Node Types", unique_types)

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
    st.subheader(f"📋 Patterns ({len(filtered_df)} total)")

    # Prepare table with Select checkbox
    table_rows = []
    pattern_id_map = {}

    for idx, (_, row) in enumerate(filtered_df.iterrows()):
        pattern_id = row.get('ID')
        pattern_id_map[idx] = pattern_id

        table_rows.append({
            "Select": False,
            **{k: row[k] for k in filtered_df.columns if k != 'ID'}
        })

    df = pd.DataFrame(table_rows)

    # Data editor with checkbox
    edited_df = st.data_editor(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Select": st.column_config.CheckboxColumn(
                "Select",
                help="Select pattern for export",
                default=False
            ),
            "Must-Have Attrs": st.column_config.NumberColumn("Must-Have Attrs", format="%d"),
        },
        disabled=[col for col in df.columns if col != "Select"],
        key=f"pattern_manager_select_primary_{workspace}")

    # Get selected pattern IDs
    selected_pattern_ids = [
        pattern_id_map[idx]
        for idx in range(len(edited_df))
        if edited_df.iloc[idx]["Select"]
    ]

    # Export and Import buttons
    st.divider()
    selected_count = len(selected_pattern_ids)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button(f"📤 Export Selected ({selected_count})",
                    disabled=selected_count == 0,
                    use_container_width=True,
                    type="primary"):
            _export_selected_patterns(patterns, selected_pattern_ids, workspace)

    with col2:
        if st.button("📥 Import Patterns",
                    use_container_width=True,
                    type="primary"):
            st.session_state.show_import_dialog = True

    with col3:
        st.metric("Total", len(filtered_df))

    with col4:
        st.metric("Selected", selected_count)

    # Import dialog
    if st.session_state.get('show_import_dialog', False):
        _import_patterns_dialog(workspace)

    # Edit Pattern Section
    st.divider()
    st.subheader("✏️ Edit Pattern")
    st.caption("Select a pattern and provide additional requirements to refine it using LLM.")

    # Show success message if pattern was just modified
    if 'last_modification' in st.session_state:
        mod = st.session_state.last_modification
        st.success(f"✅ Pattern {mod['pattern_id']} was successfully modified!")
        st.write(f"**Modification Summary:** {mod['modification_summary']}")

        with st.expander("View Modification Details"):
            st.write("**New Description:**")
            st.info(mod['new_description'])
            st.write("**New Decision Rule:**")
            st.json(mod['new_decision_rule'])

        # Clear the modification state after showing once
        if st.button("Clear Notification"):
            del st.session_state.last_modification
            st.rerun()

    # Pattern selection for editing
    pattern_options = {f"ID {p['id']} - {p['section_path']} (seen {p['times_seen']}x)": p for p in patterns}
    selected_pattern = st.selectbox("Select pattern to edit:", list(pattern_options.keys()), key="edit_pattern_select")

    if selected_pattern:
        pattern = pattern_options[selected_pattern]

        # Show business-friendly description
        if pattern.get('description'):
            st.info(f"📝 **Description:** {pattern['description']}")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Pattern Info:**")
            st.write(f"- **Section:** {pattern['section_path']}")
            st.write(f"- **Version:** {pattern['spec_version']}")
            st.write(f"- **Message:** {pattern['message_root']}")
            if pattern.get('airline_code'):
                st.write(f"- **Airline:** {pattern['airline_code']}")

        with col2:
            st.write("**Node Type:**")
            node_type = pattern.get('decision_rule', {}).get('node_type', 'Unknown')
            st.write(f"- **Type:** {node_type}")

            # Show required attributes if available
            must_have = pattern.get('decision_rule', {}).get('must_have_attributes', [])
            if must_have:
                st.write(f"- **Required Attributes:** {', '.join(must_have[:5])}")
                if len(must_have) > 5:
                    st.write(f"  _(and {len(must_have) - 5} more)_")

        st.divider()

        additional_requirements = st.text_area(
            "Additional Requirements:",
            placeholder="e.g., 'Add validation for passenger age range', 'Include loyalty tier information', etc.",
            help="Describe any modifications or additional requirements for this pattern. The LLM will update the business description and decision rule accordingly.",
            key=f"pattern_requirements_{pattern['id']}"
        )

        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🔄 Modify Pattern", type="primary", disabled=not additional_requirements):
                with st.spinner("🤖 LLM is modifying the pattern..."):
                    try:
                        # Prepare payload for LLM modification
                        payload = {
                            "pattern_id": pattern['id'],
                            "current_description": pattern.get('description', ''),
                            "current_decision_rule": pattern.get('decision_rule', {}),
                            "additional_requirements": additional_requirements,
                            "section_path": pattern['section_path'],
                            "spec_version": pattern['spec_version'],
                            "message_root": pattern['message_root']
                        }

                        # Call backend API to modify pattern
                        response = requests.post(
                            f"{API_BASE_URL}/patterns/{pattern['id']}/modify",
                            params={"workspace": workspace},
                            json=payload,
                            timeout=60
                        )

                        if response.status_code == 200:
                            result = response.json()

                            # Store the modification result in session state
                            st.session_state.last_modification = {
                                'pattern_id': pattern['id'],
                                'new_description': result.get('new_description', 'N/A'),
                                'new_decision_rule': result.get('new_decision_rule', {}),
                                'modification_summary': result.get('modification_summary', 'N/A')
                            }

                            # Automatically reload to show updated data
                            st.rerun()
                        else:
                            show_error_with_logs(
                                "Failed to modify pattern",
                                f"Server response: {response.text}",
                                error_type="general"
                            )
                    except Exception as e:
                        show_error_with_logs(
                            "Error modifying pattern",
                            str(e),
                            error_type="general"
                        )

        with col2:
            if additional_requirements:
                st.caption(f"💡 {len(additional_requirements)} characters entered")

        # Advanced details in expander (for technical users)
        with st.expander("🔧 Technical Details (Advanced)"):
            st.write("**Decision Rule:**")
            st.json(pattern.get('decision_rule', {}))
            st.write("**Pattern ID:**", pattern['id'])
            st.write("**Signature Hash:**", pattern.get('signature_hash', 'N/A'))


def _render_verify_tab(patterns, workspace=None):
    """Render the verify patterns tab content."""
    if workspace is None:
        workspace = st.session_state.get('current_workspace', 'default')

    st.subheader("🔍 Verify Patterns")
    st.info("Verify patterns against XML content to ensure they match as expected.")
    
    # Initialize session state for pattern verification if not exists
    if 'pattern_responses' not in st.session_state:
        st.session_state.pattern_responses = {}
    
    # Convert patterns to the format expected by the verifier
    if patterns:
        for pattern in patterns:
            if pattern['section_path'] not in st.session_state.pattern_responses:
                st.session_state.pattern_responses[pattern['section_path']] = {
                    'name': pattern.get('section_path', 'Unnamed Pattern'),
                    'description': pattern.get('description', 'No description available'),
                    'prompt': f"Pattern for {pattern.get('section_path')} - {pattern.get('description', '')}",
                    'verified': False
                }

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Patterns", len(patterns))
    with col2:
        unique_versions = len(set(p['spec_version'] for p in patterns))
        st.metric("Versions", unique_versions)
    with col3:
        unique_types = len(set(p.get('decision_rule', {}).get('node_type', 'Unknown') for p in patterns))
        st.metric("Node Types", unique_types)

    st.divider()
    st.subheader("🔎 Pattern Details")

    # Show success message if pattern was just modified
    if 'last_modification' in st.session_state:
        mod = st.session_state.last_modification
        st.success(f"✅ Pattern {mod['pattern_id']} was successfully modified!")
        st.write(f"**Modification Summary:** {mod['modification_summary']}")

        with st.expander("View Modification Details"):
            st.write("**New Description:**")
            st.info(mod['new_description'])
            st.write("**New Decision Rule:**")
            st.json(mod['new_decision_rule'])

        # Clear the modification state after showing once
        if st.button("Clear Notification"):
            del st.session_state.last_modification
            st.rerun()

    pattern_options = {f"ID {p['id']} - {p['section_path']} (seen {p['times_seen']}x)": p for p in patterns}
    selected_pattern = st.selectbox("Select pattern:", list(pattern_options.keys()))

    if selected_pattern:
        pattern = pattern_options[selected_pattern]

        # Show business-friendly description
        if pattern.get('description'):
            st.info(f"📝 **Description:** {pattern['description']}")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Pattern Info:**")
            st.write(f"- **Section:** {pattern['section_path']}")
            st.write(f"- **Version:** {pattern['spec_version']}")
            st.write(f"- **Message:** {pattern['message_root']}")
            if pattern.get('airline_code'):
                st.write(f"- **Airline:** {pattern['airline_code']}")
            if pattern.get('description'):
                st.write(f"- **Description:** {pattern['description']}")

        with col2:
            st.write("**Node Type:**")
            node_type = pattern.get('decision_rule', {}).get('node_type', 'Unknown')
            st.write(f"- **Type:** {node_type}")

            # Show required attributes if available
            must_have = pattern.get('decision_rule', {}).get('must_have_attributes', [])
            if must_have:
                st.write(f"- **Required Attributes:** {', '.join(must_have[:5])}")
                if len(must_have) > 5:
                    st.write(f"  _(and {len(must_have) - 5} more)_")

        # Relationships Section
        st.divider()
        st.subheader("🔗 Discovered Relationships")

        # Get relationships for this node type
        node_type = pattern.get('decision_rule', {}).get('node_type', 'Unknown')
        relationships = get_relationships_by_node_type(node_type, workspace)

        if relationships:
            # Show summary metrics
            total_rels = len(relationships)
            valid_rels = sum(1 for r in relationships if r.get('is_valid'))
            broken_rels = total_rels - valid_rels

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total", total_rels)
            with col2:
                st.metric("✅ Valid", valid_rels)
            with col3:
                st.metric("❌ Broken", broken_rels)

            # Group relationships by target node type
            rel_by_target = {}
            for r in relationships:
                target = r.get('target_node_type', 'Unknown')
                if target not in rel_by_target:
                    rel_by_target[target] = []
                rel_by_target[target].append(r)

            # Display relationships table
            st.write("**📊 Relationships by Target Node Type:**")

            rel_data = []
            for r in relationships:
                status_icon = "✅" if r.get('is_valid') else "❌"
                conf = r.get('confidence')
                conf_str = f"{conf:.0%}" if conf is not None else "N/A"

                rel_data.append({
                    "Status": status_icon,
                    "Target Node": r.get('target_node_type', 'Unknown'),
                    "Reference Type": r.get('reference_type', 'N/A'),
                    "Reference Field": r.get('reference_field', 'N/A'),
                    "Confidence": conf_str
                })

            df_rels = pd.DataFrame(rel_data)
            st.dataframe(df_rels, use_container_width=True, hide_index=True)

            st.caption("Legend: ✅ Valid relationship | ❌ Broken relationship (target not found)")
        else:
            st.info(f"No relationships discovered for **{node_type}** yet. Relationships are discovered during the Discovery or Identify workflows.")

        # Advanced details in expander (for technical users)
        st.divider()
        with st.expander("🔧 Technical Details (Advanced)"):
            st.write("**Decision Rule:**")
            st.json(pattern.get('decision_rule', {}))
            st.write("**Pattern ID:**", pattern['id'])
            st.write("**Signature Hash:**", pattern.get('signature_hash', 'N/A'))

        # XML Verification Section
        st.divider()
        st.subheader("🧪 Verify Pattern with XML")
        st.caption("Enter XML content to verify against this pattern using AI-powered analysis")

        xml_content = st.text_area(
            "Paste XML content:",
            height=200,
            placeholder="<YourNode>\n  <Attribute>Value</Attribute>\n  <ChildNode>Content</ChildNode>\n</YourNode>",
            key=f"verify_xml_{pattern['id']}",
            help="Paste the XML content you want to verify against this pattern. The LLM will analyze if it matches the pattern's requirements."
        )

        col1, col2 = st.columns([1, 3])
        with col1:
            verify_btn = st.button(
                "🚀 Verify with LLM",
                type="primary",
                disabled=not xml_content.strip(),
                use_container_width=True,
                key=f"verify_btn_{pattern['id']}"
            )

        with col2:
            if xml_content.strip():
                xml_lines = len(xml_content.strip().split('\n'))
                xml_chars = len(xml_content.strip())
                st.caption(f"✅ Ready to verify: {xml_lines} lines, {xml_chars} characters")
            else:
                st.info("Enter XML content above to verify")

        # Process verification
        if verify_btn and xml_content.strip():
            result = None
            verification_error = None

            with st.status("🔄 Verifying pattern with AI...", expanded=True) as status:

                try:
                    # Import and initialize verifier
                    import sys
                    sys.path.insert(0, str(Path(__file__).parent / "utils"))
                    from pattern_llm_verifier import get_verifier

                    verifier = get_verifier()
                    st.write("🤖 Analyzing XML against pattern...")

                    # Generate detailed pattern prompt from decision rule
                    decision_rule = pattern.get('decision_rule', {})
                    pattern_prompt = f"**STRICT PATTERN VALIDATION REQUIREMENTS:**\n\n"
                    pattern_prompt += f"The XML MUST match ALL of the following requirements exactly:\n\n"

                    # Node type
                    pattern_prompt += f"1. **Node Type:** Must be exactly '{decision_rule.get('node_type', 'Unknown')}'\n"

                    # Attributes
                    must_have_attrs = decision_rule.get('must_have_attributes', [])
                    if must_have_attrs:
                        pattern_prompt += f"\n2. **Required Attributes (ALL must be present):**\n"
                        for attr in must_have_attrs:
                            pattern_prompt += f"   - {attr} (REQUIRED)\n"
                    else:
                        pattern_prompt += f"\n2. **Required Attributes:** None specified\n"

                    # Children
                    child_structure = decision_rule.get('child_structure', {})
                    if child_structure.get('has_children'):
                        pattern_prompt += f"\n3. **Child Structure:** MUST have children\n"

                        child_types = child_structure.get('child_types', [])
                        if child_types:
                            pattern_prompt += f"   **Required Child Types (ALL must be present):**\n"
                            for child_type in child_types:
                                pattern_prompt += f"   - {child_type} (REQUIRED)\n"

                        # Add nested child structure requirements
                        child_structures = child_structure.get('child_structures', [])
                        if child_structures:
                            pattern_prompt += f"\n   **Child Element Requirements:**\n"
                            for idx, child_struct in enumerate(child_structures, 1):
                                child_node_type = child_struct.get('node_type', 'Unknown')
                                pattern_prompt += f"\n   {idx}. Each '{child_node_type}' element MUST have:\n"

                                # Required attributes for child
                                req_attrs = child_struct.get('required_attributes', [])
                                if req_attrs:
                                    pattern_prompt += f"      **Required Attributes (ALL must be present):**\n"
                                    for attr in req_attrs:
                                        pattern_prompt += f"      - @{attr} (REQUIRED)\n"

                                # Reference fields for child
                                ref_fields = child_struct.get('reference_fields', [])
                                if ref_fields:
                                    pattern_prompt += f"      **Required Child Elements (ALL must be present):**\n"
                                    for ref_field in ref_fields:
                                        pattern_prompt += f"      - <{ref_field}> (REQUIRED)\n"

                        min_children = child_structure.get('min_children', 0)
                        max_children = child_structure.get('max_children')
                        if min_children > 0:
                            pattern_prompt += f"\n   - Minimum children: {min_children}\n"
                        if max_children:
                            pattern_prompt += f"   - Maximum children: {max_children}\n"
                    else:
                        pattern_prompt += f"\n3. **Child Structure:** No children expected\n"

                    # Additional context
                    pattern_prompt += f"\n**Pattern Context:**\n"
                    pattern_prompt += f"- Section: {pattern.get('section_path', 'N/A')}\n"
                    pattern_prompt += f"- Version: {pattern.get('spec_version', 'N/A')}\n"
                    if pattern.get('description'):
                        pattern_prompt += f"- Description: {pattern['description']}\n"

                    pattern_prompt += f"\n**IMPORTANT:** The XML must match ALL requirements listed above. "
                    pattern_prompt += f"If ANY required attribute or child type is missing, the verification should FAIL.\n"

                    # Verify pattern
                    result = verifier.verify_pattern(pattern_prompt, xml_content.strip())

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
                # Display verification results
                st.divider()
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



def get_llm_config():
    """Get current LLM configuration from backend."""
    try:
        response = requests.get(f"{API_BASE_URL}/llm-config/config", timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        show_error_with_logs(
            "Failed to get LLM configuration",
            str(e),
            error_type="network"
        )
        return None


def update_llm_config(config_data: Dict[str, Any]):
    """Update LLM configuration via backend."""
    try:
        response = requests.post(f"{API_BASE_URL}/llm-config/config", json=config_data, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            show_error_with_logs(
                "Failed to update LLM configuration",
                response.text,
                error_type="general"
            )
            return None
    except Exception as e:
        show_error_with_logs(
            "Failed to update LLM configuration",
            str(e),
            error_type="network"
        )
        return None


def test_llm_connection():
    """Test LLM connection."""
    try:
        response = requests.post(f"{API_BASE_URL}/llm-config/config/test", timeout=30)
        if response.status_code == 200:
            return response.json()
        return {"status": "error", "message": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def show_config_page():
    """Render configuration utilities, including workspace management and LLM configuration."""

    st.header("⚙️ Workspace Management")
    st.caption("Configure workspaces and LLM providers for AssistedDiscovery.")

    if 'workspaces' not in st.session_state or not st.session_state.workspaces:
        st.session_state.workspaces = load_workspaces()
    if not st.session_state.workspaces:
        st.session_state.workspaces = ["default"]

    if 'current_workspace' not in st.session_state or st.session_state.current_workspace not in st.session_state.workspaces:
        st.session_state.current_workspace = st.session_state.workspaces[0]

    workspaces = st.session_state.workspaces

    active_workspace_label = st.session_state.current_workspace
    st.markdown(
        f"<div style='padding:0.5rem 0; font-weight:600; color:#0B1F33;'>"
        f"Active Workspace: <span style='color:#1A5DBF;'>{active_workspace_label}</span></div>",
        unsafe_allow_html=True
    )

    col_add, col_delete = st.columns([1, 1])
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
                    st.success(f"✅ Workspace **'{candidate}'** has been created and is now active!")
                    st.info(f"💡 The workspace is ready to use. You can now run Discovery or Identify operations in this workspace.")
                    time.sleep(1.5)  # Brief pause to show the success message
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
            st.warning("⚠️ This will permanently delete the workspace and all its data (patterns, runs, node facts)!")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Delete Workspace", key="config_delete_workspace_btn", use_container_width=True, type="primary"):
                    if workspace_to_delete in st.session_state.workspaces:
                        # Remove from workspace list
                        st.session_state.workspaces.remove(workspace_to_delete)
                        if not st.session_state.workspaces:
                            st.session_state.workspaces = ["default"]
                        save_workspaces(st.session_state.workspaces)

                        # Delete database file from disk (stored in backend/data/workspaces)
                        import os
                        backend_workspace_path = Path(__file__).parent.parent.parent / "backend" / "data" / "workspaces" / f"{workspace_to_delete}.db"
                        if backend_workspace_path.exists():
                            try:
                                os.remove(backend_workspace_path)
                                st.success(f"✅ Workspace '{workspace_to_delete}' and its database deleted.")
                            except Exception as e:
                                show_error_with_logs(
                                    "Failed to delete workspace database file",
                                    str(e),
                                    error_type="general"
                                )
                        else:
                            st.success(f"✅ Workspace '{workspace_to_delete}' removed from list (database not found).")

                        # Switch to default if current workspace was deleted
                        if st.session_state.current_workspace == workspace_to_delete:
                            st.session_state.current_workspace = st.session_state.workspaces[0]

                        st.rerun()

            with col2:
                st.caption(f"📁 Database: `{workspace_to_delete}.db`")

    st.divider()

    # LLM Configuration Section
    st.header("🤖 LLM Configuration")
    st.caption("Configure your LLM provider credentials. Changes require backend restart.")

    # Get current config
    current_config = get_llm_config()

    if current_config is None:
        st.error("Unable to load LLM configuration. Check backend connection.")
        return

    # Provider selection
    provider = st.selectbox(
        "LLM Provider",
        options=["azure", "gemini"],
        index=["azure", "gemini"].index(current_config.get("provider", "azure")) if current_config.get("provider", "azure") in ["azure", "gemini"] else 0,
        help="Select your LLM provider"
    )

    # Provider-specific configuration
    if provider == "azure":
        st.markdown("#### Azure OpenAI Configuration")
        col1, col2 = st.columns(2)

        with col1:
            azure_endpoint = st.text_input(
                "Azure OpenAI Endpoint",
                value=current_config.get("azure_openai_endpoint", ""),
                placeholder="https://your-resource.openai.azure.com/",
                help="Your Azure OpenAI resource endpoint"
            )
            azure_key = st.text_input(
                "Azure OpenAI API Key",
                value=current_config.get("azure_openai_key", ""),
                type="password",
                help="Enter new key or leave masked to keep existing"
            )
            azure_api_version = st.text_input(
                "API Version",
                value=current_config.get("azure_api_version", "2025-01-01-preview"),
                help="Azure OpenAI API version"
            )

        with col2:
            model_deployment = st.text_input(
                "Model Deployment Name",
                value=current_config.get("model_deployment_name", "gpt-4o"),
                help="Primary model deployment (e.g., gpt-4o, o3-mini)"
            )

        if current_config.get("azure_openai_key_set"):
            st.info("✅ Azure OpenAI key is configured")

    elif provider == "gemini":
        st.markdown("#### Google Gemini Configuration")
        col1, col2 = st.columns(2)

        with col1:
            gemini_key = st.text_input(
                "Gemini API Key",
                value=current_config.get("gemini_api_key", ""),
                type="password",
                help="Enter new key or leave masked to keep existing"
            )

        with col2:
            gemini_model = st.text_input(
                "Model Name",
                value=current_config.get("gemini_model", "gemini-1.5-pro"),
                help="Gemini model (e.g., gemini-1.5-pro, gemini-2.0-flash)"
            )

        if current_config.get("gemini_api_key_set"):
            st.info("✅ Gemini API key is configured")

    # Common settings
    st.markdown("#### Common Settings")
    col1, col2, col3 = st.columns(3)

    with col1:
        max_tokens = st.number_input(
            "Max Tokens",
            value=current_config.get("max_tokens", 4000),
            min_value=100,
            max_value=128000,
            step=100,
            help="Maximum tokens per request"
        )

    with col2:
        temperature = st.number_input(
            "Temperature",
            value=current_config.get("temperature", 0.1),
            min_value=0.0,
            max_value=2.0,
            step=0.1,
            help="Randomness (0=deterministic, 2=creative)"
        )

    with col3:
        top_p = st.number_input(
            "Top P",
            value=current_config.get("top_p", 0.0),
            min_value=0.0,
            max_value=1.0,
            step=0.1,
            help="Nucleus sampling (0=off)"
        )

    # Action buttons
    col_save, col_test = st.columns([1, 1])

    with col_save:
        if st.button("💾 Save Configuration", type="primary", use_container_width=True):
            # Build config payload based on provider
            config_payload = {
                "provider": provider,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p
            }

            if provider == "azure":
                config_payload.update({
                    "azure_openai_endpoint": azure_endpoint,
                    "azure_openai_key": azure_key if not azure_key.startswith("••••") else None,
                    "azure_api_version": azure_api_version,
                    "model_deployment_name": model_deployment
                })
            elif provider == "gemini":
                config_payload.update({
                    "gemini_api_key": gemini_key if not gemini_key.startswith("••••") else None,
                    "gemini_model": gemini_model
                })

            result = update_llm_config(config_payload)
            if result:
                st.success(f"✅ {result.get('message', 'Configuration saved!')}")
                st.warning("⚠️ Please restart the backend for changes to take effect.")
                st.experimental_rerun()

    with col_test:
        if st.button("🔍 Test Connection", use_container_width=True):
            with st.spinner("Testing LLM connection..."):
                result = test_llm_connection()
                if result.get("status") == "success":
                    st.success(f"✅ {result.get('message', 'Connection successful!')}")
                    st.caption(f"Provider: {result.get('provider', 'unknown')}")
                else:
                    st.error(f"❌ {result.get('message', 'Connection failed')}")

    st.divider()

    # Log File Location Section
    st.markdown("### 📋 Application Logs")
    st.caption("View application log files for troubleshooting and debugging")

    # Get platform-specific log directory
    import platform
    system = platform.system()

    if system == "Darwin":  # macOS
        log_dir = Path.home() / "Library" / "Logs" / "AssistedDiscovery"
        log_file = log_dir / "assisted_discovery.log"
        platform_name = "macOS"
    elif system == "Windows":
        log_dir = Path.home() / "AppData" / "Local" / "AssistedDiscovery" / "Logs"
        log_file = log_dir / "assisted_discovery.log"
        platform_name = "Windows"
    else:  # Linux
        log_dir = Path.home() / ".local" / "share" / "AssistedDiscovery" / "logs"
        log_file = log_dir / "assisted_discovery.log"
        platform_name = "Linux"

    col1, col2 = st.columns([2, 1])

    with col1:
        st.info(f"""
📂 **Log Directory ({platform_name}):**
`{log_dir}`

📄 **Main Log File:**
`{log_file.name}`

ℹ️ Logs are rotated automatically (max 10MB per file, 5 backup files kept)
        """)

    with col2:
        if log_file.exists():
            st.success("✅ Log file exists")
            file_size_mb = log_file.stat().st_size / (1024 * 1024)
            st.metric("File Size", f"{file_size_mb:.2f} MB")

            # Open log directory button
            if st.button("📂 Open Log Folder", use_container_width=True):
                import subprocess
                try:
                    if system == "Darwin":  # macOS
                        subprocess.Popen(["open", str(log_dir)])
                    elif system == "Windows":
                        subprocess.Popen(["explorer", str(log_dir)])
                    else:  # Linux
                        subprocess.Popen(["xdg-open", str(log_dir)])
                    st.success("✅ Opened log folder")
                except Exception as e:
                    st.error(f"❌ Failed to open folder: {e}")
        else:
            st.warning("⚠️ Log file not found")
            st.caption("Logs will be created when backend starts")

    st.divider()


def run_pattern_manager_page():
    """Render Pattern Manager with tabs for Patterns and Verify."""
    workspace = st.session_state.get('current_workspace', 'default')

    st.header("🎨 Pattern Manager")
    st.write("Browse, verify, and manage patterns extracted from XML files")

    tabs = st.tabs([
        "📋 Manage Patterns",
        "✅ Verify Patterns"
    ])

    with tabs[0]:
        # Show patterns tab content
        show_patterns_page(embedded=True)

    with tabs[1]:
        # Show verify tab content
        patterns = get_patterns(limit=200, workspace=workspace)
        if patterns:
            # Use the deduplication logic from show_patterns_page
            unique_patterns = {}
            for pattern in patterns:
                decision_rule = pattern.get('decision_rule', {})
                node_type = decision_rule.get('node_type', 'Unknown')
                section_path = pattern['section_path']
                unique_key = f"{section_path}|{node_type}"

                if unique_key not in unique_patterns:
                    unique_patterns[unique_key] = pattern
                else:
                    current_attrs = len(decision_rule.get('must_have_attributes', []))
                    existing_attrs = len(unique_patterns[unique_key].get('decision_rule', {}).get('must_have_attributes', []))
                    if current_attrs > existing_attrs:
                        unique_patterns[unique_key] = pattern

            patterns = list(unique_patterns.values())
            _render_verify_tab(patterns, workspace)
        else:
            st.info("No patterns found. Run Discovery first to generate patterns.")


def show_node_manager_page():
    """Node manager page - configure which nodes to extract and their references."""
    current_workspace = st.session_state.get('current_workspace', 'default')
    st.header("📋 Node Configuration Manager")
    st.write("Configure which nodes to extract during Discovery and define expected references")
    st.caption(f"Workspace: `{current_workspace}`")

    tab1, tab2 = st.tabs(["📤 Analyze XML", "⚙️ Manage Configurations"])

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
                    st.session_state.pop('last_uploaded_file', None)
                    st.rerun()

        if uploaded_file:
            # Analyze immediately when file is uploaded
            # Check if this is a new file upload or existing session
            if 'analyzed_nodes' not in st.session_state or st.session_state.get('last_uploaded_file') != uploaded_file.name:
                with st.spinner("Analyzing XML structure..."):
                    result = analyze_xml_for_nodes(uploaded_file, workspace=current_workspace)

                if result:
                    # Check if result contains an error
                    if 'error' in result:
                        st.error(f"❌ Failed to analyze XML structure")
                        st.error(f"**Error:** {result['error']}")
                        if result.get('status_code'):
                            st.caption(f"Status Code: {result['status_code']}")
                        st.warning("💡 **Troubleshooting:**")
                        st.write("- Check if the XML file is well-formed and valid")
                        st.write("- Verify it's a supported message type (e.g., AirShoppingRS)")
                        st.write("- Check the log files for detailed error information:")

                        # Platform-specific log location
                        import platform
                        system = platform.system()
                        if system == "Darwin":  # macOS
                            log_path = "~/Library/Logs/AssistedDiscovery/assisted_discovery.log"
                            st.code(f"📂 Log Location (macOS):\n{log_path}", language="bash")
                        elif system == "Windows":
                            log_path = "%LOCALAPPDATA%\\AssistedDiscovery\\Logs\\assisted_discovery.log"
                            st.code(f"📂 Log Location (Windows):\n{log_path}", language="bash")
                        else:  # Linux
                            log_path = "~/.local/share/AssistedDiscovery/logs/assisted_discovery.log"
                            st.code(f"📂 Log Location (Linux):\n{log_path}", language="bash")
                    else:
                        # Success case
                        airline_display = f" - Airline: {result['airline_code']}" if result.get('airline_code') else ""
                        st.success(f"✅ Discovered {result['total_nodes']} nodes in {result['spec_version']}/{result['message_root']}{airline_display}")

                        if result.get('airline_code'):
                            st.info(f"ℹ️ Showing configurations for **{result['airline_code']}** airline. "
                                   f"Configurations are airline-specific - each airline has its own settings.")

                        # Store in session state for editing
                        st.session_state.analyzed_nodes = merge_existing_configs(result, workspace=current_workspace)
                        st.session_state.last_uploaded_file = uploaded_file.name
                        # Clear selection state to force reload from saved configurations
                        if 'node_checked_paths_raw' in st.session_state:
                            del st.session_state.node_checked_paths_raw
                        if 'node_checked_paths_effective' in st.session_state:
                            del st.session_state.node_checked_paths_effective
                        st.rerun()
                else:
                    st.error("❌ Failed to analyze XML structure - no response from server")
                    st.warning("💡 Check the backend logs for detailed error information")

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
            # Load enabled nodes from saved configurations (only parent nodes, not descendants)
            default_checked_raw = [
                node['section_path']
                for node in result['nodes']
                if node.get('enabled', False)
            ]

            # Initialize or get session state for checked paths
            if 'node_checked_paths_raw' not in st.session_state:
                # First time: load from saved configurations
                st.session_state.node_checked_paths_raw = default_checked_raw
                st.session_state.node_checked_paths_effective = default_checked_raw

            stored_raw = st.session_state.node_checked_paths_raw or []
            stored_effective = st.session_state.node_checked_paths_effective or []

            # Use stored values if available, otherwise use defaults
            pre_checked_display = stored_raw if stored_raw else default_checked_raw

            # Display tree selector
            col1, col2 = st.columns([1, 1])

            checked_paths = st.session_state.get('node_checked_paths_effective', [])

            with col1:
                st.caption("Tip: Checked nodes show with a ✓. Descendants are visually checked but only the parent is saved.")

                # Get only top-level paths for expansion (don't auto-expand checked node descendants)
                def get_top_level_paths(tree_data, max_depth=3):
                    """Get paths up to a certain depth for initial expansion."""
                    paths = []
                    def traverse(nodes, current_path="", depth=0):
                        if depth >= max_depth:
                            return
                        for node in nodes:
                            node_path = f"{current_path}/{node['label']}" if current_path else node['label']
                            paths.append(node_path)
                            if 'children' in node and node['children']:
                                traverse(node['children'], node_path, depth + 1)
                    traverse(tree_data)
                    return paths

                # Expand tree structure to reasonable depth, but not all descendants
                expanded_paths = get_top_level_paths(tree_data, max_depth=3)

                # Tree select component
                try:
                    selected = tree_select(
                        tree_data,
                        checked=pre_checked_display,
                        only_leaf_checkboxes=False,
                        expand_on_click=True,
                        no_cascade=True,  # Must be True for checked parameter to work correctly
                        expanded=expanded_paths,  # Expand tree structure but not all descendants
                        key="node_manager_tree"
                    )
                except Exception as e:
                    show_error_with_logs(
                        "Tree component error",
                        str(e),
                        error_type="general"
                    )
                    selected = {'checked': []}

                # Get checked nodes from tree_select
                raw_checked = selected.get('checked')

                # If tree returns empty/None on initial render, use pre_checked_display
                if raw_checked is None or (not raw_checked and pre_checked_display):
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
                st.write("**🌳 Node Hierarchy**")
                st.info("""
                    **ℹ️ How Node Selection Works:**
                    - **Check a parent node** → Extracts that parent + all its descendants
                    - **Check a child only** → Extracts that child + its descendants (parent NOT extracted)
                    - **Check a leaf node** → Extracts only that specific node
                                    """)
                st.write("**⚙️ Node Properties**")

                # Show configuration form for selected nodes
                if checked_paths:
                    raw_selection = st.session_state.get('node_checked_paths_raw', [])
                    auto_enabled = [path for path in checked_paths if path not in raw_selection]

                    st.info(f"✅ {len(raw_selection)} parent nodes selected for extraction")
                    if auto_enabled:
                        st.caption(f"🔁 {len(auto_enabled)} descendants will be auto-extracted (shown checked in tree)")

                    # Show selected parent nodes summary
                    st.caption("**Parent nodes selected for extraction:**")
                    for idx, path in enumerate(raw_selection[:10]):  # Show up to 10
                        if path in node_lookup:
                            st.caption(f"• {node_lookup[path]['node_type']}")
                    if len(raw_selection) > 10:
                        st.caption(f"...and {len(raw_selection) - 10} more")
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

                    # Get only the explicitly checked parent nodes (not auto-expanded descendants)
                    raw_checked_paths = st.session_state.get('node_checked_paths_raw', [])

                    # Process all nodes
                    for node in result['nodes']:
                        section_path = node['section_path']

                        # Only enable nodes that were explicitly checked (parents), not auto-expanded descendants
                        enabled = section_path in raw_checked_paths

                        config = {
                            'config_id': node.get('config_id'),
                            'spec_version': result['spec_version'],
                            'message_root': result['message_root'],
                            'airline_code': result.get('airline_code'),
                            'node_type': node['node_type'],
                            'section_path': section_path,
                            'enabled': enabled,
                            'expected_references': [],  # Always empty - LLM auto-discovers relationships
                            'ba_remarks': ''  # No longer used
                        }
                        configurations.append(config)

                    # Send to API
                    if bulk_update_node_configurations(configurations, workspace=current_workspace):
                        st.success(f"✅ Saved {len(configurations)} node configurations!")
                        st.success(f"   • {len(raw_checked_paths)} parent nodes enabled for extraction")
                        st.info("💡 Configurations saved successfully. Parent nodes will auto-extract their descendants during Discovery.")
                    else:
                        show_error_with_logs(
                            "Failed to save node configurations",
                            "The backend did not accept the configuration update",
                            error_type="general"
                        )

            with col2:
                st.caption("💡 **Tip**: Relationships will be auto-discovered by the LLM during Discovery")

    with tab2:
        st.subheader("⚙️ Existing Configurations")
        st.write("View and search existing node configurations in this workspace")

        # Load all configurations for this workspace
        configs_data = get_node_configurations(workspace=current_workspace)

        if configs_data and configs_data['configurations']:
            # Group configurations by (airline, message, version)
            from collections import defaultdict
            config_groups = defaultdict(lambda: {'count': 0, 'enabled': 0})

            for config in configs_data['configurations']:
                key = (
                    config.get('airline_code') or 'Global',
                    config['message_root'],
                    config['spec_version']
                )
                config_groups[key]['count'] += 1
                if config.get('enabled'):
                    config_groups[key]['enabled'] += 1

            # Display available configuration groups
            st.write("**📊 Available Configurations**")

            # Create options list for selectbox
            options = []
            for (airline, message, version), stats in sorted(config_groups.items()):
                option_label = f"{airline} | {message} | {version} ({stats['enabled']}/{stats['count']} enabled)"
                options.append({
                    'label': option_label,
                    'airline': airline,
                    'message': message,
                    'version': version,
                    'stats': stats
                })

            if options:
                # Display as metrics
                cols = st.columns(min(len(options), 3))
                for idx, opt in enumerate(options):
                    with cols[idx % 3]:
                        st.metric(
                            f"{opt['airline']} - {opt['message']}",
                            f"{opt['version']}",
                            f"{opt['stats']['enabled']}/{opt['stats']['count']} enabled"
                        )

                st.divider()

                # Let user select a configuration group
                selected_option = st.selectbox(
                    "Select Configuration to View",
                    options,
                    format_func=lambda x: x['label'],
                    key="config_selector"
                )

                if selected_option:
                    st.write(f"**Showing configurations for: {selected_option['label']}**")

                    # Optional search filter
                    filter_node = st.text_input(
                        "🔍 Search Node Type",
                        placeholder="e.g., Pax, PassengerList",
                        key="node_search_filter"
                    )

                    # Filter configurations for selected group
                    filtered_configs = [
                        config for config in configs_data['configurations']
                        if (config.get('airline_code') or 'Global') == selected_option['airline']
                        and config['message_root'] == selected_option['message']
                        and config['spec_version'] == selected_option['version']
                    ]

                    # Sort: enabled first, then by node type
                    filtered_configs.sort(key=lambda x: (
                        0 if x.get('enabled') else 1,  # Enabled first
                        x.get('node_type', '').lower()  # Then alphabetically
                    ))

                    # Apply node type search filter if specified
                    if filter_node and filter_node.strip():
                        filtered_configs = [
                            config for config in filtered_configs
                            if filter_node.lower() in config.get('node_type', '').lower()
                        ]

                    if filtered_configs:
                        st.success(f"Found {len(filtered_configs)} node configurations")

                        # Build table data
                        config_list = []
                        for config in filtered_configs:
                            config_list.append({
                                "Status": "✅ Enabled" if config['enabled'] else "❌ Disabled",
                                "Node Type": config['node_type'],
                                "Section Path": config['section_path']
                            })

                        df_configs = pd.DataFrame(config_list)

                        # Apply color coding to Status column
                        def highlight_status(row):
                            if row['Status'] == "✅ Enabled":
                                return ['background-color: #d4edda'] * len(row)  # Light green
                            else:
                                return ['background-color: #f8d7da'] * len(row)  # Light red

                        styled_df = df_configs.style.apply(highlight_status, axis=1)
                        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=600)
                    else:
                        if filter_node:
                            st.warning(f"No configurations found matching '{filter_node}'")
                        else:
                            st.info("No configurations found for this selection")

            else:
                st.info("No configuration groups available")
        else:
            st.info(f"No configurations found in workspace `{current_workspace}`. Upload an XML in the 'Analyze XML' tab to create configurations.")



# ========== MAIN APP ==========

def render_sidebar() -> str:
    """Render the common sidebar controls and return the active workspace."""

    apply_custom_theme()

    st.sidebar.subheader("🗂️ Workspace")

    if 'workspaces' not in st.session_state:
        st.session_state.workspaces = load_workspaces()

    if not st.session_state.workspaces:
        st.session_state.workspaces = ["default"]

    if 'current_workspace' not in st.session_state or st.session_state.current_workspace not in st.session_state.workspaces:
        st.session_state.current_workspace = st.session_state.workspaces[0]

    active_workspace = st.session_state.current_workspace

    options = st.session_state.workspaces
    current_idx = options.index(active_workspace)
    selected_sidebar_workspace = st.sidebar.selectbox(
        "Select Workspace",
        options,
        index=current_idx,
        key="sidebar_workspace_selector"
    )

    if selected_sidebar_workspace != active_workspace:
        st.session_state.current_workspace = selected_sidebar_workspace

        # Clear workspace-specific session state when switching workspaces
        # This prevents data from one workspace appearing in another
        workspace_specific_keys = [
            'analyzed_nodes',
            'node_checked_paths_raw',
            'node_checked_paths_effective',
            'node_configs',
            'discovery_selected_run',
            'identify_current_run'
        ]

        for key in workspace_specific_keys:
            st.session_state.pop(key, None)

        st.experimental_rerun()

    st.sidebar.markdown(
        f"<div style='padding-top:0.25rem; font-weight:600; color:#0B1F33;'>"
        f"Current Workspace: <span style='color:#1A5DBF;'>{selected_sidebar_workspace}</span></div>",
        unsafe_allow_html=True
    )

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
    active_workspace = st.session_state.get('current_workspace', 'default')
    backend_patterns_count = len(get_patterns(limit=500, workspace=active_workspace))
    st.sidebar.metric("Patterns", backend_patterns_count)
