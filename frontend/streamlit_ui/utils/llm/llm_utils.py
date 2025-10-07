import os
import json
import pandas as pd
import streamlit as st
import re
import numpy as np
import chromadb
from openai import AzureOpenAI
from dotenv import load_dotenv, find_dotenv
from core.llm import TokenCostCalculator
from core.llm.TokenCostCalculator import TokenCostCalculator
from core.prompts_manager.prompt_utils import *
from core.common.confluence_utils import publish_content
from core.database.database_utils import parse_questions_and_retreive_answers
from core.llm.llm_response_handler_utils import get_answer, get_answer_md, get_answer_html, consolidating_questions
from core.common.user_interaction import userInteraction
from core.common.utils import extract_space_and_page_name,get_body,refine_and_display_markdown,convert_html_to_csv, convert_html_to_markdown, refine_and_display_markdown_update, markdown_to_html_table
from core.database.llamaIndex import query_eng_setup,get_answer_llm
from core.xml_processing.xml_utils import verify_prerequisite
from core.data_processing.cleanup import row_extraction
import httpx
pd.set_option('display.max_colwidth', None)
pd.set_option('display.max_columns', None)
httpx_client = httpx.Client(verify=False)
_ = load_dotenv(find_dotenv())

global model_name_used

gpt4o_model_name = os.getenv("GPT4O_MODEL_DEPLOYMENT_NAME")
o1_model_name = os.getenv("o1_MODEL_DEPLOYMENT_NAME")
o3_mini_model_name = os.getenv("o3_mini_MODEL_DEPLOYMENT_NAME")

o1client = AzureOpenAI(
  azure_endpoint = os.getenv("o1_AZURE_OPENAI_ENDPOINT"), 
  api_key=os.getenv("o1_AZURE_OPENAI_KEY"),  
  api_version=os.getenv("o1_AZURE_API_VERSION"),
  http_client=httpx_client
)

o3client = AzureOpenAI(
  azure_endpoint = os.getenv("o3_mini_AZURE_OPENAI_ENDPOINT"), 
  api_key=os.getenv("o3_mini_AZURE_OPENAI_KEY"),  
  api_version=os.getenv("o3_mini_AZURE_API_VERSION"),
  http_client=httpx_client
)

gpt4oclient = AzureOpenAI(
  azure_endpoint = os.getenv("GPT4O_AZURE_OPENAI_ENDPOINT"), 
  api_key=os.getenv("GPT4O_AZURE_OPENAI_KEY"),  
  api_version=os.getenv("GPT4O_AZURE_API_VERSION"),
  http_client=httpx_client
)

text_embd_client = AzureOpenAI(
 azure_endpoint = os.getenv("ADA_EMBD_AZURE_OPENAI_ENDPOINT"), 
 api_key=os.getenv("ADA_EMBD_AZURE_OPENAI_KEY"),  
 api_version=os.getenv("ADA_EMBD_AZURE_API_VERSION"),
 http_client=httpx_client
)

def generate_embedding(client, text, deployment_name="text-embedding-ada-002"):
    response = client.embeddings.create(
        model=deployment_name,  # The deployment name of the embedding model
        input=[text]
    )
    # Return the embedding vector
    return response.data[0].embedding

class Agent:
    calculator = None
    def __init__(self, prompts, gpt_client, model_name) -> None:
        self.prompts = prompts
        self.gpt_client = gpt_client
        self.model_name = model_name
        self.temperature = 0
        self.responses = []
     
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

    def get_all_responses(self):
        return self.responses

    def get_chat_completion(self):
        """
        Generate a chat completion using the specified model.
        """
        try:
            response = self.gpt_client.chat.completions.create(
                model=self.model_name,
                messages=self.get_all_prompts(),
                temperature=self.temperature,
                top_p = 0.9,
                )

            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            calculator = TokenCostCalculator(self.model_name)
            cost_eur = calculator.calculate_cost(prompt_tokens, completion_tokens)
            return cost_eur, response
        except Exception as e:
            print(f"Error in get_chat_completion: {e.__cause__}")
            st.error(f"Error in get_chat_completion: {e}")
            return None

def setup_agent(model_name):
    """
    Sets up an agent with the specified model name by loading environment variables and initializing the GPT client.

    Args:
        model_name (str): The name of the model to be used for the agent.

    Returns:
        Agent: An instance of the Agent class initialized with the specified model.
    """

    _ = load_dotenv(find_dotenv())
    deployment_model = os.getenv(f"{model_name}_MODEL_DEPLOYMENT_NAME")
    azure_endpoint = os.getenv(f"{model_name}_AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv(f"{model_name}_AZURE_OPENAI_KEY")
    api_version = os.getenv(f"{model_name}_AZURE_API_VERSION")

    print("deployment: ", deployment_model)
    print("azure_endpoint: ", azure_endpoint)
    print("api_key: ", api_key)
    print("api_version:", api_version)

    gpt_client = AzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version=api_version,
        http_client=httpx.Client(verify=False)
    )

    agent = Agent([], gpt_client, deployment_model)
    return agent

def get_chat_completion(input_messages, model_name=o3_mini_model_name):
    try:
        if model_name == gpt4o_model_name:
            print(f"Model Used: {model_name}")
            response = gpt4oclient.chat.completions.create(
                model=model_name,
                messages=input_messages,
                temperature=0,
                top_p=0.9,  # this is the degree of randomness of the model's output
            )

        elif model_name == o1_model_name:
            print(f"Model Used: {o1_model_name}")
            response = o1client.chat.completions.create(
                model=model_name,
                messages=input_messages)
            
        else:
            print(f"Model Used: {o3_mini_model_name}")
            response = o3client.chat.completions.create(
                model=model_name,
                messages=input_messages
            )

        # Calculate token cost
        # prompt_tokens = response.usage.prompt_tokens
        # completion_tokens = response.usage.completion_tokens
        # calculator = TokenCostCalculator(model_name)
        # cost_eur = calculator.calculate_cost(prompt_tokens, completion_tokens, currency="EUR")
        # st.info(f"Token Cost: €{cost_eur} EUR")
        return response
    except Exception as e:
        # print(f"Error in get_chat_completion: {e.__cause__}")
        st.error(f"Error in get_chat_completion: {e}")
        return None
    
def show_result(result):
    print(result.choices[0].message.content)

def get_result(result):
    return result.choices[0].message.content
    
def show_result_with_stats(result):
    """
    Print the content of the first message and token usage statistics.
    """
    print(result.choices[0].message.content)
    print(f"prompt_tokens={result.usage.prompt_tokens}, completion_tokens={result.usage.completion_tokens}, total_tokens={result.usage.total_tokens}")

def show_stats(result):
    """
    Print token usage statistics for the chat completion.
    """
    print(f"prompt_tokens={result.usage.prompt_tokens}, completion_tokens={result.usage.completion_tokens}, total_tokens={result.usage.total_tokens}")

def initiate_conversation_with_LLM(source_xml_file, target_xml_file, mapping_specifications_file, transformation_type):
    """
    Initiates a conversation with the LLM using the provided input files.

    Args:
        source_xml_file (str): The path to the source XML file.
        target_xml_file (str): The path to the target XML file.
        mapping_specifications_file (str): The path to the mapping specifications file.

    """

    # Load prompts and create GPT client
    system_prompts = load_prompts(source_xml_file, target_xml_file, mapping_specifications_file, transformation_type)
    xslt_generator_agent = setup_agent("GPT4O")
    xslt_generator_agent.set_prompts(system_prompts)
    st.session_state.generator_agent = xslt_generator_agent

    # Invoke LLM
    with st.spinner('Analysing the inputs, processing!'):
        llm_response = xslt_generator_agent.get_chat_completion()
        if not llm_response.choices[0].message.content:
            st.error("Error in generating XSLT. No response was generated.")
            return

    with st.spinner('Processing the response!'):
        has_questions = process_response(llm_response)

    if has_questions:
        with st.spinner('Hang on, fine tuning the XSLT!'):
            subsequent_call_to_LLM(source_xml_file, target_xml_file, mapping_specifications_file)
    # else:
    #     write_chat_message("assistant", ":green[No questions, XSLT generated successfully.]")
    if not st.session_state.has_human_feedback:
        write_chat_message("assistant", ":green[No questions, XSLT generated successfully.]")
        add_to_messages(":green[No questions, XSLT generated successfully.]")

def initiate_conversation_with_LLM_coe(source_xml_file, target_xml_file, mapping_specifications_file):
    pass

def initiate_conversation_with_LLM_update(source_xml_file, target_xml_file, xslt, mapping_specifications_file, 
                                          cookbooks, user_requirement_prompt, shared_agent):
    combined_prompts = []
    print("mapping_specifications_file : ", mapping_specifications_file)
    space, page_name = extract_space_and_page_name(mapping_specifications_file)
    st.session_state.url = mapping_specifications_file
    page_name = page_name.replace("+", " ")
    st.session_state.space,st.session_state.page_name = space,page_name
    if space and page_name:
        html_content = get_body(space, page_name)
        if html_content:
            #mapping_specifications_file = convert_html_to_markdown(html_content)
            csv_data, dataFrame = convert_html_to_csv(html_content)
            markdown_table = dataFrame.to_markdown(index=False)
            print("Markdown file before refinement : ", markdown_table)
            mapping_specifications_file = refine_and_display_markdown_update(markdown_table)
            st.session_state.specs_file = mapping_specifications_file
            print("Markdown file after refinement : ", mapping_specifications_file)
        else:
            st.error("Invalid Page")
    else:
        st.error("Invalid URL format")

    system_prompts = load_prompts_update(xslt)
    combined_prompts = []
    for prompt in system_prompts:
        combined_prompts.append(prompt)
    combined_prompts.append({"role":"user", "content": "The user instruction to update the XSLT" + user_requirement_prompt})
    combined_prompts.append({"role":"user", "content": "Return only JSON with 'updated_XSLT'."})

    shared_agent.set_prompts(combined_prompts)
    with st.spinner('Updating XSLT...'):
        cost, llm_response = shared_agent.get_chat_completion()
        st.session_state.number_of_calls_to_llm += 1
        st.session_state.total_cost_per_tool += cost
    if llm_response:
        print(llm_response.choices[0].message.content)
        response = re.sub(r'[\x00-\x1F\x7F]', '', llm_response.choices[0].message.content)
        if response.lstrip().lower().startswith('json'):
            response = response.lstrip()[4:].lstrip()
        try:
            resp_json = json.loads(response)
            st.session_state.updated_xslt = resp_json['updated_XSLT']
            print(resp_json['updated_XSLT'])
            add_to_messages("XSLT has been updated. Now updating specs in the next step.")
        except json.JSONDecodeError:
            add_to_messages(response)

    # Step 2: update specs
    system_prompts = load_prompts_update_specs(mapping_specifications_file)
    combined_prompts = []
    for prompt in system_prompts:
        combined_prompts.append(prompt)
    combined_prompts.append({"role":"user", "content": "Now update the specification file based on user requirement : " + user_requirement_prompt})
    combined_prompts.append({
        "role":"system",
        "content": 
            "Your reply must be exactly a JSON object with one field:\n"
            "{\n"
            '  "updated_specs": "<the entire spec file as one JSON string>"\n'
            "}\n\n"
            "Example:\n"
            '{\n'
            '  "updated_specs": ""Input: , Output: OrderCreateRQ/@Version, Remarks: Hardcoded as 17.2, Type: Attribute\nInput: Request/Context/correlationid, Output: OrderCreateRQ/@Correlationid, Remarks: Optional, Type: \nInput: Request/Context/correlationID, Output: OrderCreateRQ/@TransactionIdentifier, Remarks: Optional, Type: \n'
            "}"
        })
    print(combined_prompts)
    shared_agent.set_prompts(combined_prompts)
    with st.spinner('Updating specs...'):
        cost, llm_response = shared_agent.get_chat_completion()
        st.session_state.number_of_calls_to_llm += 1
        st.session_state.total_cost_per_tool += cost
    if llm_response:
        print(llm_response.choices[0].message.content)
        response = re.sub(r'[\x00-\x1F\x7F]', '', llm_response.choices[0].message.content)
        if response.lstrip().lower().startswith('json'):
            response = response.lstrip()[4:].lstrip()
        try:
            resp_json = json.loads(response)
            st.session_state.updated_specs = resp_json['updated_specs']
            print(resp_json['updated_specs'])
            html_table = markdown_to_html_table(st.session_state.updated_specs)
            st.session_state.html = html_table
            add_to_messages("Specifications have been updated. Please check.")
        except json.JSONDecodeError:
            add_to_messages(response)
                
def initiate_conversation_with_LLM_for_gap_analysis(source_xml_file, target_xml_file, mapping_specifications_file, onboarding_ai, reference_ai):
    system_prompts = load_prompts_gap_analysis(source_xml_file, target_xml_file, mapping_specifications_file, onboarding_ai, reference_ai)
    for prompt in system_prompts:
        add_to_prompts(prompt)
    # user_instruction_prompt = {"role":"user", "content": "The user instruction to update the XSLT" + user_prompt}
    # system_prompts.append(user_instruction_prompt)
    # add_to_prompts(user_instruction_prompt)
    with st.spinner('Analysing the inputs, processing!'):
        llm_response = get_chat_completion(system_prompts)
        if llm_response:
            response_obj = llm_response.choices[0].message.content
            response = re.sub(r'[\x00-\x1F\x7F]', '', response_obj)

            # Check if response starts with 'json' and remove it
            if response.lstrip().startswith('json'):
                response = response.lstrip()[4:].lstrip()

            try:
                response_obj_json = json.loads(response)
                if response_obj_json.get('analysis'):
                    st.session_state.analysis = response_obj_json['analysis']
                    st.session_state.analysis_html = response_obj_json['analysis']
                    st.markdown(st.session_state.analysis_html, unsafe_allow_html=True)
                    st.session_state.questions_map = response_obj_json['questions']
                    add_to_messages(st.session_state.analysis_html)
                    if st.session_state.questions_map:
                        add_to_messages(st.session_state.questions_map)
                else:
                    add_to_messages(response)
            except json.JSONDecodeError:
                add_to_messages(response)
                
def subsequent_call_to_LLM(source_xml_file, target_xml_file, mapping_specifications_file ):
    """
    Handles subsequent calls to the LLM if there are questions requiring human feedback.

    Args:
        source_xml_file (str): The path to the source XML file.
        target_xml_file (str): The path to the target XML file.
        mapping_specifications_file (str): The path to the mapping specifications file.
    """
    questions_for_human_feedback = []

    for question, count in st.session_state.questions_map.items():
        if count > 1:
            questions_for_human_feedback.append(question)

    if not questions_for_human_feedback:
        st.session_state.has_human_feedback = False
        llm_response = st.session_state.generator_agent.get_chat_completion()
        has_questions = process_response(llm_response)
        if has_questions:
            subsequent_call_to_LLM(source_xml_file, target_xml_file, mapping_specifications_file)

    else:
        st.session_state.has_human_feedback = True
        questions_humanfeedback = ":red[Below questions require feedback from the user, please assist.]\n\n"

        for index, question in enumerate(questions_for_human_feedback):
                st.session_state.questions_map[question] = 0 # reset the count to 0 as user
                questions_humanfeedback += f"{index + 1}. {question}\n\n"
        write_chat_message("user", questions_humanfeedback)

def process_response_q(llm_response):

    response_obj = llm_response.choices[0].message.content
    generated_xslt = get_answer(response_obj)
    st.session_state.generated_xslt = generated_xslt

def process_response(llm_response):

    response_obj = llm_response.choices[0].message.content
    generated_xslt = get_answer(response_obj)
    st.session_state.generated_xslt = generated_xslt

    # Save generated XSLT to a file
    # output_path = "../../config/results/MH/generated_xslt.xslt"
    # with open(output_path, "w") as file:
    #     file.write(generated_xslt)
    has_questions, LLM_readable_questions, human_readable_questions = consolidating_questions(response_obj)

    # If any questions, retreive answers from documents (RAG)
    with st.spinner('Querying answers. Processing the given information, please wait!'):
        parse_questions_and_retreive_answers(human_readable_questions)
    return has_questions

def process_response_md(llm_response):

    response_obj = llm_response.choices[0].message.content
    generated_md = get_answer_md(response_obj)
    st.session_state.generated_md = generated_md

    # has_questions, LLM_readable_questions, human_readable_questions = consolidating_questions(response_obj)

    # # If any questions, retreive answers from documents (RAG)
    # with st.spinner('Querying answers. Processing the given information, please wait!'):
    #     parse_questions_and_retreive_answers(human_readable_questions)
    # return has_questions

def process_response_html(llm_response):

    response_obj = llm_response.choices[0].message.content
    generated_html = get_answer_html(response_obj)
    st.session_state.generated_html = generated_html

    # has_questions, LLM_readable_questions, human_readable_questions = consolidating_questions(response_obj)

    # # If any questions, retreive answers from documents (RAG)
    # with st.spinner('Querying answers. Processing the given information, please wait!'):
    #     parse_questions_and_retreive_answers(human_readable_questions)
    # return has_questions

def initiate_conversation_with_LLM_xslt(xslt_file):
    # Load prompts and create GPT client
    system_prompts = load_prompts_xslt(xslt_file)
    xslt_generator_agent = setup_agent("GPT4O")
    xslt_generator_agent.set_prompts(system_prompts)
    st.session_state.generator_agent = xslt_generator_agent

    # Invoke LLM
    with st.spinner('Analysing the inputs, processing!'):
        cost, llm_response = xslt_generator_agent.get_chat_completion()
        # st.write(llm_response)
        if not llm_response.choices[0].message.content:
            st.error("Error in generating XSLT. No response was generated.")
            return
        
    with st.spinner('Processing the response!'):
        has_questions = process_response_q(llm_response)
        if has_questions:
            st.error('Hang on, fine tuning the XSLT!')

def subsequent_conversation_with_LLM_xslt(xslt_file):
    # Load prompts and create GPT client
    system_prompts = load_prompts_md(xslt_file)
    xslt_generator_agent = setup_agent("GPT4O")
    xslt_generator_agent.set_prompts(system_prompts)
    st.session_state.generator_agent = xslt_generator_agent

    # Invoke LLM
    with st.spinner('Analysing the inputs, processing!'):
        cost, llm_response = xslt_generator_agent.get_chat_completion()
        if not llm_response.choices[0].message.content:
            st.error("Error in generating MD. No response was generated.")
            return
        
    with st.spinner('Processing the response!'):
        has_questions = process_response_md(llm_response)
        if has_questions:
            st.error('Hang on, fine tuning the MD!')

def subsequent_conversation_with_LLM_html(md_file):
    # Load prompts and create GPT client
    system_prompts = load_prompts_html(md_file)
    xslt_generator_agent = setup_agent("GPT4O")
    xslt_generator_agent.set_prompts(system_prompts)
    st.session_state.generator_agent = xslt_generator_agent

    # Invoke LLM
    with st.spinner('Analysing the inputs, processing!'):
        cost, llm_response = xslt_generator_agent.get_chat_completion()
        if not llm_response.choices[0].message.content:
            st.error("Error in generating specs. No response was generated.")
            return
        
    with st.spinner('Processing the response!'):
        has_questions = process_response_html(llm_response)
        if has_questions:
            st.error('Hang on, fine tuning the specs!')

def question_from_user(context, message, input_xml_1, output_xml_1):
    
    prompt = [
    {"role": "system", "content": "You are a helpful assistant, who is an expert in XMLs & XSLT. "}, #setting the behavior
    {"role": "user", "content": message},
    {"role": "assistant",  "content": f'''Generate only XSLT 1.0 code by fetching information from the 'Input XPATH', 'Description', and 'Output XPATH' columns in the provided context: {context}. 
                                        Generate XSLT 1.0 code STRICTLY without usage of any unnecessary libraries and for only the elements mentioned in message. Do not include any additional elements or code for additional elements beyond the one requested.
                                        The XSLT should start with '<xsl:stylesheet version="1.0"'
                                        Use this context as the primary source for generating the XSLT. Refer to the input XML ({input_xml_1}) and output XML ({output_xml_1}) to check XPaths.
                                        Focus on the formatting provided in the output XML and check for Missing Delimiters.                                        
                                        All elements in the XML use the `ns0` namespace prefix. Always include `ns0:` before each element in the XPath expressions. For example, "ns0:insuranceOptionSection/ns0:insuranceOptionDetails/ns0:pricingInformations/preferredCurrencyCode" here preferredCurrencyCode is missing the namespace ns0 which is wrong, correct thing would be "ns0:insuranceOptionSection/ns0:insuranceOptionDetails/ns0:pricingInformations/ns0:preferredCurrencyCode".
                                        Provide the XSLT in a single template as much as possible & Do not assume any details that are not explicitly mentioned in the context.'''
                                        }
            ]
    gpt_response = get_chat_completion(prompt)
    if gpt_response is None:
        st.error("Error in generating XSLT. No response was generated.")
        return
    show_stats(gpt_response)
    complete_response = gpt_response.__str__()
    print(f"COMPLETE_RESPONSE: {complete_response}")
    response = gpt_response.choices[0].message.content
    print(f"RESPONSE: {response}")
    return (response,complete_response,prompt.__str__())

def compare_text(specs_text, user_text):

    embedding1 = generate_embedding(text_embd_client, specs_text)
    embedding2 = generate_embedding(text_embd_client, user_text)
    # Calculate similarity
    similarity_score = np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))
    if similarity_score > 0.9:
        print("Inside compare_text and the output is True")
        return True  
    else:
        print("Inside compare_text and the output is False")
        return False

def refine_external(response, input_xml, transformed_xml, main_xslt,chat_history):
        
    prompt = [
        {"role": "system", "content": "You are a helpful assistant and an expert in XML and XSLT 1.0. Always provide accurate refinements, ensuring the new XSLT adheres to the input and output XML structure. Address specific questions or errors without making assumptions unless explicitly stated."},
        {"role": "user", "content": response},
        {"role": "assistant", "content": f"""
                                                Here is the previous XSLT you provided:
                                                ```xslt
                                                {main_xslt}
                                                ```
                                                This was the input XML:
                                                ```xml
                                                {input_xml}
                                                ```
                                                And the expected output XML:
                                                ```xml
                                                {transformed_xml}
                                                ``` 

                                                Providing the chat history so that you have more reference:
                                                ```Chat History
                                                {chat_history}
                                                ```
                                                Please refine only the mentioned field(s), add the necessary changes to the provided XSLT, and return the updated version. 
                                                Unchanged fields must remain exactly as they are.
                                                """}
            ]
    print("inside refine External xslt")
    gpt_response = get_chat_completion(prompt, o3_mini_model_name)
    if gpt_response is None:
        st.error("Error in generating XSLT. No response was generated.")
        return
    show_stats(gpt_response)
    complete_response = gpt_response.__str__()
    print(f"COMPLETE_RESPONSE: {complete_response}")
    response = gpt_response.choices[0].message.content
    print(f"RESPONSE: {response}")
    return (response,complete_response,prompt.__str__())

# %%
###Main Function####
def combine_xslt_2(curr_xslt,main_xslt):
    
    startCode = '''<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" 
           xmlns:ns0="http://www.amadeus.net" exclude-result-prefixes="ns0">
           <xsl:output method="xml" indent="yes"/>'''
    
    prompt = [
    {"role": "system", "content": "You are a helpful assistant, who is an expert in XMLs & XSLT. "}, #setting the behavior
    {"role": "user", "content": "Combine the XSLTs provided without adding extra elements."},
    {"role": "assistant",  "content": f'''I have two XSLT snippets: XSLT 1 {main_xslt} and XSLT 2 {curr_xslt}.
                                            1.Merge all elements from both XSLT 1 and XSLT 2 into a single XSLT document.
                                            2.Include all elements from XSLT 1, and add any unique elements from XSLT 2 that are not already present in XSLT 1.
                                            3.If an element exists in both XSLTs, use the version from XSLT 2.
                                            4.Do not include any elements that were not generated by the XSLTs. Focus strictly on elements present in XSLT 1 and XSLT 2, and do not introduce new or unrelated elements.
                                            5.Ensure that the following conditions are met:
                                                No placeholders like <!-- ... (rest of the template remains unchanged) ... --> or similar comments should be used. The output must contain all merged elements in full detail, with nothing omitted or summarized.
                                                Include namespaces (e.g., ns0) in every XPath expression, even if the elements are conditionally checked or missing. Ensure proper namespace usage in all XPath expressions.
                                            6.Use the following code as the first two lines of the final XSLT: {startCode}.
                                            7.Organize the XSLT as follows:
                                                Group all templates, variables, and parameters under appropriate sections.
                                                Ensure that the final XSLT is well-formed, properly indented, and ready for execution.'''
                                        }
            ]
    print("inside combine 2 xslt")
    gpt_response = get_chat_completion(prompt,gpt4o_model_name)
    show_stats(gpt_response)
    complete_response = gpt_response.__str__()
    print(f"COMPLETE_RESPONSE: {complete_response}")
    response = gpt_response.choices[0].message.content
    print(f"RESPONSE: {response}")
    return (response,complete_response)

# %%
def refine_internal(main_xslt,output_xml_1):
    startCode = '''<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" 
           xmlns:ns0="http://www.amadeus.net" exclude-result-prefixes="ns0">
           <xsl:output method="xml" indent="yes"/>'''
    prompt = [
    {"role": "system", "content": "You are a helpful assistant, who is an expert in XMLs & XSLT."}, #setting the behavior
    {"role": "user", "content": "Refine the provided XSLT if errors are found as mentioned ."},
    {"role": "assistant",  "content": f'''Given the following XSLT 1.0 : {main_xslt} and output XML : {output_xml_1}, Assume that the Xpaths in XSLT are correct and generate a new output XML with this XSLT.
                                        1.Strictly compare only the fields that were directly generated by the XSLT with the corresponding fields in the provided output XML.
                                        2.Do not include, process, or consider any elements or fields present in the output XML that were not generated by the XSLT. These fields should be ignored entirely.
                                        3.If the elements generated by XSLT is not present in the provided output XML, remove it from the XSLT.
                                        4.The order of elements in the XML generated by the XSLT should should be strictly same as the output XML.Refine it accordingly
                                        5.Focus only on:
                                            Differences or errors in formatting between the fields produced by the XSLT and the corresponding fields in the output XML.
                                            Missing or Extra Delimiters.
                                            Determine if any field produced by the XSLT is empty. If so, investigate the cause.
                                            Check for potential namespace issues in XPath.
                                        6.If discrepancies are found, refine and regenerate the XSLT 1.0, ensuring that the following two lines of code are added at the start: {startCode}.
                                        7.If no issues or refinements are needed, return an empty string.
                                        Important:
                                            Don't alter the Parent of each Xpath in the XSLT code. Consider to change only if there is a way to combine all under a single parent.
                                            Generate code without assumptions or hypothetical scenarios.
                                            Ignore all fields and elements not generated by the XSLT. Do not process or modify these.
                                            The focus should be exclusively on fields that the XSLT itself generates.
                                            Ensure that the regenerated XSLT contains only those fields directly involved in the transformation process.'''
                                        }
            ]
    print("inside refine_internal xslt")
    gpt_response = get_chat_completion(prompt,o3_mini_model_name)
    show_stats(gpt_response)
    complete_response = gpt_response.__str__()
    print(f"COMPLETE_RESPONSE: {complete_response}")
    response = gpt_response.choices[0].message.content
    print(f"RESPONSE: {response}")
    return (response,complete_response)

def convert_md_to_html(response):
    # Headers for the table
    headers = ["Field", "Input XPATH", "Output XPATH", "Complexity", "M/C/O", "Description"]

    # Remove the long dashes
    data_values = [val.strip() for val in response.split("|")]
    data_values.pop(0)
    data_values = [val for idx, val in enumerate(data_values, 1) if idx % 7 != 0]
    print(data_values)

    # Build the HTML table
    html_table = '<table data-table-width="1800" data-layout="full-width"><tr>'
    for header in headers:
        html_table += f"<th><p>{header}</p></th>"
    html_table += "</tr>"

    # Add rows to the table
    for i in range(12, len(data_values), 6):
        html_table += "<tr>"
        for j in range(6):
            value = data_values[i + j] if i + j < len(data_values) else ""
            html_table += f"<td><p>{value}</p></td>"
        html_table += "</tr>"

    html_table += "</table>"

    return html_table

def upload_spec(mapping_specifications):
    system_prompts = []
    if mapping_specifications is not None:
        instr_prompt = {'role': 'user', 'content': "Here are the specification :\n" + mapping_specifications}
        system_prompts.append(instr_prompt)
    return system_prompts

def update_specs(final_msg,fields_ref):
    if compare_text(final_msg,fields_ref):
        return
    else:
        ##UPdate specs
        print("MarkdownSpec : " , st.session_state.markdown_spec)
        system_prompts = upload_spec(st.session_state.markdown_spec)
        user_instruction_prompt = {"role":"user", "content": f'''The user instruction is to update the mapping specification with this update:{final_msg} and return the entire mapping document with the update. Give the updated document in this format :
                                                                | Field                              | Input XPATH                                                                                                                                                            
                                                                                                                                                                  | Output XPATH                   | Complexity   | M/C/O   | Description                                                                                                                                                                                                                   
                                                                                                        |
                                                                |:-----------------------------------|:------------------------------------------------------------------------------------------|:-------------------------------|:-------------|:--------|:---------------------------------------------------|
                                                                | Product ID                         |                                                                                                                                                                                        
                                                                                                                                                                                                                | product_id                     | S            | M       | Hardcode it to 12347nsaljscacnlaa                                                                                                                                                                                                             
                                                                                        |
                                                                | Coverage start date                | /InsuranceSmartShoppingRequest/insurancePlanSection/itineraryInfo/segmentDetails/flightDate/departureDate                                                                              
                                                                                                                                                                                                                | coverage_start_date            | S            | M       | The day on which coverage begins, Build it in this format :2021-10-01 '''}
        system_prompts.append(user_instruction_prompt)
        with st.spinner('Refining Specs....'):
            llm_response = get_chat_completion(system_prompts)
            print(llm_response)
            if llm_response:
                response = llm_response.choices[0].message.content
                print("response datatype : ",type(response))
                print("UPdated specsss:   ", response)

                refined_md,VectorDocument_ref= refine_and_display_markdown(response)
                st.session_state.updated_specs = refined_md
                html = convert_md_to_html(response)
                space, page_name = extract_space_and_page_name(st.session_state.url)
                page_name = page_name.replace("+", " ")
                st.session_state.space,st.session_state.page_name,st.session_state.html = space,page_name,html
                #publish_content(space, page_name, html)

def llm_process(context, message, input_xml, transformed_xml, main_xslt):
    print("Inside LLM Process")
    hidden_LLM_response,complete_LLM_response,bot_message = question_from_user(context, message, input_xml, transformed_xml)                                      
    LLM_xslt = hidden_LLM_response
    # Use a regular expression to capture the XSLT content
    xslt_code = re.search(r"(<xsl:stylesheet[^>]*>.*?</xsl:stylesheet>)", hidden_LLM_response, re.DOTALL)
    if not main_xslt: #If no XSLT has been generated yet, then use the current XSLT as main_xslt
        main_xslt = xslt_code.group(1)
    else: #Combining the current XSLT with already generated XSLTs
        hidden_LLM_response,complete_LLM_response = combine_xslt_2(xslt_code.group(1),main_xslt)
        xslt_code_comb = re.search(r"(<xsl:stylesheet[^>]*>.*?</xsl:stylesheet>)", hidden_LLM_response, re.DOTALL)
        main_xslt = xslt_code_comb.group(1)
    hidden_LLM_prompt,complete_LLM_response = refine_internal(main_xslt,transformed_xml)
    ref_xslt_code = re.findall(r"(<xsl:stylesheet[^>]*>.*?</xsl:stylesheet>)", hidden_LLM_prompt, re.DOTALL)
    if ref_xslt_code:
        main_xslt = ref_xslt_code[-1]
    return main_xslt

def process_user_response(message, chat_history, input_xml, transformed_xml, main_xslt, specs):
    print("-----------")
    print(message)
    print(chat_history)
    user_request = False
    bot_message = ""
    valid_format = False
    # If message contain START then resets all previous conversations
    # and then confirm if the input and output XMLs has been uploaded successfully

    # If bot_message is empty, 
    #    either the current message is START and the prerequisites are met OR we are in an ongoing conversations.
    #      Ongoing conversations can be of 2 types: 
    #      1. Its a conversation that is yet to engage LLM or has already to engaged LLM, i.e. chat_history beginning with START
    #      2. It's not a conversation that that is ready to engage LLM, i.e. chat_history not beginning with START
    #            So we ask the user to START 
    if not bot_message and message:
        # if we have chat history, we are in an ongoing conversation
        if message.strip().upper() == "START":
            chat_history = []
            bot_message = verify_prerequisite(input_xml, transformed_xml)
            print("found Start, to do: " + bot_message)
        print(f"Chat length: {len(chat_history)}")
        if len(chat_history):
            # As we reset history with every START, 
            # we can verify the presence of START message as the 1st message in hostory 
            if chat_history[0][0].strip().upper() == "START":
                # START is present, verifying the prerequisites again as they are multiple
                bot_message = verify_prerequisite(input_xml, transformed_xml)
                if not bot_message:
                    previous_message_from_bot = chat_history[-1][1]
                    print("Prev Msg from Bot: ", previous_message_from_bot)
                    
                    if previous_message_from_bot.find("UPLOAD INPUT XML") != -1 and  previous_message_from_bot.find("UPLOAD OUTPUT XML") != -1:
                        # relevant conversation has just started and all the prerequisites are met.
                        # So initiate conversation_with_LLM
                        bot_message = "Please provide Input & Output XMLs"

                        #previous_qna.extend(LLM_readable_questions)
                    elif message.strip().upper() == "YES":
                        bot_message = "Please provide the fields to be refined?"

                    elif message.strip().upper() == "NO":
                        bot_message = "Thank you. Please refresh the page to begin again"

                    elif previous_message_from_bot.find("Please provide the fields to be refined?") != -1:
                        bot_message = "What needs to be refined here?"

                    elif previous_message_from_bot.find("What needs to be refined here?") != -1:
                        chromadb.api.client.SharedSystemClient.clear_system_cache()
                        with st.spinner('Refining XSLT, Thanks for your patience'):
                            #document = chromadb_setup(specs)
                            #refine_check = chat_history[-4][1]
                            #if refine_check != 'What needs to be refined here?':
                            print(specs)
                            query_engine_llm = query_eng_setup(specs)
                            prev_user_resp = chat_history[-1][0]
                            fields_ref = get_answer_llm(query_engine_llm,prev_user_resp)
                            fields_ref_str = str(fields_ref)
                            print(fields_ref)
                            final_msg = prev_user_resp + "-" + message
                            #response = get_answer_llm(query_engine_llm,final_msg)
                            res = str(final_msg)
                            print(res)
                            whole_msg = f'''These are the fields to be refined: {prev_user_resp}. This is their previous mapping instruction: {fields_ref}. 
                                                Now please check this message from user: {res}. Now modify the specified field or fields in XSLT accordingly'''
                            print("whole msg: ", whole_msg)
                            hidden_LLM_response,complete_LLM_response,bot_message  =  refine_external(whole_msg, input_xml, transformed_xml, main_xslt,chat_history)
                            xslt_code = re.search(r"(<xsl:stylesheet[^>]*>.*?</xsl:stylesheet>)", hidden_LLM_response, re.DOTALL)
                            main_xslt = xslt_code.group(1)
                            bot_message = "Both XSLT and Specs have been refined. Any Corrections?"
                            update_specs(final_msg,fields_ref_str)
                            st.session_state.ask_yes_no = True
                            user_request = True 
                
                    elif previous_message_from_bot.find("Please provide the URL of the specs") != -1 or previous_message_from_bot.find("Provide Valid URL") != -1:
                        with st.spinner('Processing URL, Thanks for your patience'):
                            space, page_name = extract_space_and_page_name(message)
                            st.session_state.url = message
                            page_name = page_name.replace("+", " ")
                            if space and page_name:
                                html_content = get_body(space, page_name)
                                if html_content:
                                    #output_placeholder_html.markdown(html_content, unsafe_allow_html=True)
                                    csv_data,dataFrame = convert_html_to_csv(html_content)
                                    markdown_table = dataFrame.to_markdown(index=False)
                                    print("Markdown file : ", markdown_table)
                                    st.session_state.markdown_spec = markdown_table
                                    
                                    if markdown_table:
                                        refined_markdown_content,VectorDocument = refine_and_display_markdown(markdown_table)
                                    st.session_state.existing_specs = refined_markdown_content
                                    valid_format = True
                                    st.session_state.specs_file = VectorDocument

                                else:
                                    st.info("Please upload a valid URL.")
                            else:
                                st.error("Invalid URL format")
                        if valid_format:
                            print("User Response : " , message)
                            batch_size = 8
                            batch_size_c = 4
                            s_rows,c_rows =  row_extraction(dataFrame)
                            with st.spinner('Generating XSLT, Thanks for your patience'):
                                for i in range(0,len(c_rows),batch_size_c):

                                    context = c_rows.iloc[i:i + batch_size_c]
                                    print(f"context {i // batch_size_c + 1}:")
                                    context_fields = ",".join(map(str, context["Field"]))
                                    print(f"Map all the elements mentioned here :{context_fields}")
                                    if not context_fields:
                                        continue
                                    message = f"Map all the elements mentioned here :{context_fields}"
                                    print(context)                                    
                                    
                                    main_xslt = llm_process(context, message, input_xml, transformed_xml, main_xslt)
                                    
                                for i in range(0, len(s_rows), batch_size):    
                                                                                          
                                    context = s_rows.iloc[i:i + batch_size]
                                    print(f"context {i // batch_size + 1}:")
                                    context_fields = ",".join(map(str, context["Field"]))
                                    print(f"Map all the elements mentioned here :{context_fields}")
                                    if not context_fields:
                                        continue
                                    message = f"Map all the elements mentioned here :{context_fields}"
                                    print(context)
                                    main_xslt = llm_process(context, message, input_xml, transformed_xml, main_xslt)                             
                                bot_message = "XSLT for your requested field has been generated. Do you want to refine?"
                                st.session_state.ask_yes_no = True
                                user_request = True
                                st.session_state.existing_xslt = main_xslt
                        else:
                            bot_message = "Provide Valid URL"

                    else:
                        bot_message = "Please be specific"

                        
            # When START is not present we ask the user to type START to begin 
            else:
                bot_message = "Type START to begin..."

        else:
            print("No history block")     
            # If we are in this else block it means, relevant conversation has just started and all the prerequisites are met.
            # So initiate conversation_with_LLM
            bot_message = verify_prerequisite(input_xml, transformed_xml)
            xslt_code = ""
            if not bot_message and message.strip().upper() == "START":
                bot_message = "Please provide the URL of the specs"

            else:
                bot_message = "Type START to begin..."


    chat_history.append((message, bot_message))
    return user_request,bot_message, chat_history, main_xslt
