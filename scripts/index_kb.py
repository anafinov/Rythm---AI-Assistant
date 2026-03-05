"""One-shot script: index knowledge base markdown files."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.rag import KnowledgeBase

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge")


def main():
    kb = KnowledgeBase(persist_dir="./kb_data")
    count = kb.index_directory(KNOWLEDGE_DIR)
    print(f"Done — indexed {count} chunks.")


if __name__ == "__main__":
    main()
