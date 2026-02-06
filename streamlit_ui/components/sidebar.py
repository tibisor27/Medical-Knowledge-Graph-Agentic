"""Sidebar component"""

import streamlit as st
from streamlit_app.core.session_manager import clear_conversation, get_success_rate


def render_sidebar():
    """Render the sidebar with controls and information"""
    
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # Clear conversation button
        if st.button("🗑️ Clear Conversation", use_container_width=True):
            clear_conversation()
            st.rerun()
        
        st.markdown("---")
        
        # Display settings
        st.subheader("📊 Display Options")
        
        st.session_state.show_entities = st.checkbox(
            "Show extracted entities",
            value=st.session_state.show_entities,
            help="Display entities extracted from your queries"
        )
        
        st.session_state.show_cypher = st.checkbox(
            "Show Cypher queries",
            value=st.session_state.show_cypher,
            help="Display the generated Cypher database queries"
        )
        
        st.session_state.show_debug = st.checkbox(
            "Show debug panel",
            value=st.session_state.show_debug,
            help="Display detailed debug information"
        )
        
        st.markdown("---")
        
        # Statistics
        st.subheader("📈 Session Statistics")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Queries", st.session_state.total_queries)
        with col2:
            st.metric("Success Rate", f"{get_success_rate():.1f}%")
        
        st.metric("Messages", len(st.session_state.messages))
        
        st.markdown("---")
        
        # Information
        st.subheader("ℹ️ About")
        st.markdown("""
        This is a medical knowledge graph agent that can help you with:
        
        - 💊 **Medication information**
        - 🥗 **Nutrient depletion**
        - 🩺 **Symptom analysis**
        - 🔬 **Drug interactions**
        - 📚 **Scientific evidence**
        
        Ask questions in natural language!
        """)
        
        st.markdown("---")
        
        # Examples
        with st.expander("💡 Example Questions"):
            st.markdown("""
            - *What nutrients does Acetaminophen deplete?*
            - *I feel tired, what deficiency could I have?*
            - *What is Vitamin B12?*
            - *What medications deplete Zinc?*
            - *What are the symptoms of Magnesium deficiency?*
            """)
        
        # Disclaimer
        st.markdown("---")
        st.caption("⚠️ **Medical Disclaimer**: This is an educational tool. Always consult healthcare professionals for medical advice.")
