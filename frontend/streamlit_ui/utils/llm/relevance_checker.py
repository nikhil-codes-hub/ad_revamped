import os

from openai import AzureOpenAI as OpenAIAzureOpenAI
from dotenv import load_dotenv, find_dotenv
import streamlit as st

class Agent:
    def __init__(self, prompts, gpt_client, model_name) -> None:
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
        """
        Generate a chat completion using the specified model.
        """
        try:
            response = self.gpt_client.chat.completions.create(
                model=self.model_name,
                messages=self.get_all_prompts(),
                temperature=self.temperature
                )
            return response
        except Exception as e:
            print(f"Error in get_chat_completion: {e}")
            # st.error(f"Error in get_chat_completion: {e}")
            return None

def setup_agent(model_name):

    _ = load_dotenv(find_dotenv())
    deployment_model = os.getenv(f"{model_name}_MODEL_DEPLOYMENT_NAME")

    print("deployment: ", deployment_model)
    
    gpt_client = OpenAIAzureOpenAI(
        azure_endpoint = os.getenv(f"{model_name}_AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv(f"{model_name}_AZURE_OPENAI_KEY"),
        api_version=os.getenv(f"{model_name}_AZURE_API_VERSION")
        )

    agent = Agent([], gpt_client, deployment_model)
    return agent



prompts = [{"role": "system", "content": "You check the relevance of user input. The topic is XSLT and XML generation in the context of airlines and travel"}]
def message_temp(user_message):
    message = f"""Here is the user input: {user_message}
    Is this relevant to the topic? reply with yes or no."""
    return message

message = message_temp("""2. **Mapping conditions and Mandatory Sorting:**
    **Instructions for generating SelectedOfferItem:
    1. Filter the actors based on the RefIDs under each product.
    2. Create a dictionary based on the filtered actors and sort the actors by thier FirstName+LastName.
    3. Replace the sorted actors with PAX.
    4. Use the below code to populate elements.
                <xsl:for-each select="Requests/Request/set/product">
                            <ns0:SelectedOfferItem>
                                <ns0:OfferItemRefID><xsl:value-of select="ID"/></ns0:OfferItemRefID>
                                <xsl:variable name="refIds" select = "RefIDs"/>
                                <xsl:variable name="filteredActors">
                                    <xsl:for-each select="AMA_ConnectivityLayerRQ/Requests/Request/actor">
                                        <xsl:if test="contains(concat(' ', $refIds, ' '), concat(' ', ID, ' '))">
                                            <xsl:copy-of select="."/>
                                        </xsl:if>
                                    </xsl:for-each>
                                </xsl:variable>
                                <xsl:variable name="sortedActors" as="element(actor)+">
                                    <xsl:perform-sort select="$filteredActors/actor">
                                        <xsl:sort select="Name/FirstName"/>
                                        <xsl:sort select="Name/LastName"/>
                                    </xsl:perform-sort>
                                </xsl:variable>
                                <xsl:for-each select = "$sortedActors">
                                    <ns0:PaxRefID><xsl:value-of select="concat('PAX', substring(current()/ID, 2))"/></ns0:PaxRefID>
                                </xsl:for-each>
                            </ns0:SelectedOfferItem>
                </xsl:for-each>
        * Do sort only if PTC = ADT""")


prompts.append({"role": "user", "content": message})
relevance_checker_agent = setup_agent("GPT4o_mini")
relevance_checker_agent.set_prompts(prompts)
# relevance_checker_agent.add_user_message("say hi")

# print(relevance_checker_agent.get_chat_completion().choices[0].message.content)

prompts.pop(-1)
# print(prompts)

message_irrelevant = message_temp("I love online shopping, can you recommend me some airline travel books on Amazon?")
prompts.append({"role": "user", "content": message_irrelevant})
relevance_checker_agent.set_prompts(prompts)
print(relevance_checker_agent.get_chat_completion().choices[0].message.content)
