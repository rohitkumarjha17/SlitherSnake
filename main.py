import typing
import random
from flask import Flask, request, jsonify
from collections import deque

app = Flask(__name__)

# ────────────────────────────────────────────────
#  CONSTANTS & WEIGHTS
# ────────────────────────────────────────────────
MINIMAX_DEPTH = 4          # Increase for stronger play (slower)
INF = float("inf")

# Heuristic weights — tune these to shift personality
W_SPACE       =  2.0   # flood-fill space score
W_FOOD        =  1.5   # reward for being close to food when hungry
W_KILL        =  3.0   # reward for being in kill position vs smaller snake
W_HAZARD      = -4.0   # penalty per hazard tile in flood fill
W_CENTER      =  0.5   # mild reward for controlling board center
W_HEALTH_CRIT = -3.0   # penalty when health is critically low (<= 25)
HUNGER_THRESH = 50     # health below this → prioritize food


# ────────────────────────────────────────────────
#  FLASK ENDPOINTS
# ────────────────────────────────────────────────

@app.get("/")
def info():
    return {
        "apiversion": "1",
        "author":     "battlesnake-elite",
        "color":      "#FF69B4",
        "head":       "evil",
        "tail":       "sharp",
    }

@app.post("/start")
def start():
    return {}

@app.post("/end")
def end():
    return {}

@app.post("/move")
def move():
    data = request.get_json()
    chosen = best_move(data)
    return jsonify({"move": chosen})


# ────────────────────────────────────────────────
#  MAIN ENTRY: BEST MOVE
# ────────────────────────────────────────────────

def best_move(data: dict) -> str:
    board  = data["board"]
    me     = data["you"]
    width  = board["width"]
    height = board["height"]

    state = GameState(board, me, width, height)
    directions = ["up", "down", "left", "right"]

    best_score = -INF
    best_dir   = None

    for d in directions:
        nx, ny = move_coord(me["head"], d)
        if not state.is_safe(nx, ny, me["id"]):
            continue
        new_state = state.apply_move(me["id"], d)
        score = minimax(new_state, MINIMAX_DEPTH - 1, -INF, INF, False, me["id"])
        if score > best_score:
            best_score = score
            best_dir   = d

    # Fallback: any move that doesn't immediately kill us
    if best_dir is None:
        for d in directions:
            nx, ny = move_coord(me["head"], d)
            if 0 <= nx < width and 0 <= ny < height:
                best_dir = d
                break
        if best_dir is None:
            best_dir = "up"

    return best_dir


# ────────────────────────────────────────────────
#  MINIMAX WITH ALPHA-BETA PRUNING
# ────────────────────────────────────────────────

def minimax(state: "GameState", depth: int, alpha: float, beta: float,
            maximizing: bool, my_id: str) -> float:
    if depth == 0 or state.is_terminal(my_id):
        return evaluate(state, my_id)

    directions = ["up", "down", "left", "right"]
    me = state.snakes.get(my_id)
    if me is None:
        return -INF  # we're dead

    if maximizing:
        best = -INF
        for d in directions:
            nx, ny = move_coord(me["head"], d)
            if not state.is_safe(nx, ny, my_id):
                continue
            child = state.apply_move(my_id, d)
            val   = minimax(child, depth - 1, alpha, beta, False, my_id)
            best  = max(best, val)
            alpha = max(alpha, best)
            if beta <= alpha:
                break
        return best if best > -INF else -INF

    else:
        # Minimizing: simulate one worst-case opponent move
        worst = INF
        opponents = [sid for sid in state.snakes if sid != my_id]
        if not opponents:
            return minimax(state, depth - 1, alpha, beta, True, my_id)

        opp_id = opponents[0]  # simplified: consider strongest opponent
        opp    = state.snakes[opp_id]
        moved  = False

        for d in directions:
            nx, ny = move_coord(opp["head"], d)
            if not state.is_safe(nx, ny, opp_id):
                continue
            child = state.apply_move(opp_id, d)
            val   = minimax(child, depth - 1, alpha, beta, True, my_id)
            worst = min(worst, val)
            beta  = min(beta, worst)
            moved = True
            if beta <= alpha:
                break

        return worst if moved else minimax(state, depth - 1, alpha, beta, True, my_id)


# ────────────────────────────────────────────────
#  HEURISTIC EVALUATION
# ────────────────────────────────────────────────

def evaluate(state: "GameState", my_id: str) -> float:
    me = state.snakes.get(my_id)
    if me is None:
        return -INF  # dead = worst

    score = 0.0

    # 1. Flood-fill space (survival + space control)
    space = flood_fill(state, me["head"]["x"], me["head"]["y"], my_id)
    score += W_SPACE * space

    # 2. Food proximity when hungry
    health = me["health"]
    if health <= HUNGER_THRESH and state.food:
        dist = min(manhattan(me["head"], f) for f in state.food)
        score += W_FOOD * (1.0 / (dist + 1)) * (HUNGER_THRESH - health)

    if health <= 25:
        score += W_HEALTH_CRIT * (25 - health)

    # 3. Aggression: reward being adjacent to smaller snake heads
    my_len = len(me["body"])
    for sid, opp in state.snakes.items():
        if sid == my_id:
            continue
        opp_len = len(opp["body"])
        dist    = manhattan(me["head"], opp["head"])
        if my_len > opp_len and dist <= 2:
            score += W_KILL * (3 - dist)      # closer = better kill chance
        elif opp_len > my_len and dist <= 2:
            score -= W_KILL * (3 - dist)      # we're the prey — flee

    # 4. Center control
    cx = (state.width  - 1) / 2
    cy = (state.height - 1) / 2
    center_dist = abs(me["head"]["x"] - cx) + abs(me["head"]["y"] - cy)
    score += W_CENTER * (1.0 / (center_dist + 1))

    return score


# ────────────────────────────────────────────────
#  FLOOD FILL (space counting with hazard penalty)
# ────────────────────────────────────────────────

def flood_fill(state: "GameState", sx: int, sy: int, my_id: str) -> float:
    visited = set()
    queue   = deque()
    queue.append((sx, sy))
    visited.add((sx, sy))
    total   = 0.0

    blocked = set()
    for sid, snake in state.snakes.items():
        for seg in snake["body"]:
            blocked.add((seg["x"], seg["y"]))

    while queue:
        x, y = queue.popleft()
        if (x, y) in state.hazards:
            total += W_HAZARD  # negative weight
        else:
            total += 1.0

        for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
            nx, ny = x + dx, y + dy
            if (nx, ny) in visited:
                continue
            if not (0 <= nx < state.width and 0 <= ny < state.height):
                continue
            if (nx, ny) in blocked:
                continue
            visited.add((nx, ny))
            queue.append((nx, ny))

    return total


# ────────────────────────────────────────────────
#  GAME STATE
# ────────────────────────────────────────────────

class GameState:
    def __init__(self, board: dict, me: dict, width: int, height: int):
        self.width   = width
        self.height  = height
        self.food    = [{"x": f["x"], "y": f["y"]} for f in board.get("food", [])]
        self.hazards = {(h["x"], h["y"]) for h in board.get("hazards", [])}

        # Build snake map: id → {head, body, health}
        self.snakes: dict[str, dict] = {}
        for s in board.get("snakes", []):
            self.snakes[s["id"]] = {
                "head":   dict(s["head"]),
                "body":   [dict(seg) for seg in s["body"]],
                "health": s["health"],
                "id":     s["id"],
            }
        # Ensure our own snake is present with fresh health
        self.snakes[me["id"]] = {
            "head":   dict(me["head"]),
            "body":   [dict(seg) for seg in me["body"]],
            "health": me["health"],
            "id":     me["id"],
        }

    def _copy_snakes(self):
        return {
            sid: {
                "head":   dict(s["head"]),
                "body":   [dict(seg) for seg in s["body"]],
                "health": s["health"],
                "id":     s["id"],
            }
            for sid, s in self.snakes.items()
        }

    def apply_move(self, snake_id: str, direction: str) -> "GameState":
        new = GameState.__new__(GameState)
        new.width   = self.width
        new.height  = self.height
        new.food    = list(self.food)
        new.hazards = self.hazards
        new.snakes  = self._copy_snakes()

        snake = new.snakes.get(snake_id)
        if snake is None:
            return new

        hx, hy  = move_coord(snake["head"], direction)
        new_head = {"x": hx, "y": hy}

        # Move body forward
        snake["body"].insert(0, new_head)
        snake["head"] = new_head

        # Eat food?
        ate = False
        for f in new.food:
            if f["x"] == hx and f["y"] == hy:
                new.food = [fi for fi in new.food if not (fi["x"] == hx and fi["y"] == hy)]
                snake["health"] = 100
                ate = True
                break

        if not ate:
            snake["body"].pop()
            snake["health"] -= 1
            if snake["health"] <= 0:
                del new.snakes[snake_id]
                return new

        # Hazard damage
        if (hx, hy) in new.hazards:
            snake["health"] -= 15
            if snake["health"] <= 0:
                del new.snakes[snake_id]

        return new

    def is_safe(self, x: int, y: int, snake_id: str) -> bool:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        for sid, snake in self.snakes.items():
            for i, seg in enumerate(snake["body"]):
                # Tail is safe (it will move)
                if i == len(snake["body"]) - 1:
                    continue
                if seg["x"] == x and seg["y"] == y:
                    return False
        # Avoid head-to-head with equal or larger snake
        my_len = len(self.snakes[snake_id]["body"]) if snake_id in self.snakes else 0
        for sid, snake in self.snakes.items():
            if sid == snake_id:
                continue
            if snake["head"]["x"] == x and snake["head"]["y"] == y:
                return False  # direct head collision — always bad
            # Check neighbours of their head (potential head-to-head next turn)
            for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
                nx2 = snake["head"]["x"] + dx
                ny2 = snake["head"]["y"] + dy
                if nx2 == x and ny2 == y and len(snake["body"]) >= my_len:
                    return False
        return True

    def is_terminal(self, my_id: str) -> bool:
        return my_id not in self.snakes


# ────────────────────────────────────────────────
#  HELPERS
# ────────────────────────────────────────────────

def move_coord(head: dict, direction: str) -> tuple[int, int]:
    x, y = head["x"], head["y"]
    if direction == "up":    return x, y + 1
    if direction == "down":  return x, y - 1
    if direction == "left":  return x - 1, y
    if direction == "right": return x + 1, y
    return x, y

def manhattan(a: dict, b: dict) -> int:
    return abs(a["x"] - b["x"]) + abs(a["y"] - b["y"])


# ────────────────────────────────────────────────
#  RUN
# ────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)