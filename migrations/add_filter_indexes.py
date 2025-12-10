"""Миграция для добавления индексов на часто используемые колонки."""

from alembic import op
import sqlalchemy as sa


# Версия миграции: 0002
# Описание: Добавление индексов для ускорения фильтрации и соединений


def upgrade():
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])
    op.create_index('ix_messages_user_id', 'messages', ['user_id'])
    op.create_index('ix_messages_session_id', 'messages', ['session_id'])
    op.create_index('ix_followup_questions_message_id', 'followup_questions', ['message_id'])
    op.create_index('ix_chats_status', 'chats', ['status'])
    op.create_index('ix_chats_user_id', 'chats', ['user_id'])


def downgrade():
    op.drop_index('ix_chats_user_id', table_name='chats')
    op.drop_index('ix_chats_status', table_name='chats')
    op.drop_index('ix_followup_questions_message_id', table_name='followup_questions')
    op.drop_index('ix_messages_session_id', table_name='messages')
    op.drop_index('ix_messages_user_id', table_name='messages')
    op.drop_index('ix_sessions_user_id', table_name='sessions')
