"""Respaldo LLM (Gemini, tier gratuito) con anonimización de personas vivas.

El tier gratuito de Gemini permite a Google usar lo que se le envía, así que
NINGÚN dato identificativo de una persona viva sale del servidor:

- En el contexto, cada vivo es «Persona A», «Persona B»… con ID @X1@, @X2@…
  y solo conserva sexo, año de nacimiento y relaciones (también por alias).
  Sin fecha exacta, lugares, residencias, oficios, notas ni email.
- En la pregunta, el historial y el propio contexto (notas de difuntos que
  nombran a vivos) se sustituyen los nombres de TODOS los vivos de la BD.
- Guardia final: si en el texto saliente queda el nombre de un vivo, no se
  envía nada (AnonymizationError).
- La respuesta se des-anonimiza: alias → nombre real e IDs reales.

Vivo = `is_alive = 1`, o sin datos de defunción y nacido hace < 105 años, o
sin año de nacimiento ni defunción pero con padre/madre/cónyuge/hijo vivo.
"""

import json
import re
import unicodedata
from datetime import date

import gemini_client
from query_engine import SYSTEM_PROMPT, build_context, collect_context_ids

MAX_CONTEXT_PEOPLE = 60
MAX_CONTEXT_CHARS = 16000   # ≈ 4-5k tokens: que una pregunta no se coma el cupo
MAX_HISTORY_MESSAGES = 6
LANG_NAMES = {"es": "castellano", "ca": "catalán", "en": "inglés",
              "fr": "francés", "de": "alemán"}

ANON_NOTE = (
    "NOTA DE PRIVACIDAD: las personas vivas aparecen anonimizadas como "
    "«Persona A», «Persona B»… con IDs @X1@, @X2@… Refiérete a ellas EXACTAMENTE "
    "con ese alias (sin inventar nombres) e incluye su ID en people_mentioned. "
    "No escribas IDs (@I…@, @X…@) dentro del texto de answer: solo en people_mentioned."
)


class AnonymizationError(Exception):
    """Quedaba un nombre de persona viva en el texto a enviar."""


def _fold(s):
    """Minúsculas sin acentos, carácter a carácter (misma longitud que s)."""
    out = []
    for ch in s:
        base = unicodedata.normalize("NFD", ch)[0]
        out.append(base.lower() if len(base.lower()) == 1 else ch)
    return "".join(out)


def _clean(name):
    return re.sub(r"\s+", " ", (name or "")).strip()


def _alias_label(n):
    """0 → A, 25 → Z, 26 → AA…"""
    label = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        label = chr(65 + r) + label
    return "Persona " + label


def living_ids(conn):
    year_limit = date.today().year - 105
    rows = conn.execute(
        "SELECT id, is_alive, birth_year, death_year, death_date, death_place, "
        "father_id, mother_id FROM people"
    ).fetchall()
    alive, unknown = set(), []
    for r in rows:
        no_death = not (r["death_year"] or (r["death_date"] or "").strip()
                        or (r["death_place"] or "").strip())
        if r["is_alive"] or (no_death and r["birth_year"] and r["birth_year"] >= year_limit):
            alive.add(r["id"])
        elif no_death and not r["birth_year"]:
            unknown.append(r)
    for r in unknown:
        if r["father_id"] in alive or r["mother_id"] in alive:
            alive.add(r["id"])
            continue
        rel = conn.execute(
            "SELECT child_id FROM children WHERE parent_id = ? "
            "UNION SELECT CASE WHEN person1_id = ? THEN person2_id ELSE person1_id END "
            "FROM marriages WHERE person1_id = ? OR person2_id = ?",
            (r["id"],) * 4).fetchall()
        if any(x[0] in alive for x in rel):
            alive.add(r["id"])
    return alive


class Anonymizer:
    def __init__(self, conn):
        self.conn = conn
        self.alive = living_ids(conn)
        self._by_id = {}       # real id → (alias, alias_id)
        self._back = {}        # alias_id → real id
        self._names = {}       # real id → real name
        self._variants = []    # (folded variant, real id), más largas primero
        self._build_variants()

    def _build_variants(self):
        if not self.alive:
            return
        rows = self.conn.execute(
            "SELECT id, name, given_name, surname, nickname FROM people WHERE id IN (%s)"
            % ",".join("?" * len(self.alive)), list(self.alive)).fetchall()
        # «Nombre + primer apellido» solo si no lo comparte nadie más del árbol.
        all_short = {}
        for r in self.conn.execute("SELECT id, given_name, surname FROM people"):
            short = _fold(_clean("%s %s" % (r["given_name"] or "", (r["surname"] or "").split(" ")[0])))
            all_short.setdefault(short, set()).add(r["id"])
        variants = {}
        for r in rows:
            self._names[r["id"]] = _clean(r["name"])
            cands = {_clean(r["name"]), _clean("%s %s" % (r["given_name"] or "", r["surname"] or ""))}
            surname1 = (r["surname"] or "").split(" ")[0]
            short = _clean("%s %s" % (r["given_name"] or "", surname1))
            if len(all_short.get(_fold(short), ())) == 1:
                cands.add(short)
            nick = _clean(r["nickname"])
            if len(nick) >= 4 and " " in nick:
                cands.add(nick)
            for c in cands:
                if len(c) >= 6 and " " in c:
                    variants[_fold(c)] = r["id"]
        self._variants = sorted(variants.items(), key=lambda kv: -len(kv[0]))

    # ── API usada por build_context ──
    def is_living(self, pid):
        return pid in self.alive

    def _alias(self, pid):
        if pid not in self._by_id:
            n = len(self._by_id)
            alias_id = "@X%d@" % (n + 1)
            self._by_id[pid] = (_alias_label(n), alias_id)
            self._back[alias_id] = pid
        return self._by_id[pid]

    def ref(self, pid, name):
        if pid in self.alive:
            return self._alias(pid)
        return _clean(name), pid

    # ── texto libre ──
    def scrub(self, text):
        """Sustituye en `text` los nombres de cualquier vivo por su alias."""
        if not text or not self._variants:
            return text
        folded = _fold(text)
        spans = []
        for variant, pid in self._variants:
            for m in re.finditer(r"(?<!\w)%s(?!\w)" % re.escape(variant), folded):
                a, b = m.span()
                if any(a < y and x < b for x, y, _ in spans):
                    continue
                spans.append((a, b, pid))
        for a, b, pid in sorted(spans, reverse=True):
            text = text[:a] + self._alias(pid)[0] + text[b:]
        return text

    def assert_clean(self, text):
        folded = _fold(text)
        for variant, pid in self._variants:
            if re.search(r"(?<!\w)%s(?!\w)" % re.escape(variant), folded):
                raise AnonymizationError("nombre de persona viva en el texto saliente (%s)" % pid)

    def restore(self, text):
        """Alias → nombre real (y @Xn@ → ID real)."""
        if not text or not self._by_id:
            return text
        for pid, (alias, alias_id) in sorted(self._by_id.items(), key=lambda kv: -len(kv[1][0])):
            text = re.sub(r"(?<!\w)%s(?!\w)" % re.escape(alias), self._names.get(pid, alias), text)
            text = text.replace(alias_id, pid)
        return text

    def restore_id(self, pid):
        return self._back.get(pid, pid)


def build_request(conn, question, history=None, lang="es"):
    """Prepara (anonimizador, system, contents) listos para enviar a Gemini."""
    anon = Anonymizer(conn)
    ids = collect_context_ids(conn, question, max_people=MAX_CONTEXT_PEOPLE)
    if ids:
        context = anon.scrub(build_context(conn, ids, refs=anon))
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS].rsplit("\n", 1)[0] + "\n(…contexto recortado)"
        note = "(Contexto: %d personas relevantes)" % len(ids)
    else:
        total = conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
        context = "No se pudieron identificar personas específicas. Total: %d personas en el árbol." % total
        note = "(Contexto limitado)"
    system = "%s\n\n%s\n\nIDIOMA PREFERIDO: responde en %s salvo que la pregunta esté claramente en otro idioma.\n\n%s\nÁRBOL GENEALÓGICO:\n%s" % (
        SYSTEM_PROMPT, ANON_NOTE, LANG_NAMES.get(lang, lang), note, context)
    contents = []
    for msg in (history or [])[-MAX_HISTORY_MESSAGES:]:
        text = re.sub(r"<[^>]+>", "", str(msg.get("content") or ""))
        if text:
            contents.append({"role": "model" if msg.get("role") == "assistant" else "user",
                             "text": anon.scrub(text)})
    contents.append({"role": "user", "text": anon.scrub(question)})
    anon.assert_clean(system + "\n" + "\n".join(c["text"] for c in contents))
    return anon, system, contents


def _parse(text):
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.startswith("json"):
            t = t[4:]
    try:
        data = json.loads(t)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    return {"answer": text, "people_mentioned": []}


def ask(conn, question, history=None, lang="es", model=gemini_client.DEFAULT_MODEL):
    """Versión síncrona: pregunta a Gemini con los vivos anonimizados → (result, usage)."""
    anon, system, contents = build_request(conn, question, history, lang)
    text, usage = gemini_client.generate(system, contents, model=model)
    return finish(conn, anon, text), usage


def finish(conn, anon, text):
    """Des-anonimiza la respuesta del modelo y la enriquece con fotos."""
    data = _parse(text)
    answer = anon.restore(str(data.get("answer") or ""))
    answer = re.sub(r"\s*\(\s*@[IX]\d+@\s*\)", "", answer)
    answer = re.sub(r"\(\s*@[IX]\d+@\s*[,;]\s*", "(", answer)
    answer = re.sub(r"\s*@[IX]\d+@", "", answer)
    people = []
    for pid in data.get("people_mentioned") or []:
        real = anon.restore_id(str(pid))
        row = conn.execute("SELECT id, name, photo_file FROM people WHERE id = ?", (real,)).fetchone()
        if row and all(p["id"] != row["id"] for p in people):
            entry = {"id": row["id"], "name": row["name"]}
            if row["photo_file"]:
                entry["photo"] = row["photo_file"]
            people.append(entry)
    return {
        "answer": answer,
        "people_mentioned": [p["id"] for p in people],
        "people_with_photos": people,
        "source": "llm",
        "anonymized_living": len(anon._by_id),
    }
