from pydantic import BaseModel, Field


class ConversationMessageBase(BaseModel):
    external_message_id: str
    author: str
    text: str
    timestamp: str
    ordering: int


class ConversationMessageCreate(ConversationMessageBase):
    pass


class ConversationMessageRead(ConversationMessageBase):
    id: str
    conversation_id: str
    created_at: str

    model_config = {"from_attributes": True}


class ConversationBase(BaseModel):
    channel_id: str
    thread_ts: str
    title: str | None = None
    project_id: str | None = None
    source_id: str | None = None


class ConversationCreate(ConversationBase):
    messages: list[ConversationMessageCreate] = Field(default_factory=list)


class ConversationRead(ConversationBase):
    id: str
    created_at: str
    updated_at: str
    messages: list[ConversationMessageRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}
