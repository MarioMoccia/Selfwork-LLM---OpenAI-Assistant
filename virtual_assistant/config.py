# config.py
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent
ENV_FILE = ROOT_DIR / ".env"

load_dotenv(ENV_FILE)


class Config:
    # OpenAI: la chiave sta nel file .env, mai nel codice
    LLM_MODEL = "gpt-4o-mini"
    API_KEY = os.environ.get("OPENAI_API_KEY", "")

    # Knowledge base: l'ID del vector store lo scrive setup_knowledge_base.py nel file .env
    VECTOR_STORE_ID = os.environ.get("VECTOR_STORE_ID", "")
    KB_DIR = ROOT_DIR / "kb"
    VECTOR_STORE_NAME = "Studio Dentistico Sorriso - Knowledge Base"

    # Quante volte, per un singolo messaggio, il modello può chiamare funzioni prima di rispondere
    MAX_TOOL_ROUNDS = 8

    # Studio: gli appuntamenti si salvano in un file, le email simulate in una cartella
    BOOKINGS_FILE = BASE_DIR / "data" / "prenotazioni.json"
    OUTBOX_DIR = ROOT_DIR / "outbox"
    CHAIRS = 2  # poltrone: appuntamenti contemporanei possibili
    MAX_DAYS_AHEAD = 30  # fino a quanti giorni in avanti si può prenotare
