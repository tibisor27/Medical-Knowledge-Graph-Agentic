"""
Agent State Definition for Medical Knowledge Graph Agent.

This module defines the state that flows through the LangGraph workflow.
The state accumulates information as it passes through each node.
"""

from typing import TypedDict, Optional, List, Dict, Any, Literal
from typing_extensions import Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════════════════════════════
# Cypher Generator Response Types
# ═══════════════════════════════════════════════════════════════════════════════

class CypherGeneratorResponse(BaseModel):
    cypher: str = Field(..., description="The Cypher query to execute.")
    params: Dict[str, Any] = Field(default_factory=dict, description="The parameters for the query.")
    reasoning: str = Field(default="", description="The reasoning behind the Cypher query.")
    error: Optional[str] = Field(None, description="The error message if the Cypher query is invalid.")

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
    step_by_step_reasoning: str = Field(description="A detailed analysis of the conversation context, pronoun resolution, and entity accumulation logic.")
    detected_intent: VALID_INTENTS = Field( ..., description="The classification of the user's goal.") 
    has_sufficient_info: bool = Field(..., description="Set to True ONLY if we have both the intent and the necessary entities (e.g., a specific drug name) to perform a database query.")  
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

import json

def print_state_debug(state):
    print("\n" + "="*80)
    # 0. Execution Path (Mereu util de văzut)
    if state.get('execution_path'):
        print(f"----> NODE EXECUTION PATH: {state.get('execution_path')}")
    print("="*80)

    # 1. Istoric și Mesaj (Dacă există)
    if state.get('conversation_history'):
        # Presupunem că ai funcția format_conversation_history_for_analysis definită undeva
        print(f"\n----> CONVERSATION HISTORY:\n{format_conversation_history_for_analysis(state.get('conversation_history'))}")
    
    if state.get('user_message'):
        print(f"\n----> USER MESSAGE: {state.get('user_message')}")

    # 2. Analiza Conversației (Pydantic Model)
    if state.get('conversation_analysis'):
        anal = state['conversation_analysis']
        print_analysis_debug(anal)

    # 3. ENTITĂȚI (Extracted, Resolved, Unresolved)
    # 3a. Extracted
    if state.get('extracted_entities'):
        print(f"\n----> EXTRACTED ENTITIES ({len(state['extracted_entities'])}):")
        for ent in state['extracted_entities']:
            # Ajustează accesarea (ent.text sau ent['text']) în funcție de structura ExtractedEntity
            print(f"   - {ent}") 

    # 3b. Resolved (Tabelul tău frumos)
    if state.get('resolved_entities'):
        print(f"\n----> RESOLVED ENTITIES ({len(state['resolved_entities'])}):")
        print(f"   {'ORIGINAL':<20} | {'RESOLVED':<20} | {'TYPE':<10} | {'SCORE'}")
        print("   " + "-"*65)
        for ent in state['resolved_entities']:
            # Verificăm dacă e obiect sau dict pentru siguranță
            orig = ent.original_text if hasattr(ent, 'original_text') else ent.get('original_text', '')
            res = ent.resolved_name if hasattr(ent, 'resolved_name') else ent.get('resolved_name', '')
            typ = ent.node_type if hasattr(ent, 'node_type') else ent.get('node_type', '')
            score = ent.match_score if hasattr(ent, 'match_score') else ent.get('match_score', 0)
            print(f"   {orig:<20} | {res:<20} | {typ:<10} | {score:.2f}")

    # 3c. Unresolved
    if state.get('unresolved_entities'):
        print(f"\n----> UNRESOLVED ENTITIES ({len(state['unresolved_entities'])}):")
        for ent in state['unresolved_entities']:
            print(f"   - {ent}")

    # 4. CYPHER & DATABASE (Query, Params, Reasoning)
    if state.get('generated_cypher'):
        print("\n----> CYPHER QUERY:")
        print(state['generated_cypher'])
    
    if state.get('cypher_params'):
        print(f"\n----> CYPHER PARAMS: {state['cypher_params']}")

    if state.get('cypher_reasoning'):
        print(f"\n----> CYPHER REASONING: {state['cypher_reasoning']}")

    # Verificăm explicit cheile booleene (pentru că False este o valoare validă pe care vrem să o vedem)
    if 'cypher_is_valid' in state:
        valid_icon = "✅" if state['cypher_is_valid'] else "❌"
        print(f"\n----> CYPHER VALID: {valid_icon} (Retry count: {state.get('cypher_retry_count', 0)})")
        
    if state.get('cypher_errors'):
        print(f"\n----> CYPHER SYNTAX ERRORS:\n   {state['cypher_errors']}")

    # 5. REZULTATE GRAF
    if state.get('has_results') and state.get('graph_results'):
        results = state['graph_results']
        print(f"\n----> GRAPH RESULTS ({len(results)} records):")
        # Afișăm doar primele 2-3 rezultate să nu umplem consola, sau tot dacă e mic
        preview = json.dumps(results[:2], indent=2, default=str)
        print(preview)
        if len(results) > 2:
            print(f"   ... and {len(results)-2} more records.")
    elif 'has_results' in state and not state['has_results']:
        print("\n----> GRAPH RESULTS: No data found.")

    # 6. ERORI GENERALE & RĂSPUNS FINAL
    if state.get('execution_error'):
        print(f"\n----> EXECUTION ERROR: {state['execution_error']}")
    
    if state.get('errors'):
        print(f"\n----> OTHER ERRORS: {state['errors']}")

    if state.get('final_response'):
        print("\n----> FINAL RESPONSE:")
        print(f"   {state['final_response']}")

    print("="*80 + "\n")

from typing import List, Optional
# Asigură-te că ai importat clasa ConversationAnalysis

def print_analysis_debug(analysis: ConversationAnalysis):

    if not analysis:
        print("----> CONVERSATION ANALYSIS: None")
        return

    print("\n" + "="*60)
    
    print("----> CONVERSATION ANALYSIS:")
    print(f"   • Step by Step Reasoning: {analysis.step_by_step_reasoning}")
    print(f"   • Intent: {analysis.detected_intent}")
    print(f"   • Sufficient Info: {analysis.has_sufficient_info}")
    print(f"   • Needs Clarification: {analysis.needs_clarification}")
    print(f"   • Accumulated Meds: {analysis.accumulated_medications}")
    print(f"   • Accumulated Symptoms: {analysis.accumulated_symptoms}")
    print(f"   • Accumulated Nutrients: {analysis.accumulated_nutrients}")
    print("="*60 + "\n")


def format_conversation_history_for_analysis(messages: list) -> str:
    """Format conversation history for the analyzer prompt."""
    if not messages:
        return "No previous conversation."
    
    formatted = []
    # Exclude the last message (it's the current one we're analyzing)
    history_messages = messages
    
    for msg in history_messages[-10:]:  # Last 10 messages from history
        if isinstance(msg, HumanMessage):
            formatted.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            # Truncate long assistant responses
            content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
            formatted.append(f"Assistant: {content}")
        elif isinstance(msg, dict):
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")[:500] 
            formatted.append(f"{role}: {content}")
    
    return "\n".join(formatted) if formatted else "No previous conversation."
