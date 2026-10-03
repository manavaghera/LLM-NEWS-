from pydantic import BaseModel, Field
from typing import Optional, List, Literal

class ChatContext(BaseModel):
    currentGroupId: Optional[str] = Field(default=None, max_length=50)
    currentDate: Optional[str] = Field(default=None, max_length=20)

class ChatHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)

class ChatStreamRequest(BaseModel):
    """Streaming chat: the browser keeps its own history and sends the recent turns with each message"""
    message: str = Field(min_length=1, max_length=2000)
    context: Optional[ChatContext] = None
    model: Optional[str] = Field(default=None, max_length=100)
    history: List[ChatHistoryItem] = Field(default_factory=list, max_length=12)
