"""
Módulo com informações simuladas do evento para ambiente de teste.
"""
from dataclasses import dataclass
from typing import List, Dict


@dataclass(frozen=True)
class TicketCategory:
    """Categoria de ingresso do evento."""
    name: str
    description: str
    price_brl: float
    notes: str


@dataclass(frozen=True)
class EventInfo:
    """Informações completas do evento (para modo mock)."""
    name: str
    edition: str
    location: str
    dates: str
    theme: str
    contact_email: str
    contact_whatsapp: str
    website: str
    ticket_categories: List[TicketCategory]
    agenda_highlights: List[str]
    faq_extra: Dict[str, str]


def get_mock_event_info() -> EventInfo:
    """
    Retorna dados simulados do evento para ambiente de teste.
    
    ATENÇÃO: Esses valores são MOCKADOS e não representam necessariamente
    os valores finais do evento. Usar apenas para testes internos.
    """
    return EventInfo(
        name="BioSummit",
        edition="3ª edição - 2026",
        location="Expo Dom Pedro, Campinas – SP",
        dates="06 e 07 de maio de 2026",
        theme="Bioinsumos e Agricultura Regenerativa: Cultivando o Futuro Sustentável",
        contact_email="contato@biosummit.com.br",
        contact_whatsapp="+55 19 99999-0000",
        website="https://www.biosummit.com.br",
        ticket_categories=[
            TicketCategory(
                name="Produtor rural",
                description="Ingresso para produtores rurais e responsáveis técnicos.",
                price_brl=390.0,
                notes="Valor promocional de primeiro lote, sujeito a alteração."
            ),
            TicketCategory(
                name="Pesquisador / Professor",
                description="Ingresso para pesquisadores, docentes e técnicos de instituições públicas ou privadas.",
                price_brl=490.0,
                notes="Inclui acesso a todos os painéis e fóruns técnicos."
            ),
            TicketCategory(
                name="Estudante",
                description="Ingresso para estudantes de graduação e pós-graduação.",
                price_brl=250.0,
                notes="Necessário comprovar vínculo estudantil no credenciamento."
            ),
            TicketCategory(
                name="Profissional da indústria / empresa privada",
                description="Ingresso para profissionais de empresas, consultores e executivos.",
                price_brl=690.0,
                notes="Categoria voltada ao público corporativo e empresas expositoras."
            ),
        ],
        agenda_highlights=[
            "Painéis técnicos sobre manejo biológico de doenças em grandes culturas.",
            "Fóruns sobre regulamentação, registro e políticas públicas de bioinsumos.",
            "Sessões de networking entre empresas, produtores e pesquisadores.",
        ],
        faq_extra={
            "certificado_participacao": "Está prevista a emissão de certificado de participação digital para inscritos que fizerem check-in no evento.",
            "idioma_evento": "O evento será conduzido principalmente em português, com algumas palestras possivelmente em inglês.",
            "alimentacao": "Haverá praça de alimentação terceirizada no local, não inclusa no valor da inscrição.",
        },
    )

