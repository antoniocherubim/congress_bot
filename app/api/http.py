import logging
from fastapi import FastAPI, HTTPException, Header
from typing import Optional
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


class WhatsAppMessage(BaseModel):
    number: str
    text: str


class WhatsAppResponse(BaseModel):
    reply: str


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

    @app.post("/whatsapp", response_model=WhatsAppResponse)
    def whatsapp_webhook(
        payload: WhatsAppMessage,
        x_api_key: Optional[str] = Header(default=None, alias="X-API-KEY"),
    ) -> WhatsAppResponse:
        """
        Endpoint para receber mensagens do gateway WhatsApp.
        """
        # Autenticação simples via header X-API-KEY
        expected_key = config.bot_api_key or ""
        if expected_key and x_api_key != expected_key:
            logger.warning(
                f"Tentativa de acesso não autorizado ao endpoint /whatsapp: "
                f"key_fornecida={'***' if x_api_key else 'nenhuma'}"
            )
            raise HTTPException(status_code=401, detail="Invalid API key")

        user_id = payload.number
        user_text = payload.text

        logger.info(
            f"Recebida requisição /whatsapp para number={user_id}, "
            f"message_length={len(user_text)}"
        )
        logger.debug(
            f"Payload completo: number={user_id}, "
            f"message_preview={user_text[:80]}..."
        )

        try:
            # Chamar o ChatbotEngine
            result = engine.handle_message(user_id=user_id, message_text=user_text)

            reply_text = result.get("reply", "").strip()
            if not reply_text:
                # Resposta padrão em caso de problema
                logger.warning(
                    f"Resposta vazia gerada para number={user_id}, "
                    f"usando resposta padrão"
                )
                reply_text = (
                    "No momento não consegui gerar uma resposta. "
                    "Por favor, tente novamente em instantes."
                )

            logger.info(
                f"Resposta gerada para number={user_id}, "
                f"reply_length={len(reply_text)}, turns={result.get('turns', 0)}"
            )
            logger.debug(
                f"Resposta completa para number={user_id}: "
                f"reply_preview={reply_text[:100]}..."
            )

            return WhatsAppResponse(reply=reply_text)

        except Exception as e:
            logger.error(
                f"Erro ao processar mensagem do WhatsApp para number={user_id}: "
                f"{type(e).__name__}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Erro interno ao processar sua mensagem. Tente novamente mais tarde.",
            )

    return app


app = create_app()

