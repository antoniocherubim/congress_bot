from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

Base = declarative_base()


def create_engine_from_url(database_url: str):
    """
    Cria um engine SQLAlchemy a partir de uma URL de banco de dados.
    """
    return create_engine(database_url, echo=False)


def create_session_factory(database_url: str):
    """
    Cria uma factory de sessões SQLAlchemy.
    
    Também cria as tabelas automaticamente se não existirem.
    """
    engine = create_engine_from_url(database_url)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)

