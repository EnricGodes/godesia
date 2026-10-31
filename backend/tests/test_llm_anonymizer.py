"""Privacidad del respaldo Gemini: ningún dato identificativo de un vivo sale."""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import database
from database import SCHEMA, _normalize_accent
import llm_anonymizer
from llm_anonymizer import AnonymizationError, Anonymizer, build_request, finish


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.create_function("NORMALIZE", 1, _normalize_accent)
    c.executescript(SCHEMA)
    people = [
        # id, name, given, surname, sex, birth_date, birth_year, birth_place, death_date, death_year, is_alive, father, mother
        ("@I1@", "Pau Godes Caballeria", "Pau", "Godes Caballeria", "M", "3 feb. 1880", 1880, "Barcelona",
         "1 ene. 1950", 1950, 0, None, None),
        ("@I2@", "Mireia Godes Ferrer", "Mireia", "Godes Ferrer", "F", "12 mar. 1960", 1960, "Girona",
         None, None, 1, "@I1@", None),
        ("@I3@", "Oriol Puig Godes", "Oriol", "Puig Godes", "M", "5 may. 1990", 1990, "Sabadell",
         None, None, 1, None, "@I2@"),
    ]
    for p in people:
        c.execute(
            "INSERT INTO people (id, name, given_name, surname, sex, birth_date, birth_year, birth_place, "
            "death_date, death_year, is_alive, father_id, mother_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", p)
    c.execute("INSERT INTO children (parent_id, child_id) VALUES ('@I1@', '@I2@')")
    c.execute("INSERT INTO children (parent_id, child_id) VALUES ('@I2@', '@I3@')")
    c.execute("INSERT INTO notes (person_id, content) VALUES ('@I1@', 'Avi de Mireia Godes Ferrer, vivia al Born')")
    c.execute("INSERT INTO residences (person_id, address, city) VALUES ('@I2@', 'Carrer Major 1', 'Girona')")
    c.commit()
    return c


def _payload(system, contents):
    return system + "\n" + "\n".join(x["text"] for x in contents)


def test_living_people_are_aliased_everywhere(conn):
    anon, system, contents = build_request(conn, "Qui és la Mireia Godes Ferrer i on viu el seu fill?", lang="ca")
    out = _payload(system, contents)
    for leaked in ("Mireia", "Oriol Puig", "Girona", "Sabadell", "12 mar. 1960", "Carrer Major"):
        assert leaked not in out, leaked
    assert "Persona " in contents[-1]["text"]
    # El difunto sí va con datos completos.
    assert "Pau Godes Caballeria" in out and "3 feb. 1880" in out
    # Año de nacimiento del vivo sí (útil y no identificativo por sí solo).
    assert "n.1960" in out


def test_note_of_dead_person_naming_living_is_scrubbed(conn):
    anon, system, _ = build_request(conn, "Explica'm la vida de Pau Godes Caballeria")
    assert "Mireia Godes Ferrer" not in system
    assert "Avi de Persona" in system


def test_history_is_scrubbed(conn):
    history = [{"role": "user", "content": "Parla'm d'Oriol Puig Godes"},
               {"role": "assistant", "content": "<a href='x'>Oriol Puig Godes</a> va néixer el 1990"}]
    _, system, contents = build_request(conn, "I la seva mare?", history=history)
    assert all("Oriol" not in c["text"] for c in contents)
    assert contents[1]["role"] == "model"


def test_round_trip_restores_names_and_ids(conn):
    anon, system, contents = build_request(conn, "Qui és la Mireia Godes Ferrer?")
    alias, alias_id = anon.ref("@I2@", "Mireia Godes Ferrer")
    text = '{"answer": "%s (%s) és filla de Pau Godes Caballeria.", "people_mentioned": ["%s", "@I1@"]}' % (
        alias, alias_id, alias_id)
    result = finish(conn, anon, text)
    assert result["answer"] == "Mireia Godes Ferrer és filla de Pau Godes Caballeria."
    assert result["people_mentioned"] == ["@I2@", "@I1@"]


def test_guard_blocks_unscrubbed_name(conn):
    anon = Anonymizer(conn)
    with pytest.raises(AnonymizationError):
        anon.assert_clean("text amb mireia godes ferrer dins")


def test_accent_and_case_insensitive_scrub(conn):
    conn.execute("UPDATE people SET name = 'Mireia Godés Ferrer', surname = 'Godés Ferrer' WHERE id = '@I2@'")
    anon = Anonymizer(conn)
    assert "Mireia" not in anon.scrub("Qui és MIREIA GODES FERRER?")
    assert "Mireia" not in anon.scrub("i la mireia godés?")  # nombre + primer apellido, único


def test_living_without_dates_inferred_from_relatives(conn):
    conn.execute(
        "INSERT INTO people (id, name, given_name, surname, sex, is_alive) "
        "VALUES ('@I4@', 'Laia Roca Vidal', 'Laia', 'Roca Vidal', 'F', 0)")
    conn.execute("INSERT INTO marriages (person1_id, person2_id) VALUES ('@I3@', '@I4@')")
    assert "@I4@" in llm_anonymizer.living_ids(conn)
