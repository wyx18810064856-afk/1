"""Game engine for custom Go-like variant.

Implements board operations, legality checks (capture, self-atari, ko),
variant-specific virtual liberties, and scoring with territory-majority rule.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

Color = str  # 'B' or 'W'
Point = Tuple[int, int]


@dataclass
class MoveResult:
    success: bool
    message: str
    captured: int = 0
    board: Optional[List[List[Color]]] = None


@dataclass
class ScoreBreakdown:
    stones: Dict[Color, int]
    territory: Dict[Color, int]
    prisoners: Dict[Color, int]
    total: Dict[Color, float]


@dataclass
class GameState:
    size: int = 11
    komi: float = 5.5
    board: List[List[Color]] = field(init=False)
    to_play: Color = "B"
    prisoners: Dict[Color, int] = field(default_factory=lambda: {"B": 0, "W": 0})
    history: List[Tuple[Tuple[Color, ...], ...]] = field(default_factory=list)
    ko_point: Optional[Point] = None
    last_captured_points: Set[Point] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.board = [["." for _ in range(self.size)] for _ in range(self.size)]
        self.history.append(self._hash_position())

    # Utility helpers -----------------------------------------------------
    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.size and 0 <= y < self.size

    def neighbors(self, x: int, y: int) -> List[Point]:
        return [(nx, ny) for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)) if self.in_bounds(nx, ny)]

    def _hash_position(self) -> Tuple[Tuple[Color, ...], ...]:
        return tuple(tuple(row) for row in self.board)

    def _clone_board(self) -> List[List[Color]]:
        return [row.copy() for row in self.board]

    # Group analysis ------------------------------------------------------
    def _collect_group(self, x: int, y: int) -> Tuple[Set[Point], Set[Point]]:
        color = self.board[x][y]
        stones: Set[Point] = set()
        liberties: Set[Point] = set()
        frontier = [(x, y)]
        while frontier:
            cx, cy = frontier.pop()
            if (cx, cy) in stones:
                continue
            stones.add((cx, cy))
            for nx, ny in self.neighbors(cx, cy):
                occupant = self.board[nx][ny]
                if occupant == ".":
                    liberties.add((nx, ny))
                elif occupant == color and (nx, ny) not in stones:
                    frontier.append((nx, ny))
        return stones, liberties

    def _remove_group(self, stones: Set[Point]) -> None:
        for x, y in stones:
            self.board[x][y] = "."

    # Move legality and application --------------------------------------
    def _apply_virtual_liberties(self, liberties: Set[Point]) -> int:
        """Apply variant rule: liberties touching last-captured points count double."""
        bonus = len(liberties & self.last_captured_points)
        return len(liberties) + bonus

    def is_legal_move(self, x: int, y: int, color: Optional[Color] = None) -> Tuple[bool, str, int]:
        if color is None:
            color = self.to_play
        if not self.in_bounds(x, y):
            return False, "Move is off-board", 0
        if self.board[x][y] != ".":
            return False, "Intersection is occupied", 0
        if self.ko_point == (x, y):
            return False, "Ko prohibition", 0

        backup_board = self._clone_board()
        backup_prisoners = self.prisoners.copy()
        backup_ko = self.ko_point
        backup_captured = self.last_captured_points.copy()

        result = self._play_move_internal(x, y, color, simulate=True)
        # restore
        self.board = backup_board
        self.prisoners = backup_prisoners
        self.ko_point = backup_ko
        self.last_captured_points = backup_captured
        return result.success, result.message, result.captured

    def _play_move_internal(self, x: int, y: int, color: Color, simulate: bool = False) -> MoveResult:
        opponent = "W" if color == "B" else "B"
        self.board[x][y] = color

        captured_total = 0
        captured_points: Set[Point] = set()
        for nx, ny in self.neighbors(x, y):
            if self.board[nx][ny] == opponent:
                stones, liberties = self._collect_group(nx, ny)
                if not liberties:
                    captured_total += len(stones)
                    captured_points |= stones
                    self._remove_group(stones)

        # Check liberties for placed stone after captures
        stones, liberties = self._collect_group(x, y)
        liberties_count = self._apply_virtual_liberties(liberties)
        if liberties_count == 0:
            self.board[x][y] = "."
            return MoveResult(False, "Suicide is not allowed")

        # Ko detection (simple ko with single capture reversion)
        new_hash = self._hash_position()
        if captured_total == 1 and len(self.history) >= 2 and new_hash == self.history[-2]:
            self.board[x][y] = "."
            if captured_points:
                for px, py in captured_points:
                    self.board[px][py] = opponent
            return MoveResult(False, "Ko rule forbids immediate retake")

        if not simulate:
            self.prisoners[color] += captured_total
            self.history.append(new_hash)
            self.to_play = opponent
            self.ko_point = None
            if captured_total == 1:
                # Ko point is the captured stone location if neighboring group size 1
                self.ko_point = next(iter(captured_points))
            self.last_captured_points = captured_points
        return MoveResult(True, "Move played", captured_total, self._clone_board())

    def play_move(self, x: int, y: int, color: Optional[Color] = None) -> MoveResult:
        if color is None:
            color = self.to_play
        legal, msg, _ = self.is_legal_move(x, y, color)
        if not legal:
            return MoveResult(False, msg)
        return self._play_move_internal(x, y, color)

    def pass_turn(self) -> None:
        self.to_play = "W" if self.to_play == "B" else "B"
        self.last_captured_points = set()
        self.history.append(self._hash_position())
        self.ko_point = None

    # Scoring -------------------------------------------------------------
    def _empty_regions(self) -> List[Set[Point]]:
        visited: Set[Point] = set()
        regions: List[Set[Point]] = []
        for x in range(self.size):
            for y in range(self.size):
                if self.board[x][y] == "." and (x, y) not in visited:
                    region: Set[Point] = set()
                    frontier = [(x, y)]
                    while frontier:
                        cx, cy = frontier.pop()
                        if (cx, cy) in visited:
                            continue
                        visited.add((cx, cy))
                        region.add((cx, cy))
                        for nx, ny in self.neighbors(cx, cy):
                            if self.board[nx][ny] == "." and (nx, ny) not in visited:
                                frontier.append((nx, ny))
                    regions.append(region)
        return regions

    def _region_owner(self, region: Set[Point]) -> Optional[Color]:
        border_counts: Dict[Color, int] = {"B": 0, "W": 0}
        for x, y in region:
            for nx, ny in self.neighbors(x, y):
                occupant = self.board[nx][ny]
                if occupant in border_counts:
                    border_counts[occupant] += 1
        if border_counts["B"] == 0 and border_counts["W"] == 0:
            return None
        if border_counts["B"] == 0:
            return "W"
        if border_counts["W"] == 0:
            return "B"
        if border_counts["B"] == border_counts["W"]:
            return None
        return "B" if border_counts["B"] > border_counts["W"] else "W"

    def score(self) -> ScoreBreakdown:
        territory = {"B": 0, "W": 0}
        for region in self._empty_regions():
            owner = self._region_owner(region)
            if owner:
                territory[owner] += len(region)

        stones = {"B": 0, "W": 0}
        for row in self.board:
            for cell in row:
                if cell in stones:
                    stones[cell] += 1

        totals: Dict[Color, float] = {
            "B": float(stones["B"] + territory["B"] + self.prisoners.get("B", 0)),
            "W": float(stones["W"] + territory["W"] + self.prisoners.get("W", 0) + self.komi),
        }
        return ScoreBreakdown(stones=stones, territory=territory, prisoners=self.prisoners.copy(), total=totals)

    # Convenience serialization -----------------------------------------
    def serialize(self) -> Dict[str, object]:
        return {
            "size": self.size,
            "board": self._clone_board(),
            "to_play": self.to_play,
            "prisoners": self.prisoners.copy(),
            "komi": self.komi,
            "ko_point": self.ko_point,
            "last_captured_points": sorted(list(self.last_captured_points)),
        }
