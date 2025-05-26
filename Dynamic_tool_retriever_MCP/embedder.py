"""Handles text embedding using a pre-trained sentence transformer model."""

from sentence_transformers import SentenceTransformer

# Initialize the sentence transformer model.
# 'all-MiniLM-L6-v2' is a good choice for generating sentence embeddings
# due to its balance of speed and performance.
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

def embed_text(text: str):
    """
    Embeds a given text string into a numerical vector representation.

    Args:
        text: The input string to embed.

    Returns:
        A list of floats representing the embedding of the input text.
    """
    return model.encode(text).tolist()