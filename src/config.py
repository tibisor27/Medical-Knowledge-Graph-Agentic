import os
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════════
# AZURE OPENAI CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION")

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
    
    if errors:
        raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
    
    return True