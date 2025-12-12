import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)

Base = declarative_base()


def create_engine_from_url(database_url: str):
    """
    Cria um engine SQLAlchemy a partir de uma URL de banco de dados.
    
    Para PostgreSQL, usa pool_pre_ping=True para detectar conexões perdidas.
    """
    # Detectar se é PostgreSQL
    is_postgres = "postgresql" in database_url.lower() or "postgres" in database_url.lower()
    
    if is_postgres:
        # Para PostgreSQL, usar pool_pre_ping e configurações de pool
        engine = create_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,  # Verifica conexões antes de usar
            pool_size=5,
            max_overflow=10,
        )
        logger.info("Engine PostgreSQL criado com pool_pre_ping=True")
    else:
        # Para SQLite, manter comportamento simples
        engine = create_engine(database_url, echo=False)
        logger.info("Engine SQLite criado")
    
    return engine


def create_session_factory(database_url: str, create_tables: bool = False):
    """
    Cria uma factory de sessões SQLAlchemy.
    
    Args:
        database_url: URL de conexão do banco
        create_tables: Se True, cria tabelas automaticamente (apenas para dev/test)
                      Em produção, use migrações Alembic!
    """
    engine = create_engine_from_url(database_url)
    
    # Criar tabelas apenas se solicitado (modo dev/test)
    # Em produção, sempre usar migrações Alembic!
    if create_tables:
        env = os.getenv("ENV", "dev").lower()
        if env == "prod":
            logger.warning(
                "⚠️  create_tables=True em produção! "
                "Use migrações Alembic ao invés de criar tabelas automaticamente."
            )
        else:
            logger.info("Criando tabelas automaticamente (modo dev/test)")
            Base.metadata.create_all(bind=engine)
    
    return sessionmaker(bind=engine, expire_on_commit=False)

