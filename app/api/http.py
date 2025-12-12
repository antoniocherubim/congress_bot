import logging
import base64
import tempfile
import time
import hashlib
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Header, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional
from pydantic import BaseModel
from openai import OpenAI
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


class AudioTranscribeRequest(BaseModel):
    audio_base64: str


class AudioTranscribeResponse(BaseModel):
    text: str


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware que gera request_id único para cada requisição
    e adiciona aos logs e headers de resposta.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Gerar request_id único
        request_id = uuid4().hex[:16]  # 16 caracteres hexadecimais
        request.state.request_id = request_id
        
        # Medir tempo de execução
        start_time = time.time()
        
        # Processar requisição
        response = await call_next(request)
        
        # Adicionar header X-Request-ID
        response.headers["X-Request-ID"] = request_id
        
        # Calcular tempo de execução
        duration_ms = (time.time() - start_time) * 1000
        
        # Log da requisição
        logger.info(
            f"Request processado: request_id={request_id}, "
            f"method={request.method}, path={request.url.path}, "
            f"status={response.status_code}, duration_ms={duration_ms:.2f}"
        )
        
        return response


def require_api_key(config: AppConfig, x_api_key: Optional[str]) -> None:
    """
    Valida API key baseado no ambiente.
    
    Em produção (ENV=prod), sempre exige API key.
    Em desenvolvimento (ENV=dev), só exige se BOT_API_KEY estiver configurada.
    """
    expected_key = config.bot_api_key or ""
    
    if config.env == "prod":
        # Em produção, sempre exige
        if not x_api_key or x_api_key != expected_key:
            logger.warning("Tentativa de acesso não autorizado em PRODUÇÃO")
            raise HTTPException(status_code=401, detail="Invalid API key")
    else:
        # Em dev, só exige se BOT_API_KEY estiver configurada
        if expected_key and expected_key.strip():
            if x_api_key != expected_key:
                logger.warning("Tentativa de acesso não autorizado em DEV")
                raise HTTPException(status_code=401, detail="Invalid API key")
        else:
            logger.debug("BOT_API_KEY não configurada, aceitando requisição sem autenticação (modo desenvolvimento)")


def hash_number(number: str) -> str:
    """
    Retorna hash parcial do número para logs (primeiros 4 e últimos 4 dígitos).
    Ex: "5511999999999" -> "5511****9999"
    """
    if len(number) <= 8:
        return "****"
    return f"{number[:4]}****{number[-4:]}"


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
    
    # Adicionar middleware de request_id
    app.add_middleware(RequestIDMiddleware)

    @app.post("/chat", response_model=ChatResponse)
    def chat_endpoint(payload: ChatRequest, request: Request) -> ChatResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.info(
            f"Recebida requisição /chat: request_id={request_id}, "
            f"user_id={payload.user_id}, message_length={len(payload.message)}"
        )
        logger.debug(
            f"Payload completo: request_id={request_id}, user_id={payload.user_id}, "
            f"message_preview={payload.message[:80]}..."
        )
        
        start_time = time.time()
        try:
            result = engine.handle_message(
                user_id=payload.user_id,
                message_text=payload.message,
                request_id=request_id,
            )
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Resposta gerada: request_id={request_id}, user_id={payload.user_id}, "
                f"turns={result.get('turns', 0)}, duration_ms={duration_ms:.2f}"
            )
            logger.debug(
                f"Resposta completa: request_id={request_id}, user_id={payload.user_id}: "
                f"reply_preview={result.get('reply', '')[:100]}..."
            )
            
            return ChatResponse(**result)
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Erro ao processar mensagem: request_id={request_id}, "
                f"user_id={payload.user_id}, duration_ms={duration_ms:.2f}, "
                f"error={type(e).__name__}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Erro interno ao processar sua mensagem. Tente novamente mais tarde.",
            )

    @app.post("/whatsapp", response_model=WhatsAppResponse)
    def whatsapp_webhook(
        payload: WhatsAppMessage,
        request: Request,
        x_api_key: Optional[str] = Header(default=None, alias="X-API-KEY"),
    ) -> WhatsAppResponse:
        """
        Endpoint para receber mensagens do gateway WhatsApp.
        """
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Validar API key
        require_api_key(config, x_api_key)

        user_id = payload.number
        user_text = payload.text
        number_hash = hash_number(user_id)

        logger.info(
            f"Recebida requisição /whatsapp: request_id={request_id}, "
            f"number={number_hash}, message_length={len(user_text)}"
        )
        logger.debug(
            f"Payload completo: request_id={request_id}, number={number_hash}, "
            f"message_preview={user_text[:80]}..."
        )

        start_time = time.time()
        try:
            # Chamar o ChatbotEngine
            result = engine.handle_message(
                user_id=user_id,
                message_text=user_text,
                request_id=request_id,
            )

            reply_text = result.get("reply", "").strip()
            if not reply_text:
                # Resposta padrão em caso de problema
                logger.warning(
                    f"Resposta vazia gerada: request_id={request_id}, number={number_hash}, "
                    f"usando resposta padrão"
                )
                reply_text = (
                    "No momento não consegui gerar uma resposta. "
                    "Por favor, tente novamente em instantes."
                )

            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Resposta gerada: request_id={request_id}, number={number_hash}, "
                f"reply_length={len(reply_text)}, turns={result.get('turns', 0)}, "
                f"duration_ms={duration_ms:.2f}"
            )
            logger.debug(
                f"Resposta completa: request_id={request_id}, number={number_hash}: "
                f"reply_preview={reply_text[:100]}..."
            )

            return WhatsAppResponse(reply=reply_text)

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Erro ao processar mensagem do WhatsApp: request_id={request_id}, "
                f"number={number_hash}, duration_ms={duration_ms:.2f}, "
                f"error={type(e).__name__}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Erro interno ao processar sua mensagem. Tente novamente mais tarde.",
            )

    @app.post("/transcribe-audio", response_model=AudioTranscribeResponse)
    def transcribe_audio(
        payload: AudioTranscribeRequest,
        request: Request,
        x_api_key: Optional[str] = Header(default=None, alias="X-API-KEY"),
    ) -> AudioTranscribeResponse:
        """
        Endpoint para transcrever áudio usando OpenAI Whisper.
        """
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Validar API key
        require_api_key(config, x_api_key)

        start_time = time.time()
        try:
            # Validar tamanho do base64 ANTES de decodificar
            base64_length = len(payload.audio_base64)
            if base64_length > config.max_audio_base64_chars:
                logger.warning(
                    f"Payload base64 muito grande: request_id={request_id}, "
                    f"size={base64_length}, max={config.max_audio_base64_chars}"
                )
                raise HTTPException(
                    status_code=413,
                    detail=f"Payload muito grande. Tamanho máximo: {config.max_audio_base64_chars} caracteres (base64)."
                )
            
            # Decodificar áudio base64
            try:
                audio_data = base64.b64decode(payload.audio_base64)
            except Exception as decode_error:
                logger.error(
                    f"Erro ao decodificar base64: request_id={request_id}, "
                    f"error={type(decode_error).__name__}: {decode_error}"
                )
                raise HTTPException(
                    status_code=400,
                    detail="Erro ao decodificar base64. Verifique o formato do áudio."
                )
            
            # Validar tamanho após decodificar
            audio_size = len(audio_data)
            if audio_size > config.max_audio_bytes:
                logger.warning(
                    f"Áudio decodificado muito grande: request_id={request_id}, "
                    f"size={audio_size}, max={config.max_audio_bytes}"
                )
                raise HTTPException(
                    status_code=413,
                    detail=f"Áudio muito grande. Tamanho máximo: {config.max_audio_bytes / (1024*1024):.1f}MB."
                )
            
            logger.info(
                f"Recebido áudio para transcrição: request_id={request_id}, "
                f"base64_length={base64_length}, audio_size={audio_size} bytes"
            )
            
            # Criar arquivo temporário
            with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            try:
                # Criar cliente OpenAI
                openai_client = OpenAI(api_key=config.openai_api_key)
                
                # Transcrever usando Whisper (detecção automática de idioma)
                with open(temp_file_path, 'rb') as audio_file:
                    transcript = openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        # Não especificar language para detecção automática
                    )
                
                text = transcript.text.strip()
                
                duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Áudio transcrito com sucesso: request_id={request_id}, "
                    f"text_length={len(text)}, duration_ms={duration_ms:.2f}"
                )
                logger.debug(f"Transcrição: request_id={request_id}, text={text[:100]}...")
                
                return AudioTranscribeResponse(text=text)
                
            finally:
                # Limpar arquivo temporário
                import os
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
                    
        except HTTPException:
            # Re-lançar HTTPException sem modificar
            raise
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Erro ao transcrever áudio: request_id={request_id}, "
                f"duration_ms={duration_ms:.2f}, error={type(e).__name__}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Erro ao processar o áudio. Tente novamente.",
            )

    return app


app = create_app()

