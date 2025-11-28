from typing import List, Dict, Any
from openai import OpenAI
from ..core.models import Message, Role
from ..config import AppConfig


class LanguageModelClient:
    """
    Encapsula chamadas ao modelo de linguagem (OpenAI).
    Facilita troca de provedor no futuro e centraliza tratamento de erros.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._client = OpenAI(api_key=config.openai_api_key)

    def build_payload(self, system_prompt: str, messages: List[Message]) -> List[Dict[str, str]]:
        """
        Constrói a lista de mensagens no formato esperado pela API da OpenAI.
        """
        api_messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for m in messages:
            api_messages.append({"role": m.role.value, "content": m.content})
        return api_messages

    def generate_reply(self, system_prompt: str, messages: List[Message]) -> str:
        """
        Envia mensagens ao modelo e retorna apenas o texto da resposta.
        """
        api_messages = self.build_payload(system_prompt, messages)
        
        response = self._client.chat.completions.create(
            model=self._config.openai_model,
            messages=api_messages,
        )
        
        return response.choices[0].message.content.strip()

