import os
from dotenv import load_dotenv

load_dotenv()

MAX_ENTITIES_DETAILED = 5
MAX_RESPONSE_WORDS = 150
# ═══════════════════════════════════════════════════════════════════════════════
# AZURE OPENAI CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION")
AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_DEPLOYMENT_NAME")
AZURE_EMBEDDINGS_DEPLOYMENT_NAME = os.getenv("AZURE_EMBEDDINGS_DEPLOYMENT_NAME")
# ═══════════════════════════════════════════════════════════════════════════════
# NEO4J CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
LLM_READER_USER = os.getenv("LLM_READER_USER")
LLM_READER_PASSWORD = os.getenv("LLM_READER_PASSWORD")

# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_config():
    """Validate that all required configuration is present."""
    errors = []
    
    if not AZURE_OPENAI_API_KEY:
        errors.append("AZURE_OPENAI_API_KEY is not set")
    
    if not AZURE_DEPLOYMENT_NAME:
        errors.append("AZURE_DEPLOYMENT_NAME is not set - this should be your Azure OpenAI deployment name (e.g., 'gpt-4o-mini')")
    
    if not AZURE_EMBEDDINGS_DEPLOYMENT_NAME:
        errors.append("AZURE_EMBEDDINGS_DEPLOYMENT_NAME is not set - this should be your Azure OpenAI embeddings deployment name (e.g., 'text-embedding')")
    
    if not NEO4J_URI:
        errors.append("NEO4J_URI is not set")
    
    if not NEO4J_USER:
        errors.append("NEO4J_USER is not set")
    
    if not NEO4J_PASSWORD:
        errors.append("NEO4J_PASSWORD is not set")
    
    if not LLM_READER_USER:
        errors.append("LLM_READER_USER is not set")
    
    if not LLM_READER_PASSWORD:
        errors.append("LLM_READER_PASSWORD is not set")

    if not AZURE_OPENAI_ENDPOINT:
        errors.append("AZURE_OPENAI_ENDPOINT is not set")

    
    if errors:
        raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
    
    return True