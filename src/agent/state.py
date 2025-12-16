"""
Agent State Definition for Medical Knowledge Graph Agent.

This module defines the state that flows through the LangGraph workflow.
The state accumulates information as it passes through each node.
"""

from typing import TypedDict, Optional, List, Dict, Any, Literal
from typing_extensions import Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
# ENTITY TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class ExtractedEntity(BaseModel):
    """An entity extracted from the user's query."""
    text: str                    # Original text from query ("Tylenol")
    type: str                    # Entity type: MEDICATION, NUTRIENT, SYMPTOM, DRUG_CLASS, CONDITION
    confidence: float            # Extraction confidence (0.0 - 1.0)


class ResolvedEntity(BaseModel):
    """An entity that has been matched to a node in the knowledge graph."""
    original_text: str           # Original text from query ("Tylenol")
    resolved_name: str           # Canonical name in graph ("Acetaminophen")
    node_type: str               # Neo4j label: Medicament, Nutrient, Symptom
    match_score: float           # Full-text search score
    match_method: str            # How it was matched: "exact", "fulltext", "synonym", "brand_name"

class EntityExtractionResponse(BaseModel):
    entities: List[ExtractedEntity]

# ═══════════════════════════════════════════════════════════════════════════════
# INTENT TYPES
# ═══════════════════════════════════════════════════════════════════════════════

# All possible user intents
VALID_INTENTS = Literal[
    "DRUG_DEPLETES_NUTRIENT",    # "Ce nutrienți depletează Acetaminophen?"
    "NUTRIENT_DEPLETED_BY",      # "Ce medicamente depletează Vitamina B12?"
    "SYMPTOM_TO_DEFICIENCY",     # "Mă simt obosit, ce deficit pot avea?"
    "DRUG_INFO",                 # "Ce este Tylenol?"
    "NUTRIENT_INFO",             # "Ce face Glutathione în organism?"
    "DEFICIENCY_SYMPTOMS",       # "Ce simptome are deficitul de Zinc?"
    "FOOD_SOURCES",              # "Unde găsesc Vitamina B12?"
    "EVIDENCE_LOOKUP",           # "Ce studii există despre Acetaminophen?"
    "GENERAL_MEDICAL",           # General medical question
    "NEEDS_CLARIFICATION",       # Can't determine intent
    "OFF_TOPIC"                  # Not medical related
]

# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSATION ANALYSIS TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class ConversationAnalysis(BaseModel):
    has_sufficient_info: bool = Field(..., description="Set to True ONLY if we have both the intent and the necessary entities (e.g., a specific drug name) to perform a database query.")  
    detected_intent: VALID_INTENTS = Field( ..., description="The classification of the user's goal.") 
    needs_clarification: bool = Field(..., description="Set to True if the user mentions symptoms but hasn't specified a medication, or if the drug name is ambiguous/unknown.")
    clarification_question: Optional[str] = Field(None, description="A polite follow-up question to ask the user if clarification is needed. Return None (null) if everything is clear.")
    accumulated_medications: List[str] = Field(default_factory=list, description="A list of ALL medication names mentioned anywhere in the conversation history, not just the last message.")
    accumulated_symptoms: List[str] = Field(default_factory=list, description="A list of ALL symptoms or conditions described by the user throughout the entire chat history.") 
    accumulated_nutrients: List[str] = Field(default_factory=list, description="A list of ALL vitamins, minerals, or supplements mentioned throughout the entire chat history.")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN AGENT STATE
# ═══════════════════════════════════════════════════════════════════════════════

class MedicalAgentState(TypedDict):
    user_message: str
    conversation_history: Annotated[List[BaseMessage], add_messages]
    conversation_analysis: Optional[ConversationAnalysis]
    extracted_entities: List[ExtractedEntity]
    resolved_entities: List[ResolvedEntity]
    unresolved_entities: List[ExtractedEntity]
    generated_cypher: str
    cypher_params: Dict[str, Any]
    cypher_reasoning: str
    cypher_is_valid: bool
    cypher_errors: List[str]
    cypher_retry_count: int
    graph_results: List[Dict[str, Any]]
    has_results: bool
    execution_error: Optional[str]
    final_response: str
    execution_path: List[str]
    errors: List[str]

# ═══════════════════════════════════════════════════════════════════════════════
# STATE FACTORY FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def create_initial_state(user_message: str, conversation_history: List[BaseMessage] = None) -> MedicalAgentState:
    return MedicalAgentState(
        # Input
        user_message=user_message,
        conversation_history=conversation_history or [],
        
        # Conversation Analyzer
        conversation_analysis=None,
        
        # Entity Extractor
        extracted_entities=[],
        resolved_entities=[],
        unresolved_entities=[],
        
        # Cypher Generator
        generated_cypher="",
        cypher_params={},
        cypher_reasoning="",
        cypher_is_valid=False,
        cypher_errors=[],
        cypher_retry_count=0,
        
        # Graph Executor
        graph_results=[],
        has_results=False,
        execution_error=None,
        
        # Response Synthesizer
        final_response="",
        
        # Metadata
        execution_path=[],
        errors=[]
    )


# ═══════════════════════════════════════════════════════════════════════════════
# STATE UPDATE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def add_to_execution_path(state: MedicalAgentState, node_name: str) -> List[str]:
    """Add a node to the execution path."""
    return state.get("execution_path", []) + [node_name]


def add_error(state: MedicalAgentState, error: str) -> List[str]:
    """Add an error to the errors list."""
    return state.get("errors", []) + [error]
