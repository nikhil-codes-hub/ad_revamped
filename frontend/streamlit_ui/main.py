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


def upload_file_for_run(file, run_kind: str, target_version: Optional[str] = None, target_message_root: Optional[str] = None, target_airline_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Upload file and create a new run."""
    try:
        files = {"file": (file.name, file.getvalue(), "application/xml")}
        params = {"kind": run_kind}

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
            st.error(f"Upload failed: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Upload error: {str(e)}")
        return None


def get_runs(kind: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Get list of runs."""
    try:
        params = {"limit": limit}
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


def get_run_status(run_id: str) -> Optional[Dict[str, Any]]:
    """Get status of a specific run."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/runs/{run_id}",
            timeout=15
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def get_node_facts(run_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get node facts for a run."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/node_facts/",
            params={"run_id": run_id, "limit": limit},
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


def get_patterns(limit: int = 100, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get all patterns, optionally filtered by run_id."""
    try:
        params = {"limit": limit}
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


def analyze_xml_for_nodes(file) -> Optional[Dict[str, Any]]:
    """Upload XML and analyze its structure for node configuration."""
    try:
        files = {"file": (file.name, file.getvalue(), "application/xml")}
        response = requests.post(
            f"{API_BASE_URL}/node-configs/analyze",
            files=files,
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def get_node_configurations(spec_version: Optional[str] = None,
                            message_root: Optional[str] = None,
                            airline_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get node configurations with optional filtering."""
    try:
        params = {"limit": 500}
        if spec_version:
            params["spec_version"] = spec_version
        if message_root:
            params["message_root"] = message_root
        if airline_code:
            params["airline_code"] = airline_code

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


def bulk_update_node_configurations(configurations: List[Dict[str, Any]]) -> bool:
    """Bulk update node configurations."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/node-configs/bulk-update",
            json=configurations,
            timeout=30
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def copy_configurations_to_versions(
    source_spec_version: str,
    source_message_root: str,
    target_versions: List[str],
    source_airline_code: Optional[str] = None,
    target_airline_code: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Copy configurations from one version to multiple other versions."""
    try:
        params = {
            "source_spec_version": source_spec_version,
            "source_message_root": source_message_root,
            "target_versions": target_versions
        }
        if source_airline_code:
            params["source_airline_code"] = source_airline_code
        if target_airline_code:
            params["target_airline_code"] = target_airline_code

        response = requests.post(
            f"{API_BASE_URL}/node-configs/copy-to-versions",
            params=params,
            timeout=30
        )

        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


# ========== PAGE FUNCTIONS ==========

def show_discovery_page():
    """Discovery page - run discovery and view results."""
    st.header("🔬 Discovery Mode")
    st.write("Upload XML files to learn and extract patterns")

    # Initialize session state
    if 'discovery_selected_run' not in st.session_state:
        st.session_state.discovery_selected_run = None

    # Upload section
    st.subheader("📤 Upload XML for Discovery")
    uploaded_file = st.file_uploader("Choose an NDC XML file", type=['xml'], key="discovery_upload")

    if uploaded_file:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Filename:** {uploaded_file.name}")
        with col2:
            st.write(f"**Size:** {uploaded_file.size:,} bytes")
        with col3:
            if st.button("Start Discovery", type="primary", key="start_discovery"):
                import time
                progress_bar = st.progress(0)
                status_text = st.empty()

                # Step 1: Upload
                status_text.text("📤 Uploading XML file to backend...")
                progress_bar.progress(5)
                time.sleep(0.3)

                status_text.text("🔍 Detecting NDC version...")
                progress_bar.progress(10)
                time.sleep(0.2)

                # Step 2: Start processing
                result = upload_file_for_run(uploaded_file, "discovery")

                if result:
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
                    st.session_state.discovery_selected_run = result['id']
                    st.rerun()

    st.divider()

    # Show results from current session
    if st.session_state.discovery_selected_run:
        run_id = st.session_state.discovery_selected_run
        st.success(f"📊 Discovery Results (Run: {run_id[:12]}...)")
        show_discovery_run_details(run_id)
    else:
        st.info("👆 Upload an XML file above to see discovery results")



def show_discovery_run_details(run_id: str):
    """Show detailed view of a discovery run."""
    run_details = get_run_status(run_id)

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
    patterns = get_patterns(limit=200, run_id=run_id)

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

    # NodeFacts table
    st.subheader("📋 Extracted NodeFacts")
    node_facts = get_node_facts(run_id, limit=200)

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


def show_identify_page():
    """Identify page - match patterns and view results."""
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
        st.info("No pattern matches found")


def show_patterns_page():
    """Pattern explorer page."""
    st.header("🔍 Pattern Explorer")
    st.write("View and analyze learned patterns")

    patterns = get_patterns(limit=200)

    if patterns:
        # Patterns table
        pattern_data = []
        for pattern in patterns:
            decision_rule = pattern.get('decision_rule', {})
            pattern_data.append({
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
        col1, col2, col3 = st.columns(3)

        with col1:
            versions = ["All"] + sorted(list(set(p['spec_version'] for p in patterns)))
            selected_version = st.selectbox("Version:", versions)

        with col2:
            node_types = ["All"] + sorted(list(set(p.get('decision_rule', {}).get('node_type', 'Unknown') for p in patterns)))
            selected_type = st.selectbox("Node Type:", node_types)

        with col3:
            min_seen = st.number_input("Min Times Seen:", min_value=0, value=0)

        # Apply filters
        filtered_df = df_patterns.copy()
        if selected_version != "All":
            filtered_df = filtered_df[filtered_df['Version'] == selected_version]
        if selected_type != "All":
            filtered_df = filtered_df[filtered_df['Node Type'] == selected_type]
        if min_seen > 0:
            filtered_df = filtered_df[filtered_df['Times Seen'] >= min_seen]

        st.divider()
        st.subheader(f"📋 Patterns ({len(filtered_df)} total)")

        st.dataframe(filtered_df, use_container_width=True, hide_index=True)

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


def show_node_manager_page():
    """Node manager page - configure which nodes to extract and their references."""
    st.header("📋 Node Configuration Manager")
    st.write("Configure which nodes to extract during Discovery and define expected references")

    tab1, tab2, tab3 = st.tabs(["📤 Analyze XML", "⚙️ Manage Configurations", "📋 Copy to Versions"])

    with tab1:
        st.subheader("Upload XML to Discover Nodes")
        st.write("Upload an XML file to analyze its structure and create configurations")

        uploaded_file = st.file_uploader("Choose XML file", type=['xml'], key="node_config_upload")

        if uploaded_file:
            if st.button("Analyze Structure", type="primary"):
                with st.spinner("Analyzing XML structure..."):
                    result = analyze_xml_for_nodes(uploaded_file)

                if result:
                    st.success(f"✅ Discovered {result['total_nodes']} nodes in {result['spec_version']}/{result['message_root']}")

                    # Store in session state for editing
                    st.session_state.analyzed_nodes = result
                    st.rerun()
                else:
                    st.error("Failed to analyze XML structure")

        # Show analyzed nodes if available
        if 'analyzed_nodes' in st.session_state:
            result = st.session_state.analyzed_nodes

            st.divider()
            st.subheader("📊 Discovered Nodes")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Nodes", result['total_nodes'])
            with col2:
                st.metric("Already Configured", result['configured_nodes'])
            with col3:
                st.metric("New Nodes", result['total_nodes'] - result['configured_nodes'])

            st.divider()

            # Editable table
            st.subheader("✏️ Configure Nodes")
            st.write("Check which nodes to extract, add expected references, and remarks")

            # Create DataFrame for editing
            nodes_data = []
            for idx, node in enumerate(result['nodes']):
                nodes_data.append({
                    "Index": idx,
                    "Enabled": node.get('enabled', True),
                    "Node Type": node['node_type'],
                    "Section Path": node['section_path'],
                    "Expected References": ", ".join(node.get('expected_references', [])),
                    "BA Remarks": node.get('ba_remarks', ''),
                    "_config_id": node.get('config_id'),
                    "_has_children": node.get('has_children', False)
                })

            df_nodes = pd.DataFrame(nodes_data)

            # Convert to PyArrow-compatible types
            # Use integer (0/1) instead of boolean for PyArrow compatibility
            df_nodes['Enabled'] = df_nodes['Enabled'].apply(lambda x: 1 if (x is True or x == True) else 0).astype(int)
            df_nodes['Expected References'] = df_nodes['Expected References'].fillna('').astype(str)
            df_nodes['BA Remarks'] = df_nodes['BA Remarks'].fillna('').astype(str)

            # Create display dataframe
            display_df = df_nodes[["Enabled", "Node Type", "Section Path", "Expected References", "BA Remarks"]].copy()

            # Use experimental data editor for editable table
            edited_df = st.data_editor(
                display_df,
                use_container_width=True,
                num_rows="fixed",
                column_config={
                    "Enabled": st.column_config.CheckboxColumn(
                        "Enabled",
                        help="Extract this node during Discovery?",
                        default=True
                    ),
                    "Expected References": st.column_config.TextColumn(
                        "Expected References",
                        help="Comma-separated: infant_parent, segment_reference, etc.",
                        max_chars=200
                    ),
                    "BA Remarks": st.column_config.TextColumn(
                        "BA Remarks",
                        help="Notes and instructions",
                        max_chars=500
                    )
                },
                hide_index=True
            )

            # Save button
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("💾 Save All Configurations", type="primary"):
                    # Prepare data for bulk update
                    configurations = []
                    for idx, row in edited_df.iterrows():
                        original = nodes_data[idx]

                        # Parse expected references
                        refs_str = row['Expected References'].strip()
                        refs = [r.strip() for r in refs_str.split(',') if r.strip()] if refs_str else []

                        config = {
                            'config_id': original['_config_id'],
                            'spec_version': result['spec_version'],
                            'message_root': result['message_root'],
                            'airline_code': result.get('airline_code'),
                            'node_type': row['Node Type'],
                            'section_path': row['Section Path'],
                            'enabled': bool(row['Enabled']),  # Convert integer back to boolean
                            'expected_references': refs,
                            'ba_remarks': row['BA Remarks']
                        }
                        configurations.append(config)

                    # Send to API
                    if bulk_update_node_configurations(configurations):
                        st.success(f"✅ Saved {len(configurations)} node configurations!")
                        # Clear session state
                        if 'analyzed_nodes' in st.session_state:
                            del st.session_state.analyzed_nodes
                        st.rerun()
                    else:
                        st.error("Failed to save configurations")

            with col2:
                st.caption("💡 **Reference types**: infant_parent, segment_reference, pax_reference, baggage_reference, journey_reference")

    with tab2:
        st.subheader("⚙️ Existing Configurations")

        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            filter_version = st.text_input("Filter by Version", placeholder="e.g., 21.3")
        with col2:
            filter_message = st.text_input("Filter by Message", placeholder="e.g., OrderViewRS")
        with col3:
            filter_airline = st.text_input("Filter by Airline", placeholder="e.g., SQ")

        if st.button("🔍 Load Configurations"):
            configs_data = get_node_configurations(
                spec_version=filter_version if filter_version else None,
                message_root=filter_message if filter_message else None,
                airline_code=filter_airline if filter_airline else None
            )

            if configs_data and configs_data['configurations']:
                st.success(f"Found {configs_data['total']} configurations")

                # Display as table
                config_list = []
                for config in configs_data['configurations']:
                    config_list.append({
                        "ID": config['id'],
                        "Version": config['spec_version'],
                        "Message": config['message_root'],
                        "Airline": config['airline_code'] or "All",
                        "Node Type": config['node_type'],
                        "Section Path": config['section_path'],
                        "Enabled": "✓" if config['enabled'] else "✗",
                        "References": ", ".join(config['expected_references']) if config['expected_references'] else "-",
                        "Remarks": config['ba_remarks'] or "-"
                    })

                df_configs = pd.DataFrame(config_list)
                st.dataframe(df_configs, use_container_width=True, hide_index=True)
            else:
                st.info("No configurations found. Upload an XML in the 'Analyze XML' tab to create configurations.")

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
                    airline_info = f" (Airline: {source_airline})" if source_airline else " (auto-detected)"
                    st.info(f"📋 Copied from **{result['source_version']}{airline_info}** to: {', '.join(result['target_versions'])}")

                    if result.get('errors'):
                        st.warning("Some errors occurred:")
                        for error in result['errors']:
                            st.text(error)
                else:
                    st.error("Failed to copy configurations. Please check:\n- Source version and message root are correct\n- Configurations exist for the source version")


# ========== MAIN APP ==========

def main():
    """Main application."""

    # Check API health
    if not check_api_health():
        st.error("⚠️ Backend API is not responding. Please start the FastAPI server.")
        st.stop()

    # Sidebar navigation
    st.sidebar.title("🔍 AssistedDiscovery")
    st.sidebar.divider()

    page = st.sidebar.radio(
        "Navigation",
        ["🔬 Discovery", "🎯 Identify", "📚 Pattern Explorer", "📋 Node Manager"],
        label_visibility="collapsed"
    )

    st.sidebar.divider()

    # Show system status
    st.sidebar.subheader("System Status")
    st.sidebar.success("✅ API Connected")

    # Show page based on selection
    if page == "🔬 Discovery":
        show_discovery_page()
    elif page == "🎯 Identify":
        show_identify_page()
    elif page == "📚 Pattern Explorer":
        show_patterns_page()
    elif page == "📋 Node Manager":
        show_node_manager_page()


if __name__ == "__main__":
    main()
