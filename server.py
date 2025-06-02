from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
import anthropic # Import Anthropic library
import os
import json
from dotenv import load_dotenv, dotenv_values
from typing import Dict, List, Any
import asyncio
import httpx # Import httpx for making asynchronous HTTP requests

# Load environment variables
load_dotenv('api.env')

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Load Anthropic API key
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

# Fallback: Try reading from api.env if not set as environment variable
if not anthropic_api_key:
    config = dotenv_values('api.env')
    if config and "ANTHROPIC_API_KEY" in config:
        anthropic_api_key = config["ANTHROPIC_API_KEY"]

if not anthropic_api_key or anthropic_api_key == "your-anthropic-api-key":
    raise ValueError("ANTHROPIC_API_KEY environment variable is not set and not found in api.env")

# Log the API key being used (masking most of it for security)
print(f"Using Anthropic API Key: ...{anthropic_api_key[-5:]}")

# Initialize Anthropic client
client = anthropic.Anthropic(api_key=anthropic_api_key)

# PokeAPI base URL
POKEAPI_BASE_URL = "https://pokeapi.co/api/v2"

# Game state
game_states: Dict[str, dict] = {}

class PokemonGame:
    def __init__(self):
        self.current_pokemon: Dict[str, Any] | None = None
        self.opponent_pokemon: Dict[str, Any] | None = None
        self.caught_pokemon: List[Dict[str, Any]] = []
        self.all_pokemon_names: List[str] = []

    async def load_all_pokemon_names(self):
        """Fetches a list of all pokemon names from PokeAPI."""
        async with httpx.AsyncClient() as client:
            # Fetching a high limit to get most pokemon in one go. PokeAPI supports up to 100000.
            response = await client.get(f"{POKEAPI_BASE_URL}/pokemon?limit=1000")
            response.raise_for_status() # Raise an exception for bad status codes
            data = response.json()
            self.all_pokemon_names = [result['name'] for result in data['results']]
            print(f"Loaded {len(self.all_pokemon_names)} pokemon names from PokeAPI.")

    async def fetch_pokemon_data(self, pokemon_name: str) -> Dict[str, Any]:
        """Fetches detailed data for a specific pokemon from PokeAPI."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{POKEAPI_BASE_URL}/pokemon/{pokemon_name}")
            response.raise_for_status() # Raise an exception for bad status codes
            return response.json()

    async def select_pokemon(self, pokemon_name: str) -> bool:
        selected = next((p for p in self.caught_pokemon if p['name'] == pokemon_name), None)
        if selected:
            self.current_pokemon = selected.copy()
            for stat in self.current_pokemon.get('stats', []):
                if stat['stat']['name'] == 'hp':
                    self.current_pokemon['hp'] = stat['base_stat']
                    break
            return True
        return False

    async def select_opponent(self) -> None:
        import random
        available_names = [name for name in self.all_pokemon_names if name != self.current_pokemon['name']]
        if not available_names:
             print("No other pokemon available to select as opponent.")
             return

        opponent_name = random.choice(available_names)
        try:
            opponent_data = await self.fetch_pokemon_data(opponent_name)
            self.opponent_pokemon = opponent_data.copy()
            for stat in self.opponent_pokemon.get('stats', []):
                 if stat['stat']['name'] == 'hp':
                     self.opponent_pokemon['hp'] = stat['base_stat']
                     break
        except Exception as e:
            print(f"Error fetching opponent pokemon data: {e}")
            self.opponent_pokemon = None

    def attack(self, attacking_pokemon: Dict[str, Any], defending_pokemon: Dict[str, Any], move: str):
        attacker_attack = 0
        defender_defense = 0
        for stat in attacking_pokemon.get('stats', []):
            if stat['stat']['name'] == 'attack':
                attacker_attack = stat['base_stat']
                break
        for stat in defending_pokemon.get('stats', []):
            if stat['stat']['name'] == 'defense':
                defender_defense = stat['base_stat']
                break

        if defender_defense == 0:
            defender_defense = 1
            
        base_damage = 20
        damage = max(1, int((attacker_attack / defender_defense) * base_damage))
        defending_pokemon['hp'] = max(0, defending_pokemon['hp'] - damage)
        return f"{attacking_pokemon['name']} used {move}! It dealt {damage} damage."

    async def catch_pokemon(self) -> Dict[str, Any] | None:
        if len(self.caught_pokemon) >= 6:
            raise ValueError("You can only have 6 Pokemon in your team!")
            
        if not self.all_pokemon_names:
            await self.load_all_pokemon_names()
            if not self.all_pokemon_names:
                 print("Could not load pokemon names from PokeAPI.")
                 return None
                 
        import random
        available_to_catch = [name for name in self.all_pokemon_names if name not in [p['name'] for p in self.caught_pokemon]]
        
        if not available_to_catch:
            print("All available pokemon caught. Allowing duplicates.")
            pokemon_name = random.choice(self.all_pokemon_names)
        else:
            pokemon_name = random.choice(available_to_catch)

        try:
            pokemon_data = await self.fetch_pokemon_data(pokemon_name)
            caught_data = {
                "name": pokemon_data.get('name'),
                "id": pokemon_data.get('id'),
                "stats": pokemon_data.get('stats'),
                "sprites": pokemon_data.get('sprites'),
                "hp": None,
                "moves": ["Tackle", "Quick Attack", "Scratch", "Bite"]  # Add basic moves
            }
            self.caught_pokemon.append(caught_data)
            return caught_data
        except Exception as e:
            print(f"Error fetching pokemon data for catching: {e}")
            return None

    async def opponent_attack(self) -> str:
        if not self.opponent_pokemon or not self.current_pokemon:
            return "No Pokemon in battle!"
            
        import random
        moves = ["Tackle", "Quick Attack", "Scratch", "Bite"]
        move = random.choice(moves)
        return self.attack(self.opponent_pokemon, self.current_pokemon, move)

game = PokemonGame()

@app.on_event("startup")
async def startup_event():
    await game.load_all_pokemon_names()

@app.get("/", response_class=HTMLResponse)
async def get_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = str(id(websocket))
    game_states[client_id] = {"game": PokemonGame()}
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "select_pokemon":
                game = game_states[client_id]["game"]
                pokemon_name = message["pokemon"]
                
                if not any(p['name'] == pokemon_name for p in game.caught_pokemon):
                    await websocket.send_json({"type": "error", "message": f"You haven't caught {pokemon_name} yet!"})
                    return

                success = await game.select_pokemon(pokemon_name)
                if success:
                    await game_states[client_id]["game"].select_opponent()
                    response = {
                        "type": "game_state",
                        "player_pokemon": game_states[client_id]["game"].current_pokemon,
                        "opponent_pokemon": game_states[client_id]["game"].opponent_pokemon
                    }
                    await websocket.send_json(response)
                else:
                    await websocket.send_json({"type": "error", "message": "Failed to select Pokemon."})
            
            elif message["type"] == "catch_attempt":
                try:
                    game = game_states[client_id]["game"]
                    caught_data = await game.catch_pokemon()
                    if caught_data:
                        print(f"Successfully caught Pokemon: {caught_data['name']}")
                        await websocket.send_json({
                            "type": "catch_result",
                            "caught_pokemon": caught_data['name'],
                            "caught_list": game.caught_pokemon
                        })
                    else:
                        print("Failed to catch Pokemon - caught_data is None")
                        await websocket.send_json({"type": "error", "message": "Failed to catch a pokemon."})
                except Exception as e:
                    print(f"Error during catch attempt: {str(e)}")
                    await websocket.send_json({"type": "error", "message": f"An error occurred while catching: {str(e)}"})
            
            elif message["type"] == "attack":
                try:
                    game = game_states[client_id]["game"]
                    player_pokemon = game.current_pokemon
                    opponent_pokemon = game.opponent_pokemon
                    move = message['move']

                    if not player_pokemon or not opponent_pokemon:
                        await websocket.send_json({"type": "error", "message": "Cannot attack: Pokemon not selected or opponent not ready."})
                        return

                    winner = None # Initialize winner variable
                    battle_messages = [] # List to hold messages for the log

                    # Player's attack
                    player_attack_message = game.attack(player_pokemon, opponent_pokemon, move)
                    battle_messages.append(player_attack_message)

                    # Check if opponent is defeated after player's attack
                    if opponent_pokemon['hp'] <= 0:
                        winner = "Player"
                    else:
                        # Opponent's attack (only if opponent didn't faint)
                        opponent_attack_message = await game.opponent_attack()
                        battle_messages.append(opponent_attack_message)

                        # Check if player is defeated after opponent's attack
                        if player_pokemon['hp'] <= 0:
                            winner = "Opponent"

                    # Combine battle messages for the description
                    description_for_api = "\n".join(battle_messages)
                    api_description = description_for_api # Default description

                    # Call OpenAI API for creative description if no winner yet
                    if client and not winner:
                        try:
                            await websocket.send_json({"type": "server_log", "message": "Server: Making Anthropic API call for battle description..."})
                            response = client.messages.create(
                                model="claude-3-opus-20240229", # Using a recent Claude model
                                max_tokens=100,
                                messages=[
                                    {"role": "user", "content": f"Describe this Pokemon attack creatively, as a commentator: {description_for_api}"}
                                ]
                            )
                            await websocket.send_json({"type": "server_log", "message": f"Server: Anthropic API response received: {response.content[0].text[:50]}..."}) # Log part of the response
                            if response and response.content and len(response.content) > 0 and response.content[0].text:
                                api_description = response.content[0].text
                        except Exception as api_error:
                            await websocket.send_json({"type": "server_log", "message": f"Server: Error calling Anthropic API: {api_error}"})
                            # If API fails, revert to the basic description
                            api_description = description_for_api

                    # Prepare and send the final game state payload
                    response_payload = {
                        "type": "game_state",
                        "player_pokemon": player_pokemon,
                        "opponent_pokemon": opponent_pokemon,
                        "description": api_description, # Use API description if successful, otherwise default
                        "move": move,
                        "winner": winner # Will be None if battle continues
                    }
                    await websocket.send_json(response_payload)

                except Exception as e:
                    print(f"Error in attack handling: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"An error occurred during the attack: {str(e)}"
                    })
    
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        if client_id in game_states:
            del game_states[client_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 