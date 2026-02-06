"""Message display components"""

import streamlit as st
import json


def display_message(role: str, content: str):
    """Display a chat message with appropriate styling"""
    avatar = "👤" if role == "user" else "🤖"
    with st.chat_message(role, avatar=avatar):
        st.markdown(content)


def display_entity_info(result: dict):
    """Display extracted and resolved entities"""
    with st.expander("🔍 Extracted Entities", expanded=False):
        resolved = result.get("resolved_entities", [])
        unresolved = result.get("unresolved_entities", [])
        
        if resolved:
            st.markdown("**✅ Resolved Entities:**")
            for entity in resolved:
                # Handle both Pydantic models and dicts
                if hasattr(entity, 'original_text'):
                    original = entity.original_text
                    resolved_name = entity.resolved_name
                    node_type = entity.node_type
                    match_score = entity.match_score
                else:
                    original = entity.get("original_text", "N/A")
                    resolved_name = entity.get("resolved_name", "N/A")
                    node_type = entity.get("node_type", "N/A")
                    match_score = entity.get("match_score", 0)
                
                st.markdown(f"""
                - **{original}** → *{resolved_name}*
                  - Type: `{node_type}`
                  - Match Score: {match_score:.2f}
                """)
        else:
            st.info("No entities were resolved.")
        
        if unresolved:
            st.markdown("**❌ Unresolved Entities:**")
            for entity in unresolved:
                # Handle both Pydantic models and dicts
                if hasattr(entity, 'text'):
                    text = entity.text
                    entity_type = entity.type
                else:
                    text = entity.get("text", "N/A")
                    entity_type = entity.get("type", "N/A")
                st.markdown(f"- **{text}** (Type: `{entity_type}`)")


def display_retrieval_info(result: dict):
    """Display retrieval type information"""
    with st.expander("🔧 Retrieval Type", expanded=False):
        # Get retrieval type from conversation analysis
        analysis = result.get("conversation_analysis")
        
        if analysis:
            # Handle both Pydantic model and dict
            if hasattr(analysis, 'retrieval_type'):
                retrieval_type = str(analysis.retrieval_type.value) if hasattr(analysis.retrieval_type, 'value') else str(analysis.retrieval_type)
            else:
                retrieval_type = analysis.get("retrieval_type", "N/A")
            
            # Display retrieval type with icon
            type_icons = {
                "MEDICATION_LOOKUP": "💊",
                "SYMPTOM_INVESTIGATION": "🔍",
                "CONNECTION_VALIDATION": "🔗",
                "NUTRIENT_EDUCATION": "🥗",
                "NO_RETRIEVAL": "⏸️"
            }
            icon = type_icons.get(retrieval_type, "❓")
            st.markdown(f"### {icon} {retrieval_type}")
            
            # Add description
            type_descriptions = {
                "MEDICATION_LOOKUP": "Looking up medication information and its nutrient depletions.",
                "SYMPTOM_INVESTIGATION": "Investigating symptoms to find related nutrient deficiencies.",
                "CONNECTION_VALIDATION": "Validating connection between medication and symptoms.",
                "NUTRIENT_EDUCATION": "Providing educational information about nutrients.",
                "NO_RETRIEVAL": "No database query needed for this request."
            }
            description = type_descriptions.get(retrieval_type, "Unknown retrieval type.")
            st.info(description)
        else:
            st.info("No retrieval type information available.")


def display_graph_results(result: dict):
    """Display raw graph results"""
    with st.expander("📊 Graph Results", expanded=False):
        graph_results = result.get("graph_results", [])
        
        if graph_results:
            st.json(graph_results)
        else:
            st.info("No graph results available.")


def display_conversation_analysis(result: dict):
    """Display conversation analysis details"""
    with st.expander("🧠 Conversation Analysis", expanded=False):
        analysis = result.get("conversation_analysis")
        
        if analysis:
            # Handle both Pydantic models and dicts
            retrieval_type = getattr(analysis, 'retrieval_type', None) if hasattr(analysis, 'retrieval_type') else analysis.get('retrieval_type', 'N/A')
            has_sufficient = getattr(analysis, 'has_sufficient_info', False) if hasattr(analysis, 'has_sufficient_info') else analysis.get('has_sufficient_info', False)
            needs_clarif = getattr(analysis, 'needs_clarification', False) if hasattr(analysis, 'needs_clarification') else analysis.get('needs_clarification', False)
            
            st.markdown(f"**Retrieval Type:** `{retrieval_type}`")
            st.markdown(f"**Has Sufficient Info:** {has_sufficient}")
            st.markdown(f"**Needs Clarification:** {needs_clarif}")
            
            clarif_q = getattr(analysis, 'clarification_question', None) if hasattr(analysis, 'clarification_question') else analysis.get('clarification_question')
            if clarif_q:
                st.warning(f"**Clarification Question:** {clarif_q}")
            
            reasoning = getattr(analysis, 'step_by_step_reasoning', "") if hasattr(analysis, 'step_by_step_reasoning') else analysis.get('step_by_step_reasoning', "")
            if reasoning:
                st.markdown("**Reasoning:**")
                st.text_area("Analysis", reasoning, height=150, disabled=True)
            
            # Accumulated context
            st.markdown("**Accumulated Context:**")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                meds = getattr(analysis, 'accumulated_medications', []) if hasattr(analysis, 'accumulated_medications') else analysis.get('accumulated_medications', [])
                st.markdown(f"**Medications:** {len(meds)}")
                if meds:
                    for med in meds:
                        st.markdown(f"- {med}")
            
            with col2:
                symptoms = getattr(analysis, 'accumulated_symptoms', []) if hasattr(analysis, 'accumulated_symptoms') else analysis.get('accumulated_symptoms', [])
                st.markdown(f"**Symptoms:** {len(symptoms)}")
                if symptoms:
                    for symptom in symptoms:
                        st.markdown(f"- {symptom}")
            
            with col3:
                nutrients = getattr(analysis, 'accumulated_nutrients', []) if hasattr(analysis, 'accumulated_nutrients') else analysis.get('accumulated_nutrients', [])
                st.markdown(f"**Nutrients:** {len(nutrients)}")
                if nutrients:
                    for nutrient in nutrients:
                        st.markdown(f"- {nutrient}")
        else:
            st.info("No conversation analysis available.")
