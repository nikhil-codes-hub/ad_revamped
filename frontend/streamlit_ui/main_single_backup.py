import streamlit as st

from app_core import (
    render_sidebar,
    render_sidebar_footer,
    show_node_manager_page,
    check_api_health,
)


def main() -> None:
    """Node Manager page (landing page)."""
    st.set_page_config(
        page_title="📋 Node Manager",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    if not check_api_health():
        st.error("⚠️ Backend API is not responding. Please start the FastAPI server.")
        st.stop()

    _ = render_sidebar()
    show_node_manager_page()
    render_sidebar_footer()


if __name__ == "__main__":
    main()
