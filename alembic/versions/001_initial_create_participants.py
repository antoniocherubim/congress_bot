"""initial create participants

Revision ID: 001
Revises: 
Create Date: 2025-01-12 21:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Criar tabela participants
    op.create_table(
        'participants',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('full_name', sa.String(length=200), nullable=False),
        sa.Column('email', sa.String(length=200), nullable=False),
        sa.Column('cpf', sa.String(length=11), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=50), nullable=True),
        sa.Column('profile', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Criar índice único para CPF
    op.create_index('ix_participants_cpf', 'participants', ['cpf'], unique=True)


def downgrade() -> None:
    # Remover índice
    op.drop_index('ix_participants_cpf', table_name='participants')
    
    # Remover tabela
    op.drop_table('participants')

