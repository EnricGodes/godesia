"""Query Router: interpreta preguntas en castellano/catalán/inglés y responde desde SQLite.

Diseño:
- Capa determinista, sin fallback LLM.
- Soporte trilingüe para intents y conectores.
- Dos modos:
  1) handlers semánticos de relaciones/perfil
  2) consulta analítica genérica con filtros combinables sobre múltiples tablas

Objetivo práctico: escalar a miles de formulaciones distintas a partir de una
representación intermedia (intent + slots + filtros), no a partir de miles de
regex ad hoc independientes.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from database import (
    find_person_by_name,
    get_all_photos,
    get_alive_people,
    get_birthdays_this_week,
    get_born_in,
    get_children,
    get_grandchildren,
    get_grandparents,
    get_notes,
    get_occupations,
    get_person,
    get_residences,
    get_siblings,
    get_spouses,
)


# ---------------------------------------------------------------------------
# Utils
# ---------------------------------------------------------------------------

STOPWORDS = {
    "es": {
        "quien", "qué", "que", "cual", "cuál", "cuando", "cuándo", "donde", "dónde",
        "como", "cómo", "de", "del", "la", "el", "los", "las", "un", "una", "unos",
        "unas", "por", "para", "con", "sin", "y", "o", "en", "sobre", "entre", "a",
        "al", "lo", "me", "mi", "su", "sus", "se", "es", "son", "fue", "fueron",
        "era", "eran", "quiero", "muestrame", "muéstrame", "dime", "lista", "listar",
        "buscar", "busca", "encuentra", "ver", "mostrar", "muéstrame", "hay",
    },
    "ca": {
        "qui", "què", "que", "quan", "on", "com", "de", "del", "la", "el", "els",
        "les", "un", "una", "uns", "unes", "per", "amb", "sense", "i", "o", "en",
        "sobre", "entre", "a", "al", "ho", "em", "meu", "seu", "és", "són", "va",
        "vull", "mostra", "digue'm", "digues", "llista", "buscar", "busca", "troba",
        "veure", "mostrar", "hi", "ha",
    },
    "en": {
        "who", "what", "when", "where", "how", "of", "the", "a", "an", "for", "to",
        "with", "without", "and", "or", "in", "on", "about", "between", "show", "tell",
        "list", "find", "search", "give", "me", "is", "are", "was", "were", "there",
        "any", "all",
    },
}
ALL_STOPWORDS = set().union(*STOPWORDS.values())


@dataclass
class QueryPlan:
    mode: str = "generic"  # relation | profile | generic
    intent: str = "search"
    language: str = "es"
    person_name: Optional[str] = None
    secondary_person_name: Optional[str] = None
    place: Optional[str] = None
    text_terms: List[str] = field(default_factory=list)
    surname: Optional[str] = None
    given_name: Optional[str] = None
    sex: Optional[str] = None
    is_alive: Optional[bool] = None
    birth_year_from: Optional[int] = None
    birth_year_to: Optional[int] = None
    death_year_from: Optional[int] = None
    death_year_to: Optional[int] = None
    event_year_from: Optional[int] = None
    event_year_to: Optional[int] = None
    occupation_text: Optional[str] = None
    residence_text: Optional[str] = None
    notes_text: Optional[str] = None
    event_text: Optional[str] = None
    photo_required: Optional[bool] = None
    relation_scope: Optional[str] = None
    aggregation: str = "list"  # list | count
    sort_by: str = "name"
    sort_dir: str = "ASC"
    limit: int = 25
    raw_question: str = ""


LANG_HINTS = {
    "ca": [r"\bqui\b", r"\bquan\b", r"\bon\b", r"\bgermans?\b", r"\bfills?\b", r"\bnéts?\b", r"\bavis?\b", r"\bnaixement\b", r"\bdefunci[oó]\b", r"\bviu\b"],
    "en": [r"\bwho\b", r"\bwhen\b", r"\bwhere\b", r"\bchildren\b", r"\bsiblings\b", r"\bspouse\b", r"\bborn\b", r"\bdied\b", r"\balive\b"],
}

RELATION_PATTERNS = [
    (r"\b(mare|madre|mother)\b", "mother"),
    (r"\b(pare|padre|father)\b", "father"),
    (r"\b(germans?|hermanos?|siblings?)\b", "siblings"),
    (r"\b(fills?|hijos?|children)\b", "children"),
    (r"\b(descendents?|descendientes?|descendants?)\b", "descendants"),
    (r"\b(avis?|abuelos?|grandparents?|abuela|abuelo|grandfather|grandmother|àvia)\b", "grandparents"),
    (r"\b(n[eé]ts?|nietos?|nietas?|grandchildren?|grandchild)\b", "grandchildren"),
    (r"(es\s+va\s+casar|se\s+cas[oó]|marit|marido|esposa|spouse|wife|husband|amb\s+qui|con\s+qui[eé]n|who\s+did.*marry)", "spouse"),
]

PROFILE_PATTERNS = [
    r"\b(info(?:rmaci[oó])?|dades|datos|fitxa|ficha|perfil|about|sobre|tell me about|háblame de|parla'm de)\b",
]

COUNT_PATTERNS = [
    r"\b(cu[aá]nt[oa]s?|quants?|how many|count|nombre de|número de|numero de)\b",
]

STATS_PATTERNS = [
    r"\b(stats?|estad[ií]stic(?:as)?|estad[ií]sticas?|resumen|resum|summary)\b",
]

BIRTHDAY_PATTERNS = [
    r"\b(cumple(?:años)?|birthday|birthdays|aniversari|aniversaris|fa anys)\b",
]

ALIVE_PATTERNS = [
    r"\b(viu[s]?|viva?[os]?|alive|living|est[áa]\s+vivo|està\s+viu)\b",
]

PHOTO_PATTERNS = [
    r"\b(fotos?|photo|photos|imagen|imatge|picture|pictures)\b",
]

OCCUPATION_PATTERNS = [
    r"\b(ofici|profesi[oó]n?|ocupaci[oó]n?|occupation|job|work|worked|trabaj[oó]|treball|feina|dedicaba|dedicava)\b",
]

RESIDENCE_PATTERNS = [
    r"\b(resid[eè]ncia|residencia|residence|residences|address|direcci[oó]n|dirección|adre[çc]a|domicili|where.*live|d[oó]nde.*vivi[oó]|on.*viure)\b",
]

NOTES_PATTERNS = [
    r"\b(notes?|notas?|documents?|documentos?|observaci[oó]n?|anotaci[oó]n?)\b",
]

BIRTH_PATTERNS = [
    r"\b(naci[oó]|nacimiento|naixement|born|birth)\b",
]

DEATH_PATTERNS = [
    r"\b(muri[oó]|muerte|defunci[oó]n?|defunci[oó]|died|death|mort)\b",
]

PLACE_PATTERNS = [
    r"\b(nacidos? en|nascuts? a|born in|natural de|origen(?: de)?|from)\s+([^?.,;]+)",
    r"\b(en|a|in|at)\s+([A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][^?.,;]+)",
]

YEAR_RANGE_PATTERNS = [
    r"\bentre\s+(\d{4})\s+y\s+(\d{4})\b",
    r"\bbetween\s+(\d{4})\s+and\s+(\d{4})\b",
    r"\bentre\s+(\d{4})\s+i\s+(\d{4})\b",
    r"\bfrom\s+(\d{4})\s+to\s+(\d{4})\b",
    r"\bdesde\s+(\d{4})\s+hasta\s+(\d{4})\b",
    r"\bdes de\s+(\d{4})\s+fins\s+(\d{4})\b",
]

YEAR_SINGLE_PATTERNS = [
    (r"\bantes de\s+(\d{4})\b", "before"),
    (r"\bbefore\s+(\d{4})\b", "before"),
    (r"\bdespu[eé]s de\s+(\d{4})\b", "after"),
    (r"\bdespr[eé]s de\s+(\d{4})\b", "after"),
    (r"\bafter\s+(\d{4})\b", "after"),
    (r"\ben\s+(\d{4})\b", "exact"),
    (r"\ba\s+(\d{4})\b", "exact"),
    (r"\bin\s+(\d{4})\b", "exact"),
]

LIMIT_PATTERNS = [
    r"\btop\s+(\d+)\b",
    r"\blimit\s+(\d+)\b",
    r"\blos\s+primeros\s+(\d+)\b",
    r"\bles\s+primeres?\s+(\d+)\b",
    r"\bprimeros?\s+(\d+)\b",
    r"\bfirst\s+(\d+)\b",
]


SQL_FIELD_MAP = {
    "name": ("p.name", None),
    "nombre": ("p.name", None),
    "nom": ("p.name", None),
    "given_name": ("p.given_name", None),
    "surname": ("p.surname", None),
    "apellido": ("p.surname", None),
    "cognom": ("p.surname", None),
    "sex": ("p.sex", None),
    "sexo": ("p.sex", None),
    "birth_date": ("p.birth_date", None),
    "birth_year": ("p.birth_year", None),
    "año nacimiento": ("p.birth_year", None),
    "birth_place": ("p.birth_place", None),
    "lugar nacimiento": ("p.birth_place", None),
    "death_date": ("p.death_date", None),
    "death_year": ("p.death_year", None),
    "death_place": ("p.death_place", None),
    "death_cause": ("p.death_cause", None),
    "is_alive": ("p.is_alive", None),
    "father_name": ("p.father_name", None),
    "mother_name": ("p.mother_name", None),
    "baptism_date": ("p.baptism_date", None),
    "baptism_place": ("p.baptism_place", None),
    "godparents": ("p.godparents", None),
    "occupation": ("o.title", "LEFT JOIN occupations o ON o.person_id = p.id"),
    "oficio": ("o.title", "LEFT JOIN occupations o ON o.person_id = p.id"),
    "profession": ("o.title", "LEFT JOIN occupations o ON o.person_id = p.id"),
    "residence": ("COALESCE(r.address,'') || ' ' || COALESCE(r.address2,'') || ' ' || COALESCE(r.city,'') || ' ' || COALESCE(r.country,'')", "LEFT JOIN residences r ON r.person_id = p.id"),
    "city": ("r.city", "LEFT JOIN residences r ON r.person_id = p.id"),
    "note": ("n.content", "LEFT JOIN notes n ON n.person_id = p.id"),
    "notes": ("n.content", "LEFT JOIN notes n ON n.person_id = p.id"),
    "event": ("COALESCE(e.type,'') || ' ' || COALESCE(e.description,'') || ' ' || COALESCE(e.place,'') || ' ' || COALESCE(e.note,'')", "LEFT JOIN events e ON e.person_id = p.id"),
    "event_place": ("e.place", "LEFT JOIN events e ON e.person_id = p.id"),
    "military": ("m.description", "LEFT JOIN military m ON m.person_id = p.id"),
    "anecdote": ("a.description", "LEFT JOIN anecdotes a ON a.person_id = p.id"),
    "burial": ("COALESCE(b.place_detail,'') || ' ' || COALESCE(b.place,'')", "LEFT JOIN burial b ON b.person_id = p.id"),
    "photo": ("ph.filename", "LEFT JOIN photo_tags pt ON pt.person_id = p.id LEFT JOIN photos ph ON ph.id = pt.photo_id"),
}


def _person_card(person: Any) -> Dict[str, Any]:
    return {
        "id": person["id"] if isinstance(person, dict) else person[0],
        "name": person["name"] if isinstance(person, dict) else person[1],
        "photo": person.get("photo_file") if isinstance(person, dict) else None,
    }


def _format_person(p: Any) -> str:
    if isinstance(p, sqlite3.Row):
        p = dict(p)
    parts = [p["name"]]
    if p.get("birth_year"):
        parts.append(
            "(%s%s)" % (
                p["birth_year"],
                "-%s" % p.get("death_year", "") if p.get("death_year") else ("" if p.get("is_alive") else "-?"),
            )
        )
    if p.get("birth_place"):
        parts.append("de %s" % p["birth_place"])
    return " ".join(parts)


def _clean_fragment(text: str) -> str:
    text = re.sub(r"[?.,;:!()\[\]{}]+", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(text: str) -> List[str]:
    return [t for t in re.findall(r"[\wÀ-ÿ'-]+", text.lower()) if t not in ALL_STOPWORDS and len(t) > 2]


def _unique(seq: Iterable[Any]) -> List[Any]:
    seen = set()
    out = []
    for item in seq:
        key = item if isinstance(item, (str, int, float, tuple)) else repr(item)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


class QueryRouter:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.available_columns = self._introspect_columns("people")

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------

    def route(self, question: str) -> Optional[Dict[str, Any]]:
        question = (question or "").strip()
        if not question:
            return None

        plan = self._build_plan(question)

        if plan.intent == "birthdays":
            result = self.handle_birthdays(question)
        elif plan.intent == "stats":
            result = self.handle_stats(question)
        elif plan.mode == "relation":
            result = self._handle_relation(plan)
        elif plan.mode == "profile":
            result = self._handle_profile(plan)
        else:
            result = self._handle_generic(plan)
            if not result:
                result = self._try_name_fallback(question, plan.language)

        if result:
            result["source"] = "db"
            result["query_plan"] = self._plan_to_dict(plan)
        return result

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    def _build_plan(self, question: str) -> QueryPlan:
        q = _clean_fragment(question)
        q_lower = q.lower()
        language = self._detect_language(q_lower)
        plan = QueryPlan(language=language, raw_question=question)

        # intent routing
        for pattern, intent in RELATION_PATTERNS:
            if re.search(pattern, q_lower, re.IGNORECASE):
                plan.mode = "relation"
                plan.intent = intent
                break

        if any(re.search(p, q_lower, re.IGNORECASE) for p in PROFILE_PATTERNS):
            plan.mode = "profile"
            plan.intent = "profile"

        if any(re.search(p, q_lower, re.IGNORECASE) for p in BIRTHDAY_PATTERNS):
            plan.intent = "birthdays"
            return plan

        if any(re.search(p, q_lower, re.IGNORECASE) for p in STATS_PATTERNS):
            plan.intent = "stats"
            return plan

        if any(re.search(p, q_lower, re.IGNORECASE) for p in COUNT_PATTERNS):
            plan.aggregation = "count"

        if any(re.search(p, q_lower, re.IGNORECASE) for p in ALIVE_PATTERNS):
            plan.is_alive = True

        if any(re.search(p, q_lower, re.IGNORECASE) for p in PHOTO_PATTERNS):
            plan.photo_required = True
            if plan.intent == "search":
                plan.intent = "photos"

        if any(re.search(p, q_lower, re.IGNORECASE) for p in OCCUPATION_PATTERNS):
            plan.intent = "occupation" if plan.intent == "search" else plan.intent
        if any(re.search(p, q_lower, re.IGNORECASE) for p in RESIDENCE_PATTERNS):
            plan.intent = "residence" if plan.intent == "search" else plan.intent
        if any(re.search(p, q_lower, re.IGNORECASE) for p in NOTES_PATTERNS):
            plan.intent = "notes" if plan.intent == "search" else plan.intent
        if any(re.search(p, q_lower, re.IGNORECASE) for p in BIRTH_PATTERNS):
            plan.intent = "birth" if plan.intent == "search" else plan.intent
        if any(re.search(p, q_lower, re.IGNORECASE) for p in DEATH_PATTERNS):
            plan.intent = "death" if plan.intent == "search" else plan.intent

        if re.search(r"\b(order by|ordena(?:do)? por|ordenat per|sort by)\s+birth_year\b", q_lower):
            plan.sort_by = "birth_year"
        elif re.search(r"\b(order by|ordena(?:do)? por|ordenat per|sort by)\s+death_year\b", q_lower):
            plan.sort_by = "death_year"
        elif re.search(r"\b(order by|ordena(?:do)? por|ordenat per|sort by)\s+name\b", q_lower):
            plan.sort_by = "name"

        if re.search(r"\b(desc|descending|descendente)\b", q_lower):
            plan.sort_dir = "DESC"

        for pattern in LIMIT_PATTERNS:
            m = re.search(pattern, q_lower, re.IGNORECASE)
            if m:
                plan.limit = max(1, min(200, int(m.group(1))))
                break

        self._extract_person_slots(plan, q)
        self._extract_place_slot(plan, q)
        self._extract_year_slots(plan, q_lower)
        self._extract_direct_field_filters(plan, q)
        self._extract_text_terms(plan, q)

        return plan

    def _detect_language(self, q_lower: str) -> str:
        scores = {"es": 0, "ca": 0, "en": 0}
        for lang, patterns in LANG_HINTS.items():
            for pattern in patterns:
                if re.search(pattern, q_lower, re.IGNORECASE):
                    scores[lang] += 1
        return max(scores, key=scores.get) if any(scores.values()) else "es"

    def _extract_person_slots(self, plan: QueryPlan, question: str) -> None:
        q = question.strip()
        # Quoted names win
        quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', q)
        for pair in quoted:
            value = next((x for x in pair if x), None)
            if value:
                if not plan.person_name:
                    plan.person_name = value.strip()
                elif not plan.secondary_person_name:
                    plan.secondary_person_name = value.strip()

        # Specific prefixes for relation/profile questions
        prefixes = [
            r"(?:de|d['’]|of)\s+([A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][^?.,;]+)$",
            r"(?:sobre|about)\s+([A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][^?.,;]+)$",
        ]
        for pattern in prefixes:
            m = re.search(pattern, q, re.IGNORECASE)
            if m:
                candidate = m.group(1).strip()
                if candidate and not plan.person_name:
                    plan.person_name = candidate
                    break

        # Capitalized spans
        caps = re.findall(r"[A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][a-záéíóúàèìòùñç'’-]+(?:\s+[A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][a-záéíóúàèìòùñç'’-]+){0,4}", q)
        caps = [c.strip() for c in caps if len(c.strip()) > 2]
        if caps and not plan.person_name:
            plan.person_name = caps[0]
        if len(caps) > 1 and not plan.secondary_person_name:
            plan.secondary_person_name = caps[1]

        # Surname / given name explicit forms
        m = re.search(r"\b(?:surname|apellido|cognom)\s+(?:es|=)?\s*([\wÀ-ÿ'’-]+)", q, re.IGNORECASE)
        if m:
            plan.surname = m.group(1).strip()
        m = re.search(r"\b(?:given name|nombre|nom)\s+(?:es|=)?\s*([\wÀ-ÿ'’-]+)", q, re.IGNORECASE)
        if m:
            plan.given_name = m.group(1).strip()

        # Bare surname queries like "Godes nacidos en Barcelona"
        if not plan.surname:
            m = re.search(r"\b([A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][a-záéíóúàèìòùñç'’-]+)\s+(?:nacidos?|nascuts?|born|muertos?|morts?|alive|vius?)\b", q)
            if m:
                plan.surname = m.group(1).strip()

    def _extract_place_slot(self, plan: QueryPlan, question: str) -> None:
        for pattern in PLACE_PATTERNS:
            m = re.search(pattern, question, re.IGNORECASE)
            if m:
                place = m.group(m.lastindex).strip()
                place = re.sub(r"\b(que|who|which|què|what|where|on)$", "", place, flags=re.IGNORECASE).strip()
                if place and len(place) > 1:
                    plan.place = place
                    return

    def _extract_year_slots(self, plan: QueryPlan, q_lower: str) -> None:
        for pattern in YEAR_RANGE_PATTERNS:
            m = re.search(pattern, q_lower, re.IGNORECASE)
            if m:
                start, end = int(m.group(1)), int(m.group(2))
                plan.birth_year_from, plan.birth_year_to = min(start, end), max(start, end)
                return

        for pattern, mode in YEAR_SINGLE_PATTERNS:
            m = re.search(pattern, q_lower, re.IGNORECASE)
            if not m:
                continue
            year = int(m.group(1))
            if mode == "before":
                plan.birth_year_to = year - 1
            elif mode == "after":
                plan.birth_year_from = year + 1
            elif mode == "exact":
                plan.birth_year_from = year
                plan.birth_year_to = year
            return

    def _extract_direct_field_filters(self, plan: QueryPlan, question: str) -> None:
        q_lower = question.lower()

        if re.search(r"\b(male|masculino|home|hombre|var[oó]n)\b", q_lower):
            plan.sex = "M"
        elif re.search(r"\b(female|femenino|dona|mujer)\b", q_lower):
            plan.sex = "F"

        occupation_match = re.search(
            r"\b(?:oficio|ocupaci[oó]n|profesi[oó]n|occupation|job|worked as|trabaj[oó] como|treballava com)\s+(?:de\s+)?([\wÀ-ÿ\s'’-]+)",
            question,
            re.IGNORECASE,
        )
        if occupation_match:
            value = occupation_match.group(1).strip()
            if len(value) > 2:
                plan.occupation_text = value

        residence_match = re.search(
            r"\b(?:residencia|residence|direcci[oó]n|adre[çc]a|domicili|viv[ií]a en|lived in|viu a|viure a)\s+([\wÀ-ÿ\s'’,.-]+)",
            question,
            re.IGNORECASE,
        )
        if residence_match:
            value = residence_match.group(1).strip()
            if len(value) > 2:
                plan.residence_text = value

        notes_match = re.search(r"\b(?:nota|nota sobre|note about|notes about)\s+([\wÀ-ÿ\s'’-]+)", question, re.IGNORECASE)
        if notes_match:
            plan.notes_text = notes_match.group(1).strip()

        event_match = re.search(r"\b(?:evento|event|suceso|esdeveniment)\s+([\wÀ-ÿ\s'’-]+)", question, re.IGNORECASE)
        if event_match:
            plan.event_text = event_match.group(1).strip()

    def _extract_text_terms(self, plan: QueryPlan, question: str) -> None:
        terms = _tokenize(question)
        terms = [t for t in terms if not re.fullmatch(r"\d{4}", t)]
        # Remove obvious person tokens if a full person name exists
        if plan.person_name:
            person_tokens = set(_tokenize(plan.person_name))
            terms = [t for t in terms if t not in person_tokens]
        if plan.place:
            place_tokens = set(_tokenize(plan.place))
            terms = [t for t in terms if t not in place_tokens]
        if plan.surname:
            terms = [t for t in terms if t != plan.surname.lower()]
        plan.text_terms = _unique(terms[:10])

    # ------------------------------------------------------------------
    # Generic query execution
    # ------------------------------------------------------------------

    def _handle_generic(self, plan: QueryPlan) -> Optional[Dict[str, Any]]:
        if plan.intent == "birth":
            return self._handle_birth_like(plan, which="birth")
        if plan.intent == "death":
            return self._handle_birth_like(plan, which="death")
        if plan.intent == "occupation" and plan.person_name:
            return self._handle_person_occupations(plan)
        if plan.intent == "residence" and plan.person_name:
            return self._handle_person_residences(plan)
        if plan.intent == "notes" and plan.person_name:
            return self._handle_person_notes(plan)
        if plan.intent == "photos" and plan.person_name:
            return self._handle_person_photos(plan)
        if plan.is_alive and not any([plan.person_name, plan.place, plan.surname, plan.given_name, plan.text_terms]):
            return self.handle_alive(plan.raw_question)

        sql, params = self._compile_generic_sql(plan)
        rows = self.conn.execute(sql, params).fetchall()
        if not rows:
            return {
                "answer": self._msg(plan.language, "no_results"),
                "people_mentioned": [],
                "people_with_photos": [],
                "sql_debug": {"sql": sql, "params": params},
            }

        if plan.aggregation == "count":
            count = rows[0][0]
            return {
                "answer": self._render_count_answer(plan, count),
                "people_mentioned": [],
                "people_with_photos": [],
                "sql_debug": {"sql": sql, "params": params},
            }

        people_ids = [r["id"] for r in rows if "id" in r.keys()]
        photos = [
            {"id": r["id"], "name": r["name"], "photo": r["photo_file"]}
            for r in rows if "id" in r.keys() and r["photo_file"]
        ][:8]

        return {
            "answer": self._render_people_list(plan, rows),
            "people_mentioned": people_ids,
            "people_with_photos": photos,
            "sql_debug": {"sql": sql, "params": params},
        }

    def _compile_generic_sql(self, plan: QueryPlan) -> Tuple[str, List[Any]]:
        joins: List[str] = []
        where: List[str] = []
        params: List[Any] = []

        select = "SELECT DISTINCT p.id, p.name, p.given_name, p.surname, p.birth_year, p.death_year, p.birth_place, p.is_alive, p.photo_file FROM people p"

        def ensure_join(join_sql: str) -> None:
            if join_sql and join_sql not in joins:
                joins.append(join_sql)

        if plan.aggregation == "count":
            select = "SELECT COUNT(DISTINCT p.id)"

        if plan.person_name:
            where.append("p.name LIKE ? COLLATE NOCASE")
            params.append(f"%{re.sub(r'\\s+', '%', plan.person_name.strip())}%")
        if plan.surname:
            where.append("p.surname LIKE ? COLLATE NOCASE")
            params.append(f"%{plan.surname}%")
        if plan.given_name:
            where.append("p.given_name LIKE ? COLLATE NOCASE")
            params.append(f"%{plan.given_name}%")
        if plan.sex:
            where.append("p.sex = ?")
            params.append(plan.sex)
        if plan.is_alive is True:
            where.append("p.is_alive = 1")
        elif plan.is_alive is False:
            where.append("p.is_alive = 0")
        if plan.birth_year_from is not None:
            where.append("p.birth_year >= ?")
            params.append(plan.birth_year_from)
        if plan.birth_year_to is not None:
            where.append("p.birth_year <= ?")
            params.append(plan.birth_year_to)
        if plan.death_year_from is not None:
            where.append("p.death_year >= ?")
            params.append(plan.death_year_from)
        if plan.death_year_to is not None:
            where.append("p.death_year <= ?")
            params.append(plan.death_year_to)
        if plan.place:
            where.append("(p.birth_place LIKE ? COLLATE NOCASE OR EXISTS (SELECT 1 FROM residences r2 WHERE r2.person_id = p.id AND (COALESCE(r2.city,'') || ' ' || COALESCE(r2.country,'') || ' ' || COALESCE(r2.address,'') || ' ' || COALESCE(r2.address2,'')) LIKE ? COLLATE NOCASE) OR EXISTS (SELECT 1 FROM events e2 WHERE e2.person_id = p.id AND COALESCE(e2.place,'') LIKE ? COLLATE NOCASE))")
            params.extend([f"%{plan.place}%", f"%{plan.place}%", f"%{plan.place}%"])
        if plan.photo_required:
            ensure_join("LEFT JOIN photo_tags pt ON pt.person_id = p.id")
            ensure_join("LEFT JOIN photos ph ON ph.id = pt.photo_id")
            where.append("ph.filename IS NOT NULL")
        if plan.occupation_text:
            ensure_join("LEFT JOIN occupations o ON o.person_id = p.id")
            where.append("o.title LIKE ? COLLATE NOCASE")
            params.append(f"%{plan.occupation_text}%")
        if plan.residence_text:
            ensure_join("LEFT JOIN residences r ON r.person_id = p.id")
            where.append("(COALESCE(r.address,'') || ' ' || COALESCE(r.address2,'') || ' ' || COALESCE(r.city,'') || ' ' || COALESCE(r.country,'')) LIKE ? COLLATE NOCASE")
            params.append(f"%{plan.residence_text}%")
        if plan.notes_text:
            ensure_join("LEFT JOIN notes n ON n.person_id = p.id")
            where.append("n.content LIKE ? COLLATE NOCASE")
            params.append(f"%{plan.notes_text}%")
        if plan.event_text:
            ensure_join("LEFT JOIN events e ON e.person_id = p.id")
            where.append("(COALESCE(e.type,'') || ' ' || COALESCE(e.description,'') || ' ' || COALESCE(e.note,'') || ' ' || COALESCE(e.place,'')) LIKE ? COLLATE NOCASE")
            params.append(f"%{plan.event_text}%")

        # Free text terms search across most genealogically relevant fields.
        if plan.text_terms:
            for term in plan.text_terms:
                where.append(
                    "(" \
                    "p.name LIKE ? COLLATE NOCASE OR p.given_name LIKE ? COLLATE NOCASE OR p.surname LIKE ? COLLATE NOCASE OR " \
                    "COALESCE(p.birth_place,'') LIKE ? COLLATE NOCASE OR COALESCE(p.death_place,'') LIKE ? COLLATE NOCASE OR " \
                    "EXISTS (SELECT 1 FROM occupations o3 WHERE o3.person_id = p.id AND COALESCE(o3.title,'') LIKE ? COLLATE NOCASE) OR " \
                    "EXISTS (SELECT 1 FROM residences r3 WHERE r3.person_id = p.id AND (COALESCE(r3.address,'') || ' ' || COALESCE(r3.city,'') || ' ' || COALESCE(r3.country,'')) LIKE ? COLLATE NOCASE) OR " \
                    "EXISTS (SELECT 1 FROM notes n3 WHERE n3.person_id = p.id AND COALESCE(n3.content,'') LIKE ? COLLATE NOCASE) OR " \
                    "EXISTS (SELECT 1 FROM events e3 WHERE e3.person_id = p.id AND (COALESCE(e3.type,'') || ' ' || COALESCE(e3.description,'') || ' ' || COALESCE(e3.note,'') || ' ' || COALESCE(e3.place,'')) LIKE ? COLLATE NOCASE)"
                    ")"
                )
                like = f"%{term}%"
                params.extend([like] * 9)

        order_sql = {
            "name": "p.name",
            "birth_year": "p.birth_year",
            "death_year": "p.death_year",
        }.get(plan.sort_by, "p.name")

        sql = f"{select} {' '.join(joins)}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        if plan.aggregation != "count":
            sql += f" ORDER BY {order_sql} {plan.sort_dir}, p.name ASC LIMIT ?"
            params.append(plan.limit)
        return sql, params

    # ------------------------------------------------------------------
    # Specific handlers on top of planner
    # ------------------------------------------------------------------

    def _handle_relation(self, plan: QueryPlan) -> Optional[Dict[str, Any]]:
        if not plan.person_name:
            return None
        matches = self._find_person_matches(plan.person_name)
        if not matches:
            return None
        person = matches[0]
        full = get_person(self.conn, person["id"])
        if not full:
            return None

        intent = plan.intent
        if intent == "mother":
            return self._answer_single_relative(full, "mother_id", "madre", plan.language)
        if intent == "father":
            return self._answer_single_relative(full, "father_id", "padre", plan.language)
        if intent == "siblings":
            siblings = get_siblings(self.conn, full["id"])
            return self._answer_relative_list(full, siblings, "siblings", plan.language)
        if intent == "children":
            children = get_children(self.conn, full["id"])
            return self._answer_relative_list(full, children, "children", plan.language)
        if intent == "descendants":
            descendants = self._collect_descendants(full["id"])
            return self._answer_relative_list(full, descendants, "descendants", plan.language)
        if intent == "grandparents":
            gps = [gp["person"] for gp in get_grandparents(self.conn, full["id"])]
            return self._answer_relative_list(full, gps, "grandparents", plan.language)
        if intent == "grandchildren":
            gks = [gc["person"] for gc in get_grandchildren(self.conn, full["id"])]
            return self._answer_relative_list(full, gks, "grandchildren", plan.language)
        if intent == "spouse":
            spouses = [s["person"] for s in get_spouses(self.conn, full["id"])]
            return self._answer_relative_list(full, spouses, "spouses", plan.language)
        return None

    def _handle_profile(self, plan: QueryPlan) -> Optional[Dict[str, Any]]:
        if not plan.person_name:
            return None
        matches = self._find_person_matches(plan.person_name)
        if not matches:
            return None
        return self._build_info_response(matches[0], plan.language)

    def _handle_birth_like(self, plan: QueryPlan, which: str) -> Optional[Dict[str, Any]]:
        if not plan.person_name:
            return None
        matches = self._find_person_matches(plan.person_name)
        if not matches:
            return None
        full = get_person(self.conn, matches[0]["id"])
        if not full:
            return None
        if which == "birth":
            pieces = []
            if full["birth_date"]:
                pieces.append(full["birth_date"])
            if full["birth_place"]:
                pieces.append(full["birth_place"])
            answer = f"{full['name']}: " + (", ".join(pieces) if pieces else self._msg(plan.language, "no_birth"))
        else:
            pieces = []
            if full["death_date"]:
                pieces.append(full["death_date"])
            if full["death_place"]:
                pieces.append(full["death_place"])
            if full["death_cause"]:
                pieces.append(full["death_cause"])
            answer = f"{full['name']}: " + (", ".join(pieces) if pieces else self._msg(plan.language, "no_death"))
        return {
            "answer": answer,
            "people_mentioned": [full["id"]],
            "people_with_photos": [_person_card(dict(full))],
        }

    def _handle_person_occupations(self, plan: QueryPlan) -> Optional[Dict[str, Any]]:
        matches = self._find_person_matches(plan.person_name)
        if not matches:
            return None
        person = matches[0]
        occupations = get_occupations(self.conn, person["id"])
        if not occupations:
            return None
        parts = []
        for o in occupations:
            text = o["title"]
            if o["date"]:
                text += f" ({o['date']})"
            if o["place"]:
                text += f" - {o['place']}"
            parts.append(text)
        return {
            "answer": f"{person['name']}: " + "; ".join(parts),
            "people_mentioned": [person["id"]],
            "people_with_photos": [_person_card(person)],
        }

    def _handle_person_residences(self, plan: QueryPlan) -> Optional[Dict[str, Any]]:
        matches = self._find_person_matches(plan.person_name)
        if not matches:
            return None
        person = matches[0]
        residences = get_residences(self.conn, person["id"])
        if not residences:
            return None
        parts = []
        for r in residences:
            text = ", ".join([x for x in [r["address"], r["address2"], r["city"], r["country"]] if x])
            if r["date"]:
                text += f" ({r['date']})"
            parts.append(text)
        return {
            "answer": f"{person['name']}:\n- " + "\n- ".join(parts),
            "people_mentioned": [person["id"]],
            "people_with_photos": [_person_card(person)],
        }

    def _handle_person_notes(self, plan: QueryPlan) -> Optional[Dict[str, Any]]:
        matches = self._find_person_matches(plan.person_name)
        if not matches:
            return None
        person = matches[0]
        notes = get_notes(self.conn, person["id"])
        if not notes:
            return None
        parts = []
        for n in notes[:5]:
            content = n["content"]
            parts.append(content[:350] + ("..." if len(content) > 350 else ""))
        return {
            "answer": f"{person['name']}:\n" + "\n---\n".join(parts),
            "people_mentioned": [person["id"]],
            "people_with_photos": [_person_card(person)],
        }

    def _handle_person_photos(self, plan: QueryPlan) -> Optional[Dict[str, Any]]:
        matches = self._find_person_matches(plan.person_name)
        if not matches:
            return None
        person = matches[0]
        photos = get_all_photos(self.conn, person["id"])
        if not photos:
            return None
        photo_cards = []
        for p in photos:
            if p["local_file"]:
                photo_cards.append({
                    "id": person["id"],
                    "name": p["title"] or person["name"],
                    "photo": p["local_file"],
                })
        return {
            "answer": f"Fotos de {person['name']} ({len(photo_cards)}).",
            "people_mentioned": [person["id"]],
            "people_with_photos": photo_cards[:12],
        }

    # ------------------------------------------------------------------
    # Legacy-compatible public handlers
    # ------------------------------------------------------------------

    def handle_birthdays(self, question: str) -> Dict[str, Any]:
        birthdays = get_birthdays_this_week(self.conn)
        if not birthdays:
            return {"answer": self._msg("es", "no_birthdays"), "people_mentioned": [], "people_with_photos": []}
        today = [b for b in birthdays if b["is_today"]]
        week = [b for b in birthdays if not b["is_today"]]
        parts = []
        if today:
            parts.append("Hoy cumplen años: " + ", ".join(f"{b['name']} ({b['age']})" if b.get("age") else b["name"] for b in today))
        if week:
            parts.append("Esta semana: " + ", ".join(f"{b['name']} ({b['date_label']})" for b in week))
        return {
            "answer": ". ".join(parts) + ".",
            "people_mentioned": [b["id"] for b in birthdays],
            "people_with_photos": [{"id": b["id"], "name": b["name"], "photo": b["photo"]} for b in birthdays[:8]],
        }

    def handle_stats(self, question: str) -> Dict[str, Any]:
        total = self.conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
        alive = self.conn.execute("SELECT COUNT(*) FROM people WHERE is_alive = 1").fetchone()[0]
        marriages = self.conn.execute("SELECT COUNT(*) FROM marriages").fetchone()[0]
        with_photos = self.conn.execute("SELECT COUNT(*) FROM people WHERE photo_count > 0").fetchone()[0]
        oldest = self.conn.execute("SELECT name, birth_year FROM people WHERE birth_year IS NOT NULL ORDER BY birth_year ASC LIMIT 1").fetchone()
        answer = (
            f"El árbol tiene {total} personas, {alive} marcadas como vivas, {marriages} matrimonios y {with_photos} personas con foto. "
            f"La persona con año de nacimiento más antiguo es {oldest['name']} ({oldest['birth_year']})."
        )
        return {"answer": answer, "people_mentioned": [], "people_with_photos": []}

    def handle_alive(self, question: str) -> Dict[str, Any]:
        people = get_alive_people(self.conn)
        if not people:
            return {"answer": self._msg("es", "no_alive"), "people_mentioned": [], "people_with_photos": []}
        parts = []
        photos = []
        for p in people[:50]:
            txt = p["name"]
            if p["birth_year"]:
                txt += f" ({p['birth_year']})"
            if p["birth_place"]:
                txt += f" de {p['birth_place']}"
            parts.append(txt)
            photos.append(_person_card(dict(p)))
        return {
            "answer": "Personas vivas:\n- " + "\n- ".join(parts),
            "people_mentioned": [p["id"] for p in people],
            "people_with_photos": photos[:8],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_person_matches(self, text: Optional[str]) -> List[Dict[str, Any]]:
        if not text:
            return []
        matches = find_person_by_name(self.conn, text)
        if matches:
            return matches
        for token in text.split():
            if len(token) > 3:
                matches = find_person_by_name(self.conn, token)
                if matches:
                    return matches
        return []

    def _try_name_fallback(self, question: str, language: str) -> Optional[Dict[str, Any]]:
        q = question.strip().rstrip("?.,!")
        matches = self._find_person_matches(q)
        if not matches:
            caps = re.findall(r"[A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][a-záéíóúàèìòùñç'’-]+(?:\s+[A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][a-záéíóúàèìòùñç'’-]+)*", question)
            for name in caps:
                matches = self._find_person_matches(name)
                if matches:
                    break
        if not matches:
            return None
        if len(matches) == 1:
            return self._build_info_response(matches[0], language)
        parts = []
        photos = []
        for m in matches[:10]:
            full = get_person(self.conn, m["id"])
            parts.append(_format_person(full))
            photos.append(_person_card(m))
        return {
            "answer": self._msg(language, "found_n", n=len(parts)) + "\n- " + "\n- ".join(parts),
            "people_mentioned": [m["id"] for m in matches[:10]],
            "people_with_photos": photos,
        }

    def _answer_single_relative(self, person: sqlite3.Row, field_name: str, label: str, language: str) -> Dict[str, Any]:
        rel_id = person[field_name]
        if not rel_id:
            return {
                "answer": self._msg(language, "no_relative", relation=label, person=person["name"]),
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(dict(person))],
            }
        relative = get_person(self.conn, rel_id)
        return {
            "answer": self._msg(language, "single_relative", relation=label, person=person["name"], target=_format_person(relative)),
            "people_mentioned": [person["id"], relative["id"]],
            "people_with_photos": [_person_card(dict(relative)), _person_card(dict(person))],
        }

    def _answer_relative_list(self, person: sqlite3.Row, relatives: Sequence[Any], relation_key: str, language: str) -> Dict[str, Any]:
        if not relatives:
            return {
                "answer": self._msg(language, "no_relation_list", relation=relation_key, person=person["name"]),
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(dict(person))],
            }
        rels = [dict(r) if isinstance(r, sqlite3.Row) else r for r in relatives]
        text = "; ".join(_format_person(r) for r in rels[:25])
        return {
            "answer": self._msg(language, "relation_list", relation=relation_key, person=person["name"], count=len(rels), values=text),
            "people_mentioned": [person["id"]] + [r["id"] for r in rels if r.get("id")],
            "people_with_photos": [_person_card(dict(person))] + [_person_card(r) for r in rels[:7]],
        }

    def _collect_descendants(self, person_id: str) -> List[sqlite3.Row]:
        out: List[sqlite3.Row] = []
        visited = set()
        queue = [person_id]
        while queue:
            current = queue.pop(0)
            for child in get_children(self.conn, current):
                if child["id"] not in visited:
                    visited.add(child["id"])
                    out.append(child)
                    queue.append(child["id"])
        return out

    def _build_info_response(self, person_match: Dict[str, Any], language: str = "es") -> Optional[Dict[str, Any]]:
        full = get_person(self.conn, person_match["id"])
        if not full:
            return None
        full = dict(full)
        pid = full["id"]
        sections = [full["name"]]
        if full.get("birth_date") or full.get("birth_place"):
            birth = full.get("birth_date", "?")
            if full.get("birth_place"):
                birth += f", {full['birth_place']}"
            sections.append(self._msg(language, "birth_section", value=birth))
        if full.get("death_date") or full.get("death_place"):
            death = full.get("death_date", "?")
            if full.get("death_place"):
                death += f", {full['death_place']}"
            sections.append(self._msg(language, "death_section", value=death))
        elif full.get("is_alive"):
            sections.append(self._msg(language, "alive_section"))
        if full.get("father_name") or full.get("mother_name"):
            parents = " / ".join([x for x in [full.get("father_name"), full.get("mother_name")] if x])
            sections.append(self._msg(language, "parents_section", value=parents))
        spouses = get_spouses(self.conn, pid)
        if spouses:
            sections.append(self._msg(language, "spouses_section", value="; ".join(s["person"]["name"] for s in spouses)))
        children = get_children(self.conn, pid)
        if children:
            sections.append(self._msg(language, "children_section", value=", ".join(c["name"] for c in children[:20])))
        occupations = get_occupations(self.conn, pid)
        if occupations:
            sections.append(self._msg(language, "occupations_section", value="; ".join(o["title"] for o in occupations[:10] if o["title"])))
        residences = get_residences(self.conn, pid)
        if residences:
            sections.append(self._msg(language, "residences_section", value="; ".join(", ".join([x for x in [r['address'], r['city'], r['country']] if x]) for r in residences[:8])))
        notes = get_notes(self.conn, pid)
        if notes:
            sections.append(self._msg(language, "notes_section", value=(notes[0]["content"][:250] + ("..." if len(notes[0]["content"]) > 250 else ""))))
        all_photos = get_all_photos(self.conn, pid)
        photos = [_person_card(full)]
        for p in all_photos[:7]:
            if p["local_file"]:
                photos.append({"id": pid, "name": p["title"] or full["name"], "photo": p["local_file"]})
        return {
            "answer": "\n".join(sections),
            "people_mentioned": [pid] + [s["person"]["id"] for s in spouses] + [c["id"] for c in children],
            "people_with_photos": photos[:8],
        }

    def _render_count_answer(self, plan: QueryPlan, count: int) -> str:
        if plan.language == "ca":
            return f"Resultat: {count} persona/es."
        if plan.language == "en":
            return f"Result: {count} people."
        return f"Resultado: {count} personas."

    def _render_people_list(self, plan: QueryPlan, rows: Sequence[sqlite3.Row]) -> str:
        header = {
            "ca": f"He trobat {len(rows)} resultat/s:",
            "en": f"I found {len(rows)} result(s):",
            "es": f"He encontrado {len(rows)} resultado(s):",
        }[plan.language]
        body = "\n".join(f"- {_format_person(dict(r))}" for r in rows[: plan.limit])
        return header + "\n" + body

    def _introspect_columns(self, table_name: str) -> set:
        try:
            rows = self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            return {r[1] for r in rows}
        except Exception:
            return set()

    def _plan_to_dict(self, plan: QueryPlan) -> Dict[str, Any]:
        return {
            "mode": plan.mode,
            "intent": plan.intent,
            "language": plan.language,
            "aggregation": plan.aggregation,
            "person_name": plan.person_name,
            "secondary_person_name": plan.secondary_person_name,
            "place": plan.place,
            "surname": plan.surname,
            "given_name": plan.given_name,
            "sex": plan.sex,
            "is_alive": plan.is_alive,
            "birth_year_from": plan.birth_year_from,
            "birth_year_to": plan.birth_year_to,
            "occupation_text": plan.occupation_text,
            "residence_text": plan.residence_text,
            "notes_text": plan.notes_text,
            "event_text": plan.event_text,
            "photo_required": plan.photo_required,
            "sort_by": plan.sort_by,
            "sort_dir": plan.sort_dir,
            "limit": plan.limit,
            "text_terms": plan.text_terms,
        }

    def _msg(self, language: str, key: str, **kwargs: Any) -> str:
        messages = {
            "es": {
                "no_results": "No he encontrado resultados.",
                "no_birth": "sin dato de nacimiento",
                "no_death": "sin dato de defunción",
                "no_birthdays": "No hay cumpleaños esta semana.",
                "no_alive": "No hay personas marcadas como vivas.",
                "found_n": "He encontrado {n} resultados:",
                "no_relative": "No tengo información sobre el/la {relation} de {person}.",
                "single_relative": "El/la {relation} de {person} es {target}.",
                "no_relation_list": "No tengo información sobre {relation} de {person}.",
                "relation_list": "{person} — {relation} ({count}): {values}.",
                "birth_section": "Nacimiento: {value}",
                "death_section": "Defunción: {value}",
                "alive_section": "Estado: vivo/a",
                "parents_section": "Padres: {value}",
                "spouses_section": "Cónyuges/parejas: {value}",
                "children_section": "Hijos: {value}",
                "occupations_section": "Ocupaciones: {value}",
                "residences_section": "Residencias: {value}",
                "notes_section": "Nota: {value}",
            },
            "ca": {
                "no_results": "No he trobat resultats.",
                "no_birth": "sense dada de naixement",
                "no_death": "sense dada de defunció",
                "no_birthdays": "No hi ha aniversaris aquesta setmana.",
                "no_alive": "No hi ha persones marcades com a vives.",
                "found_n": "He trobat {n} resultats:",
                "no_relative": "No tinc informació sobre el/la {relation} de {person}.",
                "single_relative": "El/la {relation} de {person} és {target}.",
                "no_relation_list": "No tinc informació sobre {relation} de {person}.",
                "relation_list": "{person} — {relation} ({count}): {values}.",
                "birth_section": "Naixement: {value}",
                "death_section": "Defunció: {value}",
                "alive_section": "Estat: viu/va",
                "parents_section": "Pares: {value}",
                "spouses_section": "Cònjuges/parelles: {value}",
                "children_section": "Fills: {value}",
                "occupations_section": "Ocupacions: {value}",
                "residences_section": "Residències: {value}",
                "notes_section": "Nota: {value}",
            },
            "en": {
                "no_results": "No results found.",
                "no_birth": "no birth data",
                "no_death": "no death data",
                "no_birthdays": "There are no birthdays this week.",
                "no_alive": "There are no people marked as alive.",
                "found_n": "I found {n} results:",
                "no_relative": "I have no information about the {relation} of {person}.",
                "single_relative": "The {relation} of {person} is {target}.",
                "no_relation_list": "I have no information about {relation} of {person}.",
                "relation_list": "{person} — {relation} ({count}): {values}.",
                "birth_section": "Birth: {value}",
                "death_section": "Death: {value}",
                "alive_section": "Status: alive",
                "parents_section": "Parents: {value}",
                "spouses_section": "Spouses/partners: {value}",
                "children_section": "Children: {value}",
                "occupations_section": "Occupations: {value}",
                "residences_section": "Residences: {value}",
                "notes_section": "Note: {value}",
            },
        }
        template = messages.get(language, messages["es"]).get(key, messages["es"].get(key, key))
        return template.format(**kwargs)
