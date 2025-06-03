import httpx
import websockets
from typing import Dict, Any, Optional
import json

class MCPClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.ws_url = base_url.replace("http", "ws")
        self.client = httpx.AsyncClient()
        self.ws = None

    async def connect_websocket(self):
        """Connect to the WebSocket endpoint."""
        if not self.ws:
            self.ws = await websockets.connect(f"{self.ws_url}/ws")

    async def generate_content(self, prompt: str, model: str = "claude-3-opus-20240229", 
                             max_tokens: int = 1000, temperature: float = 0.7,
                             context: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate content using the MCP server.
        """
        try:
            # Try WebSocket first
            if not self.ws:
                await self.connect_websocket()
            
            request = {
                "prompt": prompt,
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "context": context
            }
            
            await self.ws.send(json.dumps(request))
            response = await self.ws.recv()
            data = json.loads(response)
            return data["response"]
            
        except Exception as e:
            print(f"WebSocket error, falling back to HTTP: {e}")
            try:
                # Fallback to HTTP
                response = await self.client.post(
                    f"{self.base_url}/generate",
                    json=request
                )
                response.raise_for_status()
                data = response.json()
                return data["response"]
            except Exception as http_error:
                print(f"Error generating content: {http_error}")
                return ""

    async def list_models(self) -> Dict[str, Any]:
        """
        Get list of available models from the MCP server.
        """
        try:
            response = await self.client.get(f"{self.base_url}/models")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error listing models: {e}")
            return {"models": []}

    async def close(self):
        """
        Close the HTTP client and WebSocket connection.
        """
        await self.client.aclose()
        if self.ws:
            await self.ws.close()
            self.ws = None 