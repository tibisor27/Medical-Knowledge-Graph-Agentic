"""Debug panel component"""

import streamlit as st
import json
from streamlit_app.components.message_display import (
    display_conversation_analysis,
    display_entity_info,
    display_retrieval_info,
    display_graph_results
)


def render_debug_panel():
    """Render comprehensive debug information panel"""
    
    if not st.session_state.last_query_details:
        st.info("🔍 No query details available yet. Ask a question to see debug information.")
        return
    
    st.header("🐛 Debug Panel")
    
    result = st.session_state.last_query_details
    
    # Create tabs for different debug sections
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Overview",
        "🧠 Analysis",
        "🔍 Entities",
        "🔧 Retrieval",
        "📊 Results"
    ])
    
    with tab1:
        render_overview_tab(result)
    
    with tab2:
        display_conversation_analysis(result)
    
    with tab3:
        display_entity_info(result)
    
    with tab4:
        display_retrieval_info(result)
    
    with tab5:
        display_graph_results(result)


def render_overview_tab(result: dict):
    """Render overview tab with key metrics"""
    
    st.subheader("Query Overview")
    
    # Execution path
    execution_path = result.get("execution_path", [])
    st.markdown("**Execution Path:**")
    st.code(" → ".join(execution_path) if execution_path else "No path recorded")
    
    # Status metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        has_results = result.get("has_results", False)
        st.metric("Has Results", "✅ Yes" if has_results else "❌ No")
    
    with col2:
        # Get retrieval type from analysis
        analysis = result.get("conversation_analysis")
        if analysis:
            if hasattr(analysis, 'retrieval_type'):
                r_type = str(analysis.retrieval_type.value) if hasattr(analysis.retrieval_type, 'value') else str(analysis.retrieval_type)
            else:
                r_type = analysis.get("retrieval_type", "N/A")
        else:
            r_type = "N/A"
        st.metric("Retrieval Type", r_type[:15] + "..." if len(r_type) > 15 else r_type)
    
    with col3:
        error = result.get("execution_error")
        st.metric("Errors", "❌ Yes" if error else "✅ None")
    
    # Error details
    if error:
        st.error(f"**Execution Error:** {error}")
    
    errors = result.get("errors", [])
    if errors:
        st.warning("**Additional Errors:**")
        for err in errors:
            st.markdown(f"- {err}")
    
    # Raw state (collapsible)
    with st.expander("🔬 Raw State (Advanced)", expanded=False):
        # Convert result to JSON-serializable format
        serializable_result = {}
        for key, value in result.items():
            try:
                # Test if value is JSON serializable
                json.dumps(value)
                serializable_result[key] = value
            except (TypeError, ValueError):
                # If not serializable, convert to string
                serializable_result[key] = str(value)
        
        st.json(serializable_result)
