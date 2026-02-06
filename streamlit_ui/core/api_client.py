import requests
import os
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


API_URL = os.getenv("API_URL", "http://localhost:8010")

class APIClient:
    
    def __init__(self, base_url: str = None, session_id: str = "default"):

        self.base_url = base_url or API_URL
        self.session_id = session_id
        self.timeout = 60  # Timeout 60s pentru queries complexe
        
    def health_check(self) -> bool:

        try:
            response = requests.get(
                f"{self.base_url}/api/health",
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def chat(self, message: str, return_details: bool = False) -> Dict[str, Any]:
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "message": message,
                    "session_id": self.session_id,
                    "return_details": return_details
                },
                timeout=self.timeout
            )
            response.raise_for_status() #arunca exceptie daca status code != 200
            return response.json() #.json contine bodyul cererii(datele mele pe care le vreau sa le afisez la user) 
            
        except requests.Timeout:
            logger.error("API request timed out")
            raise Exception("Request timed out. Please try again.")
        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise Exception(f"Failed to communicate with API: {str(e)}")
    
    def get_history(self) -> Dict[str, Any]:

        try:
            response = requests.get(
                f"{self.base_url}/api/history/{self.session_id}",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return {"messages": [], "message_count": 0}
    
    def clear_history(self) -> bool:

        try:
            response = requests.delete(
                f"{self.base_url}/api/history/{self.session_id}",
                timeout=10
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")
            return False


def get_api_client(session_id: str = "default") -> APIClient:

    return APIClient(session_id=session_id)
