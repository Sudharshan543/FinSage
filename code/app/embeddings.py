
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

# Initialize Gemini client
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env file")

client = genai.Client(api_key=api_key)

EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIMENSIONS = 1536


def generate_embedding(text):
    """
    Generate a 1536-dimensional embedding using Gemini.
    """

    if not text or not text.strip():
        raise ValueError("Text cannot be empty")

    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config={
            "output_dimensionality": EMBEDDING_DIMENSIONS
        }
    )

    embedding = response.embeddings[0].values

    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Expected {EMBEDDING_DIMENSIONS} dimensions, "
            f"received {len(embedding)}"
        )

    return embedding


if __name__ == "__main__":
    sample_text = (
        "Hotel accommodation expenses must follow "
        "the approved company travel policy."
    )

    vector = generate_embedding(sample_text)

    print("Gemini embedding generated successfully!")
    print("Model:", EMBEDDING_MODEL)
    print("Dimensions:", len(vector))
    print("First five values:", vector[:5])
