"""
Medical Agent Module - LangGraph ReAct Agent.

Main exports:
- LangGraphMedicalSession: Session-based chat interface
- get_all_tools: Get all available tools for the agent
"""

from src.agent.langgraph_agent import (
    LangGraphMedicalSession,
    MedicalChatSession,  # Backward compatibility alias
    AgenticMedicalSession,  # Backward compatibility alias
    create_medical_agent,
    get_medical_agent,
)

from src.agent.tools_native import (
    get_all_tools,
    medication_lookup,
    symptom_investigation,
    connection_validation,
    nutrient_education,
    product_recommendation,
)

__all__ = [
    # Main session interface
    "LangGraphMedicalSession",
    "MedicalChatSession",
    "AgenticMedicalSession",
    
    # Agent factory
    "create_medical_agent",
    "get_medical_agent",
    
    # Tools
    "get_all_tools",
    "medication_lookup",
    "symptom_investigation", 
    "connection_validation",
    "nutrient_education",
    "product_recommendation",
]
