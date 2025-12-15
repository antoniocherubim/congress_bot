import logging
import base64
import tempfile
import time
import hashlib
import json
import os
import urllib.request
import urllib.error
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Header, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, List
from pydantic import BaseModel
from openai import OpenAI
from ..config import AppConfig
from ..core.engine import ChatbotEngine

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    user_id: str
    message: str
    context_type: Optional[str] = None  # Tipo de contexto (ex: "default", "event_info", "registration")


class ChatResponse(BaseModel):
    user_id: str
    reply: str
    turns: int


class WhatsAppMessage(BaseModel):
    number: str
    text: str
    context_type: Optional[str] = None  # Tipo de contexto (ex: "default", "event_info", "registration")


class WhatsAppResponse(BaseModel):
    reply: str


class AudioTranscribeRequest(BaseModel):
    audio_base64: str


class AudioTranscribeResponse(BaseModel):
    text: str


class MessageHistoryItem(BaseModel):
    role: str
    content: str


class ChatTurnHistory(BaseModel):
    user_message: MessageHistoryItem
    assistant_message: MessageHistoryItem


class HistoryResponse(BaseModel):
    user_id: str
    turns: int
    history: List[ChatTurnHistory]
    registration_step: str
    registration_data: dict


class DisconnectResponse(BaseModel):
    ok: bool
    disconnected: bool
    clear_auth: bool


class QRStatusResponse(BaseModel):
    ok: bool
    whatsapp_connected: bool
    has_qr: bool
    qr: Optional[str] = None
    qr_created_at: Optional[str] = None


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

    def fetch_json(url: str, timeout_s: float) -> dict:
        """
        Fetch JSON via stdlib (sem dependências extras).
        Retorna dict. Levanta exceção em falhas de rede/HTTP/parse.
        """
        req = urllib.request.Request(
            url,
            method="GET",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read()
            try:
                return json.loads(body.decode("utf-8"))
            except Exception as e:
                raise RuntimeError(f"Resposta não-JSON em {url}: {e}") from e

    def post_json(url: str, payload: dict, timeout_s: float, headers: Optional[dict] = None) -> dict:
        """
        POST JSON via stdlib (sem dependências extras).
        Retorna dict. Levanta exceção em falhas de rede/HTTP/parse.
        """
        data = json.dumps(payload).encode("utf-8")
        req_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if headers:
            req_headers.update(headers)

        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers=req_headers,
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read()
            try:
                return json.loads(body.decode("utf-8"))
            except Exception as e:
                raise RuntimeError(f"Resposta não-JSON em {url}: {e}") from e

    def _normalize_base_url(url: str) -> str:
        url = (url or "").strip()
        if url.endswith("/"):
            url = url[:-1]
        return url

    def gateway_base_url_candidates() -> List[str]:
        """
        Retorna uma lista de URLs base possíveis para o gateway.
        Em alguns ambientes, o hostname do serviço pode ser 'gateway' ou o container_name (ex: 'biosummit-gateway').
        """
        env_url = os.environ.get("GATEWAY_URL")
        env_health_url = os.environ.get("GATEWAY_HEALTH_URL")

        # Se o usuário configurar explicitamente, damos prioridade.
        if env_health_url and env_health_url.strip():
            # Converter /health -> base
            u = _normalize_base_url(env_health_url)
            if u.endswith("/health"):
                u = u[: -len("/health")]
            return [_normalize_base_url(u)]

        if env_url and env_url.strip():
            return [_normalize_base_url(env_url)]

        # Defaults: dentro do docker-compose, tente primeiro o service name, depois o container_name.
        if config.env == "prod":
            return ["http://gateway:3333", "http://biosummit-gateway:3333"]

        # Em dev local, pode existir gateway exposto no host.
        return ["http://localhost:3333", "http://gateway:3333", "http://biosummit-gateway:3333"]

    @app.get("/health")
    def health_check():
        """
        Endpoint de health check para monitoramento e Docker healthchecks.
        """
        try:
            # Verificar conexão com Redis (se configurado)
            redis_ok = True
            if config.redis_url and config.redis_url.strip():
                try:
                    from redis import Redis
                    redis_client = Redis.from_url(config.redis_url)
                    redis_client.ping()
                    redis_ok = True
                except Exception as e:
                    logger.warning(f"Redis health check falhou: {e}")
                    redis_ok = False
            
            # Verificar conexão com banco de dados
            db_ok = True
            try:
                from ..storage.database import create_engine_from_url
                engine = create_engine_from_url(config.database_url)
                with engine.connect() as conn:
                    from sqlalchemy import text
                    conn.execute(text("SELECT 1"))
                db_ok = True
            except Exception as e:
                logger.warning(f"Database health check falhou: {e}")
                db_ok = False

            # Verificar health do gateway WhatsApp (tenta múltiplos hosts possíveis)
            gateway_reachable = False
            gateway_payload: dict = {}
            gateway_used_url: Optional[str] = None
            gateway_timeout_s = 2.0
            gateway_start = time.time()
            last_gateway_error: Optional[str] = None
            for base_url in gateway_base_url_candidates():
                gateway_health_url = f"{base_url}/health"
                try:
                    gateway_payload = fetch_json(gateway_health_url, timeout_s=gateway_timeout_s)
                    gateway_reachable = True
                    gateway_used_url = gateway_health_url
                    break
                except Exception as e:
                    last_gateway_error = str(e)
                    logger.warning(f"Gateway health check falhou: url={gateway_health_url}, error={e}")
                    continue

            if not gateway_reachable:
                gateway_payload = {"error": last_gateway_error or "Gateway indisponível"}
            gateway_duration_ms = (time.time() - gateway_start) * 1000

            gateway_whatsapp_connected = bool(gateway_payload.get("whatsapp_connected")) if gateway_reachable else False
            
            # Status geral
            status = (
                "healthy"
                if (redis_ok and db_ok and gateway_reachable and gateway_whatsapp_connected)
                else "degraded"
            )
            
            return {
                "status": status,
                "redis": "ok" if redis_ok else "error",
                "database": "ok" if db_ok else "error",
                "gateway": {
                    "reachable": gateway_reachable,
                    "whatsapp_connected": gateway_whatsapp_connected,
                    "health": gateway_payload,
                    "url": gateway_used_url,
                    "duration_ms": round(gateway_duration_ms, 2),
                },
            }
        except Exception as e:
            logger.error(f"Erro no health check: {e}")
            return {
                "status": "error",
                "error": str(e),
            }, 500

    @app.post("/ops/whatsapp/disconnect", response_model=DisconnectResponse)
    def ops_disconnect_whatsapp(
        request: Request,
        clear_auth: bool = True,
        x_api_key: Optional[str] = Header(default=None, alias="X-API-KEY"),
    ) -> DisconnectResponse:
        """
        Endpoint operacional para desconectar o WhatsApp via gateway.

        - Valida X-API-KEY (mesma regra do /whatsapp).
        - Faz proxy interno para o gateway em http://gateway:3333/admin/disconnect.
        - clear_auth=true (padrão) limpa auth_info para forçar QR code na próxima inicialização.
        """
        request_id = getattr(request.state, "request_id", "unknown")

        # Validar API key
        require_api_key(config, x_api_key)

        start_time = time.time()
        try:
            resp: Optional[dict] = None
            used_url: Optional[str] = None
            last_error: Optional[Exception] = None

            for base_url in gateway_base_url_candidates():
                disconnect_url = f"{base_url}/admin/disconnect"
                try:
                    resp = post_json(
                        disconnect_url,
                        payload={"clear_auth": bool(clear_auth)},
                        timeout_s=5.0,
                        headers={"X-API-KEY": config.bot_api_key} if config.bot_api_key else None,
                    )
                    used_url = disconnect_url
                    break
                except Exception as e:
                    last_error = e
                    continue

            if resp is None:
                raise last_error or RuntimeError("Falha ao desconectar (gateway indisponível)")

            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"WhatsApp disconnect solicitado: request_id={request_id}, "
                f"url={used_url}, duration_ms={duration_ms:.2f}, clear_auth={clear_auth}"
            )
            return DisconnectResponse(
                ok=bool(resp.get("ok", True)),
                disconnected=bool(resp.get("disconnected", True)),
                clear_auth=bool(resp.get("clear_auth", clear_auth)),
            )
        except urllib.error.HTTPError as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Erro HTTP ao desconectar no gateway: request_id={request_id}, "
                f"status={e.code}, duration_ms={duration_ms:.2f}"
            )
            raise HTTPException(status_code=502, detail=f"Gateway respondeu {e.code} no disconnect")
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Erro ao desconectar no gateway: request_id={request_id}, "
                f"duration_ms={duration_ms:.2f}, "
                f"error={type(e).__name__}: {e}",
                exc_info=True,
            )
            raise HTTPException(status_code=502, detail="Falha ao solicitar disconnect ao gateway")

    @app.get("/ops/whatsapp/qr", response_model=QRStatusResponse)
    def ops_get_whatsapp_qr(
        request: Request,
        x_api_key: Optional[str] = Header(default=None, alias="X-API-KEY"),
    ) -> QRStatusResponse:
        """
        Endpoint operacional para obter o QR code atual (string) para exibição no painel web.

        - Valida X-API-KEY (mesma regra do /whatsapp).
        - Faz proxy interno para o gateway em /admin/qr.
        """
        request_id = getattr(request.state, "request_id", "unknown")

        # Validar API key
        require_api_key(config, x_api_key)

        start_time = time.time()
        try:
            resp: Optional[dict] = None
            used_url: Optional[str] = None
            last_error: Optional[Exception] = None

            for base_url in gateway_base_url_candidates():
                qr_url = f"{base_url}/admin/qr"
                try:
                    # Como é GET, usamos fetch_json
                    # Enviamos X-API-KEY do serviço para o gateway
                    req = urllib.request.Request(
                        qr_url,
                        method="GET",
                        headers={
                            "Accept": "application/json",
                            **({"X-API-KEY": config.bot_api_key} if config.bot_api_key else {}),
                        },
                    )
                    with urllib.request.urlopen(req, timeout=5.0) as r:
                        body = r.read()
                        resp = json.loads(body.decode("utf-8"))
                    used_url = qr_url
                    break
                except Exception as e:
                    last_error = e
                    continue

            if resp is None:
                raise last_error or RuntimeError("Falha ao obter QR (gateway indisponível)")

            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"QR consultado: request_id={request_id}, url={used_url}, duration_ms={duration_ms:.2f}"
            )

            return QRStatusResponse(
                ok=bool(resp.get("ok", True)),
                whatsapp_connected=bool(resp.get("whatsapp_connected", False)),
                has_qr=bool(resp.get("has_qr", False)),
                qr=resp.get("qr"),
                qr_created_at=resp.get("qr_created_at"),
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Erro ao obter QR no gateway: request_id={request_id}, duration_ms={duration_ms:.2f}, "
                f"error={type(e).__name__}: {e}",
                exc_info=True,
            )
            raise HTTPException(status_code=502, detail="Falha ao obter QR do gateway")

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
                context_type=payload.context_type,
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
                context_type=payload.context_type,
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

    @app.get("/history/{user_id}", response_model=HistoryResponse)
    def get_history(
        user_id: str,
        request: Request,
    ) -> HistoryResponse:
        """
        Endpoint para recuperar o histórico de conversas de um usuário.
        Retorna todas as mensagens trocadas entre o usuário e o bot.
        
        Nota: Este endpoint não requer autenticação, similar ao endpoint /chat.
        Em produção, considere adicionar autenticação se necessário.
        """
        request_id = getattr(request.state, "request_id", "unknown")
        
        number_hash = hash_number(user_id) if user_id.isdigit() else user_id[:4] + "****"
        
        logger.info(
            f"Recebida requisição /history: request_id={request_id}, "
            f"user_id={number_hash}"
        )
        
        start_time = time.time()
        try:
            # Recuperar histórico do engine
            result = engine.get_conversation_history(user_id=user_id)
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Histórico recuperado: request_id={request_id}, "
                f"user_id={number_hash}, turns={result.get('turns', 0)}, "
                f"duration_ms={duration_ms:.2f}"
            )
            
            return HistoryResponse(**result)
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Erro ao recuperar histórico: request_id={request_id}, "
                f"user_id={number_hash}, duration_ms={duration_ms:.2f}, "
                f"error={type(e).__name__}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Erro interno ao recuperar histórico. Tente novamente mais tarde.",
            )

    return app


app = create_app()

