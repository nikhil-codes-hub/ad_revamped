import streamlit as st

from app_core import (
    render_sidebar,
    render_sidebar_footer,
    check_api_health,
)


def show_home_page():
    """Display the main AssistedDiscovery landing page."""
    st.title("🔍 AssistedDiscovery")
    # st.markdown("---")

    st.markdown("""
    ## Welcome to AssistedDiscovery

    AssistedDiscovery is a comprehensive tool for analyzing and managing NDC (New Distribution Capability)
    message structures across different airline implementations.

    ### Available Workflows

    Use the sidebar to navigate between different workflows:

    - **🗄️ Node Manager** - Configure extraction rules and expected references
    - **🔬 Discovery** - Analyze XML files to extract node structures and patterns
    - **🎨 Pattern Manager** - Review patterns, explore the library, and manage exports (Explorer tab inside)
    - **🎯 Identify** - Match new XML files against known patterns

    ### Getting Started

    1. Select your **workspace** from the sidebar
    2. Choose a workflow from the navigation menu
    3. Follow the on-screen instructions for each workflow

    ### Current Status
    """)

    # Show workspace info
    current_workspace = st.session_state.get("current_workspace", "default")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Current Workspace", current_workspace)

    with col2:
        st.metric("Backend Status", "🟢 Healthy" if check_api_health() else "🔴 Down")

    with col3:
        st.metric("Pages Available", "5")

    st.markdown("---")
    st.info("💡 **Tip**: Start with Node Manager to configure extraction rules, then use Discovery to analyze your first XML file.")


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
