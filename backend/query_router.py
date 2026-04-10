"""Query Router para Godesia: routing determinista multilingüe con debug visible."""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from database import (
    get_alive_people,
    get_all_photos,
    get_birthdays_this_week,
    get_children,
    get_grandchildren,
    get_grandparents,
    get_notes,
    get_occupations,
    get_parents,
    get_person,
    get_residences,
    get_siblings,
    get_spouses,
)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")



def _norm(text: str) -> str:
    text = _strip_accents(text or "").lower()
    text = re.sub(r"[\"'“”‘’]", " ", text)
    text = re.sub(r"[^\w/\-]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text



def _person_card(person: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": person.get("id"),
        "name": person.get("name"),
        "photo": person.get("photo_file") or person.get("photo"),
    }



def _format_person(person: Dict[str, Any]) -> str:
    parts = [person.get("name", "?")]
    birth_year = person.get("birth_year")
    death_year = person.get("death_year")
    if birth_year:
        if death_year:
            parts.append(f"({birth_year}-{death_year})")
        else:
            parts.append(f"({birth_year})")
    if person.get("birth_place"):
        parts.append(f"de {person['birth_place']}")
    return " ".join(parts)



def _rows_to_dicts(rows: Iterable[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [dict(r) if isinstance(r, sqlite3.Row) else r for r in rows]



def _split_two_names(fragment: str) -> Tuple[Optional[str], Optional[str]]:
    m = re.search(r"(.+?)\s+(?:y|i|and)\s+(.+)", fragment, re.IGNORECASE)
    if not m:
        return None, None
    return m.group(1).strip(" ?.,!;:"), m.group(2).strip(" ?.,!;:")



def _parse_ddmmyyyy(question: str) -> Optional[Tuple[int, int, int]]:
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", question)
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return None
    return day, month, year



def _parse_decade(question: str) -> Optional[Tuple[int, int]]:
    q = _norm(question)
    # "década de 1920", "decada del 1920", "1920s"
    m = re.search(r"(?:decada|decade)(?: de| del)?\s+(\d{4})", q)
    if not m:
        m = re.search(r"\b(\d{4})s\b", q)
    if not m:
        return None
    start = int(m.group(1))
    return start, start + 9



def _language_of(question: str) -> str:
    q = _norm(question)
    if re.search(r"\b(qui|quines|quants|naixer|morir|parella|germans|avis|nets|caso|casar|cognom|residencia|adreca|qualsevol)\b", q):
        return "ca"
    if re.search(r"\b(who|which|born|died|children|spouse|married|residence|address|surname|relationship|decade)\b", q):
        return "en"
    return "es"



@dataclass
class PersonMatch:
    row: Dict[str, Any]
    score: int


class QueryRouter:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ------------------------------------------------------------------
    # Respuesta pública
    # ------------------------------------------------------------------
    def route(self, question: str) -> Optional[Dict[str, Any]]:
        sql_trace: List[str] = []

        def tracer(statement: str) -> None:
            st = statement.strip()
            if st and not st.upper().startswith(("BEGIN", "COMMIT", "ROLLBACK", "PRAGMA")):
                sql_trace.append(st)

        try:
            self.conn.set_trace_callback(tracer)
        except Exception:
            tracer = None  # noqa: F841

        handler_name = "no_match"
        try:
            handler_name, result = self._dispatch(question)
            if not result:
                result = {
                    "answer": "No he sabido responder esta pregunta con las reglas actuales.",
                    "people_mentioned": [],
                    "people_with_photos": [],
                }
            result["source"] = "db"
            result["debug"] = {
                "handler": handler_name,
                "sql": sql_trace,
            }
            result["answer"] = self._append_debug(result.get("answer", ""), handler_name, sql_trace)
            return result
        finally:
            try:
                self.conn.set_trace_callback(None)
            except Exception:
                pass

    def _append_debug(self, answer: str, handler_name: str, sql_trace: Sequence[str]) -> str:
        lines = [answer, "", "--- DEBUG ---", f"handler: {handler_name}"]
        if sql_trace:
            lines.append("sql:")
            for idx, st in enumerate(sql_trace, start=1):
                lines.append(f"{idx}. {st}")
        else:
            lines.append("sql: (sin consultas SQLite capturadas)")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------
    def _dispatch(self, question: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        q = _norm(question)

        routes: List[Tuple[str, Callable[[str], Optional[Dict[str, Any]]]]] = [
            ("handle_relationship", self.handle_relationship),
            ("handle_birth_date_search", self.handle_birth_date_search),
            ("handle_first_surname", self.handle_first_surname),
            ("handle_death_place_year", self.handle_death_place_year),
            ("handle_birth_place_people", self.handle_birth_place_people),
            ("handle_residence", self.handle_residence),
            ("handle_spouse_disambiguated", self.handle_spouse_disambiguated),
            ("handle_children_born_in", self.handle_children_born_in),
            ("handle_births_by_decade", self.handle_births_by_decade),
            ("handle_age_at_marriage", self.handle_age_at_marriage),
            ("handle_mother", self.handle_mother),
            ("handle_father", self.handle_father),
            ("handle_parents", self.handle_parents),
            ("handle_children", self.handle_children),
            ("handle_siblings", self.handle_siblings),
            ("handle_spouse", self.handle_spouse),
            ("handle_grandparents", self.handle_grandparents),
            ("handle_grandchildren", self.handle_grandchildren),
            ("handle_birth", self.handle_birth),
            ("handle_death", self.handle_death),
            ("handle_occupation", self.handle_occupation),
            ("handle_notes", self.handle_notes),
            ("handle_photos", self.handle_photos),
            ("handle_birthdays", self.handle_birthdays),
            ("handle_alive", self.handle_alive),
            ("handle_stats", self.handle_stats),
            ("handle_search", self.handle_search),
            ("name_fallback", self._try_name_fallback),
        ]

        gating: Dict[str, Callable[[str], bool]] = {
            "handle_relationship": lambda s: bool(re.search(r"\b(parentesco|relacion|relationship)\b", _norm(s))) and bool(re.search(r"\b(entre|between)\b", _norm(s))),
            "handle_birth_date_search": lambda s: bool(_parse_ddmmyyyy(s)) and bool(re.search(r"\b(quien|qui|who)\b", _norm(s))) and bool(re.search(r"\b(nacio|nacio|nascut|born)\b", _norm(s))),
            "handle_first_surname": lambda s: bool(re.search(r"\b(primer apellido|primer cognom|first surname)\b", _norm(s))),
            "handle_death_place_year": lambda s: bool(re.search(r"\b(quien|qui|who)\b", _norm(s))) and bool(re.search(r"\b(murio|morir|died)\b", _norm(s))) and bool(re.search(r"\ben\s+.+\b(18|19|20)\d{2}\b", _norm(s))),
            "handle_birth_place_people": lambda s: bool(re.search(r"\b(que personas|quines persones|which people|who)\b", _norm(s))) and bool(re.search(r"\b(nacieron|nascudes|nascuts|born)\b", _norm(s))) and bool(re.search(r"\ben\b", _norm(s))),
            "handle_residence": lambda s: bool(re.search(r"\b(residencia|direccion|adreca|domicili|address|residence)\b", _norm(s))),
            "handle_spouse_disambiguated": lambda s: bool(re.search(r"\b(con quien se caso|amb qui es va casar|who did .* marry)\b", _norm(s))) and bool(re.search(r"\b(nacida en|nacido en|born in|llamada|llamado|named)\b", _norm(s))),
            "handle_children_born_in": lambda s: bool(re.search(r"\b(que hijos de|quins fills de|which children of)\b", _norm(s))) and bool(re.search(r"\b(nacieron en|nascuts a|born in)\b", _norm(s))),
            "handle_births_by_decade": lambda s: bool(re.search(r"\b(cuantos|quants|how many)\b", _norm(s))) and bool(re.search(r"\b(nacimientos|naixements|births)\b", _norm(s))) and _parse_decade(s) is not None,
            "handle_age_at_marriage": lambda s: bool(re.search(r"\b(que edad tenia|quina edat tenia|how old was)\b", _norm(s))) and bool(re.search(r"\b(cuando se caso|quan es va casar|when .* married|when .* got married)\b", _norm(s))),
            "handle_mother": lambda s: bool(re.search(r"\b(madre|mare|mother)\b", _norm(s))),
            "handle_father": lambda s: bool(re.search(r"\b(padre|pare|father)\b", _norm(s))),
            "handle_parents": lambda s: bool(re.search(r"\b(padres|pares|parents)\b", _norm(s))),
            "handle_children": lambda s: bool(re.search(r"\b(hijos|fills|children)\b", _norm(s))),
            "handle_siblings": lambda s: bool(re.search(r"\b(hermanos|germans|siblings)\b", _norm(s))),
            "handle_spouse": lambda s: bool(re.search(r"\b(conyuge|conyuge|spouse|espos[ao]|marido|mujer|caso|casar|marry)\b", _norm(s))),
            "handle_grandparents": lambda s: bool(re.search(r"\b(abuelos|avis|grandparents|abuelo|abuela|avia)\b", _norm(s))),
            "handle_grandchildren": lambda s: bool(re.search(r"\b(nietos|nets|grandchildren|nieto|nieta)\b", _norm(s))),
            "handle_birth": lambda s: bool(re.search(r"\b(nacio|nascut|born|fecha de nacimiento|data de naixement)\b", _norm(s))),
            "handle_death": lambda s: bool(re.search(r"\b(murio|morir|died|defuncion|muerte)\b", _norm(s))),
            "handle_occupation": lambda s: bool(re.search(r"\b(oficio|ocupacion|profesion|occupation|job|treball|feina)\b", _norm(s))),
            "handle_notes": lambda s: bool(re.search(r"\b(notas|notes|observaciones|documents?)\b", _norm(s))),
            "handle_photos": lambda s: bool(re.search(r"\b(fotos|foto|photos?|images?)\b", _norm(s))),
            "handle_birthdays": lambda s: bool(re.search(r"\b(cumpleanos|aniversari|birthday)\b", _norm(s))),
            "handle_alive": lambda s: bool(re.search(r"\b(vivos|vius|alive|living)\b", _norm(s))),
            "handle_stats": lambda s: bool(re.search(r"\b(estadisticas|estadistiques|stats|resumen|resum)\b", _norm(s))),
            "handle_search": lambda s: bool(re.search(r"\b(busca|cerca|search|quien es|qui es|who is)\b", _norm(s))),
            "name_fallback": lambda s: True,
        }

        for name, fn in routes:
            if gating[name](question):
                result = fn(question)
                if result:
                    return name, result
        return "no_match", None

    # ------------------------------------------------------------------
    # Resolución de personas
    # ------------------------------------------------------------------
    def _search_people(self, text: str, limit: int = 20) -> List[Dict[str, Any]]:
        cleaned = re.sub(r"\s+", "%", text.strip())
        rows = self.conn.execute(
            "SELECT id, name, given_name, surname, birth_year, death_year, birth_place, photo_file, is_alive, father_id, mother_id, father_name, mother_name "
            "FROM people WHERE name LIKE ? COLLATE NOCASE ORDER BY name LIMIT ?",
            (f"%{cleaned}%", limit),
        ).fetchall()
        return _rows_to_dicts(rows)

    def _rank_person_candidates(
        self,
        candidates: Sequence[Dict[str, Any]],
        raw_name: str,
        birth_place: Optional[str] = None,
        birth_year: Optional[int] = None,
    ) -> List[PersonMatch]:
        target = _norm(raw_name)
        target_tokens = set(target.split())
        ranked: List[PersonMatch] = []
        for row in candidates:
            score = 0
            name_norm = _norm(row.get("name", ""))
            cand_tokens = set(name_norm.split())
            if name_norm == target:
                score += 1000
            if name_norm.startswith(target):
                score += 200
            score += 30 * len(target_tokens & cand_tokens)
            if birth_place and row.get("birth_place") and _norm(birth_place) in _norm(row["birth_place"]):
                score += 150
            if birth_year and row.get("birth_year") == birth_year:
                score += 150
            # Penalizar candidatos con poca cobertura respecto al nombre pedido
            missing = len(target_tokens - cand_tokens)
            score -= 20 * missing
            ranked.append(PersonMatch(row=row, score=score))
        ranked.sort(key=lambda x: (-x.score, x.row.get("birth_year") or 9999, x.row.get("name") or ""))
        return ranked

    def _resolve_person(
        self,
        raw_name: str,
        birth_place: Optional[str] = None,
        birth_year: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        if not raw_name:
            return None
        candidates = self._search_people(raw_name, limit=25)
        if not candidates:
            return None
        ranked = self._rank_person_candidates(candidates, raw_name, birth_place=birth_place, birth_year=birth_year)
        best = ranked[0]
        # exigir un mínimo razonable para evitar disparates tipo Artur -> Soledad
        if best.score < 40:
            return None
        return dict(best.row)

    def _extract_name_after(self, question: str, patterns: Sequence[str]) -> Optional[str]:
        for pat in patterns:
            m = re.search(pat, question, re.IGNORECASE)
            if m:
                text = m.group(1).strip(" ?.,!;:")
                text = re.sub(r"^(de|d['’]|of)\s+", "", text, flags=re.IGNORECASE)
                return text.strip()
        return None

    def _extract_capitalized_name(self, question: str) -> Optional[str]:
        names = re.findall(r"[A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][\wÁÉÍÓÚÀÈÌÒÙÑÇáéíóúàèìòùñç'\-]+(?:\s+[A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][\wÁÉÍÓÚÀÈÌÒÙÑÇáéíóúàèìòùñç'\-]+){1,5}", question)
        if not names:
            return None
        # devolver la más larga
        names.sort(key=lambda s: (-len(s.split()), -len(s)))
        return names[0].strip()

    # ------------------------------------------------------------------
    # Handlers principales
    # ------------------------------------------------------------------
    def handle_relationship(self, question: str) -> Optional[Dict[str, Any]]:
        q = question.strip().rstrip("?.,!")
        m = re.search(r"(?:entre|between)\s+(.+)$", q, re.IGNORECASE)
        if not m:
            return None
        a, b = _split_two_names(m.group(1))
        if not a or not b:
            return None
        p1 = self._resolve_person(a)
        p2 = self._resolve_person(b)
        if not p1 or not p2:
            return None

        rel = None
        if p1["id"] == p2["id"]:
            rel = "son la misma persona"
        elif p2.get("father_id") == p1["id"] or p2.get("mother_id") == p1["id"]:
            rel = f"{p1['name']} es progenitor/a de {p2['name']}"
        elif p1.get("father_id") == p2["id"] or p1.get("mother_id") == p2["id"]:
            rel = f"{p2['name']} es progenitor/a de {p1['name']}"
        elif ((p1.get("father_id") and p1.get("father_id") == p2.get("father_id")) or
              (p1.get("mother_id") and p1.get("mother_id") == p2.get("mother_id"))):
            rel = "son hermanos/as"
        else:
            spouse_ids = {s["person"]["id"] for s in get_spouses(self.conn, p1["id"])}
            if p2["id"] in spouse_ids:
                rel = "fueron cónyuges"
        if not rel:
            gp1 = {gp["person"]["id"] for gp in get_grandparents(self.conn, p1["id"]) if gp.get("person")}
            gp2 = {gp["person"]["id"] for gp in get_grandparents(self.conn, p2["id"]) if gp.get("person")}
            if p1["id"] in gp2:
                rel = f"{p1['name']} es abuelo/a de {p2['name']}"
            elif p2["id"] in gp1:
                rel = f"{p2['name']} es abuelo/a de {p1['name']}"
            elif gp1 & gp2:
                rel = "son primos/as hermanos/as"
        if not rel:
            rel = "no he podido determinar el parentesco exacto con las reglas actuales"
        return {
            "answer": f"Entre {p1['name']} y {p2['name']}, {rel}.",
            "people_mentioned": [p1["id"], p2["id"]],
            "people_with_photos": [_person_card(p1), _person_card(p2)],
        }

    def handle_birth_date_search(self, question: str) -> Optional[Dict[str, Any]]:
        parsed = _parse_ddmmyyyy(question)
        if not parsed:
            return None
        day, month, year = parsed
        rows = self.conn.execute(
            "SELECT id, name, birth_year, death_year, birth_place, photo_file, is_alive "
            "FROM people WHERE birth_day = ? AND birth_month = ? AND birth_year = ? ORDER BY name",
            (day, month, year),
        ).fetchall()
        if not rows:
            return {
                "answer": f"No he encontrado a nadie nacido el {day:02d}/{month:02d}/{year}.",
                "people_mentioned": [],
                "people_with_photos": [],
            }
        people = _rows_to_dicts(rows)
        if len(people) == 1:
            p = people[0]
            place = f" en {p['birth_place']}" if p.get("birth_place") else ""
            return {
                "answer": f"La persona nacida el {day:02d}/{month:02d}/{year} es {p['name']}{place}.",
                "people_mentioned": [p["id"]],
                "people_with_photos": [_person_card(p)],
            }
        return {
            "answer": "He encontrado %d personas nacidas el %02d/%02d/%04d:\n%s" % (
                len(people), day, month, year, "\n".join(f"- {_format_person(p)}" for p in people)
            ),
            "people_mentioned": [p["id"] for p in people],
            "people_with_photos": [_person_card(p) for p in people[:8]],
        }

    def handle_first_surname(self, question: str) -> Optional[Dict[str, Any]]:
        m = re.search(r"([A-ZÁÉÍÓÚÀÈÌÒÙÑÇa-záéíóúàèìòùñç'\-]+)\s+como\s+primer\s+apellido", question, re.IGNORECASE)
        if not m:
            m = re.search(r"([A-ZÁÉÍÓÚÀÈÌÒÙÑÇa-záéíóúàèìòùñç'\-]+)\s+com\s+a\s+primer\s+cognom", question, re.IGNORECASE)
        if not m:
            m = re.search(r"first\s+surname\s+.*?([A-ZÁÉÍÓÚÀÈÌÒÙÑÇa-záéíóúàèìòùñç'\-]+)", question, re.IGNORECASE)
        if not m:
            return None
        surname = m.group(1).strip()
        rows = self.conn.execute(
            "SELECT id, name, birth_year, death_year, birth_place, photo_file, is_alive "
            "FROM people WHERE surname = ? COLLATE NOCASE OR surname LIKE ? COLLATE NOCASE "
            "ORDER BY birth_year, name LIMIT 200",
            (surname, f"{surname} %"),
        ).fetchall()
        people = _rows_to_dicts(rows)
        if not people:
            return {
                "answer": f"No he encontrado personas con {surname} como primer apellido.",
                "people_mentioned": [],
                "people_with_photos": [],
            }
        return {
            "answer": "He encontrado %d personas con %s como primer apellido:\n%s" % (
                len(people), surname, "\n".join(f"- {_format_person(p)}" for p in people[:25])
            ),
            "people_mentioned": [p["id"] for p in people],
            "people_with_photos": [_person_card(p) for p in people[:8]],
        }

    def handle_birth_place_people(self, question: str) -> Optional[Dict[str, Any]]:
        m = re.search(r"(?:nacieron|nascuts?|born)\s+en\s+(.+)$", question, re.IGNORECASE)
        if not m:
            return None
        place = m.group(1).strip(" ?.,!;:")
        rows = self.conn.execute(
            "SELECT id, name, birth_year, death_year, birth_place, photo_file, is_alive "
            "FROM people WHERE birth_place LIKE ? COLLATE NOCASE ORDER BY birth_year, name LIMIT 100",
            (f"%{place}%",),
        ).fetchall()
        people = _rows_to_dicts(rows)
        if not people:
            return {
                "answer": f"No he encontrado personas nacidas en {place}.",
                "people_mentioned": [],
                "people_with_photos": [],
            }
        return {
            "answer": "Personas nacidas en %s (%d):\n%s" % (
                place, len(people), "\n".join(f"- {_format_person(p)}" for p in people[:25])
            ),
            "people_mentioned": [p["id"] for p in people],
            "people_with_photos": [_person_card(p) for p in people[:8]],
        }

    def handle_death_place_year(self, question: str) -> Optional[Dict[str, Any]]:
        m = re.search(r"(?:murio|morir|died)\s+en\s+(.+?)\s+en\s+(\d{4})\b", question, re.IGNORECASE)
        if not m:
            return None
        place = m.group(1).strip(" ?.,!;:")
        year = int(m.group(2))
        rows = self.conn.execute(
            "SELECT id, name, death_date, death_year, death_place, birth_year, photo_file, is_alive "
            "FROM people WHERE death_year = ? AND death_place LIKE ? COLLATE NOCASE ORDER BY name LIMIT 50",
            (year, f"%{place}%"),
        ).fetchall()
        people = _rows_to_dicts(rows)
        if not people:
            return {
                "answer": f"No he encontrado a nadie que muriera en {place} en {year}.",
                "people_mentioned": [],
                "people_with_photos": [],
            }
        if len(people) == 1:
            p = people[0]
            when = p.get("death_date") or str(year)
            return {
                "answer": f"{p['name']} murió el {when}.",
                "people_mentioned": [p["id"]],
                "people_with_photos": [_person_card(p)],
            }
        return {
            "answer": "He encontrado %d personas que murieron en %s en %d:\n%s" % (
                len(people), place, year, "\n".join(f"- {p['name']} ({p.get('death_date') or p.get('death_year')})" for p in people)
            ),
            "people_mentioned": [p["id"] for p in people],
            "people_with_photos": [_person_card(p) for p in people[:8]],
        }

    def handle_residence(self, question: str) -> Optional[Dict[str, Any]]:
        name = self._extract_name_after(
            question,
            [
                r"aparece\s+documentad[oa]\s+(.+)$",
                r"documentado\s+(.+)$",
                r"documentada\s+(.+)$",
                r"residencia\s+de\s+(.+)$",
                r"direccion\s+de\s+(.+)$",
                r"adreca\s+de\s+(.+)$",
            ],
        )
        if not name:
            return None
        person = self._resolve_person(name)
        if not person:
            return None
        residences = _rows_to_dicts(get_residences(self.conn, person["id"]))
        if not residences:
            return {
                "answer": f"No tengo información sobre residencias o direcciones de {person['name']}.",
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }
        parts = []
        for r in residences:
            line = r.get("address") or ""
            if r.get("address2"):
                line += f" {r['address2']}"
            if r.get("city"):
                line += f", {r['city']}"
            if r.get("country"):
                line += f", {r['country']}"
            if r.get("date"):
                line += f" ({r['date']})"
            parts.append(line.strip(", "))
        return {
            "answer": f"Residencias o direcciones de {person['name']}:\n" + "\n".join(f"- {p}" for p in parts),
            "people_mentioned": [person["id"]],
            "people_with_photos": [_person_card(person)],
        }

    def handle_spouse_disambiguated(self, question: str) -> Optional[Dict[str, Any]]:
        name = self._extract_name_after(question, [r"llamad[oa]\s+(.+)$", r"named\s+(.+)$"])
        place_match = re.search(r"(?:nacida|nacido|born)\s+en\s+(.+?)\s+(?:llamad[oa]|named)\s+", question, re.IGNORECASE)
        birth_place = place_match.group(1).strip(" ?.,!;:") if place_match else None
        if not name:
            return None
        person = self._resolve_person(name, birth_place=birth_place)
        if not person:
            return None
        return self._spouse_response(person)

    def handle_children_born_in(self, question: str) -> Optional[Dict[str, Any]]:
        m = re.search(r"(?:que\s+hijos\s+de|quins\s+fills\s+de|which\s+children\s+of)\s+(.+?)\s+(?:nacieron\s+en|nascuts?\s+a|born\s+in)\s+(.+)$", question, re.IGNORECASE)
        if not m:
            return None
        raw_name = m.group(1).strip(" ?.,!;:")
        place = m.group(2).strip(" ?.,!;:")
        person = self._resolve_person(raw_name)
        if not person:
            return None
        children = _rows_to_dicts(get_children(self.conn, person["id"]))
        filtered = [c for c in children if c.get("birth_place") and _norm(place) in _norm(c["birth_place"])]
        if not filtered:
            return {
                "answer": f"No he encontrado hijos de {person['name']} nacidos en {place}.",
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }
        return {
            "answer": f"Hijos de {person['name']} nacidos en {place}:\n" + "\n".join(f"- {_format_person(c)}" for c in filtered),
            "people_mentioned": [person["id"]] + [c["id"] for c in filtered],
            "people_with_photos": [_person_card(person)] + [_person_card(c) for c in filtered[:7]],
        }

    def handle_births_by_decade(self, question: str) -> Optional[Dict[str, Any]]:
        decade = _parse_decade(question)
        if not decade:
            return None
        start, end = decade
        count = self.conn.execute(
            "SELECT COUNT(*) FROM people WHERE birth_year BETWEEN ? AND ?",
            (start, end),
        ).fetchone()[0]
        return {
            "answer": f"Hay {count} nacimientos registrados en la década de {start}.",
            "people_mentioned": [],
            "people_with_photos": [],
        }

    def handle_age_at_marriage(self, question: str) -> Optional[Dict[str, Any]]:
        m = re.search(r"(?:que\s+edad\s+tenia|quina\s+edat\s+tenia|how\s+old\s+was)\s+(.+?)\s+(?:cuando\s+se\s+caso|quan\s+es\s+va\s+casar|when\s+.*?married)", question, re.IGNORECASE)
        if not m:
            return None
        raw_name = m.group(1).strip(" ?.,!;:")
        person = self._resolve_person(raw_name)
        if not person:
            return None
        birth_year = person.get("birth_year")
        spouses = get_spouses(self.conn, person["id"])
        dated = [s for s in spouses if s.get("marriage_date")]
        if not birth_year or not dated:
            return {
                "answer": f"No tengo datos suficientes para calcular la edad al casarse de {person['name']}.",
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }
        # extraer primer año de matrimonio disponible
        marriage_years = []
        for s in dated:
            m2 = re.search(r"(\d{4})", s["marriage_date"])
            if m2:
                marriage_years.append((int(m2.group(1)), s))
        if not marriage_years:
            return {
                "answer": f"No tengo datos suficientes para calcular la edad al casarse de {person['name']}.",
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }
        marriage_year, spouse_info = sorted(marriage_years, key=lambda t: t[0])[0]
        age = marriage_year - birth_year
        spouse = spouse_info["person"]
        return {
            "answer": f"{person['name']} tenía aproximadamente {age} años cuando se casó con {spouse['name']} ({spouse_info['marriage_date']}).",
            "people_mentioned": [person["id"], spouse["id"]],
            "people_with_photos": [_person_card(person), _person_card(spouse)],
        }

    # ------------------------------------------------------------------
    # Handlers básicos reutilizados
    # ------------------------------------------------------------------
    def handle_mother(self, question: str) -> Optional[Dict[str, Any]]:
        raw_name = self._extract_name_after(question, [r"madre\s+de\s+(.+)$", r"mare\s+de\s+(.+)$", r"mother\s+of\s+(.+)$"])
        if not raw_name:
            return None
        person = self._resolve_person(raw_name)
        if not person:
            return None
        if not person.get("mother_id"):
            return {
                "answer": f"No tengo información sobre la madre de {person['name']}.",
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }
        mother = dict(get_person(self.conn, person["mother_id"]))
        return {
            "answer": f"La madre de {person['name']} es {_format_person(mother)}.",
            "people_mentioned": [person["id"], mother["id"]],
            "people_with_photos": [_person_card(person), _person_card(mother)],
        }

    def handle_father(self, question: str) -> Optional[Dict[str, Any]]:
        raw_name = self._extract_name_after(question, [r"padre\s+de\s+(.+)$", r"pare\s+de\s+(.+)$", r"father\s+of\s+(.+)$"])
        if not raw_name:
            return None
        person = self._resolve_person(raw_name)
        if not person:
            return None
        if not person.get("father_id"):
            return {
                "answer": f"No tengo información sobre el padre de {person['name']}.",
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }
        father = dict(get_person(self.conn, person["father_id"]))
        return {
            "answer": f"El padre de {person['name']} es {_format_person(father)}.",
            "people_mentioned": [person["id"], father["id"]],
            "people_with_photos": [_person_card(person), _person_card(father)],
        }

    def handle_parents(self, question: str) -> Optional[Dict[str, Any]]:
        raw_name = self._extract_name_after(question, [r"padres\s+de\s+(.+)$", r"pares\s+de\s+(.+)$", r"parents\s+of\s+(.+)$"])
        if not raw_name:
            return None
        person = self._resolve_person(raw_name)
        if not person:
            return None
        father, mother = get_parents(self.conn, person["id"])
        parts = []
        photos = [_person_card(person)]
        ids = [person["id"]]
        if father:
            fd = dict(father)
            parts.append(f"padre: {_format_person(fd)}")
            photos.append(_person_card(fd))
            ids.append(fd["id"])
        if mother:
            md = dict(mother)
            parts.append(f"madre: {_format_person(md)}")
            photos.append(_person_card(md))
            ids.append(md["id"])
        if not parts:
            return {
                "answer": f"No tengo información sobre los padres de {person['name']}.",
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }
        return {
            "answer": f"Padres de {person['name']}: " + "; ".join(parts) + ".",
            "people_mentioned": ids,
            "people_with_photos": photos,
        }

    def handle_children(self, question: str) -> Optional[Dict[str, Any]]:
        raw_name = self._extract_name_after(question, [r"hijos\s+de\s+(.+)$", r"fills\s+de\s+(.+)$", r"children\s+of\s+(.+)$"])
        if not raw_name:
            return None
        person = self._resolve_person(raw_name)
        if not person:
            return None
        children = _rows_to_dicts(get_children(self.conn, person["id"]))
        if not children:
            return {
                "answer": f"No tengo constancia de hijos de {person['name']}.",
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }
        return {
            "answer": f"{person['name']} tuvo {len(children)} hijo/s: " + ", ".join(c["name"] for c in children) + ".",
            "people_mentioned": [person["id"]] + [c["id"] for c in children],
            "people_with_photos": [_person_card(person)] + [_person_card(c) for c in children[:7]],
        }

    def _spouse_response(self, person: Dict[str, Any]) -> Dict[str, Any]:
        spouses = get_spouses(self.conn, person["id"])
        if not spouses:
            return {
                "answer": f"No tengo información sobre el/la cónyuge de {person['name']}.",
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }
        parts = []
        photos = [_person_card(person)]
        ids = [person["id"]]
        for s in spouses:
            sp = dict(s["person"])
            text = sp["name"]
            if s.get("marriage_date"):
                text += f", casados el {s['marriage_date']}"
            if s.get("marriage_place"):
                text += f" en {s['marriage_place']}"
            parts.append(text)
            photos.append(_person_card(sp))
            ids.append(sp["id"])
        return {
            "answer": f"{person['name']} se casó con: " + "; ".join(parts) + ".",
            "people_mentioned": ids,
            "people_with_photos": photos,
        }

    def handle_spouse(self, question: str) -> Optional[Dict[str, Any]]:
        raw_name = self._extract_name_after(
            question,
            [
                r"conyuge\s+de\s+(.+)$",
                r"c[oó]nyuge\s+de\s+(.+)$",
                r"esposa\s+de\s+(.+)$",
                r"marido\s+de\s+(.+)$",
                r"con\s+quien\s+se\s+cas[oó]\s+(.+)$",
                r"amb\s+qui\s+es\s+va\s+casar\s+(.+)$",
                r"spouse\s+of\s+(.+)$",
            ],
        )
        if not raw_name:
            return None
        person = self._resolve_person(raw_name)
        if not person:
            return None
        return self._spouse_response(person)

    def handle_siblings(self, question: str) -> Optional[Dict[str, Any]]:
        raw_name = self._extract_name_after(question, [r"hermanos\s+de\s+(.+)$", r"germans\s+de\s+(.+)$", r"siblings\s+of\s+(.+)$"])
        if not raw_name:
            return None
        person = self._resolve_person(raw_name)
        if not person:
            return None
        siblings = _rows_to_dicts(get_siblings(self.conn, person["id"]))
        if not siblings:
            return {
                "answer": f"No he encontrado hermanos de {person['name']}.",
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }
        return {
            "answer": f"Hermanos de {person['name']}: " + ", ".join(s["name"] for s in siblings) + ".",
            "people_mentioned": [person["id"]] + [s["id"] for s in siblings],
            "people_with_photos": [_person_card(person)] + [_person_card(s) for s in siblings[:7]],
        }

    def handle_grandparents(self, question: str) -> Optional[Dict[str, Any]]:
        raw_name = self._extract_name_after(question, [r"abuelos\s+de\s+(.+)$", r"avis\s+de\s+(.+)$", r"grandparents\s+of\s+(.+)$"])
        if not raw_name:
            return None
        person = self._resolve_person(raw_name)
        if not person:
            return None
        grandparents = get_grandparents(self.conn, person["id"])
        if not grandparents:
            return {
                "answer": f"No tengo información sobre los abuelos de {person['name']}.",
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }
        parts = []
        ids = [person["id"]]
        photos = [_person_card(person)]
        for gp in grandparents:
            gp_person = dict(gp["person"])
            parts.append(f"{gp_person['name']} (vía {gp['via']})")
            ids.append(gp_person["id"])
            photos.append(_person_card(gp_person))
        return {
            "answer": f"Abuelos de {person['name']}: " + "; ".join(parts) + ".",
            "people_mentioned": ids,
            "people_with_photos": photos[:8],
        }

    def handle_grandchildren(self, question: str) -> Optional[Dict[str, Any]]:
        raw_name = self._extract_name_after(question, [r"nietos\s+de\s+(.+)$", r"nets\s+de\s+(.+)$", r"grandchildren\s+of\s+(.+)$"])
        if not raw_name:
            return None
        person = self._resolve_person(raw_name)
        if not person:
            return None
        grandchildren = get_grandchildren(self.conn, person["id"])
        if not grandchildren:
            return {
                "answer": f"No tengo información sobre nietos de {person['name']}.",
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }
        ids = [person["id"]]
        photos = [_person_card(person)]
        parts = []
        for gc in grandchildren:
            child = dict(gc["person"])
            ids.append(child["id"])
            photos.append(_person_card(child))
            parts.append(f"{child['name']} (hijo/a de {gc['via']})")
        return {
            "answer": f"Nietos de {person['name']}: " + "; ".join(parts) + ".",
            "people_mentioned": ids,
            "people_with_photos": photos[:8],
        }

    def handle_birth(self, question: str) -> Optional[Dict[str, Any]]:
        raw_name = self._extract_name_after(
            question,
            [
                r"cuando\s+naci[oó]\s+(.+)$",
                r"quan\s+va\s+naixer\s+(.+)$",
                r"birth\s+of\s+(.+)$",
                r"fecha\s+de\s+nacimiento\s+de\s+(.+)$",
                r"data\s+de\s+naixement\s+de\s+(.+)$",
            ],
        )
        if not raw_name:
            return None
        person = self._resolve_person(raw_name)
        if not person:
            return None
        full = dict(get_person(self.conn, person["id"]))
        parts = []
        if full.get("birth_date"):
            parts.append(f"nació el {full['birth_date']}")
        if full.get("birth_place"):
            parts.append(f"en {full['birth_place']}")
        answer = f"{full['name']} " + (" ".join(parts) if parts else "no tiene fecha de nacimiento registrada") + "."
        return {
            "answer": answer,
            "people_mentioned": [full["id"]],
            "people_with_photos": [_person_card(full)],
        }

    def handle_death(self, question: str) -> Optional[Dict[str, Any]]:
        raw_name = self._extract_name_after(
            question,
            [
                r"cuando\s+muri[oó]\s+(.+)$",
                r"quan\s+va\s+morir\s+(.+)$",
                r"death\s+of\s+(.+)$",
            ],
        )
        if not raw_name:
            return None
        person = self._resolve_person(raw_name)
        if not person:
            return None
        full = dict(get_person(self.conn, person["id"]))
        parts = []
        if full.get("death_date"):
            parts.append(f"murió el {full['death_date']}")
        if full.get("death_place"):
            parts.append(f"en {full['death_place']}")
        answer = f"{full['name']} " + (" ".join(parts) if parts else "no tiene defunción registrada") + "."
        return {
            "answer": answer,
            "people_mentioned": [full["id"]],
            "people_with_photos": [_person_card(full)],
        }

    def handle_occupation(self, question: str) -> Optional[Dict[str, Any]]:
        raw_name = self._extract_name_after(
            question,
            [r"registrada\s+para\s+(.+)$", r"de\s+(.+)$", r"for\s+(.+)$"],
        )
        if not raw_name:
            return None
        person = self._resolve_person(raw_name)
        if not person:
            return None
        occupations = _rows_to_dicts(get_occupations(self.conn, person["id"]))
        if not occupations:
            return {
                "answer": f"No tengo información sobre la ocupación de {person['name']}.",
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }
        parts = []
        for o in occupations:
            line = o.get("title") or "(sin título)"
            if o.get("date"):
                line += f" ({o['date']})"
            if o.get("place"):
                line += f" en {o['place']}"
            parts.append(line)
        return {
            "answer": f"Ocupaciones de {person['name']}: " + "; ".join(parts) + ".",
            "people_mentioned": [person["id"]],
            "people_with_photos": [_person_card(person)],
        }

    def handle_notes(self, question: str) -> Optional[Dict[str, Any]]:
        raw_name = self._extract_name_after(question, [r"asociadas?\s+a\s+(.+)$", r"de\s+(.+)$", r"about\s+(.+)$"])
        if not raw_name:
            return None
        person = self._resolve_person(raw_name)
        if not person:
            return None
        notes = _rows_to_dicts(get_notes(self.conn, person["id"]))
        if not notes:
            return {
                "answer": f"No tengo notas sobre {person['name']}.",
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }
        parts = []
        for n in notes[:5]:
            content = n.get("content", "")
            if len(content) > 300:
                content = content[:300] + "..."
            parts.append(content)
        return {
            "answer": f"Notas de {person['name']}:\n" + "\n---\n".join(parts),
            "people_mentioned": [person["id"]],
            "people_with_photos": [_person_card(person)],
        }

    def handle_photos(self, question: str) -> Optional[Dict[str, Any]]:
        raw_name = self._extract_name_after(question, [r"fotos?\s+de\s+(.+)$", r"photos?\s+of\s+(.+)$"])
        if not raw_name:
            return None
        person = self._resolve_person(raw_name)
        if not person:
            return None
        photos = _rows_to_dicts(get_all_photos(self.conn, person["id"]))
        if not photos:
            return {
                "answer": f"No tengo fotos de {person['name']}.",
                "people_mentioned": [person["id"]],
                "people_with_photos": [],
            }
        cards = []
        for p in photos:
            if p.get("local_file"):
                cards.append({"id": person["id"], "name": p.get("title") or person["name"], "photo": p["local_file"]})
        return {
            "answer": f"Fotos de {person['name']} ({len(cards)}).",
            "people_mentioned": [person["id"]],
            "people_with_photos": cards[:8],
        }

    def handle_birthdays(self, question: str) -> Optional[Dict[str, Any]]:
        birthdays = get_birthdays_this_week(self.conn)
        if birthdays is None:
            return None
        birthdays = list(birthdays)
        if not birthdays:
            return {
                "answer": "No hay cumpleaños esta semana en el árbol.",
                "people_mentioned": [],
                "people_with_photos": [],
            }
        names = ", ".join(f"{b['name']} ({b['date_label']})" for b in birthdays[:12])
        return {
            "answer": f"Cumpleaños de esta semana: {names}.",
            "people_mentioned": [b["id"] for b in birthdays],
            "people_with_photos": [{"id": b["id"], "name": b["name"], "photo": b.get("photo")} for b in birthdays[:8]],
        }

    def handle_alive(self, question: str) -> Optional[Dict[str, Any]]:
        people = _rows_to_dicts(get_alive_people(self.conn))
        if people is None:
            return None
        return {
            "answer": f"Personas marcadas como vivas: {len(people)}.",
            "people_mentioned": [p["id"] for p in people],
            "people_with_photos": [_person_card(p) for p in people[:8]],
        }

    def handle_stats(self, question: str) -> Optional[Dict[str, Any]]:
        total = self.conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
        marriages = self.conn.execute("SELECT COUNT(*) FROM marriages").fetchone()[0]
        return {
            "answer": f"El árbol tiene {total} personas y {marriages} matrimonios registrados.",
            "people_mentioned": [],
            "people_with_photos": [],
        }

    def handle_search(self, question: str) -> Optional[Dict[str, Any]]:
        raw_name = self._extract_name_after(question, [r"busca\s+(.+)$", r"cerca\s+(.+)$", r"search\s+(.+)$", r"quien\s+es\s+(.+)$", r"qui\s+es\s+(.+)$", r"who\s+is\s+(.+)$"])
        if not raw_name:
            return None
        matches = self._search_people(raw_name, limit=10)
        if not matches:
            return {
                "answer": f"No he encontrado a nadie con el nombre '{raw_name}'.",
                "people_mentioned": [],
                "people_with_photos": [],
            }
        return {
            "answer": "He encontrado %d resultado(s):\n%s" % (len(matches), "\n".join(f"- {_format_person(m)}" for m in matches)),
            "people_mentioned": [m["id"] for m in matches],
            "people_with_photos": [_person_card(m) for m in matches[:8]],
        }

    def _try_name_fallback(self, question: str) -> Optional[Dict[str, Any]]:
        # Solo caer aquí si la pregunta parece básicamente un nombre o una ficha abierta.
        if re.search(r"\b(cuando|cuando|cuando|que|qué|quien|quién|quines|what|which|where|where|how many|cuantos|quants|entre|y|and)\b", _norm(question)):
            return None
        guessed = self._extract_capitalized_name(question) or question.strip().rstrip("?.,!")
        person = self._resolve_person(guessed)
        if not person:
            return None
        return self._build_info_response(person)

    def _build_info_response(self, person: Dict[str, Any]) -> Dict[str, Any]:
        full = dict(get_person(self.conn, person["id"]))
        lines = [full["name"]]
        if full.get("birth_date") or full.get("birth_place"):
            line = "Nacimiento: " + (full.get("birth_date") or "?")
            if full.get("birth_place"):
                line += f", {full['birth_place']}"
            lines.append(line)
        if full.get("death_date") or full.get("death_place"):
            line = "Defunción: " + (full.get("death_date") or "?")
            if full.get("death_place"):
                line += f", {full['death_place']}"
            lines.append(line)
        return {
            "answer": "\n".join(lines),
            "people_mentioned": [full["id"]],
            "people_with_photos": [_person_card(full)],
        }
