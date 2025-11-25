# test_retriever.py
from retrieval.retriever import retrieve_relevant_docs

if __name__ == "__main__":
    query = "Сколько стоит доставка из Китая?"
    docs = retrieve_relevant_docs(query, top_k=5)

    print("\n[TEST RETRIEVER] Результаты поиска по запросу:")
    if not docs:
        print("Документы не найдены.")
    else:
        for idx, doc in enumerate(docs):
            print(f"\nДокумент {idx + 1}:")
            print(f"Источник: {doc['metadata'].get('source', 'не указан')}")
            print(f"Содержание: {doc['content']}\n{'-'*80}")
