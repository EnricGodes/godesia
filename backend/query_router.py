"""Query Router: clasifica preguntas y responde directamente desde SQLite cuando es posible."""

import re
import sqlite3
from database import (
    find_person_by_name, get_person, get_parents, get_children,
    get_spouses, search_people, get_birthdays_this_week,
    get_related_person_ids, get_people_by_ids,
    get_siblings, get_grandparents, get_grandchildren,
    get_occupations, get_residences, get_notes, get_all_photos,
    get_alive_people, get_born_in,
)


def _person_card(person):
    """Build a response entry for a person (for people_with_photos)."""
    return {
        "id": person["id"] if isinstance(person, dict) else person[0],
        "name": person["name"] if isinstance(person, dict) else person[1],
        "photo": person.get("photo_file") if isinstance(person, dict) else None,
    }


def _format_person(p):
    """Format a person dict/row as readable text."""
    if isinstance(p, sqlite3.Row):
        p = dict(p)
    parts = [p["name"]]
    if p.get("birth_year"):
        parts.append("(%s%s)" % (
            p["birth_year"],
            "-%s" % p.get("death_year", "") if p.get("death_year") else (
                "" if p.get("is_alive") else "-?"
            )
        ))
    if p.get("birth_place"):
        parts.append("de %s" % p["birth_place"])
    return " ".join(parts)


def _extract_name(question, prefixes):
    """Extract person name from question after given prefixes."""
    q = question.strip()
    for prefix in prefixes:
        match = re.search(prefix, q, re.IGNORECASE)
        if match:
            name = q[match.end():].strip().rstrip("?.,!").strip()
            # Remove articles
            name = re.sub(r"^(el|la|l\'|en|na|de|del|los|las|els|les)\s+", "", name, flags=re.IGNORECASE)
            return name
    return None


class QueryRouter:
    def __init__(self, conn):
        self.conn = conn
        self.patterns = [
            # (regex pattern, handler method name)
            # Family relationships
            (r"(mare|madre|mother)\b", "handle_mother"),
            (r"(pare|padre|father)\b", "handle_father"),
            (r"(fills?|hijos?|children|descendents?|descendientes?)\b", "handle_children"),
            (r"(germans?|hermanos?|siblings?)\b", "handle_siblings"),
            (r"(es\s+va\s+casar|se\s+cas[oó]|esposa|marit|marido|mujer|dona|spouse|married|amb\s+qui)", "handle_spouse"),
            (r"(avi[s]?\b|abuelo[s]?|grandfather|grandmother|[àa]via|abuela|padrins?|abuelos)", "handle_grandparents"),
            (r"(n[eé]t[s]?\b|nieto[s]?|grandchild|grandchildren|nieta[s]?)", "handle_grandchildren"),
            # Life events
            (r"(quan\s+va\s+n[aà]ixer|cuando\s+naci[oó]|born|data\s+de\s+naixement|fecha\s+de\s+nacimiento|nascut|nacido|nació)", "handle_birth"),
            (r"(quan\s+va\s+morir|cuando\s+muri[oó]|died|mort\b|muri[oó]|falleci[oó]|muerte|defunci[oó])", "handle_death"),
            (r"(on\s+va\s+viure|d[oó]nde\s+vivi[oó]|where.*live|resid[eè]nci|domicili|direcci[oó]|adre[çc]a|viv[ií]a)", "handle_residence"),
            (r"(ofici|profesi[oó]|ocupaci[oó]|trabaj|feina|treball|occupation|job|dedicava|dedicaba|treballa)", "handle_occupation"),
            # Content
            (r"(fotos?|imatge|imagen|picture|photo|mostra.*foto|ense[ñn]a.*foto)\b", "handle_photos"),
            (r"(notes?\b|notas?\b|documents?|observaci|anotaci)", "handle_notes"),
            # Aggregations
            (r"(cumple|birthday|aniversari|fa\s+anys|neix\s+avui|nacen\s+hoy)", "handle_birthdays"),
            (r"(estad[ií]stic|quant[ae]s?\s+person|cu[aá]nt[oa]s?\s+person|stats|resum|resumen)", "handle_stats"),
            (r"(viu[s]?\b|viva?[os]?\b|alive|living|qui\s+est[àa]\s+viu|qui[eé]n\s+est[aá]\s+vivo)", "handle_alive"),
            (r"(nascuts?\s+a|nacidos?\s+en|born\s+in|origen|natural\s+de)", "handle_born_in"),
            # Search / info
            (r"(informaci[oó]|info\b|parla.m|h[aá]blame|cu[eé]ntame|tell\s+me|dades|datos|fitxa|ficha|perfil|sobre)\b", "handle_info"),
            (r"(busca|cerca|search|trobar|encontrar|qui\s+[eé]s|quien\s+es)\b", "handle_search"),
        ]

    def route(self, question):
        """Try to answer from SQLite. Returns response dict or None if LLM needed."""
        q = question.lower().strip()

        for pattern, handler_name in self.patterns:
            if re.search(pattern, q, re.IGNORECASE):
                handler = getattr(self, handler_name)
                result = handler(question)
                if result:
                    result["source"] = "db"
                    return result

        # Fallback: if the question looks like a person name, show their info
        result = self._try_name_fallback(question)
        if result:
            result["source"] = "db"
            return result

        return None

    def _try_name_fallback(self, question):
        """If the question is just a name or contains a recognizable name, show info."""
        # Don't fallback if the question contains comparison/complex reasoning words
        q_lower = question.lower()
        complex_words = [
            "compara", "diferencia", "relaci[oó]", "semblant", "parecid",
            "millor", "mejor", "pitjor", "peor", "entre", "versus", "vs",
            "per qu[eè]", "por qu[eé]", "why", "com [eé]s que", "cómo es que",
            "explica.*relaci", "qu[eè] va passar", "qué pasó", "what happened",
        ]
        for word in complex_words:
            if re.search(word, q_lower):
                return None

        q = question.strip().rstrip("?.,!")
        # Try the whole question as a name
        matches = find_person_by_name(self.conn, q)
        if matches:
            return self._build_info_response(matches[0])
        # Try capitalized words
        capitalized = re.findall(
            r"[A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][a-záéíóúàèìòùñç]+(?:\s+[A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][a-záéíóúàèìòùñç]+)*",
            question
        )
        for name in capitalized:
            if len(name) > 4:  # Skip short words like "Hola"
                matches = find_person_by_name(self.conn, name)
                if matches:
                    return self._build_info_response(matches[0])
        return None

    def _find_person_in_question(self, question, prefixes):
        """Extract name from question and find matching person(s)."""
        name = _extract_name(question, prefixes)
        if not name:
            # Try to find any name-like text in the question
            # Remove common words and try the rest
            cleaned = re.sub(
                r"\b(qui|que|quin|quina|quien|cual|como|com|es|és|la|el|de|del|d\'|va|ser|"
                r"mare|madre|mother|pare|padre|father|fills?|hijos?|children|"
                r"nascut|nacido|born|mort|muerto|died|casar|esposa|marit|"
                r"quan|cuando|on|donde|where)\b",
                "", question.lower(), flags=re.IGNORECASE
            ).strip().rstrip("?.,!")
            if len(cleaned) > 2:
                name = cleaned

        if not name:
            return None

        matches = find_person_by_name(self.conn, name)
        if not matches:
            # Try partial words
            words = name.split()
            for word in words:
                if len(word) > 3:
                    matches = find_person_by_name(self.conn, word)
                    if matches:
                        break
        return matches

    def handle_mother(self, question):
        prefixes = [
            r"(?:mare|madre|mother)\s+(?:de|d\'|of)\s+",
            r"(?:qui|quien|who)\s+.*(?:mare|madre|mother)",
        ]
        matches = self._find_person_in_question(question, prefixes)
        if not matches:
            return None

        person = matches[0]
        full = get_person(self.conn, person["id"])
        if not full or not full["mother_id"]:
            return {
                "answer": "No tengo información sobre la madre de %s." % person["name"],
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }

        mother = get_person(self.conn, full["mother_id"])
        return {
            "answer": "La madre de %s es %s." % (person["name"], _format_person(mother)),
            "people_mentioned": [person["id"], mother["id"]],
            "people_with_photos": [_person_card(dict(mother)), _person_card(person)],
        }

    def handle_father(self, question):
        prefixes = [
            r"(?:pare|padre|father)\s+(?:de|d\'|of)\s+",
            r"(?:qui|quien|who)\s+.*(?:pare|padre|father)",
        ]
        matches = self._find_person_in_question(question, prefixes)
        if not matches:
            return None

        person = matches[0]
        full = get_person(self.conn, person["id"])
        if not full or not full["father_id"]:
            return {
                "answer": "No tengo información sobre el padre de %s." % person["name"],
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }

        father = get_person(self.conn, full["father_id"])
        return {
            "answer": "El padre de %s es %s." % (person["name"], _format_person(father)),
            "people_mentioned": [person["id"], father["id"]],
            "people_with_photos": [_person_card(dict(father)), _person_card(person)],
        }

    def handle_children(self, question):
        prefixes = [
            r"(?:fills?|hijos?|children|descendents?|descendientes?)\s+(?:de|d\'|of)\s+",
            r"(?:quants?|cu[aá]ntos?)\s+(?:fills?|hijos?)",
        ]
        matches = self._find_person_in_question(question, prefixes)
        if not matches:
            return None

        person = matches[0]
        children = get_children(self.conn, person["id"])
        if not children:
            return {
                "answer": "No tengo constancia de hijos de %s." % person["name"],
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }

        kids_text = ", ".join(_format_person(c) for c in children)
        answer = "%s tuvo %d hijo%s: %s." % (
            person["name"], len(children),
            "s" if len(children) != 1 else "", kids_text
        )
        people_ids = [person["id"]] + [c["id"] for c in children]
        photos = [_person_card(person)] + [_person_card(dict(c)) for c in children]
        return {
            "answer": answer,
            "people_mentioned": people_ids,
            "people_with_photos": photos,
        }

    def handle_spouse(self, question):
        prefixes = [
            r"(?:esposa|marit|marido|mujer|dona|spouse)\s+(?:de|d\'|of)\s+",
            r"(?:amb\s+qui|con\s+qui[eé]n|who\s+did)\s+.*(?:casar|marry)",
            r"(?:es\s+va\s+casar|se\s+cas[oó])\s+",
        ]
        matches = self._find_person_in_question(question, prefixes)
        if not matches:
            return None

        person = matches[0]
        spouses = get_spouses(self.conn, person["id"])
        if not spouses:
            return {
                "answer": "No tengo información sobre el/la cónyuge de %s." % person["name"],
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }

        parts = []
        people_ids = [person["id"]]
        photos = [_person_card(person)]
        for s in spouses:
            sp = s["person"]
            text = _format_person(sp)
            if s["marriage_date"]:
                text += ", casados el %s" % s["marriage_date"]
            if s["marriage_place"]:
                text += " en %s" % s["marriage_place"]
            parts.append(text)
            people_ids.append(sp["id"])
            photos.append(_person_card(sp))

        answer = "%s se casó con: %s." % (person["name"], "; ".join(parts))
        return {
            "answer": answer,
            "people_mentioned": people_ids,
            "people_with_photos": photos,
        }

    def handle_birth(self, question):
        prefixes = [
            r"(?:quan|cuando|when)\s+.*(?:n[aà]ixer|naci[oó]|born)\s+",
            r"(?:nascut|nacido|born)\s+",
            r"(?:data|fecha|date)\s+.*(?:naixement|nacimiento|birth)\s+(?:de|d\'|of)\s+",
        ]
        matches = self._find_person_in_question(question, prefixes)
        if not matches:
            return None

        person = matches[0]
        full = get_person(self.conn, person["id"])
        parts = []
        if full["birth_date"]:
            parts.append("nació el %s" % full["birth_date"])
        if full["birth_place"]:
            parts.append("en %s" % full["birth_place"])

        if not parts:
            answer = "No tengo la fecha de nacimiento de %s." % full["name"]
        else:
            answer = "%s %s." % (full["name"], " ".join(parts))

        return {
            "answer": answer,
            "people_mentioned": [person["id"]],
            "people_with_photos": [_person_card(person)],
        }

    def handle_death(self, question):
        prefixes = [
            r"(?:quan|cuando|when)\s+.*(?:morir|muri[oó]|died)\s+",
            r"(?:mort|muerto|fallecido|died)\s+",
        ]
        matches = self._find_person_in_question(question, prefixes)
        if not matches:
            return None

        person = matches[0]
        full = get_person(self.conn, person["id"])
        parts = []
        if full["death_date"]:
            parts.append("murió el %s" % full["death_date"])
        if full["death_place"]:
            parts.append("en %s" % full["death_place"])
        if full["death_cause"]:
            parts.append("(%s)" % full["death_cause"])

        if not parts:
            if full["is_alive"]:
                answer = "%s está vivo/a (no consta defunción)." % full["name"]
            else:
                answer = "No tengo la fecha de defunción de %s." % full["name"]
        else:
            answer = "%s %s." % (full["name"], " ".join(parts))

        return {
            "answer": answer,
            "people_mentioned": [person["id"]],
            "people_with_photos": [_person_card(person)],
        }

    def handle_birthdays(self, question):
        birthdays = get_birthdays_this_week(self.conn)
        if not birthdays:
            return {
                "answer": "No hay cumpleaños esta semana en el árbol familiar.",
                "people_mentioned": [],
                "people_with_photos": [],
            }

        today_bdays = [b for b in birthdays if b["is_today"]]
        week_bdays = [b for b in birthdays if not b["is_today"]]

        parts = []
        if today_bdays:
            names = ", ".join(
                "%s (%s años)" % (b["name"], b["age"]) if b["age"] else b["name"]
                for b in today_bdays
            )
            parts.append("Hoy cumplen años: %s." % names)
        if week_bdays:
            names = ", ".join(
                "%s (%s, %s años)" % (b["name"], b["date_label"], b["age"]) if b["age"]
                else "%s (%s)" % (b["name"], b["date_label"])
                for b in week_bdays
            )
            parts.append("Esta semana: %s." % names)

        return {
            "answer": " ".join(parts),
            "people_mentioned": [b["id"] for b in birthdays],
            "people_with_photos": [
                {"id": b["id"], "name": b["name"], "photo": b["photo"]}
                for b in birthdays
            ],
        }

    def handle_stats(self, question):
        total = self.conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
        alive = self.conn.execute("SELECT COUNT(*) FROM people WHERE is_alive = 1").fetchone()[0]
        marriages = self.conn.execute("SELECT COUNT(*) FROM marriages").fetchone()[0]
        with_photos = self.conn.execute("SELECT COUNT(*) FROM people WHERE photo_count > 0").fetchone()[0]
        oldest = self.conn.execute(
            "SELECT name, birth_year FROM people WHERE birth_year IS NOT NULL ORDER BY birth_year LIMIT 1"
        ).fetchone()

        answer = (
            "El árbol genealógico Godes tiene %d personas, de las cuales %d están vivas (estimado). "
            "Hay %d matrimonios registrados y %d personas con fotos. "
            "La persona más antigua es %s (%d)."
        ) % (total, alive, marriages, with_photos, oldest["name"], oldest["birth_year"])

        return {
            "answer": answer,
            "people_mentioned": [],
            "people_with_photos": [],
        }

    def handle_search(self, question):
        prefixes = [
            r"(?:busca|cerca|search|trobar|encontrar)\s+(?:a\s+)?",
            r"(?:qui|quien|who)\s+[eé]s\s+",
        ]
        name = _extract_name(question, prefixes)
        if not name or len(name) < 2:
            return None

        matches = find_person_by_name(self.conn, name)
        if not matches:
            return {"answer": "No he encontrado a nadie con el nombre '%s'." % name,
                    "people_mentioned": [], "people_with_photos": []}

        parts = []
        photos = []
        for m in matches[:10]:
            full = get_person(self.conn, m["id"])
            info = _format_person(full)
            if full["father_name"]:
                info += ", hijo/a de %s" % full["father_name"]
                if full["mother_name"]:
                    info += " y %s" % full["mother_name"]
            parts.append(info)
            photos.append(_person_card(m))

        answer = "He encontrado %d resultado%s:\n%s" % (
            len(parts), "s" if len(parts) != 1 else "",
            "\n".join("- %s" % p for p in parts)
        )

        return {
            "answer": answer,
            "people_mentioned": [m["id"] for m in matches[:10]],
            "people_with_photos": photos,
        }

    # --- NEW HANDLERS ---

    def _build_info_response(self, person_match):
        """Build a complete profile/info response for a person."""
        full = get_person(self.conn, person_match["id"])
        if not full:
            return None
        full = dict(full)
        pid = full["id"]

        sections = []
        people_ids = [pid]
        photos_list = [_person_card(full)]

        # Name and basic info
        header = full["name"]
        if full.get("sex"):
            header += " (%s)" % ("Home" if full["sex"] == "M" else "Dona")
        sections.append(header)

        # Birth
        if full.get("birth_date") or full.get("birth_place"):
            birth = "Naixement: %s" % (full.get("birth_date", "?"))
            if full.get("birth_place"):
                birth += ", %s" % full["birth_place"]
            sections.append(birth)

        # Death
        if full.get("death_date") or full.get("death_place"):
            death = "Defunció: %s" % (full.get("death_date", "?"))
            if full.get("death_place"):
                death += ", %s" % full["death_place"]
            if full.get("death_cause"):
                death += " (%s)" % full["death_cause"]
            sections.append(death)
        elif full.get("is_alive"):
            sections.append("Estat: Viu/a")

        # Parents
        if full.get("father_name") or full.get("mother_name"):
            parents = "Pares: "
            parts = []
            if full.get("father_name"):
                parts.append(full["father_name"])
                if full.get("father_id"):
                    people_ids.append(full["father_id"])
            if full.get("mother_name"):
                parts.append(full["mother_name"])
                if full.get("mother_id"):
                    people_ids.append(full["mother_id"])
            sections.append(parents + " i ".join(parts))

        # Spouses
        spouses = get_spouses(self.conn, pid)
        if spouses:
            for s in spouses:
                sp = s["person"]
                text = "Cònjuge: %s" % sp["name"]
                if s.get("marriage_date"):
                    text += " (casats %s" % s["marriage_date"]
                    if s.get("marriage_place"):
                        text += ", %s" % s["marriage_place"]
                    text += ")"
                sections.append(text)
                people_ids.append(sp["id"])
                photos_list.append(_person_card(sp))

        # Children
        children = get_children(self.conn, pid)
        if children:
            kids = ", ".join(c["name"] for c in children)
            sections.append("Fills (%d): %s" % (len(children), kids))
            for c in children:
                people_ids.append(c["id"])

        # Siblings
        siblings = get_siblings(self.conn, pid)
        if siblings:
            sibs = ", ".join(s["name"] for s in siblings)
            sections.append("Germans (%d): %s" % (len(siblings), sibs))

        # Occupations
        occupations = get_occupations(self.conn, pid)
        if occupations:
            occs = []
            for o in occupations:
                text = o["title"]
                if o["date"]:
                    text += " (%s)" % o["date"]
                if o["place"]:
                    text += " a %s" % o["place"]
                occs.append(text)
            sections.append("Oficis: %s" % "; ".join(occs))

        # Residences
        residences = get_residences(self.conn, pid)
        if residences:
            addrs = []
            for r in residences:
                text = r["address"] or ""
                if r["city"]:
                    text += ", %s" % r["city"]
                if r["date"]:
                    text += " (%s)" % r["date"]
                if text.strip(", "):
                    addrs.append(text.strip(", "))
            if addrs:
                sections.append("Residències: %s" % "; ".join(addrs))

        # Notes (first 2, truncated)
        notes = get_notes(self.conn, pid)
        if notes:
            for n in notes[:2]:
                content = n["content"]
                if len(content) > 200:
                    content = content[:200] + "..."
                sections.append("Nota: %s" % content)

        # Photo count
        all_photos = get_all_photos(self.conn, pid)
        if all_photos:
            sections.append("Fotos: %d" % len(all_photos))
            for p in all_photos:
                if p["local_file"]:
                    photos_list.append({
                        "id": pid, "name": full["name"], "photo": p["local_file"]
                    })

        return {
            "answer": "\n".join(sections),
            "people_mentioned": people_ids,
            "people_with_photos": photos_list[:8],  # Limit photos shown
        }

    def handle_info(self, question):
        prefixes = [
            r"(?:informaci[oó]|info|parla.m|h[aá]blame|cu[eé]ntame|tell\s+me|dades|datos|fitxa|ficha|perfil)\s+(?:de|d\'|sobre|of)\s+",
            r"sobre\s+",
        ]
        matches = self._find_person_in_question(question, prefixes)
        if not matches:
            return None
        return self._build_info_response(matches[0])

    def handle_siblings(self, question):
        prefixes = [
            r"(?:germans?|hermanos?|siblings?)\s+(?:de|d\'|of)\s+",
        ]
        matches = self._find_person_in_question(question, prefixes)
        if not matches:
            return None

        person = matches[0]
        siblings = get_siblings(self.conn, person["id"])
        if not siblings:
            return {
                "answer": "No he trobat germans de %s." % person["name"],
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }

        sibs_text = ", ".join(_format_person(s) for s in siblings)
        return {
            "answer": "%s té %d germà/ns: %s." % (person["name"], len(siblings), sibs_text),
            "people_mentioned": [person["id"]] + [s["id"] for s in siblings],
            "people_with_photos": [_person_card(person)] + [_person_card(dict(s)) for s in siblings],
        }

    def handle_grandparents(self, question):
        prefixes = [
            r"(?:avis?|abuelos?|grandparents?|àvia|abuela|grandfather|grandmother|padrins?)\s+(?:de|d\'|of)\s+",
        ]
        matches = self._find_person_in_question(question, prefixes)
        if not matches:
            return None

        person = matches[0]
        grandparents = get_grandparents(self.conn, person["id"])
        if not grandparents:
            return {
                "answer": "No tinc informació sobre els avis de %s." % person["name"],
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }

        parts = []
        people_ids = [person["id"]]
        photos = [_person_card(person)]
        for gp in grandparents:
            p = gp["person"]
            parts.append("%s (via %s)" % (_format_person(p), gp["via"]))
            people_ids.append(p["id"])
            photos.append(_person_card(dict(p)))

        return {
            "answer": "Avis de %s: %s." % (person["name"], "; ".join(parts)),
            "people_mentioned": people_ids,
            "people_with_photos": photos,
        }

    def handle_grandchildren(self, question):
        prefixes = [
            r"(?:n[eé]ts?|nietos?|grandchild|grandchildren|nietas?)\s+(?:de|d\'|of)\s+",
        ]
        matches = self._find_person_in_question(question, prefixes)
        if not matches:
            return None

        person = matches[0]
        grandchildren = get_grandchildren(self.conn, person["id"])
        if not grandchildren:
            return {
                "answer": "No tinc informació sobre néts de %s." % person["name"],
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }

        parts = []
        people_ids = [person["id"]]
        photos = [_person_card(person)]
        for gc in grandchildren:
            p = gc["person"]
            parts.append("%s (fill/a de %s)" % (_format_person(p), gc["via"]))
            people_ids.append(p["id"])
            photos.append(_person_card(dict(p)))

        return {
            "answer": "Néts de %s (%d): %s." % (person["name"], len(grandchildren), "; ".join(parts)),
            "people_mentioned": people_ids,
            "people_with_photos": photos[:8],
        }

    def handle_residence(self, question):
        prefixes = [
            r"(?:on\s+va\s+viure|d[oó]nde\s+vivi[oó]|where.*live|resid[eè]nci|domicili|direcci[oó]|adre[çc]a|viv[ií]a)\s*(?:de|d\'|of)?\s*",
        ]
        matches = self._find_person_in_question(question, prefixes)
        if not matches:
            return None

        person = matches[0]
        residences = get_residences(self.conn, person["id"])
        if not residences:
            return {
                "answer": "No tinc informació sobre on va viure %s." % person["name"],
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }

        parts = []
        for r in residences:
            text = r["address"] or ""
            if r["address2"]:
                text += " %s" % r["address2"]
            if r["city"]:
                text += ", %s" % r["city"]
            if r["date"]:
                text += " (%s)" % r["date"]
            parts.append(text.strip(", "))

        return {
            "answer": "Residències de %s:\n%s" % (person["name"], "\n".join("- %s" % p for p in parts)),
            "people_mentioned": [person["id"]],
            "people_with_photos": [_person_card(person)],
        }

    def handle_occupation(self, question):
        prefixes = [
            r"(?:ofici|profesi[oó]|ocupaci[oó]|trabaj|feina|treball|occupation|job|dedicava|dedicaba|treballa)\s*(?:de|d\'|of)?\s*",
            r"(?:a\s+qu[eè]\s+(?:es\s+)?dedicava|a\s+qu[eé]\s+se\s+dedicaba)\s+",
        ]
        matches = self._find_person_in_question(question, prefixes)
        if not matches:
            return None

        person = matches[0]
        occupations = get_occupations(self.conn, person["id"])
        if not occupations:
            return {
                "answer": "No tinc informació sobre l'ofici de %s." % person["name"],
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }

        parts = []
        for o in occupations:
            text = o["title"]
            if o["date"]:
                text += " (%s)" % o["date"]
            if o["place"]:
                text += " a %s" % o["place"]
            parts.append(text)

        return {
            "answer": "Oficis de %s: %s." % (person["name"], "; ".join(parts)),
            "people_mentioned": [person["id"]],
            "people_with_photos": [_person_card(person)],
        }

    def handle_photos(self, question):
        prefixes = [
            r"(?:fotos?|imatge|imagen|picture|photo)\s+(?:de|d\'|of)\s+",
            r"(?:mostra|ense[ñn]a|show).*(?:fotos?|imatge|imagen)\s+(?:de|d\'|of)\s+",
        ]
        matches = self._find_person_in_question(question, prefixes)
        if not matches:
            return None

        person = matches[0]
        photos = get_all_photos(self.conn, person["id"])
        if not photos:
            return {
                "answer": "No tinc fotos de %s." % person["name"],
                "people_mentioned": [person["id"]],
                "people_with_photos": [],
            }

        photo_cards = []
        for p in photos:
            if p["local_file"]:
                card = {"id": person["id"], "name": person["name"], "photo": p["local_file"]}
                if p["title"]:
                    card["name"] = p["title"]
                photo_cards.append(card)

        return {
            "answer": "Fotos de %s (%d):" % (person["name"], len(photo_cards)),
            "people_mentioned": [person["id"]],
            "people_with_photos": photo_cards,
        }

    def handle_notes(self, question):
        prefixes = [
            r"(?:notes?|notas?|documents?|observaci|anotaci)\s+(?:de|d\'|of|sobre)\s+",
        ]
        matches = self._find_person_in_question(question, prefixes)
        if not matches:
            return None

        person = matches[0]
        notes = get_notes(self.conn, person["id"])
        if not notes:
            return {
                "answer": "No tinc notes sobre %s." % person["name"],
                "people_mentioned": [person["id"]],
                "people_with_photos": [_person_card(person)],
            }

        parts = []
        for n in notes:
            content = n["content"]
            if len(content) > 300:
                content = content[:300] + "..."
            parts.append(content)

        return {
            "answer": "Notes de %s:\n%s" % (person["name"], "\n---\n".join(parts)),
            "people_mentioned": [person["id"]],
            "people_with_photos": [_person_card(person)],
        }

    def handle_alive(self, question):
        people = get_alive_people(self.conn)
        if not people:
            return {
                "answer": "No hi ha persones marcades com a vives.",
                "people_mentioned": [],
                "people_with_photos": [],
            }

        parts = []
        photos = []
        for p in people:
            text = "%s (%s)" % (p["name"], p["birth_year"]) if p["birth_year"] else p["name"]
            if p["birth_place"]:
                text += " de %s" % p["birth_place"]
            parts.append(text)
            photos.append(_person_card(dict(p)))

        return {
            "answer": "Persones vives (%d):\n%s" % (len(parts), "\n".join("- %s" % p for p in parts)),
            "people_mentioned": [p["id"] for p in people],
            "people_with_photos": photos[:8],
        }

    def handle_born_in(self, question):
        prefixes = [
            r"(?:nascuts?\s+a|nacidos?\s+en|born\s+in|origen|natural\s+de)\s+",
        ]
        place = _extract_name(question, prefixes)
        if not place or len(place) < 2:
            return None

        people = get_born_in(self.conn, place)
        if not people:
            return {
                "answer": "No he trobat ningú nascut a '%s'." % place,
                "people_mentioned": [],
                "people_with_photos": [],
            }

        parts = []
        photos = []
        for p in people:
            text = "%s (%s)" % (p["name"], p["birth_year"]) if p["birth_year"] else p["name"]
            parts.append(text)
            photos.append(_person_card(dict(p)))

        return {
            "answer": "Persones nascudes a %s (%d):\n%s" % (place, len(parts), "\n".join("- %s" % p for p in parts)),
            "people_mentioned": [p["id"] for p in people],
            "people_with_photos": photos[:8],
        }
