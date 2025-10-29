import streamlit as st

from app_core import (
    render_sidebar,
    render_sidebar_footer,
    check_api_health,
    run_pattern_manager_page,
)


def main() -> None:
    st.set_page_config(
        page_title="🎨 Pattern Manager",
        page_icon="🎨",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    if not check_api_health():
        st.error("⚠️ Backend API is not responding. Please start the FastAPI server.")
        st.stop()

    render_sidebar()
    run_pattern_manager_page()
    render_sidebar_footer()


if __name__ == "__main__":
    main()
