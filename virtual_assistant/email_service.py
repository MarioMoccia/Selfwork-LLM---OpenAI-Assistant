# email_service.py
from datetime import datetime
from pathlib import Path

from config import Config


def send_email(to: str, subject: str, body: str, outbox_dir: Path | None = None) -> str:
    """Invia un'email... salvandola in un file nella cartella `outbox/`.

    L'invio è simulato di proposito: così il progetto funziona senza account o chiavi di un
    servizio di posta e non scrive a persone reali durante i test. Per mandare email vere basta
    sostituire il corpo di questa funzione con la chiamata al servizio scelto (ad esempio Resend):
    il resto del codice non cambia. Restituisce il percorso del file creato.
    """
    outbox = Path(outbox_dir or Config.OUTBOX_DIR)
    outbox.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    safe_to = "".join(c if c.isalnum() or c in "@._-" else "_" for c in to)
    path = outbox / f"{stamp}_{safe_to}.txt"
    path.write_text(f"A: {to}\nOggetto: {subject}\n\n{body}\n", encoding="utf-8")
    return str(path)
