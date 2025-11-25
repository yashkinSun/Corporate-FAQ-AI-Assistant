# retrieval/indexer.py

import sys
import os
import threading
import time

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from config import DOCUMENTS_PATH, INDEX_SCHEDULE_HOURS
from retrieval.doc_parser import parse_document
from retrieval.store import store_document_chunks, collection

def index_documents():
    print(f"[DEBUG] index_documents: Starting indexing in {DOCUMENTS_PATH}")
    if not os.path.isdir(DOCUMENTS_PATH):
        print(f"[ERROR] index_documents: {DOCUMENTS_PATH} is not a directory.")
        return

    files = os.listdir(DOCUMENTS_PATH)
    print(f"[DEBUG] index_documents: Found {len(files)} file(s) in {DOCUMENTS_PATH}")

    for file_name in files:
        file_path = os.path.join(DOCUMENTS_PATH, file_name)
        if not os.path.isfile(file_path):
            continue

        print(f"[DEBUG] index_documents: Parsing file {file_path}")
        content = parse_document(file_path)
        if not content:
            print(f"[DEBUG] index_documents: No text extracted from {file_name}, skipping.")
            continue

        print(f"[DEBUG] index_documents: Storing chunks for {file_name}")
        store_document_chunks(content, file_path)

    print(f"[DEBUG] Final count in collection after indexing: {collection.count()}")

def schedule_indexing():
    def run_indexing():
        while True:
            index_documents()
            print(f"[DEBUG] schedule_indexing: Sleep for {INDEX_SCHEDULE_HOURS} hours.")
            time.sleep(INDEX_SCHEDULE_HOURS * 3600)

    threading.Thread(target=run_indexing, daemon=True).start()

if __name__ == "__main__":
    index_documents()
