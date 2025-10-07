import json
import re
import streamlit as st
import xml.etree.ElementTree as ET
# from database.database_utils import configure_database

def has_answer(response_obj):
    if response_obj['generated_xslt'] != "":
        return True
    else:
        return False

def has_answer(response: str):
    response = re.sub(r'[\x00-\x1F\x7F]', '', response)
    response_obj = json.loads(response)
    if response_obj['generated_xslt'] != "":
        return True
    else:
        return False

def get_answer(response_obj):
    if response_obj:
        return response_obj['generated_xslt']

def get_answer(response: str):
    try:
        if response:
            response = re.sub(r'[\x00-\x1F\x7F]', '', response)
            response_obj = json.loads(response)
            return response_obj['generated_xslt']
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        st.error(f"Error processing response, please reload and try again:")        
        return None

def get_answer_md(response_obj):
    if response_obj:
        return response_obj['generated_md']

def get_answer_md(response: str):
    try:
        if response:
            response = re.sub(r'[\x00-\x1F\x7F]', '', response)
            response_obj = json.loads(response)
            return response_obj['generated_md']
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        st.error(f"Error processing response, please reload and try again:")        
        return None

def get_answer_html(response_obj):
    if response_obj:
        return response_obj['generated_html']

def get_answer_html(response: str):
    try:
        if response:
            response = re.sub(r'[\x00-\x1F\x7F]', '', response)
            response_obj = json.loads(response)
            return response_obj['generated_html']
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        st.error(f"Error processing response, please reload and try again:")        
        return None

def has_questions(response):
    if response:
        response = re.sub(r'[\x00-\x1F\x7F]', '', response)
        response_obj = json.loads(response)
        if len(response_obj['questions']) > 0:
            return True
        else:
            return False 

def has_questions(response_obj):
    if len(response_obj['questions']) > 0:
        return True
    else:
        return False
    
def update_live_activity(response, live_activity_log):
    print("Updating update_live_activity")
    for text in response:
        live_activity_log += f"\n {text}"
    return live_activity_log

def consolidating_questions(response: str):
    if response:
        response = re.sub(r'[\x00-\x1F\x7F]', '', response)
        response_obj = json.loads(response)
        if has_questions(response_obj):
            ques = []
            ques_string = ''
            count = 1
            if len(response_obj['questions']) > 0:
                for questions_set in response_obj['questions']:
                    ques.append(questions_set['question'])
                    ques_string += str(count) + "." + questions_set['question']
                    ques_string += '\n'
                    count += 1
                consolidated_ques = [ {"role": "assistant", "content": ques_string} ]
                return (True, consolidated_ques, ques)
        else:
            # ques = "[End the session]"
            # consolidated_ques = []
            consolidated_ques = [ {"role": "user", "content": "Verify and validate that XSLT is completely generated and if no more questions, respond with 'No more questions detected. Exiting the process.' and end the session. Do not ask any further questions."} ]
            return (False, consolidated_ques, None)


# def get_specifications_and_configure(input_file_name):
#     ndc_qna_collection = configure_database(input_file_name)
#     return ndc_qna_collection