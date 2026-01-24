from typing import List, Dict, Any, Optional, Annotated
from typing_extensions import TypedDict, Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field
from enum import Enum
import json
# ═══════════════════════════════════════════════════════════════════════════════
# ENTITY TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class ResolvedEntity(BaseModel):    
    original_text: str           
    resolved_name: str           
    node_type: str               
    match_score: float          
    match_method: str           

# ═══════════════════════════════════════════════════════════════════════════════
# INTENT & RETRIEVAL TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class RetrievalType(str, Enum):
    """What type of Cypher query to perform"""
    MEDICATION_LOOKUP = "MEDICATION_LOOKUP"
    SYMPTOM_INVESTIGATION = "SYMPTOM_INVESTIGATION"
    CONNECTION_VALIDATION = "CONNECTION_VALIDATION"
    NUTRIENT_EDUCATION = "NUTRIENT_EDUCATION"
    PRODUCT_RECOMMENDATION = "PRODUCT_RECOMMENDATION"
    NO_RETRIEVAL = "NO_RETRIEVAL"

# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSATION ANALYSIS TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class ConversationAnalysis(BaseModel):
    step_by_step_reasoning: str = Field(description="A detailed analysis of the conversation context, pronoun resolution, and entity accumulation logic.")
    has_sufficient_info: bool = Field(..., description="Set to True ONLY if we have both the intent and the necessary entities (e.g., a specific drug name) to perform a database query.") 
    retrieval_type: RetrievalType = Field(..., description="The type of retrieval to perform.")
    needs_clarification: bool = Field(..., description="Set to True if the user mentions symptoms but hasn't specified a medication, or if the drug name is ambiguous/unknown.")
    clarification_question: Optional[str] = Field(None, description="A polite follow-up question to ask the user if clarification is needed. Return None (null) if everything is clear.")
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # ACCUMULATED ENTITIES - toate entitățile din întreaga conversație
    # ═══════════════════════════════════════════════════════════════════════════════
    accumulated_medications: List[str] = Field(default_factory=list, description="A list of ALL medication names mentioned anywhere in the conversation history, not just the last message.")
    accumulated_symptoms: List[str] = Field(default_factory=list, description="A list of ALL symptoms or conditions described by the user throughout the entire chat history.") 
    accumulated_nutrients: List[str] = Field(default_factory=list, description="A list of ALL vitamins, minerals, or supplements mentioned throughout the entire chat history.")
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # QUERY ENTITIES - entitățile SPECIFICE pentru acest retrieval
    # IMPORTANT: Acestea sunt entitățile care trebuie folosite în Cypher query
    # ═══════════════════════════════════════════════════════════════════════════════
    query_medications: List[str] = Field(default_factory=list, description="The SPECIFIC medications to use in this query. For MEDICATION_LOOKUP: the new medication. For CONNECTION_VALIDATION: medication(s) to check against symptoms.")
    query_symptoms: List[str] = Field(default_factory=list, description="The SPECIFIC symptoms to use in this query. For SYMPTOM_INVESTIGATION: the symptom(s) to investigate. For CONNECTION_VALIDATION: symptom(s) to validate against medication.")
    query_nutrients: List[str] = Field(default_factory=list, description="The SPECIFIC nutrients to use in this query. For NUTRIENT_EDUCATION: the nutrient to explain. For PRODUCT_RECOMMENDATION: nutrients to find products for.")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN AGENT STATE
# ═══════════════════════════════════════════════════════════════════════════════

class MedicalAgentState(TypedDict):
    # Input
    user_message: str
    conversation_history: Annotated[List[BaseMessage], add_messages]

    # Analysis
    conversation_analysis: Optional[ConversationAnalysis]

    persisted_medications: List[str]   # Medicamente confirmate de user
    persisted_symptoms: List[str]      # Simptome raportate de user
    persisted_nutrients: List[str]     # Nutrienți identificați ca deficitari

    # Entities (per-turn, de la entity_extractor)
    resolved_entities: List[ResolvedEntity]
    
    # Graph Results
    graph_results: List[Dict[str, Any]]
    has_results: bool
    execution_error: Optional[str]

    # Outputs
    final_response: str
    execution_path: List[str]
    errors: List[str]

# ═══════════════════════════════════════════════════════════════════════════════
# STATE FACTORY FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def create_initial_state(
    user_message: str, 
    conversation_history: List[BaseMessage] = None,
    # Entități persistente de la turn-ul anterior
    persisted_medications: List[str] = None,
    persisted_symptoms: List[str] = None,
    persisted_nutrients: List[str] = None
) -> MedicalAgentState:

    return MedicalAgentState(
        # Input
        user_message=user_message,
        conversation_history=conversation_history or [],
        
        # Conversation Analyzer
        conversation_analysis=None,
        
        # Persisted Entities (previous turns)
        persisted_medications=persisted_medications or [],
        persisted_symptoms=persisted_symptoms or [],
        persisted_nutrients=persisted_nutrients or [],
        
        resolved_entities=[],
        
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


def print_state_execution_path(state: MedicalAgentState):
    if state.get('execution_path'):
        print(f"\n----> EXECUTION PATH: {state.get('execution_path')}\n")
