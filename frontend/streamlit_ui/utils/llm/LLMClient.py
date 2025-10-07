import os
import httpx
import streamlit as st
from openai import AzureOpenAI
from dotenv import load_dotenv, find_dotenv

class LLMClient:
    def __init__(self, model_name):
        _ = load_dotenv(find_dotenv())
        self.model_name = model_name
        self.azure_endpoint = os.getenv(f"{model_name}_AZURE_OPENAI_ENDPOINT")
        self.api_key = os.getenv(f"{model_name}_AZURE_OPENAI_KEY")
        self.api_version = os.getenv(f"{model_name}_AZURE_API_VERSION")
        self.deployment_model = os.getenv(f"{model_name}_MODEL_DEPLOYMENT_NAME")
        self.http_client = httpx.Client(verify=False)
        self.client = self._initialize_client()

    def _initialize_client(self):
        if not self.azure_endpoint or not self.api_key or not self.api_version:
            st.info(f"self.azure_endpoint: {self.azure_endpoint}")
            st.info(f"self.api_key: {self.api_key}")
            st.info(f"self.api_version: {self.api_version}")
            st.error(f"Configuration for {self.model_name} is incomplete. Please check your environment variables.")
            return None
        return AzureOpenAI(
            azure_endpoint=self.azure_endpoint,
            api_key=self.api_key,
            api_version=self.api_version,
            http_client=self.http_client
        )

    def get_client(self):
        return self.client
    
    def get_deployment_model(self):
        return self.deployment_model
    
    