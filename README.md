# Custom Go-like Variant Backend

Python backend implementing a Go-inspired board game with unique rules:
- Standard capture/self-atari logic with ko.
- Variant twist: liberties touching the last capture count double for the next move.
- Territory is decided by majority influence around empty regions (mixed-border areas go to the dominant color; ties are neutral).
- Supports local play, AI opponent, and scoring with komi.

## Project layout
- `go_backend/engine.py` – core rules engine (move validation, captures, ko, territory scoring).
- `go_backend/ai.py` – lightweight heuristic AI for move suggestions.
- `main.py` – FastAPI application exposing REST endpoints.
- `requirements.txt` – Python dependencies.

## Running the server
1. Install dependencies (ideally in a virtual environment):
   ```bash
   pip install -r requirements.txt
   ```
2. Start the API (11×11 board by default):
   ```bash
   uvicorn main:app --reload --port 8000
   ```
3. Interact with the API via cURL or the interactive docs at `http://localhost:8000/docs`.

## Example API flow
```bash
# Create a game
curl -X POST http://localhost:8000/game -H "Content-Type: application/json" -d '{"size":11}'

# Play a move (B at 3,3)
curl -X POST http://localhost:8000/game/<id>/move -H "Content-Type: application/json" -d '{"x":3,"y":3}'

# Ask AI to move
curl -X POST http://localhost:8000/game/<id>/ai -H "Content-Type: application/json" -d '{"strength":40}'

# Pass and score
curl -X POST http://localhost:8000/game/<id>/pass -H "Content-Type: application/json" -d '{}' 
curl http://localhost:8000/game/<id>/score
```

The server tracks captured stones, ko, and the variant liberty/territory rules to determine legality and game results.
