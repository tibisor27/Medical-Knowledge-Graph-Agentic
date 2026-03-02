from src.utils.get_llm import get_llm_4_1_mini
from src.agent.tools import get_tools
from langgraph.prebuilt import create_react_agent

_compiled_agent = None  #Getter for singleton ReAct agent instance
 
 
def create_medical_react_agent():
    """Create ReAct agent with medical tools."""
    llm = get_llm_4_1_mini()
   
    # Lazy load tools here, not at import time
    tools = get_tools()
   
    agent = create_react_agent(
        model=llm,
        tools=tools,
    )
   
    return agent
 
 
def get_medical_agent():    #function that initalizes 1 agent globally, so it is created only once and reused across calls
    """Get or create the singleton ReAct agent."""
    global _compiled_agent
    if _compiled_agent is None:
        _compiled_agent = create_medical_react_agent()  #global variable that holds the agent permanently after first initialization
    return _compiled_agent
 