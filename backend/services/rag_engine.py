import os
import re
from typing import List, Dict, Any

class RAGEngine:
    """
    Memory-efficient RAG Engine for Free Tier deployments.
    Uses a simple keyword-based ranking instead of heavy vector embeddings (PyTorch/FAISS).
    This reduces memory usage from >1GB to <50MB.
    """
    def __init__(self, docs_dir: str = None):
        if docs_dir is None:
            # Use absolute path relative to this file
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.docs_dir = os.path.join(base_dir, "data", "rag_docs")
        else:
            self.docs_dir = docs_dir
        self.documents = []
        self._initialized = False

    def initialize(self):
        """Loads documents into memory."""
        if self._initialized:
            return

        print(f"Initializing Lightweight RAG Engine from {self.docs_dir}...")
        try:
            self._load_documents()
            self._initialized = True
            print(f"RAG Engine ready with {len(self.documents)} chunks.")
        except Exception as e:
            print(f"CRITICAL: RAG Engine initialization failed: {e}")
            # Don't set _initialized to True so it might retry or stay empty

    def _ensure_initialized(self):
        if not self._initialized:
            self.initialize()

    def _load_documents(self):
        """Loads and chunks documents from the rag_docs directory."""
        if not os.path.exists(self.docs_dir):
            print(f"Warning: RAG docs directory not found at {self.docs_dir}")
            return

        for filename in os.listdir(self.docs_dir):
            if filename.endswith(".txt"):
                path = os.path.join(self.docs_dir, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                        # Split by double newline to get logical chunks
                        sections = content.split("\n\n")
                        for section in sections:
                            text = section.strip()
                            if text:
                                # Pre-process text for faster matching
                                words = set(re.findall(r'\w+', text.lower()))
                                self.documents.append({
                                    "content": text,
                                    "source": filename,
                                    "words": words
                                })
                except Exception as e:
                    print(f"Error loading {filename}: {e}")

    def retrieve(self, query: str, top_k: int = 5) -> List[str]:
        """
        Retrieves relevant chunks using simple keyword overlap.
        Perfect for small document sets and low-memory environments.
        """
        self._ensure_initialized()
        if not self.documents:
            return []

        # Tokenize query
        query_words = set(re.findall(r'\w+', query.lower()))
        
        # Rank documents by word overlap (Jaccard-like or simple count)
        scored_docs = []
        for doc in self.documents:
            overlap = len(query_words.intersection(doc["words"]))
            if overlap > 0:
                scored_docs.append((overlap, doc["content"]))
        
        # Sort by overlap count (descending)
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        
        # Return top K contents
        return [doc[1] for doc in scored_docs[:top_k]]

# Singleton instance
rag_engine = RAGEngine()
