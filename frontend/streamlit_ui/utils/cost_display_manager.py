import streamlit as st
import os

from core.llm.TokenCostCalculator import TokenCostCalculator

class CostDisplayManager:
    
    @staticmethod
    def load_css():
        """Load CSS for sidebar metrics styling"""
        # Always use inline CSS to ensure it's loaded
        css_loaded = False
        
        # Try to find and load external CSS file
        from core.common.css_utils import load_table_styles
        css_loaded = load_table_styles()
        
        if not css_loaded:
            # Fallback - continue with inline CSS below
            pass
        
        # Enhanced sidebar CSS with gradient background
        st.markdown("""
            <style>
            /* Enhanced Sidebar Styling - Very Light Pastel Colors */
            [data-testid="stSidebar"],
            .css-1d391kg,
            section[data-testid="stSidebar"] {
                background: linear-gradient(180deg, #e0e7ff 0%, #fef3c7 25%, #fecaca 50%, #fce7f3 75%, #dbeafe 100%) !important;
                background-size: 100% 400% !important;
                animation: sidebarGradientShift 12s ease infinite !important;
                border-right: 1px solid rgba(0, 0, 0, 0.1) !important;
                box-shadow: 4px 0 20px rgba(0, 0, 0, 0.05) !important;
            }
            
            @keyframes sidebarGradientShift {
                0% { background-position: 0% 0%; }
                50% { background-position: 0% 100%; }
                100% { background-position: 0% 0%; }
            }
            
            /* Header styling */
            .sidebar .stMarkdown h2,
            [data-testid="stSidebar"] h2 {
                color: #1f2937 !important;
                font-weight: 700 !important;
                text-align: center !important;
                margin-bottom: 1.5rem !important;
                padding-bottom: 0.75rem !important;
                border-bottom: 1px solid rgba(0, 0, 0, 0.2) !important;
                text-shadow: 0 2px 4px rgba(255, 255, 255, 0.5) !important;
            }
            
            /* Enhanced metrics styling for sidebar - Light Theme */
            .sidebar .stMetric,
            [data-testid="stSidebar"] .stMetric {
                background: rgba(255, 255, 255, 0.7) !important;
                border: 1px solid rgba(0, 0, 0, 0.1) !important;
                border-radius: 16px !important;
                padding: 1rem !important;
                margin: 0.5rem 0 !important;
                backdrop-filter: blur(10px) !important;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05) !important;
                transition: all 0.3s ease !important;
            }
            
            /* Enhanced hover effect */
            .sidebar .stMetric:hover,
            [data-testid="stSidebar"] .stMetric:hover {
                transform: translateY(-2px) scale(1.02) !important;
                background: rgba(255, 255, 255, 0.9) !important;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1) !important;
            }
            
            /* Metric label styling */
            .sidebar .stMetric > div > div:first-child,
            [data-testid="stSidebar"] .stMetric > div > div:first-child {
                color: #374151 !important;
                font-weight: 600 !important;
                font-size: 0.875rem !important;
                margin-bottom: 0.25rem !important;
                text-transform: uppercase !important;
                letter-spacing: 0.05em !important;
                text-shadow: 0 1px 2px rgba(255, 255, 255, 0.5) !important;
            }
            
            /* Metric value styling */
            .sidebar .stMetric > div > div:last-child,
            [data-testid="stSidebar"] .stMetric > div > div:last-child {
                color: #1f2937 !important;
                font-weight: 700 !important;
                font-size: 1.125rem !important;
                text-shadow: 0 1px 2px rgba(255, 255, 255, 0.5) !important;
            }
            
            /* Ensure all sidebar text has good contrast */
            [data-testid="stSidebar"] *,
            .sidebar * {
                color: #1f2937 !important;
                text-shadow: 0 1px 2px rgba(255, 255, 255, 0.5) !important;
            }
            
            </style>
            """, unsafe_allow_html=True)
    @staticmethod
    def render_cost_metrics():
        try:
            # Load CSS for styling
            CostDisplayManager.load_css()
            
            with st.sidebar:
                st.markdown("## 📊 Model Information & Metrics")
                
                # Use native Streamlit components with improved styling
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.metric(
                        label="🤖 GPT Model",
                        value=getattr(st.session_state, 'gpt_model_used', 'GPT-4o')
                    )
                    
                with col2:
                    st.metric(
                        label="📞 LLM Calls", 
                        value=getattr(st.session_state, 'number_of_calls_to_llm', 0)
                    )
                
                # Cost metrics in separate row
                col3, col4 = st.columns([1, 1])
                
                with col3:
                    cost_eur = getattr(st.session_state, 'total_cost_per_tool', 0.0)
                    st.metric(
                        label="💰 Cost (EUR)",
                        value=f"{cost_eur}"
                    )
                    
                with col4:
                    cost_inr = TokenCostCalculator.convert_cost(cost_eur, "INR") if cost_eur else 0.0
                    st.metric(
                        label="💸 Cost (INR)",
                        value=f"{cost_inr}"
                    )
        except Exception as e:
            # Fallback elegant error display
            CostDisplayManager.load_css()
            with st.sidebar:
                st.markdown(
                    """
                    <div class="model-metrics-container">
                        <div class="model-metrics-header">
                            <span class="model-metrics-icon">⚠️</span>
                            <h3 class="model-metrics-title">Metrics Unavailable</h3>
                        </div>
                        <div class="metric-item">
                            <div class="metric-label">Status</div>
                            <div class="metric-value" style="color: #f59e0b;">Initializing...</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )