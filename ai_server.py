from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import os
from dotenv import load_dotenv
from typing import Optional, Dict, Any

# Load environment variables
load_dotenv('api.env')

app = FastAPI(title="AI Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Load Anthropic API key
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

# Initialize Anthropic client
client = anthropic.Anthropic(
    api_key=anthropic_api_key,
    base_url="https://api.anthropic.com/v1"
)

class ModelRequest(BaseModel):
    prompt: str
    model: str = "claude-3-opus-20240229"
    max_tokens: int = 1000
    temperature: float = 0.7
    context: Optional[Dict[str, Any]] = None

class ModelResponse(BaseModel):
    response: str
    model: str
    usage: Dict[str, int]

@app.get("/")
async def root():
    return {"message": "AI Server is running"}

@app.post("/generate", response_model=ModelResponse)
async def generate_content(request: ModelRequest):
    try:
        # Prepare the message for Claude
        message = client.messages.create(
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            messages=[
                {"role": "user", "content": request.prompt}
            ]
        )
        
        # Extract the response
        response_text = message.content[0].text if message.content else ""
        
        return ModelResponse(
            response=response_text,
            model=request.model,
            usage={
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/models")
async def list_models():
    return {
        "models": [
            {
                "id": "claude-3-opus-20240229",
                "name": "Claude 3 Opus",
                "capabilities": ["complex_reasoning", "creative_tasks", "long_form_content"]
            },
            {
                "id": "claude-3-sonnet-20240229",
                "name": "Claude 3 Sonnet",
                "capabilities": ["general_purpose", "creative_tasks"]
            },
            {
                "id": "claude-3-haiku-20240229",
                "name": "Claude 3 Haiku",
                "capabilities": ["fast_responses", "general_purpose"]
            }
        ]
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            request = ModelRequest.parse_raw(data)
            response = await generate_content(request)
            await websocket.send_json(response.dict())
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 