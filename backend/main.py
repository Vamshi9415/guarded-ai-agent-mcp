"""
main.py – FastAPI entry point for Guarded AI Agent
Exposes:
  POST /chat                        – send a user message, get agent response
  GET  /api/tools                   – list tools discovered from MCP server
  GET  /api/rules                   – list all guardrail rules
  POST /api/rules                   – create a new rule
  PATCH /api/rules/{id}/toggle      – enable/disable a rule
  DELETE /api/rules/{id}            – delete a rule
  GET  /api/approvals               – list pending approvals
  POST /api/approvals/{id}/approve  – approve a pending request
  POST /api/approvals/{id}/deny     – deny a pending request
  GET  /api/logs                    – recent tool-call audit logs
  GET  /                            – serve admin dashboard HTML
"""

import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

if __package__ in (None, ""):
    import sys
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.agent import GuardedAgent
from backend.db import (
    create_rule, get_all_rules, toggle_rule, delete_rule,
    get_pending_approvals, resolve_approval, get_recent_logs,
)

# ---------------------------------------------------------------------------
# Lifespan – start/stop the GuardedAgent alongside FastAPI
# ---------------------------------------------------------------------------

_agent: Optional[GuardedAgent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent
    _agent = GuardedAgent()
    await _agent.start()
    yield
    await _agent.stop()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Guarded AI Agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str


class RuleCreate(BaseModel):
    tool_name: str           # exact tool name, or "*" for all tools
    action: str              # block | require_approval | input_validation | token_budget
    reason: str = ""
    config: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# /chat
# ---------------------------------------------------------------------------

@app.post("/chat")
async def chat(req: ChatRequest):
    if _agent is None:
        raise HTTPException(503, "Agent not initialised yet")
    try:
        reply = await _agent.run(req.message)
        return {"response": reply}
    except Exception as exc:
        raise HTTPException(500, str(exc))


# ---------------------------------------------------------------------------
# /api/tools  – live tool list from the running MCP server
# ---------------------------------------------------------------------------

@app.get("/api/tools")
async def list_tools():
    if _agent is None:
        raise HTTPException(503, "Agent not initialised yet")
    tools = await _agent.list_tools()
    return {"tools": tools}


# ---------------------------------------------------------------------------
# /api/rules  – CRUD for guardrail rules stored in MongoDB
# ---------------------------------------------------------------------------

@app.get("/api/rules")
def list_rules():
    return {"rules": get_all_rules()}


@app.post("/api/rules", status_code=201)
def add_rule(body: RuleCreate):
    rule_id = create_rule(body.model_dump())
    return {"id": rule_id}


@app.patch("/api/rules/{rule_id}/toggle")
def toggle(rule_id: str):
    if not toggle_rule(rule_id):
        raise HTTPException(404, "Rule not found")
    return {"status": "toggled"}


@app.delete("/api/rules/{rule_id}")
def remove_rule(rule_id: str):
    if not delete_rule(rule_id):
        raise HTTPException(404, "Rule not found")
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# /api/approvals  – human-in-the-loop approval queue
# ---------------------------------------------------------------------------

@app.get("/api/approvals")
def list_approvals():
    return {"approvals": get_pending_approvals()}


@app.post("/api/approvals/{approval_id}/approve")
def approve(approval_id: str):
    if not resolve_approval(approval_id, "approved"):
        raise HTTPException(404, "Approval not found or already resolved")
    return {"status": "approved"}


@app.post("/api/approvals/{approval_id}/deny")
def deny(approval_id: str):
    if not resolve_approval(approval_id, "denied"):
        raise HTTPException(404, "Approval not found or already resolved")
    return {"status": "denied"}


# ---------------------------------------------------------------------------
# /api/logs  – audit trail of every tool call
# ---------------------------------------------------------------------------

@app.get("/api/logs")
def logs(limit: int = 50):
    return {"logs": get_recent_logs(limit)}


# ---------------------------------------------------------------------------
# /  – serve the single-file admin dashboard
# ---------------------------------------------------------------------------

DASHBOARD = Path(__file__).parent.parent / "dashboard" / "index.html"


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    if DASHBOARD.exists():
        return HTMLResponse(content=DASHBOARD.read_text(encoding="utf-8"))
    return HTMLResponse(
        "<h1>Dashboard not found</h1><p>Place <code>dashboard/index.html</code> in the repo root.</p>",
        status_code=404,
    )
