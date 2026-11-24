
from pathlib import Path
from app.chunking import chunk_text

# Locate the travel policy
file_path = Path("data/documents/policies/travel_expense_policy.txt")

# Read the document
text = file_path.read_text(encoding="utf-8")

# Split into chunks
chunks = chunk_text(text, chunk_size=100, overlap=20)

print("DOCUMENT PROCESSING SUCCESSFUL!")
print("Total chunks:", len(chunks))

for i, chunk in enumerate(chunks, start=1):
    print(f"\n--- CHUNK {i} ---")
    print(chunk)
