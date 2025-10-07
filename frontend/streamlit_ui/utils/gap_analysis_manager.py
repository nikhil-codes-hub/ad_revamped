import pandas as pd
from core.llm.LLMManager import LLMManager
import streamlit as st
from core.common.ui_utils import render_custom_table

class GapAnalysisManager(LLMManager):
    
    def __init__(self, model_name):
        super().__init__(model_name)
    
    def _initiate_conversation(self):
        return self.run()
    
    def run(self):
        cost, llm_response = self.agent.get_chat_completion()
        st.session_state.number_of_calls_to_llm += 1
        st.session_state.total_cost_per_tool += cost 
        if llm_response:
            return llm_response.choices[0].message.content
        
    def display_patterns(self):
        data = []
        try:
            for tag, values in st.session_state.pattern_responses.items():
                # Extract values from the dictionary
                data.append([
                    values.get('path', ''),
                    values.get('name', ''),
                    values.get('description', ''),
                    values.get('prompt', '')
                ]) 
            if data:
                df = pd.DataFrame(data, columns=['XPATH', 'Name', 'Description', 'Prompt'])
                st.subheader(":blue[Here are the patterns identified for the given XML]")
                from core.common.css_utils import get_css_path
                css_path = get_css_path()
                render_custom_table(df, long_text_cols=['Description', 'Prompt'], css_rel_path=css_path)
        except Exception as e:
            st.error(f"An error occurred while displaying patterns: {e}")

                    
