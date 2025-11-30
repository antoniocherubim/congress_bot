import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ..config import AppConfig
from ..core.engine import ChatbotEngine

logger = logging.getLogger(__name__)


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
        logger.info(
            f"Recebida requisição /chat para user_id={payload.user_id}, "
            f"message_length={len(payload.message)}"
        )
        logger.debug(
            f"Payload completo: user_id={payload.user_id}, "
            f"message_preview={payload.message[:80]}..."
        )
        
        try:
            result = engine.handle_message(
                user_id=payload.user_id,
                message_text=payload.message,
            )
            
            logger.info(
                f"Resposta gerada para user_id={payload.user_id}, "
                f"turns={result.get('turns', 0)}"
            )
            logger.debug(
                f"Resposta completa para user_id={payload.user_id}: "
                f"reply_preview={result.get('reply', '')[:100]}..."
            )
            
            return ChatResponse(**result)
        except Exception as e:
            logger.error(
                f"Erro ao processar mensagem para user_id={payload.user_id}: {type(e).__name__}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Erro interno ao processar sua mensagem. Tente novamente mais tarde.",
            )

    return app


app = create_app()

