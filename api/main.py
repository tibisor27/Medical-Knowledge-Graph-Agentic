from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.multi_agent.state import log_state_summary
from src.agent.session import MedicalAgent
from src.multi_agent.graph import build_multi_agent_graph
from src.config import validate_config
from src.utils.langfuse_client import get_langfuse_handler
from langchain_core.messages import HumanMessage, AIMessage

# Configurare logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# INIȚIALIZARE FASTAPI
# ═══════════════════════════════════════════════════════════════

app = FastAPI(
    title="Medical Knowledge Graph API",
    description="API pentru agentul medical bazat pe graph database Neo4j",
    version="1.0.0",
    docs_url="/docs",   # Swagger UI
    redoc_url="/redoc"  # ReDoc
)

# CORS - permite Streamlit să acceseze API-ul
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # În producție, specifică doar domeniile permise
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════
# SESSION MANAGEMENT
# ═══════════════════════════════════════════════════════════════

# V1 sessions (single ReAct agent)
sessions: Dict[str, MedicalAgent] = {}

# The compiled multi-agent graph (singleton)
multi_agent_graph = None


def get_multi_agent_graph():
    global multi_agent_graph
    if multi_agent_graph is None:
        multi_agent_graph = build_multi_agent_graph()
    return multi_agent_graph


def get_or_create_session(session_id: str) -> MedicalAgent:
    if session_id not in sessions:
        sessions[session_id] = MedicalAgent(session_id=session_id)
        logger.info(f"Created new session: {session_id}")
    return sessions[session_id]


class ChatRequest(BaseModel):
    message: str = Field(..., description="Mesajul utilizatorului", min_length=1)
    session_id: str = Field(default="default", description="ID-ul sesiunii")
    user_id: Optional[str] = Field(default=None, description="ID-ul utilizatorului (pentru Langfuse)")
    return_details: bool = Field(default=False, description="Returnează detalii complete (entities, cypher, etc.)")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Ce nutrienți depletează Acetaminophen?",
                "session_id": "user123",
                "return_details": True
            }
        }


class ChatResponse(BaseModel):
    response: str = Field(..., description="Răspunsul agentului")
    session_id: str = Field(..., description="ID-ul sesiunii")
    details: Optional[Dict[str, Any]] = Field(None, description="Detalii despre procesare (opțional)")

    class Config:
        json_schema_extra = {
            "example": {
                "response": "Acetaminophen depletează Glutathione...",
                "session_id": "user123",
                "details": None
            }
        }


class HealthResponse(BaseModel):
    """Response pentru health check"""
    status: str
    version: str
    message: str


class HistoryResponse(BaseModel):
    """Response pentru history endpoint"""
    session_id: str
    message_count: int
    messages: List[Dict[str, str]]


# ═══════════════════════════════════════════════════════════════
# API ROUTER (toate endpoint-urile sub /api)
# ═══════════════════════════════════════════════════════════════

api_router = APIRouter(prefix="/api", tags=["API"])


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/", response_model=HealthResponse)
async def root():

    return {
        "status": "online",
        "version": "1.0.0",
        "message": "Medical Knowledge Graph API is running. Visit /docs for documentation."
    }


@api_router.get("/health", response_model=HealthResponse)  #validate configs
async def health_check():

    try:
        # Validează configurarea
        validate_config()
        
        return {
            "status": "healthy",
            "version": "1.0.0",
            "message": "All systems operational"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@api_router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        session = get_or_create_session(request.session_id)
        if request.return_details:
            result = session.run_medical_query(request.message)
            details = {
                "tool_calls": result.get("tool_calls", []),
                "medications": result.get("medications", []),
                "symptoms": result.get("symptoms", []),
                "nutrients": result.get("nutrients", []),
                "products": result.get("products", []),
            }
            response_text = result.get("final_response", "")
        else:
            response_text = session.chat(request.message)
            details = None
        return ChatResponse(
            response=response_text,
            session_id=request.session_id,
            details=details
        )
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/v2/chat", response_model=ChatResponse)
async def chat_v2(request: ChatRequest):

    try:
        graph = get_multi_agent_graph()

        # Configurare Checkpointer (thread_id)
        config = {"configurable": {"thread_id": request.session_id}}
        
        # Configurare Langfuse (Observability)
        langfuse_handler = get_langfuse_handler()
        if langfuse_handler:
            # Setam atributele pe handler inainte de a rula graful
            # Astfel, toate LLM calls din acest thread vor fi grupate sub acelasi session_id
            if request.session_id:
                langfuse_handler.session_id = request.session_id
            if request.user_id:
                langfuse_handler.user_id = request.user_id
            
            # Pasam handler-ul in config-ul Langchain
            config["callbacks"] = [langfuse_handler]
        
        # Invoke graph with just the latest user message
        result = graph.invoke(
            {"messages": [HumanMessage(content=request.message)]},
            config=config
        )
        
        response_text = result.get("final_response", "")

        logger.info(f"State after {result.get('step_count')+1} turns: ")
        log_state_summary(result)

        details = None
        if request.return_details:
            details = {
                "execution_path": result.get("execution_path", []),
                "safety_flags": result.get("safety_flags", []),
                "guardrail_pass": result.get("guardrail_pass", True),
                "persisted_medications": result.get("persisted_medications", []),
                "persisted_symptoms": result.get("persisted_symptoms", []),
                "persisted_nutrients": result.get("persisted_nutrients", []),
                "persisted_products": result.get("persisted_products", []),
            }

        return ChatResponse(
            response=response_text,
            session_id=request.session_id,
            details=details,
        )

    except Exception as e:
        logger.error(f"V2 Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))




# ═══════════════════════════════════════════════════════════════
# V1 HISTORY/SESSION ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@api_router.get("/history/{session_id}", response_model=HistoryResponse)

async def get_history(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    session = sessions[session_id]
    history = session.get_history()

    # Convertește mesajele într-un format serializable
    messages = []
    for msg in history:
        messages.append({
            "role": "user" if msg.__class__.__name__ == "HumanMessage" else "Assistant",
            "content": msg.content
        })
    
    return HistoryResponse(
        session_id=session_id,
        message_count=len(messages),
        messages=messages
    )


@api_router.delete("/history/{session_id}")
async def clear_history(session_id: str):

    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    sessions[session_id].clear_history()
    logger.info(f"Cleared history for session: {session_id}")
    
    return {"message": f"History cleared for session {session_id}"}


@api_router.delete("/session/{session_id}")
async def delete_session(session_id: str):

    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    del sessions[session_id]
    logger.info(f"Deleted session: {session_id}")
    
    return {"message": f"Session {session_id} deleted"}


@api_router.get("/sessions")
async def list_sessions():

    session_info = {}
    for session_id, session in sessions.items():
        session_info[session_id] = {
            "message_count": len(session.get_history())
        }
    
    return {
        "total_sessions": len(sessions),
        "sessions": session_info
    }


# ═══════════════════════════════════════════════════════════════
# INCLUDE ROUTER
# ═══════════════════════════════════════════════════════════════

app.include_router(api_router)

# ═══════════════════════════════════════════════════════════════
# STARTUP/SHUTDOWN EVENTS
# ═══════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    """Rulează la pornirea API-ului"""
    logger.info("Starting Medical Knowledge Graph API")
    try:
        validate_config()
        logger.info("Configuration validated")
        logger.info("API is ready to accept requests")
        logger.info("Documentation available at /docs")
        logger.info("API endpoints available at /api/*")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Rulează la oprirea API-ului"""
    logger.info("Shutting down Medical Knowledge Graph API")
    logger.info(f"Total sessions: {len(sessions)}")