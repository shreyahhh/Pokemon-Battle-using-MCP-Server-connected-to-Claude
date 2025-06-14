import httpx
from typing import Dict, Any, Optional

class AIClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def generate_content(
        self,
        prompt: str,
        model: str = "claude-3-opus-20240229",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate content using the AI server.
        
        Args:
            prompt: The input prompt for the AI
            model: The model to use (default: claude-3-opus-20240229)
            max_tokens: Maximum number of tokens to generate
            temperature: Controls randomness (0.0 to 1.0)
            context: Optional context for the generation
            
        Returns:
            The generated text response
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/generate",
                json={
                    "prompt": prompt,
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "context": context
                }
            )
            response.raise_for_status()
            return response.json()["response"]
        except Exception as e:
            print(f"Error generating content: {e}")
            return ""

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose() 