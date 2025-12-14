from typing import TypedDict, Optional, Literalm

class ExtractedEntity(TypedDict):
    text: str
    type: str
    confidence: float

class ExtractedSymptoms(BaseModel):
    canonical_name: str
    layman_variants: list[str]

class ExtractedSymptomsResult(BaseModel):
    symptoms: list[ExtractedSymptoms]
        
class AgentState(TypedDict):
    
    user_query: str
    is_valid_query: bool
    conversation_history: Annotated[Sequence[BaseMessage], add_messages]
    rewritten_query: str
    extracted_entities: list[ExtractedEntity]
    generated_cypher: str
    cypher_is_valid: bool
    cypher_errors: list[str]
    cypher_retry_count: int
    llm_response: str
    generated_cypher: str
    cypher_params: dict
    cypher_reasoning: str
    cypher_is_valid: bool



    # """Whether the generated Cypher passed validation."""
    
    # cypher_errors: list[str]
    # """Validation errors, if any."""
    
    # cypher_retry_count: int
    # """Number of times Cypher generation has been retried."""
    
    # # ═══════════════════════════════════════════════════════════════════════════
    # # GRAPH EXECUTOR NODE
    # # ═══════════════════════════════════════════════════════════════════════════
    
    # graph_results: list[dict]
    # """Raw results from the Neo4j query."""
    
    # has_results: bool
    # """Whether the query returned any results."""
    
    # execution_error: Optional[str]
    # """Error message if query execution failed."""
    
    # # ═══════════════════════════════════════════════════════════════════════════
    # # RESPONSE GENERATOR NODE
    # # ═══════════════════════════════════════════════════════════════════════════
    
    # final_response: str
    # """The final response to send to the user."""
    
    # follow_up_questions: list[str]
    # """Suggested follow-up questions."""
    
    # # ═══════════════════════════════════════════════════════════════════════════
    # # CLARIFICATION (used when we need more info from user)
    # # ═══════════════════════════════════════════════════════════════════════════
    
    # needs_clarification: bool
    # """Whether we need to ask the user for clarification."""
    
    # clarification_question: str
    # """The question to ask the user."""
    
    # # ═══════════════════════════════════════════════════════════════════════════
    # # METADATA (for debugging and monitoring)
    # # ═══════════════════════════════════════════════════════════════════════════
    
    # execution_path: list[str]
    # """List of nodes that were executed, in order."""
    
    # total_llm_calls: int
    # """Total number of LLM calls made."""
    
    # errors: list[str]
    # """Any errors that occurred during execution."""


def create_initial_state(user_query: str, conversation_history: list[dict] = None) -> AgentState:
    """
    Create the initial state for a new agent run.
    
    Args:
        user_query: The user's question
        conversation_history: Previous messages in the conversation
        
    Returns:
        Initial AgentState with defaults set
    """
    return AgentState(
        # Input
        user_query=user_query,
        conversation_history=conversation_history or [],
        
        # Guardrails
        is_valid_query=True,
        
        # Query Rewriter
        rewritten_query="",
        
        # Entity Extractor
        extracted_entities=[],
        
        # Cypher Generator
        generated_cypher="",        
        cypher_is_valid=False,
        cypher_errors=[],
        cypher_retry_count=0,        
        llm_response="",
    )

