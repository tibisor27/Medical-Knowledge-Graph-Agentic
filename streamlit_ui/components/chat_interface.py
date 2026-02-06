"""Main chat interface component"""

import streamlit as st
from streamlit_app.core.session_manager import add_message, update_statistics
from streamlit_app.components.message_display import display_message, display_entity_info, display_retrieval_info
import time


def render_chat_interface():
    """Render the main chat interface"""
    
    # Display existing messages
    for message in st.session_state.messages:
        display_message(message["role"], message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask a medical question... (e.g., What nutrients does Acetaminophen deplete?)"):
        # Display user message
        display_message("user", prompt)
        add_message("user", prompt)
        
        # Get agent response
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("🔍 Analyzing your question..."):
                try:
                    # Call API instead of direct agent
                    api_client = st.session_state.api_client
                    
                    # Get response from API
                    api_response = api_client.chat(
                        message=prompt,
                        return_details=True  # Get full details for display
                    )
                    
                    # Extract response and details
                    response = api_response.get("response", "Sorry, I couldn't process your request.")
                    details = api_response.get("details", {})
                    
                    # Store query details for debug panel
                    st.session_state.last_query_details = details
                    
                    # Display response
                    st.markdown(response)
                    
                    # Add to message history
                    add_message("assistant", response)
                    
                    # Update statistics
                    update_statistics(success=True)
                    
                    # Show additional information if enabled
                    if st.session_state.show_entities or st.session_state.show_cypher:
                        st.markdown("---")
                    
                    # Display entities if enabled
                    if st.session_state.show_entities and details:
                        display_entity_info(details)
                    
                    # Display Retrieval Type if enabled
                    if st.session_state.show_cypher and details:
                        display_retrieval_info(details)
                    
                except Exception as e:
                    error_msg = f"❌ An error occurred: {str(e)}"
                    st.error(error_msg)
                    add_message("assistant", error_msg)
                    update_statistics(success=False)
        
        # Rerun to update the interface
        st.rerun()
    
    # Show welcome message if no messages yet
    if len(st.session_state.messages) == 0:
        render_welcome_message()


def render_welcome_message():
    """Display welcome message when chat is empty"""
    st.markdown("""
    <div class="info-box">
        <h3>👋 Welcome to the Medical Knowledge Graph Agent!</h3>
        <p>I can help you with medical information about:</p>
        <ul>
            <li>💊 Medications and their effects</li>
            <li>🥗 Nutrient depletions caused by drugs</li>
            <li>🩺 Symptoms and potential deficiencies</li>
            <li>🔬 Drug interactions and pharmacology</li>
        </ul>
        <p><strong>Try asking:</strong></p>
        <ul>
            <li>"What nutrients does Acetaminophen deplete?"</li>
            <li>"I feel tired, what deficiency could I have?"</li>
            <li>"What is Vitamin B12?"</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
