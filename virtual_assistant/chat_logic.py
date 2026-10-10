# chat_logic.py
import json
import re
from dataclasses import dataclass, field
from datetime import date

from openai import OpenAI

from config import Config
from studio import Studio
from tools import FUNCTION_TOOLS, execute_tool

WEEKDAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]


@dataclass
class AssistantEvent:
    """Un passaggio della risposta, da mostrare all'utente mentre avviene.

    kind può essere:
    - "file_search": il modello ha cercato nei documenti (le query sono in `queries`)
    - "tool_start" / "tool_end": una funzione richiesta dal modello sta per essere eseguita /
      è stata eseguita (`name`, `arguments`, `result`)
    - "answer": la risposta finale in `text`, con i documenti citati in `sources`
    """

    kind: str
    name: str = ""
    arguments: dict = field(default_factory=dict)
    result: str = ""
    queries: list[str] = field(default_factory=list)
    text: str = ""
    sources: list[str] = field(default_factory=list)


def instructions() -> str:
    today = date.today()
    return (
        "Il tuo nome è Giulia. Sei l'assistente virtuale dello Studio Dentistico Sorriso di Bari "
        "e aiuti i pazienti con le loro richieste, in italiano, con tono cordiale e rassicurante.\n"
        f"Oggi è {WEEKDAYS[today.weekday()]} {today.isoformat()}.\n"
        "Regole:\n"
        "- Per informazioni sullo studio (servizi, prezzi, orari, team, preparazione e cure "
        "post-visita) usa SEMPRE la ricerca nei documenti: non inventare mai prezzi o regole. "
        "Se i documenti non contengono la risposta, dillo e suggerisci di telefonare allo studio.\n"
        "- Non dare diagnosi né consigli medici personalizzati: per sintomi o dubbi clinici "
        "invita a prenotare una visita.\n"
        "- Per sapere quali orari sono liberi usa la funzione get_available_slots, che controlla "
        "un giorno solo. Se il paziente indica un periodo (\"la prossima settimana\") o non sceglie "
        "un giorno, controlla più giorni (lunedì-sabato, mai la domenica: è chiuso), chiamando la funzione per tutti i giorni insieme nello stesso passaggio, e riassumi gli orari per giorno, oppure "
        "chiedi quale giorno preferisce. Di' sempre quali giorni hai controllato.\n"
        "- Prenota con book_appointment solo quando hai nome e cognome, email, servizio, giorno "
        "e orario scelti dal paziente. Se manca qualcosa, chiedilo. Non inventare l'email.\n"
        "- Se una funzione restituisce un errore, spiegalo in modo semplice e proponi un'alternativa."
    )


class ChatLogic:
    """Gestisce una conversazione con l'assistente tramite la Responses API di OpenAI.

    Ogni chat ha il suo `ChatLogic`. La memoria della conversazione non la tengo io: la tiene
    OpenAI, e a ogni richiesta indico `previous_response_id` (la risposta precedente), al posto
    del "thread" della vecchia API Assistants. Strumenti usati dal modello:
    - `file_search`: cerca nei documenti caricati nel vector store (la knowledge base);
    - le funzioni di `tools.py`, che eseguo io (agenda e prenotazioni dello studio).
    """

    def __init__(self, client: OpenAI, vector_store_id: str, studio: Studio):
        self.client = client
        self.studio = studio
        self.previous_response_id: str | None = None
        self.tools = [
            {"type": "file_search", "vector_store_ids": [vector_store_id]},
            *FUNCTION_TOOLS,
        ]

    def process_message(self, user_message: str):
        """Gestisce un messaggio dell'utente e produce gli `AssistantEvent` man mano.

        1. Mando il messaggio al modello, con le istruzioni e gli strumenti.
        2. La ricerca nei documenti la esegue OpenAI da sé, e la vedo nella risposta.
        3. Se il modello chiede delle funzioni, le eseguo io e rimando i risultati
           (`function_call_output`) collegandoli alla risposta precedente: poi il modello
           continua, e può chiamarne altre prima di rispondere.
        4. Quando risponde con testo, ho finito e salvo l'ID della risposta per il turno dopo.

        La conversazione si "conferma" solo a risposta completata: se qualcosa va storto a
        metà, `previous_response_id` resta quello dell'ultimo turno riuscito.
        """
        previous_id = self.previous_response_id
        input_items = [{"role": "user", "content": user_message}]

        for _ in range(Config.MAX_TOOL_ROUNDS):
            response = self.client.responses.create(
                model=Config.LLM_MODEL,
                instructions=instructions(),
                input=input_items,
                tools=self.tools,
                previous_response_id=previous_id,
            )

            calls = []
            for item in response.output:
                if item.type == "file_search_call":
                    yield AssistantEvent("file_search", queries=list(item.queries or []))
                elif item.type == "function_call":
                    calls.append(item)

            if not calls:
                text, sources = self._read_answer(response)
                self.previous_response_id = response.id
                yield AssistantEvent("answer", text=text, sources=sources)
                return

            input_items = []
            for call in calls:
                try:
                    arguments = json.loads(call.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                yield AssistantEvent("tool_start", name=call.name, arguments=arguments)
                result = execute_tool(self.studio, call.name, call.arguments)
                yield AssistantEvent(
                    "tool_end", name=call.name, arguments=arguments, result=result
                )
                input_items.append(
                    {"type": "function_call_output", "call_id": call.call_id, "output": result}
                )
            previous_id = response.id

        yield AssistantEvent(
            "answer",
            text="Mi dispiace, non sono riuscita a completare la richiesta: riprova o riformulala.",
        )

    @staticmethod
    def _read_answer(response) -> tuple[str, list[str]]:
        """Testo della risposta e nomi dei documenti citati da file_search."""
        sources: list[str] = []
        for item in response.output:
            if item.type != "message":
                continue
            for part in item.content:
                if part.type != "output_text":
                    continue
                for annotation in part.annotations or []:
                    if annotation.type == "file_citation" and annotation.filename not in sources:
                        sources.append(annotation.filename)
        text = re.sub(r"【[^】]*】", "", response.output_text or "").strip()
        return text, sources
