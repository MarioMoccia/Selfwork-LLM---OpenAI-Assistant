# Selfwork LLM - OpenAI Assistant

Assistente virtuale (Chainlit) dello **Studio Dentistico Sorriso**, un esempio inventato di
studio odontoiatrico a Bari. Giulia, l'assistente, fa due cose:

1. **risponde alle domande dei pazienti cercando nei documenti dello studio** (servizi e prezzi,
   orari e team, domande frequenti) con `file_search` e un *vector store* di OpenAI, citando i
   documenti usati;
2. **prenota gli appuntamenti** con delle funzioni (`get_available_slots`, `book_appointment`)
   e manda al paziente una **email di conferma**.

## Nota importante: Assistants API → Responses API

Il progetto di riferimento del corso usa l'**API Assistants** di OpenAI (assistente, thread,
run con polling). Quell'API è stata **dismessa**: le chiamate a `assistants` e `threads`
rispondono ora `404 Not Found` (verificato con una chiave valida). Il progetto usa quindi la
**Responses API**, il suo sostituto ufficiale, con gli stessi concetti:

| API Assistants (dismessa) | Questo progetto (Responses API) |
|---|---|
| assistente creato una volta (nome, istruzioni, modello) | `instructions` e `model` a ogni richiesta (`chat_logic.py`) |
| tool `file_search` + vector store | identico: `file_search` + vector store, creato da `setup_knowledge_base.py` |
| thread della conversazione | `previous_response_id`: OpenAI ricorda la conversazione |
| run + polling di `run.status` | una sola chiamata `client.responses.create(...)` |
| `requires_action` + `submit_tool_outputs` | il modello chiede una funzione → la eseguo → rimando `function_call_output` |

## Come funziona

```
domanda del paziente
        │
        ▼
  ┌─ Responses API (modello + istruzioni + strumenti) ◀──────────────┐
  │         │                                                         │
  │         ├─ file_search ─▶ cerca nei documenti (lo fa OpenAI)      │
  │         │                                                         │
  │         ├─ function_call ─▶ la eseguo io (studio.py) ─▶ risultato ┘
  │         │
  │         └─ testo ─▶ risposta finale (con i documenti citati)
```

1. **Knowledge base** (una volta sola): `setup_knowledge_base.py` carica in un vector store i
   documenti della cartella `kb/` e salva l'ID in `.env` (`VECTOR_STORE_ID`).
2. **Messaggio**: `ChatLogic.process_message` (`chat_logic.py`) invia il messaggio con le
   istruzioni e gli strumenti. Nei test il modello ha cercato nei documenti da sé ("quanto
   costa l'igiene?") e usato le funzioni per le prenotazioni.
3. **Funzioni**: se il modello ne chiede una, la eseguo io e rimando il risultato collegandolo
   alla risposta precedente; il modello può concatenarne più d'una (ad esempio controllare gli
   orari di più giorni) prima di rispondere. Il ciclo ha un limite di giri.
4. **Memoria**: l'ID dell'ultima risposta viene salvato solo quando la risposta è completa; se
   una chiamata fallisce a metà, la conversazione resta utilizzabile.

Nella chat ogni ricerca nei documenti e ogni funzione compaiono come passaggi espandibili,
e sotto la risposta sono indicati i documenti usati.

## Le funzioni

| Funzione | Cosa fa |
|---|---|
| `get_available_slots(date)` | orari di inizio ancora liberi in un giorno (ogni 30 minuti; 2 poltrone) |
| `book_appointment(patient_name, email, service, date, time)` | registra l'appuntamento e manda l'email di conferma |

Regole controllate dal codice (`studio.py`): prenotazione da domani a 30 giorni in avanti,
domenica chiusa, orari solo dentro le fasce di apertura, massimo due appuntamenti per orario,
email valida, servizio tra quelli ammessi (`enum` nello schema della funzione), un solo
appuntamento al giorno per email. Un errore non blocca l'app: diventa il risultato della funzione,
con gli orari liberi come alternativa, e il modello lo spiega al paziente.

Gli appuntamenti sono salvati in `virtual_assistant/data/prenotazioni.json`, le email in `outbox/`
(entrambi non versionati). **L'email è simulata**: `email_service.py` scrive il messaggio in un
file, così non servono account esterni e non si scrive a persone vere. Per inviarle davvero basta
sostituire il corpo di `send_email` con la chiamata a un servizio come Resend.

## Setup

```bash
poetry install
cp .env.example .env   # e inserisci la tua OPENAI_API_KEY
eval $(poetry env activate)
python virtual_assistant/setup_knowledge_base.py   # una sola volta: crea la knowledge base
```

## Per eseguire l'applicazione

```bash
chainlit run virtual_assistant/__init__.py -w
```

## Test

```bash
poetry run pytest
```

I test controllano la logica dell'agenda e la gestione degli errori delle funzioni, senza
chiamare il modello.

## Struttura

| File | Contenuto |
|---|---|
| `kb/` | i documenti della knowledge base (servizi e prezzi, studio e orari, domande frequenti) |
| `virtual_assistant/setup_knowledge_base.py` | crea il vector store e lo salva in `.env` |
| `virtual_assistant/chat_logic.py` | istruzioni, strumenti e ciclo delle risposte |
| `virtual_assistant/tools.py` | descrizione delle funzioni per il modello e `execute_tool` |
| `virtual_assistant/studio.py` | agenda e prenotazioni |
| `virtual_assistant/email_service.py` | invio (simulato) dell'email di conferma |
| `virtual_assistant/__init__.py` | app Chainlit |

## Limiti

- Lo studio, i prezzi e il team sono inventati per l'esercizio.
- Il modello non dà consigli medici: per i dubbi clinici invita a prenotare una visita.
- Non c'è autenticazione né modifica o cancellazione degli appuntamenti.
- Se i documenti di `kb/` cambiano, va creata una nuova knowledge base (cancella la riga
  `VECTOR_STORE_ID` da `.env` e rilancia lo script di setup).
