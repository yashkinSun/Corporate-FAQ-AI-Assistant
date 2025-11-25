# Миграция базы данных для расширения модели FollowupQuestion

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Версия миграции: 0001
# Описание: Расширение модели FollowupQuestion для хранения дополнительных данных

def upgrade():
    # Добавляем новые поля в таблицу followup_questions
    op.add_column('followup_questions', sa.Column('original_query', sa.Text(), nullable=True))
    op.add_column('followup_questions', sa.Column('confidence_score', sa.Float(), nullable=True))
    op.add_column('followup_questions', sa.Column('generated_by', sa.String(20), nullable=False, server_default='map'))
    
    # Переносим данные из поля is_generated в generated_by
    op.execute("""
    UPDATE followup_questions 
    SET generated_by = CASE WHEN is_generated THEN 'llm' ELSE 'map' END
    """)
    
    # Удаляем старое поле is_generated
    op.drop_column('followup_questions', 'is_generated')

def downgrade():
    # Добавляем обратно поле is_generated
    op.add_column('followup_questions', sa.Column('is_generated', sa.Boolean(), nullable=False, server_default='false'))
    
    # Переносим данные из generated_by в is_generated
    op.execute("""
    UPDATE followup_questions 
    SET is_generated = (generated_by = 'llm')
    """)
    
    # Удаляем новые поля
    op.drop_column('followup_questions', 'generated_by')
    op.drop_column('followup_questions', 'confidence_score')
    op.drop_column('followup_questions', 'original_query')
