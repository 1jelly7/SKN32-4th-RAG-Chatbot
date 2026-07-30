from __future__ import annotations

from app.agent.state import GraphState, Route


def route_question(question: str) -> Route:
    ...


async def cache_lookup(state: GraphState) -> GraphState:
    ...


async def router(state: GraphState) -> GraphState:
    ...


async def document_retrieval(state: GraphState) -> GraphState:
    ...


async def database_retrieval(state: GraphState) -> GraphState:
    ...


async def evidence_eval(state: GraphState) -> GraphState:
    ...


async def answer_synthesis(state: GraphState) -> GraphState:
    ...


async def cache_write(state: GraphState) -> GraphState:
    ...
