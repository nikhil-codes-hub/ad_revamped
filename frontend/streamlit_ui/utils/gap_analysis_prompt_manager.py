import os
from pathlib import Path
from core.common.constants import PROJECT_ROOT
from core.prompts_manager.prompt_manager import promptManager
import streamlit as st

class GapAnalysisPromptManager(promptManager):
    
    # Define the root directory (e.g., from an environment variable or a config file)
    ROOT_DIR = Path(os.getenv("PROJECT_ROOT", PROJECT_ROOT))

    """
    A manager class for handling prompts related to XSLT updates.
    """

    def load_default_prompts(self, params):
        pass
    
    def load_prompts():
        pass
    
    def get_default_system_prompt(self):
        pass
    
    def load_prompts_for_pattern_identification(self, unknown_source_xml_content, search_prompt):
        current_dir = Path(__file__).resolve().parent
        file_path = current_dir / "../config/prompts/generic/default_system_prompt_for_gap_analysis.md"
        with file_path.open() as f:
            pattern_identifier_prompt = f.read()
        prompts = [
            {"role": "system", "content": pattern_identifier_prompt},
            {"role": "user", "content": "Here is the input XML file." + "\n" + "```" + unknown_source_xml_content + "```" },
            {"role": "user", "content": search_prompt }
        ]
        self.agent.set_prompts(prompts)
    
    def load_prompts_for_intelligent_pattern_identification(self, unknown_source_xml_content, search_prompt):
        """
        Load enhanced prompts for intelligent pattern identification that can handle
        passenger combinations and airline-specific relationship patterns.
        """
        current_dir = Path(__file__).resolve().parent
        file_path = current_dir / "../config/prompts/generic/enhanced_paxlist_pattern_analysis.md"
        
        try:
            with file_path.open() as f:
                intelligent_pattern_prompt = f.read()
        except FileNotFoundError:
            # Fallback to regular prompt if enhanced prompt not found
            st.warning("Enhanced pattern analysis prompt not found. Using standard prompt.")
            return self.load_prompts_for_pattern_identification(unknown_source_xml_content, search_prompt)
        
        prompts = [
            {"role": "system", "content": intelligent_pattern_prompt},
            {"role": "user", "content": "Here is the input XML file to analyze for passenger patterns:" + "\n" + "```" + unknown_source_xml_content + "```"},
            {"role": "user", "content": f"Pattern to match against: {search_prompt}"}
        ]
        self.agent.set_prompts(prompts)
    
    def load_prompts_for_extracting_patterns(self, content, insights=None):
        current_dir = Path(__file__).resolve().parent
        file_path = current_dir / "../config/prompts/generic/default_system_prompt_for_pattern_extraction.md"
        with file_path.open() as f:
            pattern_identifier_prompt = f.read()
        prompts = [
            {"role": "system", "content": pattern_identifier_prompt},
            {"role": "user", "content": f"Here is the combined XML content - {content}"},
            {"role": "user", "content": f"Here are the insights - {insights}"}
        ]
        self.agent.set_prompts(prompts)
    
    def load_prompts_for_airline_focused_extraction(self, content, insights=None):
        """
        Load enhanced prompts for airline-focused pattern extraction that avoids 
        generic patterns and focuses on airline-differentiating patterns.
        """
        current_dir = Path(__file__).resolve().parent
        
        # Try simplified prompt first (more reliable)
        simplified_file_path = current_dir / "../config/prompts/generic/simplified_airline_focused_extraction.md"
        detailed_file_path = current_dir / "../config/prompts/generic/airline_focused_pattern_extraction.md"
        
        try:
            # Use simplified prompt for better reliability
            with simplified_file_path.open() as f:
                airline_focused_prompt = f.read()
        except FileNotFoundError:
            try:
                # Fallback to detailed prompt
                with detailed_file_path.open() as f:
                    airline_focused_prompt = f.read()
            except FileNotFoundError:
                # Final fallback to regular prompt
                st.warning("Airline-focused pattern extraction prompt not found. Using standard prompt.")
                return self.load_prompts_for_extracting_patterns(content, insights)
        
        prompts = [
            {"role": "system", "content": airline_focused_prompt},
            {"role": "user", "content": f"XML content to analyze for airline fingerprints:\n{content}"},
            {"role": "user", "content": f"Additional insights: {insights}" if insights else "No additional insights provided."}
        ]
        self.agent.set_prompts(prompts)
    
    def load_prompts_for_manual_addition(self, conversational_params):
        current_dir = Path(__file__).resolve().parent
        file_path = current_dir / "../config/prompts/generic/default_system_prompt_for_manual_pattern_addition.md"
        with file_path.open() as f:
            pattern_identifier_prompt = f.read()
        
        xml_chunk = conversational_params.get('xml_chunk')
        tag = conversational_params.get('tag')
        name = conversational_params.get('name')
        description = conversational_params.get('description')
        
        prompts = [
            {"role": "system", "content": pattern_identifier_prompt},
            {"role": "user", "content": f"Here is the XML - {xml_chunk}"},
            {"role": "user", "content": f"XML XPath - {tag}, Name - {name}, Description - {description}"}
        ]
        self.agent.set_prompts(prompts)
    
    def load_prompts_for_pattern_verfication(self, conversational_params):
        current_dir = Path(__file__).resolve().parent
        file_path = current_dir / "../config/prompts/generic/default_system_prompt_for_pattern_verification.md"

        with file_path.open() as f:
            pattern_verifier_prompt = f.read()

        # Prepare the prompts for the agent
        xml_content = conversational_params.get('xml_content')
        selected_prompt = conversational_params.get('selected_prompt')
        
        prompts = [
            {"role": "user", "content": pattern_verifier_prompt},
            {"role": "user", "content": f"Here is the XML content - {xml_content}"},
            {"role": "user", "content": f"Here is the prompt - {selected_prompt}"}
        ]
        self.agent.set_prompts(prompts)

    def load_prompts_for_insights(self, selected_nodes_map):
        current_dir = Path(__file__).resolve().parent
        file_path = current_dir / "../config/prompts/generic/default_system_prompt_for_pattern_insights.md"

        with file_path.open() as f:
            pattern_verifier_prompt = f.read()

        # Prepare the prompts for the agent
        prompts = [
            {"role": "user", "content": pattern_verifier_prompt},
            {"role": "user", "content": f"Here are the XML nodes - {selected_nodes_map}"}
        ]

        # Set the prompts in the shared agent
        self.agent.set_prompts(prompts)