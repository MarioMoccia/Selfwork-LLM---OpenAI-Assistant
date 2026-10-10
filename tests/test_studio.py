import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "virtual_assistant"))

from studio import SERVICES, Studio  # noqa: E402
from tools import execute_tool  # noqa: E402

TODAY = date(2026, 10, 12)  # lunedì


@pytest.fixture
def studio(tmp_path):
    return Studio(tmp_path / "prenotazioni.json", tmp_path / "outbox", today=lambda: TODAY)


def book(studio, **overrides):
    data = dict(
        patient_name="Luca Verdi",
        email="luca@example.com",
        service="igiene dentale",
        date="2026-10-14",  # mercoledì
        time="15:30",
    )
    return studio.book_appointment(**{**data, **overrides})


def test_slots_follow_opening_hours(studio):
    weekday = studio.get_available_slots("2026-10-14")
    assert weekday["giorno"] == "mercoledì"
    assert weekday["orari_liberi"][0] == "09:00" and "13:00" not in weekday["orari_liberi"]
    assert "15:00" in weekday["orari_liberi"] and weekday["orari_liberi"][-1] == "18:30"
    saturday = studio.get_available_slots("2026-10-17")
    assert saturday["orari_liberi"][-1] == "12:30"


def test_date_rules(studio):
    assert "domenica" in studio.get_available_slots("2026-10-18")["errore"]
    assert studio.get_available_slots("2026-10-12")["ok"] is False  # oggi
    assert studio.get_available_slots("2026-12-30")["ok"] is False  # oltre 30 giorni
    assert studio.get_available_slots("domani")["ok"] is False


def test_booking_saves_and_sends_email(studio, tmp_path):
    result = book(studio)
    assert result["ok"] and result["giorno"] == "mercoledì"
    emails = list((tmp_path / "outbox").glob("*.txt"))
    assert len(emails) == 1
    body = emails[0].read_text(encoding="utf-8")
    assert "luca@example.com" in body and "igiene dentale" in body and "15:30" in body
    # i dati restano dopo un riavvio
    again = Studio(tmp_path / "prenotazioni.json", tmp_path / "outbox", today=lambda: TODAY)
    assert len(again.bookings) == 1


def test_two_chairs_then_full(studio):
    assert book(studio)["ok"]
    assert book(studio, email="anna@example.com", patient_name="Anna Neri")["ok"]
    full = book(studio, email="paolo@example.com", patient_name="Paolo Gialli")
    assert full["ok"] is False and "15:30" not in full["orari_liberi"]
    assert "15:30" not in studio.get_available_slots("2026-10-14")["orari_liberi"]


def test_booking_validation(studio):
    assert book(studio, email="non-una-email")["ok"] is False
    assert book(studio, patient_name="  ")["ok"] is False
    assert book(studio, service="chirurgia plastica")["ok"] is False
    assert book(studio, time="13:00")["ok"] is False  # pausa pranzo
    assert book(studio, time="15:10")["ok"] is False  # non è un orario di inizio
    assert book(studio)["ok"]
    assert book(studio, time="16:00")["ok"] is False  # stessa email, stesso giorno


def test_execute_tool_survives_bad_input(studio):
    ok = json.loads(execute_tool(studio, "get_available_slots", '{"date": "2026-10-14"}'))
    assert ok["ok"]
    assert json.loads(execute_tool(studio, "volare", "{}"))["ok"] is False
    assert json.loads(execute_tool(studio, "get_available_slots", "{non json"))["ok"] is False
    assert json.loads(execute_tool(studio, "get_available_slots", '{"giorno": 1}'))["ok"] is False


def test_services_are_documented_in_kb():
    prices = (ROOT / "kb" / "servizi_e_prezzi.txt").read_text(encoding="utf-8").lower()
    for key in ("visita", "igiene", "sbiancamento", "otturazione", "devitalizzazione",
                "estrazione", "ortodont", "urgen"):
        assert key in prices
    assert len(SERVICES) == 9
