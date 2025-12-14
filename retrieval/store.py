# store.py
import os
import chromadb
import logging
# ВАЖНО: для langchain==0.1.14 используем:
from langchain.embeddings.openai import OpenAIEmbeddings
from typing import List, Dict, Any
from config import CHROMA_DB_PATH

logger = logging.getLogger(__name__)

client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

# Основная коллекция документов
COLLECTION_NAME = "corporate_docs"
collection = client.get_or_create_collection(name=COLLECTION_NAME)

# Дополнительная коллекция для FAQ
FAQ_COLLECTION_NAME = "faq_docs"
faq_collection = client.get_or_create_collection(name=FAQ_COLLECTION_NAME)

def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    tokens = text.split()
    chunks = []
    current_start = 0
    while current_start < len(tokens):
        end = current_start + chunk_size
        chunk = tokens[current_start:end]
        chunks.append(" ".join(chunk))
        current_start = end - chunk_overlap
        if current_start < 0:
            current_start = 0
    return chunks

def store_document_chunks(content: str, source_path: str):
    """
    Разбивает текст на чанки, создает эмбеддинги и сохраняет в ChromaDB (corporate_docs).
    """
    embedder = OpenAIEmbeddings()
    chunks = chunk_text(content)
    if not chunks:
        return

    documents, metadatas, ids, embeddings = [], [], [], []

    for idx, chunk in enumerate(chunks):
        chunk_id = f"{os.path.basename(source_path)}_{idx}"
        documents.append(chunk)
        metadatas.append({"source_path": source_path, "chunk_index": idx})
        ids.append(chunk_id)

    vectors = embedder.embed_documents(documents)
    embeddings.extend(vectors)

    _delete_ids_if_exist(ids, collection)

    collection.add(
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids
    )

def _delete_ids_if_exist(ids: List[str], target_collection):
    """
    Если данные IDs уже есть в коллекции, удалим, чтобы не было дубликатов.
    """
    existing = target_collection.get(ids=ids)
    existing_ids = existing.get("ids", [])
    if existing_ids:
        target_collection.delete(ids=existing_ids)


def delete_document_chunks(source_path: str) -> None:
    """Удаляет все чанки документа из основной коллекции по пути источника."""
    try:
        deleted_count = collection.delete(where={"source_path": source_path})
        logger.info(
            "Removed %s chunks for source_path=%s from Chroma collection %s",
            deleted_count,
            source_path,
            COLLECTION_NAME,
        )
    except Exception as e:
        logger.error(f"Failed to delete chunks for {source_path} from Chroma: {e}")

def get_similar_docs(query: str, k: int = 3) -> List[Dict[str, Any]]:
    """
    Выполняет векторный поиск по основной коллекции ChromaDB,
    возвращает до k самых релевантных чанков.
    """
    embedder = OpenAIEmbeddings()
    query_embedding = embedder.embed_query(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k
    )

    if not results["documents"] or not results["documents"][0]:
        return []

    docs_list = results["documents"][0]
    meta_list = results["metadatas"][0]

    docs = []
    for doc, metadata in zip(docs_list, meta_list):
        docs.append({
            "content": doc,
            "metadata": {
                "source": metadata.get("source_path", ""),
                "restricted": metadata.get("restricted", False)
            }
        })

    return docs

# ---------------------- Новые функции для FAQ ----------------------

def store_faq_question(question: str, faq_id: str):
    """
    Сохраняет короткий вопрос (FAQ) в отдельную коллекцию faq_collection.
    Предполагается, что подробный ответ (если нужен) хранится где-то ещё,
    либо мы можем здесь же хранить и ответ.
    """
    embedder = OpenAIEmbeddings()
    vector = embedder.embed_query(question)

    _delete_ids_if_exist([faq_id], faq_collection)

    faq_collection.add(
        documents=[question],
        embeddings=[vector],
        metadatas=[{"faq_id": faq_id}],
        ids=[faq_id]
    )

def get_similar_faq(query: str, k: int = 3) -> List[str]:
    """
    Аналогично get_similar_docs, но для FAQ.
    Возвращает список близких по смыслу коротких вопросов (strings).
    """
    embedder = OpenAIEmbeddings()
    query_embedding = embedder.embed_query(query)

    results = faq_collection.query(
        query_embeddings=[query_embedding],
        n_results=k
    )

    if not results["documents"] or not results["documents"][0]:
        return []

    # docs_list — список документов (то есть FAQ-вопросов)
    docs_list = results["documents"][0]

    return docs_list
