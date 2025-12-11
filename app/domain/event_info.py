"""
Módulo com informações do evento BioSummit 2026.

Contém funções para obter informações reais e simuladas do evento.
"""
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass(frozen=True)
class TicketCategory:
    """Categoria de ingresso do evento (para modo mock)."""
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


def get_event_info() -> Dict[str, Any]:
    """
    Retorna todas as informações reais do evento BioSummit 2026.
    
    Todas as informações são hard-coded e não fazem scraping ou requisições HTTP.
    Retorna um dicionário estruturado com todas as informações factuais do evento.
    
    Returns:
        Dict com informações completas do evento, incluindo:
        - name, theme, dates, location, format
        - organizer (contatos e informações)
        - description, target_audience
        - structure_highlights
        - tickets (categorias, preços, status)
        - speakers_page, sponsorship
        - user_area, menu_endpoints
        - short_summary
    """
    return {
        "name": "BioSummit 2026",
        "theme": "Bioinsumos e Agricultura Regenerativa: Cultivando o Futuro Sustentável",
        "dates": {
            "start": "2026-05-06",
            "end": "2026-05-07",
            "display": "06 e 07 de maio de 2026",
            "time_window": {
                "start_time": "08:00",
                "end_time": "18:00"
            }
        },
        "location": {
            "city": "Campinas",
            "state": "SP",
            "venue": "Expo Dom Pedro",
            "description": "Um dos maiores e mais completos centros de eventos do interior paulista, integrado ao Parque Dom Pedro Shopping, facilitando acesso, hospedagem e alimentação.",
            "address": "Expo Dom Pedro - Campinas/SP",
            "display": "Expo Dom Pedro, Campinas - SP"
        },
        "format": {
            "type": "presencial",
            "highlights": [
                "Evento presencial com foco em conteúdo técnico, networking e negócios",
                "Debates técnicos sobre bioinsumos e agricultura regenerativa",
                "Apresentação de soluções biológicas e tecnologias",
                "Troca de experiências de campo",
                "Conexões entre diferentes elos da cadeia do agro"
            ]
        },
        "organizer": {
            "name": "FB Group Brasil",
            "brand": "FB GROUP",
            "phone": "(43) 3025-5223",
            "email": "contato@biosummit.com.br",
            "website": "https://biosummit.com.br"
        },
        "description": (
            "O BioSummit 2026 é um encontro focado em bioinsumos e agricultura regenerativa, "
            "reunindo produtores, pesquisadores, empresas e profissionais do agro para discutir "
            "o futuro da produção agrícola no Brasil. Ao longo de dois dias, o evento promove "
            "debates técnicos, apresentação de soluções biológicas e tecnologias, troca de "
            "experiências de campo e conexões entre diferentes elos da cadeia do agro. "
            "A proposta central é mostrar como os bioinsumos e as práticas regenerativas podem "
            "construir uma agricultura mais sustentável, economicamente viável e alinhada com os ciclos da natureza."
        ),
        "target_audience": [
            "Produtores rurais e técnicos de campo",
            "Pesquisadores e profissionais de universidades e instituições de pesquisa",
            "Empresas de bioinsumos, biológicos, sementes, fertilizantes, maquinário e tecnologia",
            "Consultores, agrônomos, engenheiros e profissionais de assistência técnica",
            "Estudantes e entusiastas de agricultura regenerativa e inovação no agro"
        ],
        "structure_highlights": {
            "area_m2": 6500,
            "features": [
                "Road TRIP pré-evento",
                "Mais de 6.500 m² de pavilhão com estandes das principais empresas do setor",
                "Espaço imprensa e podcast",
                "Programação intensa com painéis e palestras",
                "Espaços para reuniões e networking"
            ]
        },
        "speakers_page": {
            "url": "https://biosummit.com.br/convidados",
            "status": "em_construcao",
            "note": "O evento contará com a participação dos principais nomes da indústria e da academia. Lista completa a ser divulgada no site oficial."
        },
        "technical_committee": {
            "description": "O evento contará com a participação dos principais nomes da área.",
            "members": [
                {
                    "name": "Wagner Betiol",
                    "institution": "Embrapa"
                },
                {
                    "name": "Sérgio Mazaro",
                    "institution": "UTFPR"
                },
                {
                    "name": "Flávio Medeiros",
                    "institution": "UFLA"
                }
            ]
        },
        "sponsorship": {
            "url": "https://biosummit.com.br/patrocinio",
            "qualified_audience_over": 1000,
            "benefits": [
                "Visibilidade institucional",
                "Geração de leads",
                "Relacionamento com decisores do agro"
            ],
            "note": "Existem diferentes cotas e formatos de patrocínio; detalhes (valores e contrapartidas) devem ser obtidos diretamente com a organização."
        },
        "tickets": {
            "routes": {
                "home_section": "Ingressos na home do site",
                "local_page": "https://biosummit.com.br/local",
                "divulgue_page": "https://biosummit.com.br/divulgue",
                "user_area": "https://biosummit.com.br/acesso",
                "inscricao_page": "https://biosummit.com.br/inscricao"
            },
            "categories": [
                {
                    "name": "Profissional",
                    "prices": [
                        {
                            "amount": 700.00,
                            "currency": "BRL",
                            "label": "Até 13/02/2026",
                            "valid_until": "2026-02-13"
                        },
                        {
                            "amount": 850.00,
                            "currency": "BRL",
                            "label": "Até 30/04/2026",
                            "valid_until": "2026-04-30"
                        },
                        {
                            "amount": 950.00,
                            "currency": "BRL",
                            "label": "Após 30/04/2026",
                            "valid_from": "2026-05-01"
                        }
                    ]
                },
                {
                    "name": "Estudante",
                    "prices": [
                        {
                            "amount": 450.00,
                            "currency": "BRL",
                            "label": "Até 13/02/2026",
                            "valid_until": "2026-02-13"
                        },
                        {
                            "amount": 650.00,
                            "currency": "BRL",
                            "label": "Até 30/04/2026",
                            "valid_until": "2026-04-30"
                        },
                        {
                            "amount": 800.00,
                            "currency": "BRL",
                            "label": "Após 30/04/2026",
                            "valid_from": "2026-05-01"
                        }
                    ]
                },
                {
                    "name": "Produtor",
                    "prices": [
                        {
                            "amount": 450.00,
                            "currency": "BRL",
                            "label": "Até 13/02/2026",
                            "valid_until": "2026-02-13"
                        },
                        {
                            "amount": 650.00,
                            "currency": "BRL",
                            "label": "Até 30/04/2026",
                            "valid_until": "2026-04-30"
                        },
                        {
                            "amount": 800.00,
                            "currency": "BRL",
                            "label": "Após 30/04/2026",
                            "valid_from": "2026-05-01"
                        }
                    ]
                },
                {
                    "name": "Patrocinador",
                    "prices": [
                        {
                            "amount": 450.00,
                            "currency": "BRL",
                            "label": "Até 13/02/2026",
                            "valid_until": "2026-02-13"
                        },
                        {
                            "amount": 650.00,
                            "currency": "BRL",
                            "label": "Até 30/04/2026",
                            "valid_until": "2026-04-30"
                        },
                        {
                            "amount": 800.00,
                            "currency": "BRL",
                            "label": "Após 30/04/2026",
                            "valid_from": "2026-05-01"
                        }
                    ]
                }
            ],
            "status": {
                "registration_open": True,
                "message": "As inscrições serão liberadas em 64 dias.",
                "presential_tickets": "esgotados",
                "note": "Ingressos presenciais esgotados, mas ainda podem existir alternativas (lista de espera, formato online ou outras soluções) divulgadas nos canais oficiais."
            },
            "cancellation_policy": "Não efetuamos devolução, reembolso ou estornos.",
            "registration_process": {
                "description": (
                    "Após o preenchimento do formulário abaixo o participante recebe uma mensagem de confirmação "
                    "e é direcionado para a área de usuário, onde poderá editar os dados, efetuar pagamentos, "
                    "baixar recibos e quaisquer processos relativos ao site. "
                    "Só é possível fazer a inscrição uma única vez. Após o cadastro clique em Área do Inscrito "
                    "e informe os dados de acesso."
                ),
                "single_registration_only": True,
                "user_area_instructions": "Após o cadastro, acesse a Área do Inscrito e informe os dados de acesso."
            },
            "limitations": [
                "Tipos de ingressos, valores, lotes e regras de meia-entrada não estão públicos de forma estruturada.",
                "O endpoint /inscricao já foi divulgado em redes sociais, mas pode retornar erro ou estar em atualização."
            ],
            "notes": [
                "Valores em reais (BRL) para as categorias Profissional, Estudante, Produtor e Patrocinador.",
                "Os períodos de validade seguem as datas exibidas no site: até 13/02/2026, até 30/04/2026 e após 30/04/2026.",
                "Políticas de meia-entrada, descontos adicionais e condições específicas devem ser confirmadas diretamente na página oficial de inscrições."
            ],
            "recommendation_for_bot": (
                "Quando o usuário perguntar sobre valores ou lotes, o bot pode informar a tabela básica de preços, "
                "mas deve sempre recomendar a consulta em tempo real à página oficial de inscrições em biosummit.com.br, "
                "pois os valores e condições podem ser atualizados pelos organizadores."
            )
        },
        "user_area": {
            "url": "https://biosummit.com.br/acesso",
            "features": [
                "Login com e-mail, CPF ou login",
                "Acesso à conta e dados de inscrição",
                "Reset de senha"
            ]
        },
        "menu_endpoints": [
            {"path": "/", "description": "Home visão geral e CTA de ingressos"},
            {"path": "/local", "description": "Informações sobre o local (Expo Dom Pedro)"},
            {"path": "/convidados", "description": "Palestrantes / convidados (em construção)"},
            {"path": "/patrocinio", "description": "Página 'Por que Patrocinar?'"},
            {"path": "/divulgue", "description": "Materiais de divulgação + reforço de ingressos"},
            {"path": "/acesso", "description": "Área do usuário (login / recuperação de senha)"},
            {"path": "/inscricao", "description": "Página de inscrição/compra de ingressos (linkada em redes sociais)"}
        ],
        "short_summary": (
            "O BioSummit 2026 acontece nos dias 6 e 7 de maio de 2026, no Expo Dom Pedro em Campinas/SP, "
            "com o tema 'Bioinsumos e Agricultura Regenerativa: Cultivando o Futuro Sustentável'. "
            "É um evento presencial que reúne produtores, pesquisadores, empresas e profissionais do agro "
            "para dois dias de conteúdo técnico, networking e negócios, organizado pela FB Group Brasil."
        )
    }


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
        contact_whatsapp="+55 43 3025-5121",
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

