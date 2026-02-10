import json
from typing import Dict, Any
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
import logging
from langchain_core.prompts import ChatPromptTemplate
from src.agent.react_tools import ALL_TOOLS
from src.prompts.react_agent_prompt import REACT_SYSTEM_PROMPT
from src.utils.get_llm import get_llm_4_1_mini
from src.utils.langfuse_client import get_langfuse_handler, get_prompt_from_langfuse
from langfuse import observe, propagate_attributes
from pprint import pprint
logger = logging.getLogger(__name__)
 
AGENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", REACT_SYSTEM_PROMPT),
])
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# ReAct AGENT FACTORY
# ═══════════════════════════════════════════════════════════════════════════════
 
_compiled_agent = None
 
 
def create_medical_react_agent():
    """Create ReAct agent with medical tools."""
    llm = get_llm_4_1_mini()
   
    agent = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
    )
   
    return agent
 
 
def get_medical_agent():
    """Get or create the singleton ReAct agent."""
    global _compiled_agent
    if _compiled_agent is None:
        _compiled_agent = create_medical_react_agent()
    return _compiled_agent
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# SUPERVISOR: Session Management + Context Injection
# ═══════════════════════════════════════════════════════════════════════════════
 
class MedicalChatSession:
    """
    Thin supervisor layer that:
    1. Manages conversation history across turns
    2. Tracks confirmed medications/symptoms/nutrients
    3. Injects user context into system prompt
    4. Invokes the ReAct agent
    """
   
    def __init__(self, session_id: str = None):
        self.history: list = []
        self.medications: list = []
        self.symptoms: list = []
        self.nutrients: list = []
        self.session_id = session_id
   
    def chat(self, user_message: str) -> str:
        """Simple chat interface - returns response string."""
        result = self.run_medical_query(user_message)
        return result.get("final_response", "Sorry, I couldn't process your request.")
   
    @observe()
    def run_medical_query(self, user_message: str) -> Dict[str, Any]:
        """
        Main entry point. Builds context, invokes ReAct agent, updates state.
        """
        with propagate_attributes(
            session_id=self.session_id,
            user_id=self.session_id or "anonymous"
        ):
            langfuse_handler = get_langfuse_handler()
           
            # ═══════════════════════════════════════════════════════════════
            # 1. BUILD SYSTEM PROMPT WITH CONTEXT
            # ═══════════════════════════════════════════════════════════════
            user_context = self._build_user_context()
            system_prompt_text = self._get_system_prompt(user_context)
           
            # ═══════════════════════════════════════════════════════════════
            # 2. BUILD MESSAGES (system + history + new user message)
            # ═══════════════════════════════════════════════════════════════
            messages = [SystemMessage(content=system_prompt_text)]
 
           
            # Add conversation history (previous turns only - Human/AI pairs)
            for msg in self.history:
                messages.append(msg)
           
            # Add current user message
            messages.append(HumanMessage(content=user_message))
           
            # ═══════════════════════════════════════════════════════════════
            # 3. INVOKE ReAct AGENT
            # ═══════════════════════════════════════════════════════════════
            agent = get_medical_agent()
           
            logger.info(f"[Session {self.session_id}] Invoking ReAct agent")
            logger.info(f"  Context: meds={self.medications}, symptoms={self.symptoms}, nuts={self.nutrients}")
           
            try:
                result = agent.invoke(
                    {"messages": messages},
                    config={
                        "callbacks": [langfuse_handler],
                        "recursion_limit": 15
                    }
                )
               
                # Extract the final AI response
                final_response = self._extract_final_response(result)
                pprint("=== ReAct Agent Result ===")
                pprint(result)
                tool_calls = self._extract_tool_calls(result)
 
               
                # ═══════════════════════════════════════════════════════════
                # 4. UPDATE SESSION STATE
                # ═══════════════════════════════════════════════════════════
                self._update_history(user_message, final_response)
                self._extract_entities_from_tools(result)
               
                logger.info(f"[Session {self.session_id}] Response generated successfully")
                logger.info(f"  Tools called: {[tc['tool'] for tc in tool_calls]}")
                logger.info(f"  Updated: meds={self.medications}, symptoms={self.symptoms}, nuts={self.nutrients}")
               
                return {
                    "final_response": final_response,
                    "execution_path": ["react_agent"],
                    "errors": [],
                    "tool_calls": tool_calls
                }
               
            except Exception as e:
                logger.error(f"ReAct agent error: {str(e)}", exc_info=True)
                error_response = "I'm sorry, I encountered an error processing your request. Could you please try again?"
                self._update_history(user_message, error_response)
               
                return {
                    "final_response": error_response,
                    "execution_path": ["react_agent_error"],
                    "errors": [str(e)]
                }
   
    # ═══════════════════════════════════════════════════════════════════════════
    # CONTEXT BUILDING
    # ═══════════════════════════════════════════════════════════════════════════
   
    def _build_user_context(self) -> str:
        """Build the context string injected into system prompt."""
        parts = []
       
        if self.medications:
            parts.append(f"Medications user takes: {', '.join(self.medications)}")
        else:
            parts.append("Medications: None confirmed yet")
       
        if self.symptoms:
            parts.append(f"Symptoms user reported: {', '.join(self.symptoms)}")
        else:
            parts.append("Symptoms: None reported yet")
       
        if self.nutrients:
            parts.append(f"Nutrients identified as relevant: {', '.join(self.nutrients)}")
        else:
            parts.append("Nutrients: None identified yet")
       
        parts.append(f"Conversation turns so far: {len(self.history) // 2}")
       
        return "\n".join(parts)
   
    def _get_system_prompt(self, user_context: str) -> str:
        """Get system prompt from Langfuse or fallback to singleton template."""
        try:
            langfuse_prompt = get_prompt_from_langfuse("REACT_AGENT")
            if langfuse_prompt:
                if hasattr(langfuse_prompt, 'format'):
                    try:
                        return langfuse_prompt.format(user_context=user_context)
                    except Exception as format_err:
                        logger.warning(f"Could not format Langfuse prompt: {format_err}. Using fallback.")
                # If it's a string, try to format it
                elif isinstance(langfuse_prompt, str):
                    return langfuse_prompt.format(user_context=user_context)
        except Exception as e:
            logger.warning(f"Could not fetch prompt from Langfuse: {str(e)}. Using fallback prompt.")
       
        # Fallback to hardcoded singleton template
        return AGENT_PROMPT.format(user_context=user_context)
       
    # ═══════════════════════════════════════════════════════════════════════════
    # RESPONSE EXTRACTION
    # ═══════════════════════════════════════════════════════════════════════════
   
    def _extract_final_response(self, result: dict) -> str:
        """Extract the final AI text response from ReAct agent result."""
        messages = result.get("messages", [])
       
        # Walk backwards to find the last AIMessage (not a tool call)
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                return msg.content
       
        # Fallback: any AIMessage with content
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                return msg.content
       
        return "I processed your request but couldn't generate a response."
   
    def _extract_tool_calls(self, result: dict) -> list:
        """Extract tool call info for debugging/logging."""
        messages = result.get("messages", [])
        tool_calls = []
       
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "tool": tc.get("name", "unknown"),
                        "args": tc.get("args", {})
                    })
       
        return tool_calls
   
    # ═══════════════════════════════════════════════════════════════════════════
    # ENTITY EXTRACTION FROM TOOL CALLS
    # ═══════════════════════════════════════════════════════════════════════════
   
    def _extract_entities_from_tools(self, result: dict):
        """
        Post-process tool results to update session memory.
        When a tool successfully resolves an entity, we remember it.
        """
        messages = result.get("messages", [])
       
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc.get("name", "")
                    args = tc.get("args", {})
                   
                    # Track medications
                    if tool_name in ("medication_lookup", "connection_validation"):
                        med = args.get("medication", "")
                        if med and med not in self.medications:
                            self.medications.append(med)
                   
                    # Track symptoms
                    if tool_name in ("symptom_investigation", "connection_validation"):
                        sym = args.get("symptom", "")
                        if sym and sym not in self.symptoms:
                            self.symptoms.append(sym)
                   
                    # Track nutrients from product_recommendation
                    if tool_name == "product_recommendation":
                        nuts = args.get("nutrients", [])
                        if isinstance(nuts, str):
                            nuts = [nuts]
                        for nut in nuts:
                            if nut and nut not in self.nutrients:
                                self.nutrients.append(nut)
                   
                    # Track nutrients from nutrient_education
                    if tool_name == "nutrient_education":
                        nut = args.get("nutrient", "")
                        if nut and nut not in self.nutrients:
                            self.nutrients.append(nut)
       
        # Also extract nutrients from medication_lookup results
        self._extract_nutrients_from_results(messages)
   
    def _extract_nutrients_from_results(self, messages: list):
        """Extract nutrient names from medication_lookup tool results."""
        for msg in messages:
            if isinstance(msg, ToolMessage):
                try:
                    data = json.loads(msg.content)
                    if isinstance(data, list):
                        for item in data:
                            context = item.get("context", item)
                            depletions = context.get("depletions", [])
                            for dep in depletions:
                                nut_name = dep.get("nutrient", "")
                                if nut_name and nut_name not in self.nutrients:
                                    self.nutrients.append(nut_name)
                except (json.JSONDecodeError, AttributeError, TypeError):
                    pass
   
    # ═══════════════════════════════════════════════════════════════════════════
    # HISTORY MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
   
    def _update_history(self, user_message: str, ai_response: str):
        """Add turn to conversation history."""
        self.history.append(HumanMessage(content=user_message))
        self.history.append(AIMessage(content=ai_response))
   
    def get_full_result(self, user_message: str) -> Dict[str, Any]:
        """Get full result dict including tool calls."""
        return self.run_medical_query(user_message)
   
    def clear_history(self):
        """Reset session."""
        self.history = []
        self.medications = []
        self.symptoms = []
        self.nutrients = []
   
    def get_history(self) -> list:
        return self.history