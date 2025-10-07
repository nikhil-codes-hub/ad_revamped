import streamlit as st

from core.llm.TokenCostCalculator import TokenCostCalculator

class LLMAgent:
    def __init__(self, prompts, gpt_client, model_name):
        self.prompts = prompts
        self.gpt_client = gpt_client
        self.model_name = model_name
        self.temperature = 0

    def add_message(self, prompt):
        self.prompts.append(prompt)

    def add_user_message(self, prompt):
        self.prompts.append({"role": "user", "content": prompt})

    def get_all_prompts(self):
        return self.prompts

    def set_temperature(self, temperature):
        self.temperature = temperature

    def set_prompts(self, prompts):
        self.prompts = prompts

    def get_chat_completion(self):
        try:
            response = self.gpt_client.chat.completions.create(
                model=self.model_name,
                messages=self.get_all_prompts(),
                temperature=self.temperature,
                top_p=0.9,
            )
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            calculator = TokenCostCalculator(self.model_name)
            cost_eur = calculator.calculate_cost(prompt_tokens, completion_tokens)
            return cost_eur, response
        except Exception as e:
            st.error(f"Error in get_chat_completion: {e}")
            st.error(e.with_traceback)
            return None