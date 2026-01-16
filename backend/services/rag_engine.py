import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any

class RAGEngine:
    def __init__(self, docs_dir: str = "backend/data/rag_docs"):
        self.docs_dir = docs_dir
        # Use a very lightweight model for faster inference and smaller footprint
        self.model_name = 'paraphrase-MiniLM-L3-v2'
        self.model = None
        self.documents = []
        self.index = None
        self._initialized = False

    def initialize(self):
        """Explicit initialization to be called during startup."""
        if self._initialized:
            return

        print(f"Initializing RAG Engine (Loading {self.model_name})...")
        # Load model and move to CPU (standard for lightweight deployments)
        self.model = SentenceTransformer(self.model_name)
        self._load_documents()
        self._build_index()
        self._initialized = True
        print("RAG Engine ready.")

    def _ensure_initialized(self):
        """Fallback for lazy initialization if not called during startup."""
        if not self._initialized:
            self.initialize()

    def _load_documents(self):
        """Loads and chunks documents from the rag_docs directory."""
        if not os.path.exists(self.docs_dir):
            return

        for filename in os.listdir(self.docs_dir):
            if filename.endswith(".txt"):
                path = os.path.join(self.docs_dir, filename)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Simple chunking by paragraph/section
                    sections = content.split("\n\n")
                    for section in sections:
                        if section.strip():
                            self.documents.append({
                                "content": section.strip(),
                                "source": filename
                            })

    def _build_index(self):
        """Builds a FAISS index for vector search."""
        if not self.documents:
            return

        contents = [doc["content"] for doc in self.documents]
        embeddings = self.model.encode(contents)
        
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(np.array(embeddings).astype('float32'))

    def retrieve(self, query: str, top_k: int = 5) -> List[str]:
        """Retrieves relevant chunks for a given query."""
        self._ensure_initialized()
        if self.index is None or not self.documents:
            return []

        query_embedding = self.model.encode([query])
        distances, indices = self.index.search(np.array(query_embedding).astype('float32'), top_k)
        
        results = []
        for idx in indices[0]:
            if idx != -1:
                results.append(self.documents[idx]["content"])
        
        return results

# Singleton instance
rag_engine = RAGEngine()
