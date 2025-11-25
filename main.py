"""FastAPI entrypoint for the custom Go-like game backend."""
from __future__ import annotations

import uuid
from typing import Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from go_backend.ai import HeuristicAI
from go_backend.engine import GameState

app = FastAPI(title="Go-like Variant Backend", version="0.1.0")


class CreateGameRequest(BaseModel):
    size: int = Field(11, ge=5, le=19)
    komi: float = 5.5


class MoveRequest(BaseModel):
    x: int
    y: int
    player: str | None = None


class PassRequest(BaseModel):
    player: str | None = None


class AIRequest(BaseModel):
    strength: int = Field(30, ge=1, le=200, description="Number of heuristic playout samples")


GAMES: Dict[str, GameState] = {}


@app.post("/game")
def create_game(body: CreateGameRequest) -> Dict[str, object]:
    game_id = uuid.uuid4().hex
    GAMES[game_id] = GameState(size=body.size, komi=body.komi)
    return {"game_id": game_id, "state": GAMES[game_id].serialize()}


@app.get("/game/{game_id}")
def get_state(game_id: str) -> Dict[str, object]:
    game = GAMES.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game.serialize()


@app.post("/game/{game_id}/move")
def play_move(game_id: str, body: MoveRequest) -> Dict[str, object]:
    game = GAMES.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    result = game.play_move(body.x, body.y, color=body.player)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return {"message": result.message, "captured": result.captured, "state": game.serialize()}


@app.post("/game/{game_id}/pass")
def pass_turn(game_id: str, body: PassRequest) -> Dict[str, object]:
    game = GAMES.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if body.player and body.player != game.to_play:
        raise HTTPException(status_code=400, detail="It is not this player's turn")
    game.pass_turn()
    return {"message": "Passed", "state": game.serialize()}


@app.post("/game/{game_id}/ai")
def ai_move(game_id: str, body: AIRequest) -> Dict[str, object]:
    game = GAMES.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    ai = HeuristicAI(playouts=body.strength)
    result = ai.play_move(game)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return {"message": result.message, "captured": result.captured, "state": game.serialize()}


@app.get("/game/{game_id}/score")
def score(game_id: str) -> Dict[str, object]:
    game = GAMES.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    breakdown = game.score()
    return {
        "stones": breakdown.stones,
        "territory": breakdown.territory,
        "prisoners": breakdown.prisoners,
        "total": breakdown.total,
        "winner": "B" if breakdown.total["B"] > breakdown.total["W"] else "W",
    }


@app.get("/")
def root() -> Dict[str, str]:
    return {"message": "Go-like variant backend running"}
