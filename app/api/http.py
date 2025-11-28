from fastapi import FastAPI
from pydantic import BaseModel
from ..config import AppConfig
from ..core.engine import ChatbotEngine


class ChatRequest(BaseModel):
    user_id: str
    message: str


class ChatResponse(BaseModel):
    user_id: str
    reply: str
    turns: int


def create_app() -> FastAPI:
    """
    Cria a aplicação FastAPI e injeta dependências principais (config + engine).
    """
    config = AppConfig.load_from_env()
    engine = ChatbotEngine(config=config)

    app = FastAPI(
        title="Event Chatbot API",
        version="0.1.0",
        description="API mínima para o chatbot do evento (MVP).",
    )

    @app.post("/chat", response_model=ChatResponse)
    def chat_endpoint(payload: ChatRequest) -> ChatResponse:
        result = engine.handle_message(
            user_id=payload.user_id,
            message_text=payload.message,
        )
        return ChatResponse(**result)

    return app


app = create_app()

