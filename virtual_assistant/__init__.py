import json

import chainlit as cl
from openai import OpenAI

from chat_logic import ChatLogic
from config import Config
from studio import Studio

client = OpenAI(api_key=Config.API_KEY)
studio = Studio()  # agenda condivisa da tutte le chat

# Nome leggibile delle funzioni, per i passaggi mostrati in chat
TOOL_LABELS = {
    "get_available_slots": "🗓️ Controllo gli orari liberi",
    "book_appointment": "✅ Registro l'appuntamento",
}


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(label="Prezzo dell'igiene dentale", message="Quanto costa l'igiene dentale e ogni quanto va fatta?"),
        cl.Starter(label="Ho paura del dentista", message="Ho molta paura del dentista, come vi comportate con i pazienti ansiosi?"),
        cl.Starter(label="Prenotare una visita", message="Vorrei prenotare la prima visita, che orari ci sono liberi la prossima settimana?"),
        cl.Starter(label="Dopo un'estrazione", message="Ho appena tolto un dente, cosa devo fare nei prossimi giorni?"),
    ]


@cl.on_chat_start
async def start():
    if not Config.VECTOR_STORE_ID:
        await cl.Message(
            content=(
                "⚠️ La knowledge base non è ancora stata creata. Lancia una volta sola "
                "`python virtual_assistant/setup_knowledge_base.py` e riavvia l'app."
            )
        ).send()
        return
    cl.user_session.set("chat_logic", ChatLogic(client, Config.VECTOR_STORE_ID, studio))


@cl.on_message
async def handle_message(message: cl.Message):
    chat_logic = cl.user_session.get("chat_logic")
    if chat_logic is None:
        await cl.Message(content="Prima crea la knowledge base (vedi il messaggio iniziale).").send()
        return

    # process_message è un generatore bloccante (chiamate al modello): lo faccio girare in un
    # thread e mostro ogni passaggio (ricerca nei documenti, funzioni) nella chat man mano.
    events = chat_logic.process_message(message.content)
    step = None
    answer, sources = "", []

    try:
        while True:
            event = await cl.make_async(next)(events, None)
            if event is None:
                break

            if event.kind == "file_search":
                async with cl.Step(name="📚 Cerco nei documenti dello studio", type="tool") as s:
                    s.input = "\n".join(event.queries)

            elif event.kind == "tool_start":
                step = cl.Step(name=TOOL_LABELS.get(event.name, event.name), type="tool")
                step.input = json.dumps(event.arguments, ensure_ascii=False, indent=2)
                await step.send()

            elif event.kind == "tool_end":
                step.output = json.dumps(json.loads(event.result), ensure_ascii=False, indent=2)
                await step.update()

            elif event.kind == "answer":
                answer, sources = event.text, event.sources

    except Exception as e:
        error_message = f"❌ Si è verificato un errore: {e}"
        await cl.Message(content=error_message).send()
        print(error_message)
        return

    if sources:
        answer += "\n\n*Fonti: " + ", ".join(sources) + "*"
    await cl.Message(content=answer).send()
