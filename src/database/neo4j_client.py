from pathlib import Path
import os
from neo4j import GraphDatabase, RoutingControl
from dotenv import load_dotenv
from src.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, LLM_READER_USER, LLM_READER_PASSWORD

load_dotenv()

class Neo4jManager:
    def __init__(self):
        self._driver_admin = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self._driver_reader = GraphDatabase.driver(NEO4J_URI, auth=(LLM_READER_USER, LLM_READER_PASSWORD))

    def close(self):
        self._driver_admin.close()
        self._driver_reader.close()

    def run_safe_query(self, cypher_query, parameters=None):
        """
        Aceasta este funcția pe care o apelezi din LangGraph.
        Folosește DOAR driverul READER.
        
        Args:
            cypher_query: The Cypher query string
            parameters: Optional dictionary of query parameters
        """
        try:
            # Folosim execute_query (metoda modernă din Neo4j 5.x)
            records, _, _ = self._driver_reader.execute_query(
                cypher_query,
                parameters_=parameters,
                routing_=RoutingControl.READ
            )
            # Transformăm în JSON simplu pentru LLM
            return [r.data() for r in records]
            
        except Exception as e:
            # Aici prinzi eroarea dacă AI-ul a încercat să șteargă
            if "Forbidden" in str(e):
                return "SECURITY_BLOCK: AI attempted a write operation."
            return f"ERROR: {str(e)}"

    def run_admin_write(self, cypher_query, params=None):
        """
        Folosită când încarci PDF-uri sau modifici date manual.
        """
        self._driver_admin.execute_query(cypher_query, parameters_=params)


neo4j_client = Neo4jManager()

def get_neo4j_client()-> Neo4jManager:
    return neo4j_client
