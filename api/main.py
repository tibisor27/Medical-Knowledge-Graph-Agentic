from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.graph import MedicalChatSession
from src.config import validate_config

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

#storage sessions - memory
sessions: Dict[str, MedicalChatSession] = {}


def get_or_create_session(session_id: str) -> MedicalChatSession:
    if session_id not in sessions:
        sessions[session_id] = MedicalChatSession(session_id=session_id)
        logger.info(f"Created new session: {session_id}")
    return sessions[session_id]


# ═══════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str = Field(..., description="Mesajul utilizatorului", min_length=1)
    session_id: str = Field(default="default", description="ID-ul sesiunii")
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
            result = session.get_full_result(request.message)
            # Serializează conversation_analysis
            conv_analysis = result.get("conversation_analysis")
            logger.debug(f"Conversation analysis type: {type(conv_analysis)}")
            logger.debug(f"Conversation analysis content: {conv_analysis}")

            if conv_analysis:
                conv_analysis_dict = conv_analysis.dict() if hasattr(conv_analysis, 'dict') else conv_analysis.model_dump()
            else:
                conv_analysis_dict = None
            details = {
                "resolved_entities": [
                    {
                        "original_text": e.original_text,
                        "resolved_name": e.resolved_name,
                        "node_type": e.node_type,
                        "match_score": float(e.match_score),
                        "match_method": e.match_method,
                    }
                    for e in result.get("resolved_entities", [])
                ],
                "has_results": result.get("has_results", False),
                "execution_path": result.get("execution_path", []),
                "conversation_analysis": conv_analysis_dict,
                "graph_results": result.get("graph_results", []),
            }
            response_text = result.get("final_response", "")
            conv_analysis = result.get("conversation_analysis")

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