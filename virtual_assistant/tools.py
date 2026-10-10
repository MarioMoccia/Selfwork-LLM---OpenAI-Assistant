# tools.py
import json

from studio import SERVICES, Studio

# Le funzioni descritte al modello (formato della Responses API). Il modello non le esegue:
# legge nome, descrizione e parametri e, quando serve, ci chiede di chiamarne una.
FUNCTION_TOOLS = [
    {
        "type": "function",
        "name": "get_available_slots",
        "description": (
            "Elenca gli orari di inizio ancora liberi per un appuntamento in un dato giorno. "
            "Usala prima di proporre o prenotare un orario, e quando il paziente non sa quando venire."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Il giorno, in formato AAAA-MM-GG, ad esempio 2026-10-14",
                }
            },
            "required": ["date"],
        },
    },
    {
        "type": "function",
        "name": "book_appointment",
        "description": (
            "Prenota un appuntamento e invia al paziente l'email di conferma. Chiamala solo quando "
            "hai tutti i dati: nome e cognome, email, servizio, data e orario. Se manca qualcosa, "
            "chiedilo. Non inventare mai l'email del paziente."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "patient_name": {"type": "string", "description": "Nome e cognome del paziente"},
                "email": {"type": "string", "description": "Email del paziente"},
                "service": {
                    "type": "string",
                    "enum": list(SERVICES),
                    "description": "Il servizio da prenotare",
                },
                "date": {"type": "string", "description": "Giorno, in formato AAAA-MM-GG"},
                "time": {
                    "type": "string",
                    "description": "Orario di inizio, in formato HH:MM, ad esempio 15:30",
                },
            },
            "required": ["patient_name", "email", "service", "date", "time"],
        },
    },
]


def execute_tool(studio: Studio, name: str, raw_arguments: str) -> str:
    """Esegue la funzione richiesta dal modello e restituisce il risultato come testo JSON.

    Se il modello sbaglia (argomenti non validi, funzione inesistente), l'errore diventa il
    risultato della funzione: lo legge e può correggersi o spiegarlo all'utente, senza far
    cadere l'applicazione.
    """
    functions = {
        "get_available_slots": studio.get_available_slots,
        "book_appointment": studio.book_appointment,
    }

    function = functions.get(name)
    if function is None:
        return json.dumps(
            {"ok": False, "errore": f"La funzione '{name}' non esiste."}, ensure_ascii=False
        )

    try:
        result = function(**json.loads(raw_arguments or "{}"))
    except (json.JSONDecodeError, TypeError) as e:
        result = {"ok": False, "errore": f"Argomenti non validi per {name}: {e}"}

    return json.dumps(result, ensure_ascii=False)
