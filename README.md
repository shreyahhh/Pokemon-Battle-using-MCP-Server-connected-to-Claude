# Pokemon Game with Claude AI

This is a Pokemon game that uses Claude AI through the Model Context Protocol (MCP) server to create an interactive gaming experience.

## Setup Instructions

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory and add your Anthropic API key:
```
ANTHROPIC_API_KEY=your_api_key_here
```

4. Run the server:
```bash
python server.py
```

5. Open the game client in your browser at `http://localhost:8000`

## Project Structure

- `server.py`: Main FastAPI server with MCP implementation
- `game_logic.py`: Core game mechanics and Pokemon logic
- `static/`: Static files for the web client
- `templates/`: HTML templates for the web interface

## Features

- Interactive Pokemon battles
- AI-powered responses and game logic
- Real-time game updates
- Simple web-based interface 