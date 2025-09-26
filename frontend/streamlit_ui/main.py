"""
AssistedDiscovery Streamlit UI

Main application for the AssistedDiscovery system frontend.
Provides interface for uploading XMLs, monitoring runs, and viewing reports.
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any
import json

# Configure Streamlit page
st.set_page_config(
    page_title="AssistedDiscovery",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"
HEALTH_URL = "http://localhost:8000/health"


def check_api_health() -> bool:
    """Check if the FastAPI backend is running."""
    try:
        response = requests.get(HEALTH_URL, timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def upload_file_for_run(file, run_kind: str) -> Optional[Dict[str, Any]]:
    """Upload file and create a new run."""
    try:
        files = {"file": (file.name, file.getvalue(), "application/xml")}
        params = {"kind": run_kind}

        response = requests.post(
            f"{API_BASE_URL}/runs/",
            files=files,
            params=params,
            timeout=30
        )

        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Upload failed: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")
        return None


def get_run_status(run_id: str) -> Optional[Dict[str, Any]]:
    """Get the status of a specific run."""
    try:
        response = requests.get(f"{API_BASE_URL}/runs/{run_id}", timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def get_runs_list(limit: int = 10) -> list:
    """Get list of recent runs."""
    try:
        response = requests.get(f"{API_BASE_URL}/runs/", params={"limit": limit}, timeout=10)
        if response.status_code == 200:
            return response.json()
        return []
    except requests.exceptions.RequestException:
        return []


def get_run_report(run_id: str) -> Optional[Dict[str, Any]]:
    """Get the report for a completed run."""
    try:
        response = requests.get(f"{API_BASE_URL}/runs/{run_id}/report", timeout=15)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def main():
    """Main Streamlit application."""

    # Header
    st.title("🔍 AssistedDiscovery")
    st.markdown("*Deterministic, token-efficient extraction and pattern learning over airline NDC XMLs*")

    # Check API health
    if not check_api_health():
        st.error("⚠️ Unable to connect to AssistedDiscovery API. Please ensure the backend is running.")
        st.info("Start the backend with: `cd backend && python -m app.main`")
        return

    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page",
        ["Upload & Process", "Run Dashboard", "Pattern Explorer", "Reports", "System Status"]
    )

    if page == "Upload & Process":
        show_upload_page()
    elif page == "Run Dashboard":
        show_dashboard_page()
    elif page == "Pattern Explorer":
        show_patterns_page()
    elif page == "Reports":
        show_reports_page()
    elif page == "System Status":
        show_status_page()


def show_upload_page():
    """Upload and processing page."""
    st.header("Upload XML for Processing")

    # File upload
    uploaded_file = st.file_uploader(
        "Choose an NDC XML file",
        type=["xml"],
        help="Upload OrderViewRS or similar NDC XML files for analysis"
    )

    if uploaded_file is not None:
        # Show file details
        file_details = {
            "Filename": uploaded_file.name,
            "File size": f"{len(uploaded_file.getvalue()):,} bytes",
            "File type": uploaded_file.type
        }

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("File Details")
            for key, value in file_details.items():
                st.write(f"**{key}:** {value}")

        with col2:
            st.subheader("Processing Options")

            run_kind = st.selectbox(
                "Processing Type",
                ["discovery", "identify"],
                help="Discovery: Learn new patterns | Identify: Match against existing patterns"
            )

            if st.button("Start Processing", type="primary"):
                with st.spinner("Uploading file and starting processing..."):
                    result = upload_file_for_run(uploaded_file, run_kind)

                    if result:
                        st.success(f"✅ Processing started successfully!")
                        st.json(result)

                        # Store run ID in session state for tracking
                        if "current_run_id" not in st.session_state:
                            st.session_state.current_run_id = result.get("id")
                    else:
                        st.error("❌ Failed to start processing")


def show_dashboard_page():
    """Run dashboard page."""
    st.header("Run Dashboard")

    # Auto-refresh checkbox
    auto_refresh = st.checkbox("Auto-refresh (10s)", value=False)
    if auto_refresh:
        st.rerun()

    # Get recent runs
    runs = get_runs_list(20)

    if runs:
        # Convert to DataFrame for better display
        df_data = []
        for run in runs:
            df_data.append({
                "Run ID": run["id"],
                "Type": run["kind"].title(),
                "Status": run["status"].replace("_", " ").title(),
                "Filename": run.get("filename", "N/A"),
                "Created": run["created_at"][:19].replace("T", " "),
                "Duration": f"{run.get('duration_seconds', 0)}s" if run.get("duration_seconds") else "N/A"
            })

        df = pd.DataFrame(df_data)

        # Display runs table
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

        # Run details section
        st.subheader("Run Details")
        selected_run_id = st.selectbox("Select a run for details:", [run["id"] for run in runs])

        if selected_run_id:
            run_details = get_run_status(selected_run_id)
            if run_details:
                col1, col2 = st.columns(2)

                with col1:
                    st.json(run_details)

                with col2:
                    if run_details["status"] in ["completed", "partial_failure"]:
                        if st.button("View Report", key=f"report_{selected_run_id}"):
                            st.session_state.selected_report_run = selected_run_id
                            st.rerun()

    else:
        st.info("No runs found. Upload an XML file to get started!")


def show_patterns_page():
    """Pattern explorer page."""
    st.header("Pattern Explorer")
    st.info("🚧 Pattern exploration features coming soon...")

    # Placeholder for pattern browsing
    st.subheader("Discovered Patterns")
    st.markdown("""
    This section will show:
    - Pattern library with filtering and search
    - Pattern details and decision rules
    - Usage statistics and examples
    - Pattern quality metrics
    """)


def show_reports_page():
    """Reports page."""
    st.header("Analysis Reports")

    # Check if we have a selected report
    if hasattr(st.session_state, 'selected_report_run'):
        run_id = st.session_state.selected_report_run

        st.subheader(f"Report for Run: {run_id}")

        with st.spinner("Loading report..."):
            report = get_run_report(run_id)

            if report:
                # Display report based on type
                if report.get("report_type") == "discovery":
                    show_discovery_report(report)
                elif report.get("report_type") == "identify":
                    show_identify_report(report)
                else:
                    st.json(report)
            else:
                st.error("Failed to load report")

    else:
        st.info("Select a completed run from the Dashboard to view its report.")


def show_discovery_report(report: Dict[str, Any]):
    """Display discovery report."""
    st.subheader("🔍 Discovery Report")

    summary = report.get("summary", {})

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Patterns Discovered", summary.get("patterns_discovered", 0))
    with col2:
        st.metric("Nodes Processed", summary.get("nodes_processed", 0))
    with col3:
        st.metric("Coverage %", f"{summary.get('coverage_percentage', 0):.1f}%")
    with col4:
        st.metric("Processing Time", f"{summary.get('processing_time_seconds', 0)}s")

    # Patterns details
    st.subheader("Discovered Patterns")
    patterns = report.get("patterns", [])
    if patterns:
        st.write(f"Found {len(patterns)} patterns:")
        for i, pattern in enumerate(patterns):
            with st.expander(f"Pattern {i+1}: {pattern.get('section_path', 'Unknown')}"):
                st.json(pattern)
    else:
        st.info("No patterns in this report")


def show_identify_report(report: Dict[str, Any]):
    """Display identify report."""
    st.subheader("🎯 Identify Report")

    summary = report.get("summary", {})

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Nodes Processed", summary.get("nodes_processed", 0))
    with col2:
        st.metric("High Confidence", summary.get("high_confidence_matches", 0))
    with col3:
        st.metric("Avg Confidence", f"{summary.get('avg_confidence', 0):.2f}")
    with col4:
        st.metric("Unmatched Nodes", summary.get("unmatched_nodes", 0))

    # Gap analysis
    st.subheader("Gap Analysis")
    gap_analysis = report.get("gap_analysis", {})
    if gap_analysis:
        st.json(gap_analysis)


def show_status_page():
    """System status page."""
    st.header("System Status")

    # API Health
    if check_api_health():
        st.success("✅ AssistedDiscovery API is running")
    else:
        st.error("❌ AssistedDiscovery API is not accessible")

    # System information
    st.subheader("Configuration")
    config_info = {
        "API Base URL": API_BASE_URL,
        "Health Check URL": HEALTH_URL,
        "UI Version": "1.0.0-beta",
        "Last Updated": "2025-09-26"
    }

    for key, value in config_info.items():
        st.write(f"**{key}:** {value}")

    st.subheader("Quick Actions")
    if st.button("Test API Connection"):
        if check_api_health():
            st.success("✅ Connection successful!")
        else:
            st.error("❌ Connection failed!")


if __name__ == "__main__":
    main()