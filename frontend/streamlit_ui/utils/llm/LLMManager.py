
import streamlit as st
from core.common.user_interaction import userInteraction
from core.llm.LLMAgent import LLMAgent
from core.llm.LLMClient import LLMClient
from abc import ABC, abstractmethod

class LLMManager(ABC):
    model_name = None
    
    def __init__(self, model_name):
        self.client = LLMClient(model_name)
        self.model_name = model_name
        self.agent = self._setup_agent()
        self.init_session_state()

    def init_session_state(self):
        """
        Initializes the session state for the XSLT Updater application.

        Raises:
            Exception: If the agent is not properly initialized or any unexpected error occurs.
        """
        try:
            # Check if the agent is properly initialized
            if not self._get_agent():
                st.error("Agent is not properly initialized. Please check your configuration.")
                st.stop()

            # Set the GPT model name in the session state
            st.session_state.gpt_model_used = self._get_model_name()

            # Initialize other session objects
            userInteraction.init_objects_into_session()

        except AttributeError as e:
            st.error(f"An attribute error occurred during session initialization: {e}")
            st.stop()
        except Exception as e:
            st.error(f"An unexpected error occurred during session initialization: {e}")
            st.stop()

    def _setup_agent(self):
        gpt_client = self.client.get_client()
        deployment_model = self.client.get_deployment_model()
        if gpt_client and deployment_model:
            return LLMAgent([], gpt_client, deployment_model)
        return None
    
    @abstractmethod
    def _initiate_conversation(self, action):
        """This method must be overridden in subclasses."""
        pass
   
    def _get_model_name(self):
        return self.model_name
    
    def _get_agent(self):
        return self.agent
    
    def _reset_agent(self):
        if not self.agent:
            st.error(f"Agent for {self.model_name} doesn't exists. Please try again.")
            return None
        self.agent = None