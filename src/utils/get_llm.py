from langchain_openai import AzureChatOpenAI
from langchain_openai import AzureOpenAIEmbeddings
from src.config import  AZURE_DEPLOYMENT_NAME, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, OPENAI_API_VERSION, validate_config, AZURE_EMBEDDINGS_DEPLOYMENT_NAME

def get_llm_5_1_chat() -> AzureChatOpenAI:
    """Get the Azure OpenAI LLM instance."""
    validate_config()
    return AzureChatOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=OPENAI_API_VERSION,
        azure_deployment=AZURE_DEPLOYMENT_NAME
    )

def get_llm_4_1_mini() -> AzureChatOpenAI:
    """Get the Azure OpenAI LLM instance."""
    validate_config()
    return AzureChatOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=OPENAI_API_VERSION,
        azure_deployment=AZURE_DEPLOYMENT_NAME  
        )

def get_embeddings_client() -> AzureOpenAIEmbeddings:
    """Get the Azure OpenAI embeddings client."""
    validate_config()
    return AzureOpenAIEmbeddings(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=OPENAI_API_VERSION,
        azure_deployment=AZURE_EMBEDDINGS_DEPLOYMENT_NAME
    )