"""Motor de consultas LLM con contexto reducido desde SQLite."""

import json
import re
import sqlite3

import anthropic

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


class QueryEngine:
    def __init__(self, db_conn):
        self.client = anthropic.Anthropic(timeout=120.0)
        self.conn = db_conn

    def _extract_names_from_question(self, question):
        """Try to extract person names mentioned in the question."""
        # Remove common question words
        cleaned = re.sub(
            r"\b(qui|que|quin|quina|quien|cual|como|com|es|és|la|el|de|del|d\'|va|ser|"
            r"explica|conta|cuéntame|parla|habla|tell|compara|compare|"
            r"vida|history|historia|relació|relación|entre|and|y|i)\b",
            " ", question.lower(), flags=re.IGNORECASE
        ).strip()
        # Find potential names (capitalized words in original question)
        capitalized = re.findall(r"[A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][a-záéíóúàèìòùñç]+(?:\s+[A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][a-záéíóúàèìòùñç]+)*", question)
        results = []
        for name in capitalized:
            matches = find_person_by_name(self.conn, name)
            if matches:
                results.extend(matches)
        # Fallback: try cleaned fragments
        if not results and len(cleaned) > 3:
            for fragment in cleaned.split():
                if len(fragment) > 3:
                    matches = find_person_by_name(self.conn, fragment)
                    results.extend(matches)
        # Deduplicate
        seen = set()
        unique = []
        for r in results:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)
        return unique

    def _build_targeted_context(self, person_ids):
        """Build compact text context for only the specified people."""
        people = get_people_by_ids(self.conn, person_ids)
        lines = []
        for p in people:
            parts = ["[%s] %s" % (p["id"], p["name"])]
            if p.get("sex"):
                parts.append("(%s)" % p["sex"])
            if p.get("birth_date"):
                parts.append("n.%s en %s" % (p["birth_date"], p.get("birth_place", "?")))
            if p.get("death_date"):
                death_info = "m.%s en %s" % (p["death_date"], p.get("death_place", "?"))
                if p.get("death_cause"):
                    death_info += " (%s)" % p["death_cause"]
                parts.append(death_info)
            if p.get("father_name"):
                parts.append("padre:%s(%s)" % (p["father_name"], p.get("father_id", "")))
            if p.get("mother_name"):
                parts.append("madre:%s(%s)" % (p["mother_name"], p.get("mother_id", "")))
            if p.get("spouses_list"):
                for s in p["spouses_list"]:
                    sp = s["person"]
                    sp_text = "cónyuge:%s(%s)" % (sp["name"], sp["id"])
                    if s.get("marriage_date"):
                        sp_text += " casados:%s" % s["marriage_date"]
                    parts.append(sp_text)
            if p.get("children_list"):
                kids = ", ".join("%s(%s)" % (c["name"], c["id"]) for c in p["children_list"])
                parts.append("hijos:[%s]" % kids)
            if p.get("occupations"):
                occs = ", ".join(o["title"] for o in p["occupations"] if o.get("title"))
                if occs:
                    parts.append("oficio:%s" % occs)
            if p.get("residences"):
                addrs = []
                for r in p["residences"]:
                    a = r.get("address", "")
                    c = r.get("city", "")
                    if a or c:
                        addrs.append("%s %s" % (a, c))
                if addrs:
                    parts.append("residencias:%s" % "; ".join(addrs))
            if p.get("notes"):
                for note in p["notes"][:2]:
                    if len(note) > 150:
                        note = note[:150] + "..."
                    parts.append("nota:%s" % note)

            lines.append(" | ".join(parts))

        return "\n".join(lines)

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
