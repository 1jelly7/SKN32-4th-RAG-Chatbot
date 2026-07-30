from fastapi import APIRouter
from app.schemas.chat import ChatRequest, ChatResponse
from app.agent.graph import build_graph

router = APIRouter(tags=["chat"])

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    state = {"question": request.question, "user_context": request.user_context, "session_id": request.session_id}
    result = await build_graph().ainvoke(state)
    return ChatResponse(answer=result.get("answer", ""), sources=result.get("sources", []), cached=result.get("cached", False))
