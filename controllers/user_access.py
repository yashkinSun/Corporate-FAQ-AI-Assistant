# controllers/user_access.py

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

def check_user_access(user_id: int, query: str) -> bool:
    """
    Здесь может быть логика проверки ролей пользователя, уровня доступа и т.д.
    Для упрощения всегда возвращаем True.
    """
    return True

def filter_docs_by_access(user_id: int, docs: List[Dict]) -> List[Dict]:
    """
    Фильтрует список документов по ролям/правам доступа пользователя.
    Пример: если в метаданных документа стоит restricted=True, разрешаем
    только условному user_id=42.
    """
    allowed_docs = []
    for d in docs:
        restricted = d["metadata"].get("restricted", False)
        if restricted:
            # Здесь ваша логика. Пример: только user_id=42 имеет доступ
            if user_id == 42:
                allowed_docs.append(d)
        else:
            # Если restricted=False, доступ для всех
            allowed_docs.append(d)
    return allowed_docs
