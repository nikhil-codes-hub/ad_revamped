"""
CSS utility functions for loading stylesheets with fallback paths.
"""
import os
import streamlit as st


def load_table_styles():
    """
    Load the table_styles.css file from various possible locations.
    This function tries multiple paths to ensure CSS loads correctly
    when the project is copied to different environments.
    """
    # Get the current file's directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try multiple possible CSS paths for better compatibility
    possible_paths = [
        # From core/common/ -> app/css/
        os.path.join(current_dir, "../../app/css/table_styles.css"),
        # Alternative paths
        os.path.join(os.path.dirname(os.path.dirname(current_dir)), "app/css/table_styles.css"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))), "app/css/table_styles.css"),
        # Relative to working directory
        "app/css/table_styles.css",
        "./app/css/table_styles.css",
        # Legacy paths for backward compatibility (removed after project rename)
    ]
    
    # Debug output only in development (when DEBUG env var is set)
    debug_mode = os.environ.get('DEBUG', '').lower() in ('1', 'true', 'yes')
    
    if debug_mode:
        print(f"DEBUG: Current working directory: {os.getcwd()}")
        print(f"DEBUG: Script directory: {current_dir}")
    
    for i, css_path in enumerate(possible_paths):
        if debug_mode:
            abs_path = os.path.abspath(css_path)
            print(f"DEBUG: Trying path {i+1}: {css_path} -> {abs_path}")
            print(f"DEBUG: Path exists: {os.path.exists(css_path)}")
        
        if os.path.exists(css_path):
            try:
                with open(css_path, 'r', encoding='utf-8') as f:
                    css_content = f.read()
                    st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
                    # Also store in session_state to prevent reloading
                    if 'css_loaded' not in st.session_state:
                        st.session_state.css_loaded = True
                if debug_mode:
                    print(f"DEBUG: Successfully loaded CSS from: {css_path}")
                return True  # Successfully loaded CSS
            except UnicodeDecodeError:
                # Try with different encodings if UTF-8 fails
                try:
                    with open(css_path, 'r', encoding='latin-1') as f:
                        css_content = f.read()
                        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
                        # Also store in session_state to prevent reloading
                        if 'css_loaded' not in st.session_state:
                            st.session_state.css_loaded = True
                    if debug_mode:
                        print(f"DEBUG: Successfully loaded CSS (latin-1) from: {css_path}")
                    return True  # Successfully loaded CSS
                except Exception as e:
                    if debug_mode:
                        print(f"DEBUG: Failed to load CSS with latin-1: {e}")
                    continue  # Try next path
            except Exception as e:
                if debug_mode:
                    print(f"DEBUG: Failed to load CSS: {e}")
                continue  # Try next path
    
    # If no CSS file found, load essential inline CSS as fallback
    print("Warning: CSS file (table_styles.css) not found in any expected location")
    print("Loading fallback inline CSS...")
    
    # Load essential CSS inline as fallback
    _load_fallback_css()
    return False


def get_css_path():
    """
    Get the path to the CSS file without loading it.
    Returns the first valid path found, or None if not found.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    possible_paths = [
        os.path.join(current_dir, "../../app/css/table_styles.css"),
        os.path.join(os.path.dirname(os.path.dirname(current_dir)), "app/css/table_styles.css"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))), "app/css/table_styles.css"),
        "app/css/table_styles.css",
        "./app/css/table_styles.css",
        "app/agentic_gap_analyser/css/table_styles.css",
        "./app/agentic_gap_analyser/css/table_styles.css"
    ]
    
    for css_path in possible_paths:
        if os.path.exists(css_path):
            return css_path
    
    return None


def _load_fallback_css():
    """
    Load essential CSS inline as a fallback when external CSS file is not found.
    This ensures basic styling is applied even when the CSS file is missing.
    """
    fallback_css = """
    <style>
    /* Essential fallback CSS for tables and UI components */
    
    /* Global styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        background: linear-gradient(135deg, rgba(248, 250, 252, 0.8) 0%, rgba(241, 245, 249, 0.6) 100%);
        min-height: 100vh;
    }
    
    .stApp {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    }
    
    /* Table styling */
    .custom-table-wrapper {
        border-radius: 8px;
        overflow: hidden;
        overflow-x: auto;
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.1);
        margin: 1rem 0;
        max-width: 100%;
        border: 1px solid #e5e7eb;
    }
    
    .custom-table-wrapper table {
        width: 100%;
        border-collapse: collapse;
        background: white;
    }
    
    .custom-table-wrapper th {
        background: #3b82f6 !important;
        color: white !important;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-size: 0.875rem;
        padding: 12px 16px;
        border: none;
    }
    
    .custom-table-wrapper td {
        background-color: #ffffff;
        border-bottom: 1px solid #f3f4f6;
        padding: 12px 16px;
        color: #1f2937;
        word-wrap: break-word;
        white-space: normal;
    }
    
    .custom-table-wrapper tbody tr:hover td {
        background: rgba(59, 130, 246, 0.05) !important;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%) !important;
        color: white !important;
        font-weight: 500 !important;
        border-radius: 12px !important;
        border: none !important;
        padding: 0.75rem 1.5rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 14px rgba(96, 165, 250, 0.25) !important;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%) !important;
        color: #1e40af !important;
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(59, 130, 246, 0.3) !important;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab"] {
        background: linear-gradient(135deg, #64748b 0%, #475569 100%) !important;
        color: white !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        margin: 0 5px !important;
        font-weight: 500 !important;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%) !important;
        color: white !important;
    }
    
    /* File uploader styling */
    .stFileUploader > div {
        border-radius: 16px !important;
        border: 2px dashed rgba(59, 130, 246, 0.3) !important;
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.04) 0%, rgba(147, 197, 253, 0.04) 100%) !important;
        padding: 2rem !important;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f1f5f9 0%, #e2e8f0 100%) !important;
        border-right: 1px solid rgba(59, 130, 246, 0.2) !important;
    }
    
    /* Metrics styling */
    .stMetric {
        background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%) !important;
        padding: 1.5rem !important;
        border-radius: 16px !important;
        box-shadow: 0 4px 16px rgba(59, 130, 246, 0.08) !important;
        border: 1px solid rgba(59, 130, 246, 0.1) !important;
    }
    
    /* Input styling */
    .stTextInput input,
    .stTextArea textarea {
        border-radius: 12px !important;
        border: 1px solid rgba(59, 130, 246, 0.2) !important;
        background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%) !important;
    }
    
    .stTextInput input:focus,
    .stTextArea textarea:focus {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
    }
    </style>
    """
    
    st.markdown(fallback_css, unsafe_allow_html=True)