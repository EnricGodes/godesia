"""Motor de consultas LLM con contexto reducido desde SQLite."""

import json
import re
import sqlite3

from database import (
    find_person_by_name, get_related_person_ids, get_people_by_ids,
)


SYSTEM_PROMPT = """Eres un asistente experto en genealogía de la familia Godes. Tienes acceso a parte del árbol genealógico familiar que se te proporciona como contexto.

INSTRUCCIONES:
- Responde siempre en el idioma en que te pregunten (catalán, castellano, etc.)
- Sé preciso: cita fechas, lugares y datos exactos del árbol
- Si no encuentras la información en el contexto proporcionado, dilo claramente
- Sé conversacional pero conciso
- Cuando menciones personas, incluye sus datos relevantes (fechas, lugares)

FORMATO DE RESPUESTA:
Responde en JSON con esta estructura:
{
  "answer": "Tu respuesta en texto natural",
  "people_mentioned": ["@I1@", "@I2@"]
}

El campo "people_mentioned" debe contener los IDs (formato @Ixx@) de TODAS las personas que mencionas en tu respuesta.

IMPORTANTE: Responde SOLO con el JSON, sin markdown ni texto adicional."""


def extract_people_from_question(conn, question):
    """Personas cuyo nombre aparece en la pregunta (por palabras con mayúscula)."""
    cleaned = re.sub(
        r"\b(qui|que|quin|quina|quien|cual|como|com|es|és|la|el|de|del|d\'|va|ser|"
        r"explica|conta|cuéntame|parla|habla|tell|compara|compare|"
        r"vida|history|historia|relació|relación|entre|and|y|i)\b",
        " ", question.lower(), flags=re.IGNORECASE
    ).strip()
    capitalized = re.findall(r"[A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][a-záéíóúàèìòùñç]+(?:\s+[A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][a-záéíóúàèìòùñç]+)*", question)
    results = []
    for name in capitalized:
        matches = find_person_by_name(conn, name)
        if matches:
            results.extend(matches)
    if not results and len(cleaned) > 3:
        for fragment in cleaned.split():
            if len(fragment) > 3:
                results.extend(find_person_by_name(conn, fragment))
    seen = set()
    unique = []
    for r in results:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)
    return unique


def collect_context_ids(conn, question, max_people=None):
    """IDs relevantes: personas nombradas + 2 generaciones de parientes."""
    all_ids = set()
    for person in extract_people_from_question(conn, question):
        all_ids.update(get_related_person_ids(conn, person["id"], generations=2))
        if max_people and len(all_ids) >= max_people:
            break
    if not all_ids:
        for word in [w for w in question.split() if len(w) > 3]:
            for m in find_person_by_name(conn, word)[:3]:
                all_ids.update(get_related_person_ids(conn, m["id"], generations=1))
    if max_people and len(all_ids) > max_people:
        all_ids = set(sorted(all_ids)[:max_people])
    return all_ids


class _PlainRefs:
    """Sin anonimizar: nombre e ID reales."""
    def ref(self, pid, name):
        return name, pid

    def is_living(self, pid):
        return False


def build_context(conn, person_ids, refs=None):
    """Contexto compacto (una línea por persona).

    `refs` decide cómo se nombra a cada persona (ref(id, nombre) → (nombre, id))
    y quién es vivo (is_living(id)); de los vivos solo salen sexo, año de
    nacimiento y relaciones. Sin `refs` → datos completos sin anonimizar.
    """
    refs = refs or _PlainRefs()
    people = get_people_by_ids(conn, person_ids)
    lines = []
    for p in people:
        living = refs.is_living(p["id"])
        name, pid = refs.ref(p["id"], p["name"])
        parts = ["[%s] %s" % (pid, name)]
        if p.get("sex"):
            parts.append("(%s)" % p["sex"])
        if living:
            if p.get("birth_year"):
                parts.append("n.%s" % p["birth_year"])
            parts.append("vivo")
        else:
            if p.get("birth_date"):
                parts.append("n.%s en %s" % (p["birth_date"], p.get("birth_place") or "?"))
            if p.get("death_date"):
                death_info = "m.%s en %s" % (p["death_date"], p.get("death_place") or "?")
                if p.get("death_cause"):
                    death_info += " (%s)" % p["death_cause"]
                parts.append(death_info)
        if p.get("father_id"):
            parts.append("padre:%s(%s)" % refs.ref(p["father_id"], p.get("father_name") or "?"))
        if p.get("mother_id"):
            parts.append("madre:%s(%s)" % refs.ref(p["mother_id"], p.get("mother_name") or "?"))
        for s in p.get("spouses_list") or []:
            sp = s["person"]
            sp_text = "cónyuge:%s(%s)" % refs.ref(sp["id"], sp["name"])
            if s.get("marriage_date") and not living and not refs.is_living(sp["id"]):
                sp_text += " casados:%s" % s["marriage_date"]
            parts.append(sp_text)
        if p.get("children_list"):
            kids = ", ".join("%s(%s)" % refs.ref(c["id"], c["name"]) for c in p["children_list"])
            parts.append("hijos:[%s]" % kids)
        if not living:
            occs = ", ".join(o["title"] for o in p.get("occupations") or [] if o.get("title"))
            if occs:
                parts.append("oficio:%s" % occs)
            addrs = []
            for r in p.get("residences") or []:
                a, c = r.get("address") or "", r.get("city") or ""
                if a or c:
                    addrs.append(("%s %s" % (a, c)).strip())
            if addrs:
                parts.append("residencias:%s" % "; ".join(addrs))
            for note in (p.get("notes") or [])[:2]:
                note = re.sub(r"<[^>]+>|https?://\S+|&\w+;", " ", note or "")
                note = re.sub(r"\s+", " ", note).strip()
                if not note:
                    continue
                if len(note) > 150:
                    note = note[:150] + "..."
                parts.append("nota:%s" % note)
        lines.append(" | ".join(parts))
    return "\n".join(lines)


class QueryEngine:
    def __init__(self, db_conn):
        import anthropic  # perezoso: el respaldo Gemini no lo necesita
        self.client = anthropic.Anthropic(timeout=120.0)
        self.conn = db_conn

    def _extract_names_from_question(self, question):
        return extract_people_from_question(self.conn, question)

    def _build_targeted_context(self, person_ids):
        return build_context(self.conn, person_ids)

    LANG_NAMES = {"es": "castellano", "ca": "catalán", "en": "inglés",
                  "fr": "francés", "de": "alemán"}

    def query(self, question, conversation_history=None, lang="es"):
        """Send a question with reduced context to Claude."""
        # Find relevant people
        mentioned = self._extract_names_from_question(question)
        all_ids = set()
        for person in mentioned:
            related = get_related_person_ids(self.conn, person["id"], generations=2)
            all_ids.update(related)

        # If no names found, use broader search (but still not all 922)
        if not all_ids:
            # Try a broader search with any word > 3 chars
            words = [w for w in question.split() if len(w) > 3]
            for word in words:
                matches = find_person_by_name(self.conn, word)
                for m in matches[:3]:
                    related = get_related_person_ids(self.conn, m["id"], generations=1)
                    all_ids.update(related)

        # Build context
        if all_ids:
            context = self._build_targeted_context(all_ids)
            context_note = "(Contexto: %d personas relevantes)" % len(all_ids)
        else:
            # Last resort: send basic stats
            total = self.conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
            context = "No se pudieron identificar personas específicas. Total: %d personas en el árbol." % total
            context_note = "(Contexto limitado)"

        messages = []
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": question})

        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            system="%s\n\nIDIOMA PREFERIDO: responde en %s salvo que la pregunta esté claramente en otro idioma.\n\n%s\nÁRBOL GENEALÓGICO:\n%s"
                   % (SYSTEM_PROMPT, self.LANG_NAMES.get(lang, lang), context_note, context),
            messages=messages,
        )

        response_text = response.content[0].text

        # Parse JSON response
        try:
            if "```" in response_text:
                json_match = response_text.split("```")[1]
                if json_match.startswith("json"):
                    json_match = json_match[4:]
                result = json.loads(json_match)
            else:
                result = json.loads(response_text)
        except (json.JSONDecodeError, IndexError):
            result = {"answer": response_text, "people_mentioned": []}

        # Enrich with photo info
        people_with_photos = []
        for pid in result.get("people_mentioned", []):
            row = self.conn.execute(
                "SELECT id, name, photo_file FROM people WHERE id = ?", (pid,)
            ).fetchone()
            if row:
                entry = {"id": row["id"], "name": row["name"]}
                if row["photo_file"]:
                    entry["photo"] = row["photo_file"]
                people_with_photos.append(entry)

        result["people_with_photos"] = people_with_photos
        return result
