import logging
import random
import time
from typing import List, Dict, Any, Optional
from openai import OpenAI, APITimeoutError, APIError, APIStatusError
from ..core.models import Message, Role
from ..config import AppConfig

logger = logging.getLogger(__name__)


class LanguageModelClient:
    """
    Encapsula chamadas ao modelo de linguagem (OpenAI).
    Facilita troca de provedor no futuro e centraliza tratamento de erros.
    Implementa timeout e retry com backoff exponencial + jitter.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        # Criar cliente OpenAI com timeout
        timeout_seconds = config.openai_timeout_ms / 1000.0
        self._client = OpenAI(
            api_key=config.openai_api_key,
            timeout=timeout_seconds,
        )
        self._max_retries = config.openai_max_retries
        self._retry_base_delay_ms = config.openai_retry_base_delay_ms

    def build_payload(self, system_prompt: str, messages: List[Message]) -> List[Dict[str, str]]:
        """
        Constrói a lista de mensagens no formato esperado pela API da OpenAI.
        """
        api_messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for m in messages:
            api_messages.append({"role": m.role.value, "content": m.content})
        return api_messages

    def _should_retry(self, error: Exception, attempt: int) -> bool:
        """
        Determina se um erro deve ser retentado.
        
        Retry para:
        - 429 (rate limit)
        - 500-599 (erros de servidor)
        - Timeout/connection errors
        
        Não retry para:
        - 400, 401, 403 (erros de cliente)
        - Tentativas excedidas
        """
        if attempt >= self._max_retries:
            return False
        
        # Timeout errors
        if isinstance(error, APITimeoutError) or isinstance(error, TimeoutError):
            return True
        
        # API errors com status code
        if isinstance(error, APIStatusError):
            status_code = error.status_code
            # Rate limit
            if status_code == 429:
                return True
            # Server errors (5xx)
            if 500 <= status_code < 600:
                return True
            # Client errors (4xx) - não retry
            if 400 <= status_code < 500:
                return False
        
        # API errors genéricos (pode ser erro de conexão)
        if isinstance(error, APIError):
            return True
        
        # Outros erros não são retentados
        return False

    def _calculate_retry_delay(self, attempt: int) -> float:
        """
        Calcula delay para retry com backoff exponencial + jitter.
        
        Delay = base_delay * (2 ^ attempt) + jitter
        Jitter é um valor aleatório entre 0 e 20% do delay calculado.
        """
        base_delay_seconds = self._retry_base_delay_ms / 1000.0
        exponential_delay = base_delay_seconds * (2 ** attempt)
        jitter = random.uniform(0, exponential_delay * 0.2)
        return exponential_delay + jitter

    def generate_reply(
        self, 
        system_prompt: str, 
        messages: List[Message],
        request_id: Optional[str] = None
    ) -> str:
        """
        Envia mensagens ao modelo e retorna apenas o texto da resposta.
        Implementa retry com backoff exponencial + jitter para erros transitórios.
        
        Args:
            system_prompt: Prompt do sistema
            messages: Lista de mensagens
            request_id: ID da requisição para logs (opcional)
            
        Returns:
            Texto da resposta do modelo
            
        Raises:
            ValueError: Se resposta estiver vazia
            APIError: Se todas as tentativas falharem
        """
        api_messages = self.build_payload(system_prompt, messages)
        request_id_str = f"request_id={request_id}, " if request_id else ""
        
        logger.debug(
            f"Chamando OpenAI API: {request_id_str}model={self._config.openai_model}, "
            f"num_messages={len(api_messages)}"
        )
        
        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                start_time = time.time()
                response = self._client.chat.completions.create(
                    model=self._config.openai_model,
                    messages=api_messages,
                )
                duration_ms = (time.time() - start_time) * 1000
                
                reply_text = response.choices[0].message.content.strip()
                
                # ASSERT: garantir que a resposta não está vazia
                if not reply_text or not reply_text.strip():
                    logger.error(
                        f"Resposta vazia recebida da OpenAI: {request_id_str}model={self._config.openai_model}, "
                        f"num_messages={len(api_messages)}"
                    )
                    raise ValueError(
                        "Resposta vazia recebida da OpenAI. "
                        "Isso indica um erro no modelo ou no parsing da resposta."
                    )
                
                if attempt > 0:
                    logger.info(
                        f"Chamada à OpenAI bem-sucedida após {attempt} retry(s): "
                        f"{request_id_str}model={self._config.openai_model}, duration_ms={duration_ms:.2f}"
                    )
                else:
                    logger.debug(
                        f"Resposta recebida da OpenAI: {request_id_str}reply_length={len(reply_text)} caracteres, "
                        f"duration_ms={duration_ms:.2f}"
                    )
                    logger.info(
                        f"Chamada à OpenAI bem-sucedida: {request_id_str}model={self._config.openai_model}"
                    )
                
                return reply_text
                
            except Exception as e:
                last_error = e
                
                # Verificar se deve retry
                if not self._should_retry(e, attempt):
                    # Não retry - logar e relançar
                    logger.error(
                        f"Erro não retentável ao chamar OpenAI: {request_id_str}model={self._config.openai_model}, "
                        f"attempt={attempt + 1}, error={type(e).__name__}: {e}",
                        exc_info=True,
                    )
                    raise
                
                # Calcular delay para retry
                delay_seconds = self._calculate_retry_delay(attempt)
                
                logger.warning(
                    f"Erro transitório ao chamar OpenAI (tentativa {attempt + 1}/{self._max_retries + 1}): "
                    f"{request_id_str}model={self._config.openai_model}, "
                    f"error={type(e).__name__}: {e}, retry_em={delay_seconds:.2f}s"
                )
                
                # Aguardar antes de retry (usar sleep síncrono, já que estamos em código síncrono)
                time.sleep(delay_seconds)
        
        # Todas as tentativas falharam
        logger.error(
            f"Todas as tentativas falharam ao chamar OpenAI: {request_id_str}model={self._config.openai_model}, "
            f"max_retries={self._max_retries}, last_error={type(last_error).__name__}: {last_error}",
            exc_info=True,
        )
        raise last_error or Exception("Erro desconhecido ao chamar OpenAI")

