import chromadb
import os
import hashlib

# Initialize ChromaDB client (runs locally, no cost)
client = chromadb.Client()
collection = client.get_or_create_collection(
    name="codebase",
    metadata={"hnsw:space": "cosine"}
)


def ingest_codebase(repo_name: str, code_files: list):
    """
    Ingests all code files from a repo into ChromaDB.
    Called once when a repo is first connected.
    """
    if not code_files:
        print("No files to ingest")
        return

    documents = []
    metadatas = []
    ids = []

    for file in code_files:
        content = file.get("content", "")
        filename = file.get("name", "unknown")

        if not content:
            continue

        # Create unique ID using hash
        file_id = hashlib.md5(f"{repo_name}_{filename}".encode()).hexdigest()

        documents.append(content)
        metadatas.append({
            "repo": repo_name,
            "filename": filename
        })
        ids.append(file_id)

    if documents:
        # Add to ChromaDB (upsert to avoid duplicates)
        collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"✅ Ingested {len(documents)} files from {repo_name} into ChromaDB")


def get_context(query: str, repo_name: str, n_results: int = 3) -> str:
    """
    Retrieves relevant code from ChromaDB based on the diff.
    This gives agents context about how the team writes code.
    """
    try:
        count = collection.count()
        if count == 0:
            return ""

        results = collection.query(
            query_texts=[query[:500]],  # limit query size
            n_results=min(n_results, count),
            where={"repo": repo_name} if count > 0 else None
        )

        if results and results["documents"] and results["documents"][0]:
            context_parts = []
            for i, doc in enumerate(results["documents"][0]):
                filename = results["metadatas"][0][i].get("filename", "unknown")
                context_parts.append(f"File: {filename}\n{doc[:500]}")

            return "\n\n---\n\n".join(context_parts)

    except Exception as e:
        print(f"Warning: RAG context fetch failed: {e}")

    return ""


def clear_repo_context(repo_name: str):
    """Clears all stored vectors for a specific repo."""
    try:
        results = collection.get(where={"repo": repo_name})
        if results["ids"]:
            collection.delete(ids=results["ids"])
            print(f"Cleared context for {repo_name}")
    except Exception as e:
        print(f"Warning: Could not clear context: {e}")
