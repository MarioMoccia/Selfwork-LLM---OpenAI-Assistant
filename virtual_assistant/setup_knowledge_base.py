# setup_knowledge_base.py
"""Crea la knowledge base dell'assistente: da lanciare una sola volta.

    python virtual_assistant/setup_knowledge_base.py

Carica i documenti della cartella `kb/` in un vector store di OpenAI (il database in cui il
modello cerca per significato) e salva il suo ID nel file `.env` come VECTOR_STORE_ID.
Questo prende il posto della creazione dell'assistente dell'API Assistants, ormai chiusa:
con la Responses API non esiste più un "assistente" da creare, resta solo la knowledge base.
"""
from openai import OpenAI

from config import ENV_FILE, Config


def save_vector_store_id(vector_store_id: str):
    """Scrive (o aggiorna) VECTOR_STORE_ID nel file .env, senza toccare le altre righe."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    lines = [l for l in lines if not l.startswith("VECTOR_STORE_ID=")]
    lines.append(f"VECTOR_STORE_ID={vector_store_id}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def create_knowledge_base(client: OpenAI) -> str:
    files = sorted(Config.KB_DIR.glob("*.txt"))
    if not files:
        raise SystemExit(f"Nessun documento .txt in {Config.KB_DIR}")

    vector_store = client.vector_stores.create(name=Config.VECTOR_STORE_NAME)
    streams = [open(path, "rb") for path in files]
    try:
        # Carica i file e aspetta che OpenAI li abbia indicizzati
        batch = client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id, files=streams
        )
    finally:
        for stream in streams:
            stream.close()

    print(f"Documenti caricati: {batch.file_counts.completed} su {len(files)}")
    if batch.file_counts.failed:
        raise SystemExit(f"{batch.file_counts.failed} documenti non sono stati indicizzati")
    return vector_store.id


if __name__ == "__main__":
    if Config.VECTOR_STORE_ID:
        print(f"Esiste già una knowledge base (VECTOR_STORE_ID nel file .env): {Config.VECTOR_STORE_ID}")
        print("Per ricrearla, cancella quella riga dal file .env e rilancia questo script.")
        raise SystemExit(0)

    vector_store_id = create_knowledge_base(OpenAI(api_key=Config.API_KEY))
    save_vector_store_id(vector_store_id)
    print(f"Knowledge base creata: {vector_store_id} (salvata nel file .env)")
