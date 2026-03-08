# Elite Battlesnake 🐍

A full Python Battlesnake server using **Minimax with Alpha-Beta Pruning** and a multi-objective heuristic.

## Setup

```bash
pip install -r requirements.txt
python main.py
```

Server runs on `http://0.0.0.0:8000`

---
## How to Run the Project

### Prerequisites

Make sure you have the following installed:

Python 3

pip

### Step 1: Install dependencies

Open a terminal in the project folder and run:

pip install -r requirements.txt

### Step 2: Start the Battlesnake server

Run:

python main.py
### Step 3: Confirm the server is running

You should see the server start on:

http://0.0.0.0:8000

For local testing in your browser, use:

http://localhost:8000
### Step 4: Connect it to Battlesnake

If you want to use it on the Battlesnake platform, your server must be publicly accessible.

You can do that by deploying it to a hosting platform like Render, Railway, Replit, or a VPS, or by exposing your local server using a tunneling tool like ngrok.

Example with ngrok:

ngrok http 8000

This will generate a public URL. Use that URL when registering your snake on play.battlesnake.com.

### Step 5: Register your snake

Go to play.battlesnake.com, create a new snake, and paste your public server URL there.

Once connected, Battlesnake will call your API endpoints automatically during games.
---

## Algorithm Overview

### 1. Minimax + Alpha-Beta Pruning
- Looks `MINIMAX_DEPTH` turns ahead (default: 4)
- **Maximizing** node = our snake's best move
- **Minimizing** node = worst-case opponent response
- Alpha-beta cuts off branches that can't affect the result, keeping it fast

### 2. Heuristic Evaluation (what the AI optimizes for)

| Factor | Weight | Description |
|---|---|---|
| Flood Fill Space | +2.0 | How many squares we can reach — core survival metric |
| Food Proximity | +1.5 | Prioritized when health ≤ 50 |
| Kill Position | +3.0 | Reward for being adjacent to a smaller snake's head |
| Flee Pressure | -3.0 | Penalty for being adjacent to a larger snake's head |
| Center Control | +0.5 | Mild reward for controlling the middle of the board |
| Hazard Tiles | -4.0 | Flood fill penalizes hazard zones |
| Critical Health | -3.0 | Penalty when health ≤ 25 |

### 3. Safety Filter
Before any move is even considered in Minimax, it's checked for:
- Wall collisions
- Body collisions (own and others)
- Potential head-to-head collisions with equal/larger snakes

### 4. Flood Fill
BFS-based space counting used in the heuristic. Hazard tiles are counted as negative space rather than fully blocked, so the snake avoids but doesn't fear them absolutely.

---

## Tuning

All weights are at the top of `main.py` — easy to tweak:

```python
MINIMAX_DEPTH = 4      # Increase for stronger play (exponentially slower)
W_SPACE       = 2.0    # Space control importance
W_FOOD        = 1.5    # Food seeking aggression
W_KILL        = 3.0    # Aggression toward smaller snakes
W_HAZARD      = -4.0   # Hazard avoidance
HUNGER_THRESH = 50     # Health level that triggers food-seeking
```

---

## Deployment

You can host this on any platform that supports Python web servers:
- **Replit** (free, easy)
- **Railway** / **Render** (free tier available)
- **Heroku**
- Any VPS with a public IP

Make sure port `8000` is publicly accessible and register your URL on [play.battlesnake.com](https://play.battlesnake.com).