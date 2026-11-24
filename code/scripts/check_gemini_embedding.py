import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env file")

client = genai.Client(api_key=api_key)

response = client.models.embed_content(
    model="gemini-embedding-2",
    contents="Hotel accommodation expenses must follow the approved company policy.",
    config={
        "output_dimensionality": 1536
    }
)

embedding = response.embeddings[0].values

print("Gemini embedding generated successfully!")
print("Embedding dimensions:", len(embedding))
print("First five values:", embedding[:5])