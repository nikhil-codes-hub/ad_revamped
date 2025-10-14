import streamlit as st

from app_core import (
    render_sidebar,
    render_sidebar_footer,
    check_api_health,
)


def show_home_page():
    """Display the main AssistedDiscovery landing page."""
    st.title("🔍 AssistedDiscovery")
    st.caption("AI-Powered NDC XML Analysis & Pattern Discovery")

    # Current Status
    current_workspace = st.session_state.get("current_workspace", "default")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Current Workspace", current_workspace)

    with col2:
        st.metric("Backend Status", "🟢 Healthy" if check_api_health() else "🔴 Down")

    with col3:
        st.metric("Pages Available", "5")

    st.markdown("---")

    # Quick Start Guide
    st.markdown("## 🚀 Quick Start")

    tab1, tab2, tab3, tab4 = st.tabs(["📖 Overview", "🎯 Workflows", "⚡ Quick Guide", "📚 Documentation"])

    with tab1:
        st.markdown("""
        ### What is AssistedDiscovery?

        AssistedDiscovery is an **AI-powered tool** that helps you:
        - 🔍 **Understand** NDC XML message structures automatically
        - 🔗 **Discover** relationships between nodes (who references whom)
        - 🎨 **Generate** reusable patterns for validation
        - 🎯 **Identify** structural changes in XML over time
        - ✅ **Validate** new XML files against known patterns

        ### Key Benefits

        - **Hybrid Intelligence**: Combines BA knowledge with AI auto-discovery
        - **Multi-Airline Support**: Isolated workspaces per airline/project
        - **Version Compatibility**: Supports NDC 17.2, 18.1, 19.2, 21.3 and future versions
        - **Pattern Library**: Build and share reusable validation patterns
        - **Change Detection**: Identify deviations from expected structure

        ### Supported NDC Messages

        ✅ OrderViewRS / IATA_OrderViewRS
        ✅ AirShoppingRS / IATA_AirShoppingRS
        ✅ OfferPriceRS / IATA_OfferPriceRS
        ✅ OrderCreateRQ / IATA_OrderCreateRQ
        ✅ OrderChangeRQ / IATA_OrderChangeRQ
        ✅ Any other NDC message type (dynamic)

        ---

        ### ⚠️ Important: AI-Powered Analysis

        AssistedDiscovery uses **Large Language Models (LLMs)** to analyze XML. This means:

        **Results May Vary**:
        - **LLMs can make mistakes**: Like humans, AI can misinterpret or miss information
        - **Non-deterministic**: Running Discovery/Identify on the same XML multiple times may produce slightly different results
        - **Confidence scores matter**: Always review low-confidence matches (< 85%)
        - **Human validation required**: Treat results as AI-assisted suggestions, not absolute truth

        **Typical Accuracy**:
        - Node extraction: 90-95%
        - Relationship discovery: 85-90%
        - Pattern matching: 90-95%

        **Best Practices**:
        1. Always review results - don't trust blindly
        2. Validate unexpected discoveries
        3. Check low-confidence matches (< 85%)
        4. Run multiple times if uncertain
        5. Report issues to help improve the system

        **We Need Your Feedback!**
        Help improve AssistedDiscovery by reporting:
        - False positives/negatives
        - Incorrect patterns
        - Inconsistent results
        - Quality issues

        **Contact**: nikhilkrishna.lepakshi@amadeus.com
        """)

    with tab2:
        st.markdown("""
        ### 🗄️ Node Manager
        **Purpose**: Configure which nodes to extract and their expected references

        **When to use**:
        - Before running Discovery (optional, for guided extraction)
        - To define expected relationships between nodes
        - To standardize extraction across multiple runs

        **What you can do**:
        - Upload XML to analyze available nodes
        - Configure extraction rules per node type
        - Define expected references (e.g., Passenger → Segment)
        - Copy configurations across NDC versions

        ---

        ### 🔬 Discovery Workflow
        **Purpose**: Extract structure and relationships from XML

        **When to use**:
        - First time analyzing an airline's XML format
        - New XML message type received
        - Need to understand XML structure and relationships

        **Output**:
        - **NodeFacts**: Extracted node structures with attributes and children
        - **Relationships**: Discovered references (e.g., PassengerList → SegmentList)
        - **Patterns**: Reusable templates for future validation

        **Typical Duration**: 2-5 minutes for standard XML

        **Relationship Discovery**:
        - ✅ **Expected Validated**: BA-configured references that exist and are valid
        - ⚠️ **Expected Missing**: BA-expected references that are broken
        - 🔍 **Unexpected Discovered**: New references found by AI (not configured by BA)

        ---

        ### 🎨 Pattern Manager
        **Purpose**: View, export, and manage discovered patterns

        **Features**:
        - Browse pattern library with filters
        - View pattern details (decision rules, examples)
        - Export patterns to JSON for documentation
        - Import patterns from other workspaces

        **Use Cases**:
        - Documentation: Include patterns in API specifications
        - Backup: Save pattern library
        - Sharing: Send patterns to team members
        - Migration: Move patterns between workspaces

        ---

        ### 🎯 Identify Workflow
        **Purpose**: Validate new XML files against known patterns

        **When to use**:
        - After Discovery has generated patterns
        - Validating new XML files from same airline
        - Testing for structural changes or deviations

        **Output**:
        - **Pattern Matches**: What matches, what changed
        - **Confidence Scores**: 0-100% similarity to patterns
        - **Deviation Reports**: Detailed comparison of differences

        **Match Verdicts**:
        - ✅ **EXACT_MATCH** (95-100%): Perfect match to pattern
        - 🟡 **HIGH_MATCH** (85-95%): Close match, minor differences
        - 🟠 **PARTIAL_MATCH** (70-85%): Some deviations, review recommended
        - 🔴 **NEW_PATTERN**: No matching pattern found, structural change detected

        **Typical Duration**: 30 seconds for standard XML
        """)

    with tab3:
        st.markdown("""
        ### First-Time Setup

        #### 1️⃣ Configure LLM (One-Time)

        AssistedDiscovery uses AI to extract information from XML. You need to configure your LLM provider first.

        **Steps**:
        1. Click **⚙️ Config** in the sidebar
        2. Scroll to **🤖 LLM Configuration**
        3. Select **Azure OpenAI** or **Google Gemini**
        4. Enter your credentials:
           - **Azure**: Endpoint, API Key, Deployment Name
           - **Gemini**: API Key, Model Name
        5. Click **💾 Save Configuration**
        6. Click **🔍 Test Connection** to verify
        7. **Restart the backend** for changes to take effect

        ---

        #### 2️⃣ Create Workspace

        Workspaces isolate data per airline or project.

        **Steps**:
        1. Go to **⚙️ Config** → Workspace Management
        2. Enter workspace name (e.g., `LATAM`, `United`, `Test`)
        3. Click **➕ Add Workspace**
        4. Switch to new workspace using sidebar dropdown

        ---

        #### 3️⃣ Your First Discovery

        **Scenario**: Analyze an airline's OrderViewRS XML for the first time

        **Steps**:
        1. Click **🔬 Discovery** in sidebar
        2. Select your workspace
        3. Upload XML file (drag & drop or browse)
        4. Review detected information:
           - Message Type (e.g., OrderViewRS)
           - NDC Version (e.g., 19.2)
           - Airline Code (e.g., LA for LATAM)
        5. Click **🚀 Start Discovery**
        6. Wait 2-5 minutes for completion
        7. Review results:
           - **NodeFacts**: See all extracted structures
           - **Relationships**: Check discovered references
           - **Patterns**: View generated templates

        **What to look for**:
        - ✅ **Expected Validated**: Known references are working
        - ⚠️ **Expected Missing**: Known references are broken (investigate!)
        - 🔍 **Unexpected Discovered**: New references found (document these!)

        ---

        #### 4️⃣ Using Patterns for Validation

        **Scenario**: Validate a new XML file against known patterns

        **Prerequisites**: Must have run Discovery first to generate patterns

        **Steps**:
        1. Click **🎯 Identify** in sidebar
        2. Select same workspace as Discovery
        3. Upload XML file to validate
        4. Click **🔍 Start Identify**
        5. Wait 30 seconds
        6. Review match results:
           - **EXACT_MATCH**: Structure unchanged ✅
           - **NEW_PATTERN**: New node type found 🔴
           - **PARTIAL_MATCH**: Some differences ⚠️

        ---

        ### Common Workflows

        #### Discovery → Pattern Manager → Export
        **Use Case**: Document XML structure for new airline integration

        1. Run Discovery on sample XML
        2. Open Pattern Manager
        3. Select patterns to export
        4. Click **📤 Export Selected Patterns**
        5. Share JSON file with team

        ---

        #### Discovery → Node Config → Discovery Again
        **Use Case**: Refine extraction rules

        1. Run Discovery with auto-detection
        2. Review unexpected discoveries
        3. Configure node configs with expected references
        4. Run Discovery again for validation

        ---

        #### Discovery → Identify → Compare
        **Use Case**: Regression testing after API changes

        1. Run Discovery on old XML (baseline)
        2. Run Identify on new XML (test)
        3. Review deviations
        4. Investigate NEW_PATTERN or PARTIAL_MATCH results
        """)

    with tab4:
        st.markdown("""
        ### 📚 Available Documentation

        #### USER_GUIDE.md
        **Complete end-user manual covering**:
        - Installation & setup
        - LLM configuration (Azure OpenAI & Gemini)
        - All workflows with step-by-step instructions
        - Workspace management
        - Troubleshooting common issues
        - Best practices and FAQs

        #### RELATIONSHIP_DISCOVERY_LOGIC.md
        **Technical deep-dive covering**:
        - How relationship discovery works
        - LLM prompt engineering
        - Reference field extraction logic
        - Validation strategies
        - Performance considerations

        #### Location
        Both documents are in the project root directory.

        ---

        ### 🆘 Getting Help

        **Log Files**: Check application logs for detailed error messages

        **Log Location**:
        - **macOS**: `~/Library/Logs/AssistedDiscovery/`
        - **Windows**: `%LOCALAPPDATA%\\AssistedDiscovery\\Logs\\`
        - **Linux**: `~/.local/share/AssistedDiscovery/logs/`

        **Access Logs via UI**:
        1. Go to **⚙️ Config**
        2. Scroll to **📋 Application Logs**
        3. Click **📂 Open Log Folder**

        ---

        ### ⚙️ System Requirements

        **Minimum**:
        - 4 GB RAM
        - 2 CPU cores
        - Python 3.9+
        - Internet connection (for LLM API)

        **Recommended**:
        - 8 GB RAM
        - 4 CPU cores
        - Python 3.10+
        """)

    st.markdown("---")
    st.info("💡 **Tip**: New to AssistedDiscovery? Start with the **⚡ Quick Guide** tab above for step-by-step instructions!")


def main() -> None:
    st.set_page_config(
        page_title="AssistedDiscovery",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    if not check_api_health():
        st.error("⚠️ Backend API is not responding. Please start the FastAPI server.")
        st.stop()

    render_sidebar()
    show_home_page()
    render_sidebar_footer()


if __name__ == "__main__":
    main()
