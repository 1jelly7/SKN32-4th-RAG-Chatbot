from __future__ import annotations

from typing import Literal

from app.agent.state import GraphState

GraphTransition = Literal["end", "router", "document", "database", "answer"]


def after_cache(state: GraphState) -> GraphTransition:
    ...


def after_router(state: GraphState) -> GraphTransition:
    ...


def build_graph() -> object:
    ...
