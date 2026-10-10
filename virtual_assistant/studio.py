# studio.py
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from config import Config
from email_service import send_email

# Servizi prenotabili con durata indicativa in minuti (prezzi e dettagli stanno nei documenti)
SERVICES = {
    "prima visita": 30,
    "visita di controllo": 30,
    "igiene dentale": 45,
    "sbiancamento": 60,
    "otturazione": 45,
    "devitalizzazione": 60,
    "estrazione": 45,
    "visita ortodontica": 30,
    "visita urgente": 30,
}

WEEKDAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _slots_for(day: date) -> list[str]:
    """Orari di inizio possibili in un giorno (ogni 30 minuti), in base agli orari di apertura."""
    if day.weekday() == 6:  # domenica: chiuso
        return []
    ranges = [(9, 13)] if day.weekday() == 5 else [(9, 13), (15, 19)]
    return [
        f"{hour:02d}:{minute:02d}"
        for start, end in ranges
        for hour in range(start, end)
        for minute in (0, 30)
    ]


class Studio:
    """Agenda dello studio dentistico: orari liberi e prenotazioni.

    Sono le funzioni che il modello può chiamare (vedi tools.py). Ogni metodo restituisce un
    dizionario convertibile in JSON; gli errori hanno `"ok": False` e un messaggio chiaro, che
    spesso suggerisce l'alternativa (ad esempio gli orari liberi), così il modello può proporla.
    """

    def __init__(self, bookings_file=None, outbox_dir=None, today=None):
        self.bookings_file = Path(bookings_file or Config.BOOKINGS_FILE)
        self.outbox_dir = Path(outbox_dir or Config.OUTBOX_DIR)
        self.today = today or date.today  # funzione, così nei test si può fissare la data
        self.bookings = (
            json.loads(self.bookings_file.read_text(encoding="utf-8"))
            if self.bookings_file.exists()
            else []
        )

    def _save(self):
        self.bookings_file.parent.mkdir(parents=True, exist_ok=True)
        self.bookings_file.write_text(
            json.dumps(self.bookings, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _parse_day(self, raw: str) -> tuple[date | None, dict | None]:
        """Legge una data AAAA-MM-GG e controlla che sia prenotabile; altrimenti dà l'errore."""
        try:
            day = date.fromisoformat((raw or "").strip())
        except ValueError:
            return None, {"ok": False, "errore": "Data non valida: usa il formato AAAA-MM-GG."}

        today = self.today()
        if day <= today:
            return None, {"ok": False, "errore": "Si può prenotare solo da domani in poi."}
        if day > today + timedelta(days=Config.MAX_DAYS_AHEAD):
            return None, {
                "ok": False,
                "errore": f"Si può prenotare al massimo {Config.MAX_DAYS_AHEAD} giorni in avanti.",
            }
        if not _slots_for(day):
            return None, {"ok": False, "errore": "La domenica lo studio è chiuso."}
        return day, None

    def _free_slots(self, day: date) -> list[str]:
        taken = [b["orario"] for b in self.bookings if b["data"] == day.isoformat()]
        return [s for s in _slots_for(day) if taken.count(s) < Config.CHAIRS]

    # ------------------------------------------------------------- funzioni

    def get_available_slots(self, date: str) -> dict:
        """Orari di inizio ancora liberi in un giorno."""
        day, error = self._parse_day(date)
        if error:
            return error
        free = self._free_slots(day)
        return {
            "ok": True,
            "data": day.isoformat(),
            "giorno": WEEKDAYS[day.weekday()],
            "orari_liberi": free,
            "nota": "" if free else "Nessun orario libero in questo giorno: prova un altro giorno.",
        }

    def book_appointment(
        self, patient_name: str, email: str, service: str, date: str, time: str
    ) -> dict:
        """Registra un appuntamento e manda la email di conferma."""
        name = patient_name.strip()
        if not name:
            return {"ok": False, "errore": "Serve il nome e cognome del paziente."}
        if not EMAIL_RE.match(email.strip()):
            return {"ok": False, "errore": f"L'indirizzo email '{email}' non sembra valido."}
        if service not in SERVICES:
            return {
                "ok": False,
                "errore": f"Servizio '{service}' non prenotabile. Scegli tra: {', '.join(SERVICES)}.",
            }

        day, error = self._parse_day(date)
        if error:
            return error
        if time not in _slots_for(day):
            return {
                "ok": False,
                "errore": f"Alle {time} non si può iniziare un appuntamento.",
                "orari_liberi": self._free_slots(day),
            }
        if time not in self._free_slots(day):
            return {
                "ok": False,
                "errore": f"L'orario {time} del {day.isoformat()} è già al completo.",
                "orari_liberi": self._free_slots(day),
            }
        if any(
            b["email"].lower() == email.strip().lower() and b["data"] == day.isoformat()
            for b in self.bookings
        ):
            return {"ok": False, "errore": f"Con questa email c'è già un appuntamento il {day.isoformat()}."}

        booking = {
            "paziente": name,
            "email": email.strip(),
            "servizio": service,
            "data": day.isoformat(),
            "orario": time,
            "creato_il": datetime.now().isoformat(timespec="seconds"),
        }
        self.bookings.append(booking)
        self._save()

        giorno = f"{WEEKDAYS[day.weekday()]} {day.strftime('%d/%m/%Y')}"
        send_email(
            to=booking["email"],
            subject="Conferma appuntamento - Studio Dentistico Sorriso",
            body=(
                f"Gentile {name},\n\n"
                f"abbiamo prenotato il tuo appuntamento: {service}, {giorno} alle {time} "
                f"(durata indicativa {SERVICES[service]} minuti).\n\n"
                "Ti aspettiamo in via Sparano 112, a Bari. Porta un documento d'identità e la "
                "tessera sanitaria. Se non puoi venire, avvisaci almeno 24 ore prima.\n\n"
                "Studio Dentistico Sorriso"
            ),
            outbox_dir=self.outbox_dir,
        )
        return {
            "ok": True,
            "paziente": name,
            "servizio": service,
            "data": day.isoformat(),
            "giorno": WEEKDAYS[day.weekday()],
            "orario": time,
            "email_di_conferma_inviata_a": booking["email"],
        }
