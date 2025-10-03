"""
AssistedDiscovery Streamlit UI

Clean table-based interface with sidebar navigation.
"""

import streamlit as st
import requests
import pandas as pd
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


def upload_file_for_run(file, run_kind: str) -> Optional[Dict[str, Any]]:
    """Upload file and create a new run."""
    try:
        files = {"file": (file.name, file.getvalue(), "application/xml")}
        params = {"kind": run_kind}

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


# ========== PAGE FUNCTIONS ==========

def show_discovery_page():
    """Discovery page - run discovery and view results."""
    st.header("🔬 Discovery Mode")
    st.write("Upload XML files to learn and extract patterns")

    # Initialize session state
    if 'discovery_selected_run' not in st.session_state:
        st.session_state.discovery_selected_run = None

    # Upload section
    with st.expander("📤 Upload XML for Discovery", expanded=False):
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
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Status", run_details["status"])
    with col2:
        st.metric("Version", run_details["spec_version"])
    with col3:
        st.metric("NodeFacts", run_details.get("node_facts_count", 0))
    with col4:
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
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Filename:** {uploaded_file.name}")
            with col2:
                st.write(f"**Size:** {uploaded_file.size:,} bytes")
            with col3:
                if st.button("Start Identify", type="primary", key="start_identify"):
                    import time
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    status_text.text("📤 Uploading XML file to backend...")
                    progress_bar.progress(5)
                    time.sleep(0.3)

                    status_text.text("🔍 Detecting NDC version...")
                    progress_bar.progress(10)
                    time.sleep(0.2)

                    result = upload_file_for_run(uploaded_file, "identify")

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
        ["🔬 Discovery", "🎯 Identify", "📚 Pattern Explorer"],
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


if __name__ == "__main__":
    main()
