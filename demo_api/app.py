"""Small in-memory API used as the target for the example suites.

It is intentionally realistic: token auth with two roles, server side money math,
status transitions, an expand parameter, and a budget rule that returns 402.
Replace this package with the real product's API when you adopt the framework.
"""
from __future__ import annotations

import itertools
import uuid
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Starter Demo API", version="1.0.0")

USERS = {
    "admin": {"password": "admin-secret", "role": "admin", "budget": 0.0},
    "member": {"password": "member-secret", "role": "member", "budget": 500.0},
}
TOKENS: dict[str, str] = {}
DB: dict[str, dict[str, Any]] = {"items": {}, "orders": {}}
_seq = itertools.count(1)


class TokenRequest(BaseModel):
    username: str
    password: str


class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    price: float = Field(gt=0)
    active: bool = True


class OrderLineIn(BaseModel):
    item_id: str
    quantity: int = Field(gt=0, le=99)


class OrderIn(BaseModel):
    lines: list[OrderLineIn] = Field(min_length=1)
    note: str | None = None


def _round(value: float) -> float:
    return round(value + 1e-9, 2)


def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    username = TOKENS.get(authorization.removeprefix("Bearer "))
    if username is None:
        raise HTTPException(status_code=401, detail="invalid token")
    return {"username": username, **USERS[username]}


def admin_only(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="admin role required")
    return user


@app.post("/auth/token")
def issue_token(body: TokenRequest):
    user = USERS.get(body.username)
    if user is None or user["password"] != body.password:
        raise HTTPException(status_code=401, detail="bad credentials")
    token = uuid.uuid4().hex
    TOKENS[token] = body.username
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}


@app.get("/", include_in_schema=False)
def ui():
    """A small page so the UI suites have something real to drive."""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "items": len(DB["items"]), "orders": len(DB["orders"])}


@app.post("/_test/reset", status_code=204)
def reset(_: dict = Depends(admin_only)):
    DB["items"].clear()
    DB["orders"].clear()
    USERS["member"]["budget"] = 500.0
    return None


@app.post("/items", status_code=201)
def create_item(body: ItemIn, _: dict = Depends(admin_only)):
    item = {"id": f"itm-{next(_seq)}", **body.model_dump()}
    DB["items"][item["id"]] = item
    return item


@app.get("/items")
def list_items(
    _: dict = Depends(current_user),
    name: str | None = None,
    active: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    rows = list(DB["items"].values())
    if name is not None:
        rows = [r for r in rows if name.lower() in r["name"].lower()]
    if active is not None:
        rows = [r for r in rows if r["active"] is active]
    return {"total": len(rows), "content": rows[offset : offset + limit]}


@app.get("/items/{item_id}")
def get_item(item_id: str, _: dict = Depends(current_user)):
    item = DB["items"].get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return item


@app.patch("/items/{item_id}")
def update_item(item_id: str, body: dict, _: dict = Depends(admin_only)):
    item = DB["items"].get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    if "price" in body and (not isinstance(body["price"], (int, float)) or body["price"] <= 0):
        raise HTTPException(status_code=422, detail="price must be greater than 0")
    item.update({k: v for k, v in body.items() if k in {"name", "price", "active"}})
    return item


@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: str, _: dict = Depends(admin_only)):
    if DB["items"].pop(item_id, None) is None:
        raise HTTPException(status_code=404, detail="item not found")
    return None


def _build_order(body: OrderIn, username: str) -> dict[str, Any]:
    lines = []
    for line in body.lines:
        item = DB["items"].get(line.item_id)
        if item is None:
            raise HTTPException(status_code=422, detail=f"unknown item {line.item_id}")
        if not item["active"]:
            raise HTTPException(status_code=422, detail=f"item {item['id']} is not active")
        lines.append(
            {
                "item_id": item["id"],
                "name": item["name"],
                "unit_price": item["price"],
                "quantity": line.quantity,
                "line_total": _round(item["price"] * line.quantity),
            }
        )
    return {
        "id": f"ord-{next(_seq)}",
        "owner": username,
        "status": "draft",
        "note": body.note,
        "lines": lines,
        "total_amount": _round(sum(line["line_total"] for line in lines)),
    }


def _view(order: dict[str, Any], expand: set[str]) -> dict[str, Any]:
    out = {k: v for k, v in order.items() if k != "lines"}
    out["line_count"] = len(order["lines"])
    out["lines"] = order["lines"] if "lines" in expand else []
    return out


@app.post("/orders", status_code=201)
def create_order(body: OrderIn, user: dict = Depends(current_user)):
    order = _build_order(body, user["username"])
    DB["orders"][order["id"]] = order
    return _view(order, {"lines"})


@app.get("/orders")
def list_orders(
    user: dict = Depends(current_user),
    status: str | None = None,
    expand: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    rows = list(DB["orders"].values())
    if user["role"] != "admin":
        rows = [r for r in rows if r["owner"] == user["username"]]
    if status is not None:
        rows = [r for r in rows if r["status"] == status]
    fields = set((expand or "").split(",")) - {""}
    return {"total": len(rows), "content": [_view(r, fields) for r in rows[offset : offset + limit]]}


@app.get("/orders/{order_id}")
def get_order(order_id: str, user: dict = Depends(current_user), expand: str | None = None):
    order = DB["orders"].get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    if user["role"] != "admin" and order["owner"] != user["username"]:
        raise HTTPException(status_code=403, detail="not your order")
    return _view(order, set((expand or "").split(",")) - {""})


@app.post("/orders/{order_id}/submit")
def submit_order(order_id: str, user: dict = Depends(current_user)):
    order = DB["orders"].get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    if order["owner"] != user["username"]:
        raise HTTPException(status_code=403, detail="not your order")
    if order["status"] != "draft":
        raise HTTPException(status_code=409, detail=f"cannot submit from {order['status']}")
    budget = USERS[order["owner"]]["budget"]
    if order["total_amount"] > budget:
        raise HTTPException(status_code=402, detail="insufficient budget")
    USERS[order["owner"]]["budget"] = _round(budget - order["total_amount"])
    order["status"] = "submitted"
    return _view(order, {"lines"})


@app.post("/orders/{order_id}/approve")
def approve_order(order_id: str, _: dict = Depends(admin_only)):
    order = DB["orders"].get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    if order["status"] != "submitted":
        raise HTTPException(status_code=409, detail=f"cannot approve from {order['status']}")
    order["status"] = "approved"
    return _view(order, {"lines"})


class AssistantQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=300)


@app.post("/assistant/answer")
def assistant_answer(body: AssistantQuestion, user: dict = Depends(current_user)):
    """A stand-in for an LLM feature.

    It answers in varying phrasing, grounded in the caller's real data, and
    refuses questions it has no data for. That is enough to exercise the shape
    of an LLM evaluation: non-deterministic wording, facts that must survive,
    and a refusal path.
    """
    question = body.question.lower()
    budget = USERS[user["username"]]["budget"]
    mine = [o for o in DB["orders"].values() if o["owner"] == user["username"]]
    phrasing = len(question) % 2

    if "budget" in question:
        text = (
            f"You have {budget:.2f} left in your budget."
            if phrasing == 0
            else f"Your remaining budget is {budget:.2f}."
        )
        return {"answer": text, "grounded_in": {"budget": budget}, "refused": False}

    if "order" in question:
        if not mine:
            return {
                "answer": "You have no orders yet.",
                "grounded_in": {"order_count": 0, "total": 0.0},
                "refused": False,
            }
        total = _round(sum(o["total_amount"] for o in mine))
        text = (
            f"You have {len(mine)} order(s) totalling {total:.2f}."
            if phrasing == 0
            else f"Across {len(mine)} order(s) your total is {total:.2f}."
        )
        return {"answer": text, "grounded_in": {"order_count": len(mine), "total": total}, "refused": False}

    return {
        "answer": "I can only answer questions about your budget and your orders.",
        "grounded_in": {},
        "refused": True,
    }


@app.get("/me/budget")
def my_budget(user: dict = Depends(current_user)):
    return {"username": user["username"], "budget": USERS[user["username"]]["budget"]}
