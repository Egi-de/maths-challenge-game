import os
import random
from typing import Optional, List

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mathgame.settings")
import django
django.setup()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from pydantic import BaseModel
from django.db import transaction
from game.models import User, Question, Score

app = FastAPI(title="Math Challenge Game API")

# =======================
# Utility Functions
# =======================
OPS = ["+", "-", "*", "/"]

def generate_arithmetic_problem(difficulty: int = 1):
    if difficulty == 1:
        a, b = random.randint(1, 10), random.randint(1, 10)
        op = random.choice(["+", "-"])
    elif difficulty == 2:
        a, b = random.randint(5, 20), random.randint(5, 20)
        op = random.choice(["+", "-", "*"])
    else:
        a, b = random.randint(10, 50), random.randint(1, 20)
        op = random.choice(OPS)
        if op == "/":
            b = random.randint(1, 10)
            a = a * b
    expr = f"{a} {op} {b}"
    return expr, float(eval(expr))

def compute_points(correct, difficulty, time_taken):
    if not correct:
        return 0
    base = 10 * difficulty
    bonus = max(0, int((5.0 - time_taken) * 2))
    return base + bonus

# =======================
# Schemas
# =======================
class StartRequest(BaseModel):
    name: str
    email: str
    difficulty: Optional[int] = 1

class StartResponse(BaseModel):
    user_id: int
    question_id: int
    question_text: str
    difficulty: int
    total_score: int

class PlayRequest(BaseModel):
    user_id: int
    question_id: int
    answer: float
    time_taken: Optional[float] = 0.0

class PlayResponse(BaseModel):
    correct: bool
    points_awarded: int
    total_score: int
    next_question_id: int
    next_question_text: str

class ScoreResponse(BaseModel):
    user_id: int
    total_score: int
    recent: list

class LeaderboardEntry(BaseModel):
    rank: int
    name: str
    score: int

class LeaderboardResponse(BaseModel):
    leaderboard: List[LeaderboardEntry]

# =======================
# WebSocket Manager
# =======================
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except:
                pass

manager = ConnectionManager()

async def broadcast_leaderboard():
    users = User.objects.order_by("-total_score")[:10]
    leaderboard = [{"rank": i+1, "name": u.name, "score": u.total_score} for i, u in enumerate(users)]
    await manager.broadcast({"type": "leaderboard_update", "leaderboard": leaderboard})

# =======================
# API Endpoints
# =======================
@app.post("/start", response_model=StartResponse)
def start_game(req: StartRequest):
    user, _ = User.objects.get_or_create(email=req.email, defaults={"name": req.name})
    q_text, q_ans = generate_arithmetic_problem(req.difficulty)
    q = Question.objects.create(text=q_text, answer=q_ans, difficulty=req.difficulty)
    return StartResponse(
        user_id=user.id,
        question_id=q.id,
        question_text=q.text,
        difficulty=q.difficulty,
        total_score=user.total_score
    )

@app.post("/play", response_model=PlayResponse)
@transaction.atomic
def play(req: PlayRequest, background_tasks: BackgroundTasks):
    try:
        user = User.objects.get(id=req.user_id)
        question = Question.objects.get(id=req.question_id)
    except (User.DoesNotExist, Question.DoesNotExist):
        raise HTTPException(status_code=404, detail="User or Question not found")

    correct = abs(req.answer - question.answer) < 1e-6
    points = compute_points(correct, question.difficulty, req.time_taken)
    Score.objects.create(user=user, question=question, points=points, time_taken=req.time_taken)
    user.total_score += points
    user.save()

    background_tasks.add_task(broadcast_leaderboard)

    next_q_text, next_q_ans = generate_arithmetic_problem(question.difficulty)
    next_q = Question.objects.create(text=next_q_text, answer=next_q_ans, difficulty=question.difficulty)

    return PlayResponse(
        correct=correct,
        points_awarded=points,
        total_score=user.total_score,
        next_question_id=next_q.id,
        next_question_text=next_q.text
    )

@app.get("/score/{user_id}", response_model=ScoreResponse)
def get_score(user_id: int):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise HTTPException(status_code=404, detail="User not found")

    recent_scores = list(user.scores.order_by("-created_at").values("points", "time_taken", "created_at")[:10])
    for s in recent_scores:
        s["created_at"] = s["created_at"].isoformat()

    return ScoreResponse(user_id=user.id, total_score=user.total_score, recent=recent_scores)

@app.get("/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard():
    users = User.objects.order_by("-total_score")[:10]
    leaderboard = [{"rank": i+1, "name": u.name, "score": u.total_score} for i, u in enumerate(users)]
    return LeaderboardResponse(leaderboard=leaderboard)

@app.websocket("/ws/leaderboard")
async def leaderboard_ws(websocket: WebSocket):
    await manager.connect(websocket)
    await broadcast_leaderboard()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
