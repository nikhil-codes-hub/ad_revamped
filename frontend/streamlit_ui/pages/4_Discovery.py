import streamlit as st

from app_core import (
    render_sidebar,
    render_sidebar_footer,
    check_api_health,
    show_identify_page,
)


def main() -> None:
    st.set_page_config(
        page_title="🎯 Identify",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    if not check_api_health():
        st.error("⚠️ Backend API is not responding. Please start the FastAPI server.")
        st.stop()

    current_workspace = render_sidebar()
    show_identify_page(current_workspace=current_workspace)
    render_sidebar_footer()


if __name__ == "__main__":
    main()
