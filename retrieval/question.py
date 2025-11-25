from retrieval.retriever import retrieve_relevant_docs

query = "Сколько стоит доставка из Китая?"
docs = retrieve_relevant_docs(query, top_k=3)
print("Docs found:", docs)
if docs:
    for d in docs:
        print("-----")
        print("CONTENT:", d["content"])
        print("SOURCE:", d["source_path"])
