import sqlite3
import os
from dotenv import load_dotenv, find_dotenv
from openai import AzureOpenAI as OpenAIAzureOpenAI
import httpx
import streamlit as st
from pathlib import Path
import time
import re

class SQLDatabaseUtils:
    def __init__(self, db_name="api_analysis.db", base_dir=None):
        """
        Initialize the SQLDatabaseUtils class.
        Args:
            db_name (str): The name of the SQLite database file.
            base_dir (str or Path, optional): The base directory where the DB is located.
        """
        self.db_name = db_name
        if base_dir is None:
            self.base_dir = Path(__file__).parent / "data"
        else:
            self.base_dir = Path(base_dir)
        self.db_path = self.base_dir / self.db_name

    def connect(self):
        """
        Connects to the SQLite database.
        Returns:
            sqlite3.Connection: SQLite connection object.
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database file not found: {self.db_path}")
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=100)
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def insert_data(self, table_name, values, columns=None, retries=2, delay=2):
        last_inserted_id = None
        for attempt in range(retries):
            try:
                conn = self.connect()
                cursor = conn.cursor()
                if columns:
                    columns_str = ", ".join(columns)
                    placeholders = ", ".join(["?"] * len(values))
                    query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
                else:
                    placeholders = ", ".join(["?"] * len(values))
                    query = f"INSERT INTO {table_name} VALUES ({placeholders})"
                cursor.execute(query, values)
                conn.commit()
                last_inserted_id = cursor.lastrowid
                break  # Exit the loop if successful
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    time.sleep(delay)
                else:
                    raise  # Raise other exceptions
            finally:
                cursor.close()
                conn.close()
        return last_inserted_id

    def execute_query(self, query, params=None):
        """
        Executes a query on the SQLite database.
        Args:
            query (str): The SQL query to execute.
            params (tuple, optional): Parameters for parameterized queries. Defaults to None.
        Returns:
            list: Query results as a list of tuples.
        """
        conn = self.connect()
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        results = cursor.fetchall()
        conn.commit()
        cursor.close()
        conn.close()
        return results

    def run_query(self, query, params=None):
        """
        Alias for execute_query for backward compatibility.
        """
        return self.execute_query(query, params)

    @staticmethod
    def print_results(results):
        """
        Prints the query results.
        Args:
            results (list): Query results as a list of tuples.
        """
        if results:
            for row in results:
                print(row)

    def search_in_database(self, element, selected_airlines=None):
        query = """
            SELECT a.api_name, COALESCE(av.version_number, 'N/A') as api_version, pd.pattern_description, pd.pattern_prompt
            FROM api a
            LEFT JOIN apiversion av ON a.api_id = av.api_id
            JOIN api_section aps ON a.api_id = aps.api_id
            JOIN section_pattern_mapping spm ON aps.section_id = spm.section_id AND aps.api_id = spm.api_id
            JOIN pattern_details pd ON spm.pattern_id = pd.pattern_id
            WHERE aps.section_display_name = ?
            GROUP BY a.api_name, av.version_number, pd.pattern_prompt
        """
        section_display_name = element
        results = self.run_query(query, (section_display_name,))
        return results

    def get_all_patterns(self):
        query = """
            SELECT a.api_name, COALESCE(av.version_number, 'N/A') as api_version, aps.section_name, pd.pattern_description, pd.pattern_prompt
            FROM api a
            LEFT JOIN apiversion av ON a.api_id = av.api_id
            JOIN api_section aps ON a.api_id = aps.api_id
            JOIN section_pattern_mapping spm ON aps.section_id = spm.section_id AND aps.api_id = spm.api_id
            JOIN pattern_details pd ON spm.pattern_id = pd.pattern_id
            GROUP BY a.api_name, av.version_number, pd.pattern_prompt
        """
        results = self.run_query(query)
        return results

    @staticmethod
    def list_main_elements(xml_text):
        elements = set()
        elements_dict = {}
        pattern = re.compile(r"^\s*<([^/?!][^ >]*)[^>]*?>")
        for i, line in enumerate(xml_text.split("\n")):
            search = pattern.search(line)
            if search:
                element = search.group(1)
                elements.add(element)
                elements_dict[element] = [i]
        return elements

    def print_table_data(self, table_name):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        conn.close()
        print(f"Data from {table_name}:")
        for row in rows:
            print(row)

    def create_apiversion_table(self):
        """
        Creates the apiversion table if it doesn't exist.
        """
        query = """
            CREATE TABLE IF NOT EXISTS apiversion (
                version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_id INTEGER NOT NULL,
                version_number TEXT NOT NULL,
                FOREIGN KEY (api_id) REFERENCES api(api_id),
                UNIQUE(api_id, version_number)
            )
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            print(f"Error creating apiversion table: {e}")
            return False

    def insert_api_version(self, api_id, version_number):
        """
        Inserts a new API version.
        Args:
            api_id (int): The API ID
            version_number (str): The version number (e.g., "17.2", "18.2")
        Returns:
            int: The version_id of the inserted record, or None if failed
        """
        return self.insert_data("apiversion", (api_id, version_number), 
                              columns=["api_id", "version_number"])

# For backward compatibility with existing imports
# _default_db_utils = SQLDatabaseUtils()
# get_all_patterns = _default_db_utils.get_all_patterns
# search_in_database = _default_db_utils.search_in_database
# list_main_elements = SQLDatabaseUtils.list_main_elements

# Print data from relevant tables

                    
# if __name__ == "__main__":
#     print_table_data("api_analysis.db", "api")
#     print_table_data("api_analysis.db", "api_section")
#     print_table_data("api_analysis.db", "section_pattern_mapping")
#     print_table_data("api_analysis.db", "pattern_details")
    # current_dir = Path(__file__).resolve().parent
    # file_path = current_dir / "../config/prompts/generic/default_system_prompt_for_gap_analysis.md"
    # with file_path.open() as file:
    #     prompt = file.read()
    # json_text = {
    #     "confirmation": "NO",
    #     "reason": "The XML does not contain a <PaxRefID> element inside the INF passenger's section. Therefore, it cannot be verified if the reference of an ADT passenger is correctly returned."
    # }
    # json_string = json.dumps(json_text)
    # # Load the JSON string into a Python object
    # response_obj_json = json.loads(json_string)
    # confirmation = response_obj_json.get('reason')
    
# if __name__ == "__main__":
#     os.chdir("/Users/nlepakshi/Documents/GitHub/genie/app/gap_analyser/data/")
#     conn = connect_to_db("api_analysis.db")
#     insert_data(conn, "api_section", (1, "hello_tag", "hello_tag"), columns=["api_id", "section_name", "section_display_name"])