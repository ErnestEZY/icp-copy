import os
from sentence_transformers import SentenceTransformer

def download_models():
    """Pre-downloads the embedding models for deployment."""
    # Use the same lightweight model defined in rag_engine.py
    model_name = 'paraphrase-MiniLM-L3-v2'
    
    print(f"Pre-downloading model: {model_name}...")
    # This will download the model to the default cache directory (e.g., ~/.cache/torch/sentence_transformers)
    model = SentenceTransformer(model_name)
    print(f"Successfully downloaded {model_name}.")

if __name__ == "__main__":
    download_models()
