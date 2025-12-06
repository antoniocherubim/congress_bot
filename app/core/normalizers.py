"""
Funções para normalizar e validar dados de entrada do usuário.
"""
import re
import unicodedata
from typing import Tuple, Optional


# Mapeamento de UFs brasileiras
UF_MAP = {
    "AC": "AC", "AL": "AL", "AP": "AP", "AM": "AM", "BA": "BA", "CE": "CE",
    "DF": "DF", "ES": "ES", "GO": "GO", "MA": "MA", "MT": "MT", "MS": "MS",
    "MG": "MG", "PA": "PA", "PB": "PB", "PR": "PR", "PE": "PE", "PI": "PI",
    "RJ": "RJ", "RN": "RN", "RS": "RS", "RO": "RO", "RR": "RR", "SC": "SC",
    "SP": "SP", "SE": "SE", "TO": "TO",
}


def strip_accents(text: str) -> str:
    """
    Remove acentos de uma string.
    """
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text)
        if unicodedata.category(ch) != "Mn"
    )


def normalize_cpf(raw: str) -> Optional[str]:
    """
    Normaliza CPF removendo caracteres não numéricos.
    Retorna apenas os 11 dígitos ou None se inválido.
    """
    # Remove tudo que não é dígito
    digits = re.sub(r'\D', '', raw)
    
    # Deve ter exatamente 11 dígitos
    if len(digits) != 11:
        return None
    
    # Validação básica: não pode ser todos os dígitos iguais
    if len(set(digits)) == 1:
        return None
    
    return digits


def normalize_cpf(raw: str) -> Optional[str]:
    """
    Normaliza CPF removendo caracteres não numéricos.
    Retorna apenas os 11 dígitos ou None se inválido.
    
    Aceita formatos como:
    - "123.456.789-10" → "12345678910"
    - "12345678910" → "12345678910"
    """
    # Remove tudo que não é dígito
    digits = re.sub(r'\D', '', raw)
    
    # Deve ter exatamente 11 dígitos
    if len(digits) != 11:
        return None
    
    # Validação básica: não pode ser todos os dígitos iguais (ex: 111.111.111-11)
    if len(set(digits)) == 1:
        return None
    
    return digits


def normalize_phone(raw: str) -> Optional[str]:
    """
    Extrai dígitos de um telefone brasileiro e formata como +55 DD XXXXX-XXXX.
    
    Retorna None se não encontrar nada com tamanho plausível.
    
    Exemplos:
        "meu número é 41 99938-0969" → "+55 41 99938-0969"
        "41999380969" → "+55 41 99938-0969"
    """
    # Remove tudo que não é número
    digits = re.sub(r"\D", "", raw)
    
    # Remove zero inicial de DDI se vier com 055 por exemplo
    if digits.startswith("55") and len(digits) > 11:
        digits = digits[2:]
    
    # Tamanho esperado (celular com DDD): 11 dígitos
    if len(digits) != 11:
        return None
    
    ddd = digits[:2]
    num = digits[2:]
    return f"+55 {ddd} {num[:5]}-{num[5:]}"


def normalize_city_state(raw: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Tenta extrair cidade e UF a partir de uma string.
    
    Aceita formatos como:
    - "Londrina/PR"
    - "moro em Londrina/PARANÁ"
    - "São Paulo/SP"
    - "Londrina PR"
    
    Retorna (cidade, uf) ou (cidade, None) se não encontrar UF.
    """
    text = raw.strip()
    
    # Remove prefixos comuns usando regex (case-insensitive)
    prefix_pattern = re.compile(
        r"^(moro em|sou de|sou da|vivo em|vivo na|vivo no|sou do|sou da cidade de|moro na|moro no)\s+",
        re.IGNORECASE
    )
    text = prefix_pattern.sub("", text).strip()
    
    # Tenta encontrar padrão "Cidade/UF"
    if "/" in text:
        parts = text.split("/", 1)
        city_part = parts[0].strip()
        state_part = parts[1].strip()
        
        city = city_part.title()
        state_clean = strip_accents(state_part).upper().strip()
        
        # Se vier tipo PARANA → vira PR
        # Heurística simples: se tiver 2 letras e estiver no UF_MAP, usa direto
        if len(state_clean) == 2 and state_clean in UF_MAP:
            uf = state_clean
        else:
            # Mapeamentos manuais para estados com nomes completos
            # Como state_clean já passa por strip_accents, apenas versões sem acento são necessárias
            # Cobre todos os 27 estados brasileiros (26 estados + 1 Distrito Federal)
            state_mappings = {
                # Acre
                "ACRE": "AC",
                # Alagoas
                "ALAGOAS": "AL",
                # Amapá
                "AMAPA": "AP",
                # Amazonas
                "AMAZONAS": "AM",
                # Bahia
                "BAHIA": "BA",
                # Ceará
                "CEARA": "CE",
                # Distrito Federal
                "DISTRITO FEDERAL": "DF",
                "DF": "DF",
                # Espírito Santo
                "ESPIRITO SANTO": "ES",
                # Goiás
                "GOIAS": "GO",
                # Maranhão
                "MARANHAO": "MA",
                # Mato Grosso
                "MATO GROSSO": "MT",
                # Mato Grosso do Sul
                "MATO GROSSO DO SUL": "MS",
                # Minas Gerais
                "MINAS GERAIS": "MG",
                # Pará
                "PARA": "PA",
                # Paraíba
                "PARAIBA": "PB",
                # Paraná
                "PARANA": "PR",
                # Pernambuco
                "PERNAMBUCO": "PE",
                # Piauí
                "PIAUI": "PI",
                # Rio de Janeiro
                "RIO DE JANEIRO": "RJ",
                # Rio Grande do Norte
                "RIO GRANDE DO NORTE": "RN",
                # Rio Grande do Sul
                "RIO GRANDE DO SUL": "RS",
                # Rondônia
                "RONDONIA": "RO",
                # Roraima
                "RORAIMA": "RR",
                # Santa Catarina
                "SANTA CATARINA": "SC",
                # São Paulo
                "SAO PAULO": "SP",
                # Sergipe
                "SERGIPE": "SE",
                # Tocantins
                "TOCANTINS": "TO",
            }
            
            uf = None
            for key, value in state_mappings.items():
                if key in state_clean:
                    uf = value
                    break
        
        return city, uf
    
    # Sem "/", assume que usuário só mandou a cidade
    # Mas tenta detectar se tem UF no final (ex: "Londrina PR")
    words = text.split()
    if len(words) >= 2:
        last_word = words[-1].upper()
        if last_word in UF_MAP:
            city = " ".join(words[:-1]).title()
            return city, last_word
    
    return text.title(), None


def normalize_profile(raw: str) -> str:
    """
    Normaliza respostas livres para um conjunto de perfis padrão.
    
    Exemplos:
        "Sou expositor" → "Empresa/Expositor"
        "trabalho como produtor rural" → "Produtor rural"
        "sou pesquisador" → "Pesquisador(a)"
    """
    text = raw.lower().strip()
    
    if "produtor" in text or "fazenda" in text or "fazendeiro" in text:
        return "Produtor rural"
    if "pesquisador" in text or "professor" in text or "academia" in text or "pesquisa" in text:
        return "Pesquisador(a)"
    if "empresa" in text or "expositor" in text or "indústria" in text or "industria" in text:
        return "Empresa/Expositor"
    if "consultor" in text or "consultoria" in text:
        return "Consultor(a)"
    if "estudante" in text or "aluno" in text or "universidade" in text:
        return "Estudante"
    
    # Se não encontrar padrão, retorna o texto original capitalizado
    return raw.strip().title()

