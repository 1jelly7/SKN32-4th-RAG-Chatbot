from pydantic import BaseModel, Field
class Source(BaseModel):
    id: str
    title: str = ""
class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    session_id: str = "default"
    user_context: dict = {}
class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = []
    cached: bool = False
