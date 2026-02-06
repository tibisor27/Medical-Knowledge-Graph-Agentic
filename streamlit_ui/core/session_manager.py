import streamlit as st
from typing import List, Dict, Any
import uuid


def initialize_session_state():
    """Initialize all session state variables"""
    
    # Chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # API client session ID (persistent pentru fiecare utilizator)
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    
    # API client
    if "api_client" not in st.session_state:
        from streamlit_app.core.api_client import get_api_client
        st.session_state.api_client = get_api_client(st.session_state.session_id)
    
    # UI settings
    if "show_debug" not in st.session_state:
        st.session_state.show_debug = False
    
    if "show_entities" not in st.session_state:
        st.session_state.show_entities = False
    
    if "show_cypher" not in st.session_state:
        st.session_state.show_cypher = False
    
    # Statistics
    if "total_queries" not in st.session_state:
        st.session_state.total_queries = 0
    
    if "successful_queries" not in st.session_state:
        st.session_state.successful_queries = 0
    
    # Last query details
    if "last_query_details" not in st.session_state:
        st.session_state.last_query_details = None


def add_message(role: str, content: str):
    """Add a message to the chat history"""
    st.session_state.messages.append({"role": role, "content": content})


def clear_conversation():
    """Clear all conversation history"""
    st.session_state.messages = []
    
    # Clear history prin API
    if "api_client" in st.session_state:
        st.session_state.api_client.clear_history()
    
    st.session_state.total_queries = 0
    st.session_state.successful_queries = 0
    st.session_state.last_query_details = None


def update_statistics(success: bool = True):
    """Update query statistics"""
    st.session_state.total_queries += 1
    if success:
        st.session_state.successful_queries += 1


def get_success_rate() -> float:
    """Calculate success rate percentage"""
    if st.session_state.total_queries == 0:
        return 0.0
    return (st.session_state.successful_queries / st.session_state.total_queries) * 100
