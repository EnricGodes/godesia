"""Query Router de Godesia: resolución determinista priorizando precisión semántica."""

import re
import sqlite3
import unicodedata
from html import escape as _html_escape
from typing import List, Optional, Tuple

from database import (
    get_person,
    get_children,
    get_spouses,
    get_siblings,
    get_occupations,
    get_residences,
    get_notes,
    get_birthdays_this_week,
    get_alive_people,
    get_born_in,
    get_military,
    get_burial,
    get_events,
)


def _as_dict(row):
    return dict(row) if isinstance(row, sqlite3.Row) else row


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text or "") if unicodedata.category(c) != "Mn")


def _norm_cmp(text: str) -> str:
    text = _strip_accents((text or "").lower())
    text = re.sub(r"\((\d{4})\)", r" \1 ", text)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _tokenize_name(text: str) -> List[str]:
    return [t for t in _norm_cmp(text).split() if t]


def _clean_question(question: str) -> str:
    q = question.strip()
    q = re.sub(r"^(?:\d+\.\s*)+", "", q).strip()
    q = q.rstrip(" .?!;:¡¿")
    return q



def _normalize_name_fragment(text: str) -> str:
    text = text.strip().strip("¿?¡!.,;:")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(
        r"^(era|eran|qué|que|quién|quienes|quiénes|de qué|de que|tenía|tenia|quants|cuántos|cuantos)\s+",
        "",
        text,
        flags=re.I,
    )
    return text.strip()


def _person_card(person):
    person = _as_dict(person)
    if not person:
        return None
    return {
        "id": person["id"],
        "name": person["name"],
        "photo": person.get("photo_file"),
    }


def _person_brief(person):
    person = _as_dict(person)
    if not person:
        return ""
    parts = [person["name"]]
    by = person.get("birth_year")
    dy = person.get("death_year")
    if by and dy:
        parts.append(f"({by}-{dy})")
    elif by:
        parts.append(f"({by})")
    if person.get("birth_place"):
        parts.append(f"de {person['birth_place']}")
    return " ".join(parts)


def _sexed_role(person, male: str, female: str, neutral: str) -> str:
    person = _as_dict(person)
    sex = person.get("sex") if person else None
    if sex == "M":
        return male
    if sex == "F":
        return female
    return neutral


def _unique_people(rows):
    seen = set()
    out = []
    for r in rows:
        rr = _as_dict(r)
        if not rr:
            continue
        if rr["id"] in seen:
            continue
        seen.add(rr["id"])
        out.append(rr)
    return out


def _sort_people(rows):
    rows = _unique_people(rows)

    def key(p):
        by = p.get("birth_year")
        return (by is None, by or 999999, _norm_cmp(p.get("name", "")))

    return sorted(rows, key=key)


def _join_names(rows):
    return ", ".join(p["name"] for p in _sort_people(rows))


def _clean_person_id(raw):
    return str(raw or '').strip().strip('@')


def _smart_title_name(name: str) -> str:
    s = re.sub(r"\s+", " ", str(name or '').strip())
    if not s:
        return s
    lower_particles = {'de','del','dels','de la','de las','de los','y','i','la','las','los','el','da','do','dos','von','van'}
    letters=[c for c in s if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / max(1,len(letters)) > 0.7:
        s = s.lower()
    words=[]
    for part in s.split(' '):
        low=part.lower()
        if low in lower_particles:
            words.append(low)
        elif part.startswith("Mª"):
            words.append("Mª")
        else:
            words.append(part[:1].upper() + part[1:].lower() if part else part)
    return ' '.join(words)


def _person_display_name(person) -> str:
    person=_as_dict(person)
    if not person:
        return ''
    return _smart_title_name(person.get('name',''))


def _person_link(person) -> str:
    person=_as_dict(person)
    if not person:
        return ''
    pid=_clean_person_id(person.get('id',''))
    name=_html_escape(_person_display_name(person))
    return f'<a href="/dossier.html?id={pid}">{name}</a>'


class QueryRouter:
    def __init__(self, conn):
        self.conn = conn
        self._sql_trace: List[str] = []

        self.patterns: List[Tuple[str, str]] = [
            (r"(?:qu[eé]\s+persona\s+(?:tuvo|tenia)\s+m[aá]s\s+hijos|cu[aá]l\s+es\s+la\s+persona\s+con\s+m[aá]s\s+hijos\s+registrados)", "handle_max_children_person"),
            (r"(?:qui[eé]n\s+(?:vivio|vivi[oó]|fue)\s+m[aá]s\s+a[nñ]os|qui[eé]n\s+es\s+la\s+persona\s+m[aá]s\s+longeva\s+del\s+[aá]rbol|cu[aá]l\s+es\s+la\s+persona\s+m[aá]s\s+longeva\s+del\s+[aá]rbol)", "handle_max_longevity_person"),
            (r"(?:cu[aá]l\s+es\s+la\s+media\s+de\s+hijos|cu[aá]l\s+es\s+la\s+media\s+de\s+hijos\?)", "handle_average_children"),
            (r"(?:hay\s+m[aá]s\s+hombres\s+o\s+mujeres|hay\s+mas\s+hombres\s+o\s+mujeres)", "handle_sex_balance"),
            (r"(?:qui[eé]n\s+es\s+la\s+persona\s+m[aá]s\s+joven|cual\s+es\s+la\s+persona\s+m[aá]s\s+joven|qui[eé]n\s+es\s+la\s+persona\s+mas\s+joven)", "handle_youngest_person"),
            (r"(?:en\s+qu[eé]\s+puesto\s+del\s+ranking\s+de\s+descendencia\s+se\s+sit[uú]a)", "handle_descendance_rank"),
            (r"(?:cu[aá]ntos?\s+hijos\s+tuvo\s+.+\s+en\s+comparaci[oó]n\s+con\s+la\s+media\s+del\s+[aá]rbol)", "handle_children_vs_average"),
            (r"(?:cu[aá]ntos?\s+hermanos\s+ten[ií]a\s+.+\s+y\s+c[oó]mo\s+se\s+compara\s+con\s+el\s+resto\s+de\s+su\s+generaci[oó]n)", "handle_siblings_vs_generation"),
            (r"(?:qu[eé]\s+edad\s+vivi[oó]\s+.+\s+y\s+est[aá]\s+entre\s+las\s+longevidades\s+m[aá]s\s+altas\s+del\s+[aá]rbol)", "handle_longevity_rank"),
            (r"(?:qu[eé]\s+edad\s+ten[ií]a\s+.+\s+cuando\s+naci[oó]\s+su\s+primer\s+hijo\s+y\s+est[aá]\s+por\s+encima\s+o\s+por\s+debajo\s+de\s+la\s+media)", "handle_age_first_child_vs_average"),
            (r"(?:qu[eé]\s+pareja\s+tuvo\s+exactamente\s+\d+\s+hijos\s+y\s+en\s+qu[eé]\s+posici[oó]n\s+queda\s+por\s+tama[nñ]o\s+familiar)", "handle_couple_exact_children_rank"),
            (r"(?:cu[aá]ntas\s+personas\s+nacieron\s+en\s+.+\s+y\s+qu[eé]\s+peso\s+tiene\s+ese\s+lugar\s+dentro\s+del\s+[aá]rbol)", "handle_birth_place_share"),
            (r"(?:cu[aá]ntas\s+personas\s+murieron\s+en\s+.+\s+y\s+qu[eé]\s+relevancia\s+tiene\s+ese\s+lugar\s+en\s+las\s+defunciones\s+registradas)", "handle_death_place_share"),
            (r"(?:cu[aá]ntos\s+nacimientos\s+hay\s+en\s+la\s+d[eé]cada\s+de\s+\d{4})", "handle_births_by_decade"),
            (r"(?:cu[aá]ntos\s+fallecimientos\s+hay\s+en\s+la\s+d[eé]cada\s+de\s+\d{4})", "handle_deaths_by_decade"),
            (r"(?:qu[eé]\s+porcentaje\s+aproximado\s+del\s+[aá]rbol\s+corresponde\s+a\s+personas\s+con\s+primer\s+apellido)", "handle_first_surname_percentage"),
            (r"(?:cu[aá]ntas\s+personas\s+tienen\s+fecha\s+de\s+nacimiento\s+conocida\s+frente\s+a\s+las\s+que\s+no\s+la\s+tienen)", "handle_known_birth_date_stats"),
            (r"(?:cu[aá]l\s+fue\s+antes:\s*el\s+nacimiento\s+de\s+.+\s+o\s+el\s+de\s+.+)", "handle_compare_births"),
            (r"(?:qu[eé]\s+rama\s+tuvo\s+m[aá]s\s+hijos:\s*la\s+formada\s+por\s+.+\s+y\s+.+\s+o\s+la\s+siguiente\s+pareja\s+en\s+el\s+ranking)", "handle_branch_vs_next_couple"),
            (r"(?:qu[eé]\s+lugar\s+de\s+nacimiento\s+tiene\s+m[aá]s\s+variantes\s+de\s+escritura)", "handle_birth_place_variants"),
            (r"(?:qu[eé]\s+matrimonio\s+tuvo\s+m[aá]s\s+descendencia\s+documentada)", "handle_marriage_max_descendants"),
            (r"(?:cu[aá]ntos?\s+a[nñ]os\s+ten[ií]a\s+.+\s+cuando\s+naci[oó]\s+su\s+primer\s+hij[oa])", "handle_age_at_first_child"),
            (r"(?:(?:a\s+)?qu[eé]\s+edad\s+(?:se\s+cas[oó]|ten[ií]a.*cuando\s+se\s+cas[oó]|gastaba.*al\s+casarse|ten[ií]a.*al\s+casarse)|qu[eé]\s+edad\s+ten[ií]a.*al\s+casarse)", "handle_age_at_marriage"),
            (r"(?:con\s+qui[eé]n\s+se\s+cas[oó]\s+la\s+persona\s+nacida\s+en\s+.+\s+llamada\s+.+)", "handle_spouse_disambiguated_by_birth_place"),
            (r"(?:cu[aá]ntos?\s+hijos\s+(?:tuvo\s+)?(?:el\s+matrimonio\s+de\s+)?.+\s+y\s+.+|cu[aá]ntos?\s+hijos\s+tuvieron\s+.+\s+y\s+.+)", "handle_couple_children_count"),
            (r"(?:qui[eé]nes\s+eran\s+los\s+abuelos\s+de\s+.+\s+y\s+en\s+qu[eé]\s+a[nñ]os\s+nacieron)", "handle_grandparents_with_years"),
            (r"(?:c[oó]mo\s+se\s+llamaban\s+los\s+(?:cuatro\s+)?abuelos\s+de|qui[eé]nes\s+(?:eran|fueron)\s+los\s+(?:cuatro\s+)?abuelos\s+de|qu[eé]\s+abuelos?\s+ten[ií]a\s+.+|me\s+sacas\s+los\s+nombres\s+de\s+los\s+abuelos\s+de|abuelos\s+ten[ií]a\s+por\s+las\s+dos\s+ramas\s+.+|abuelos?\s+(?:paternos?\s+y\s+maternos?|maternos?\s+y\s+paternos?)\s+de)", "handle_grandparents_names"),
            (r"(?:en\s+qu[eé]\s+posici[oó]n\s+(?:entre\s+)?sus\s+hermanos\s+(?:naci[oó]|naci[oó]\s+)|qu[eé]\s+lugar\s+(?:ocupaba|ocupa)\s+(?:dentro|entre)\s+sus\s+hermanos)", "handle_birth_order_among_siblings"),
            (r"(?:qui[eé]nes\s+eran\s+los\s+padres\s+de\s+.+\s+y\s+d[oó]nde\s+se\s+casaron)", "handle_parents_and_marriage_place"),
            (r"(?:qu[eé]\s+personas\s+nacieron\s+en\s+.+\s+y\s+murieron\s+en\s+.+)", "handle_birth_and_death_place_people"),
            (r"(?:qu[eé]\s+parentesco\s+ten[ií]a\s+.+\s+con\s+.+\s+y\s+cu[aá]l\s+de\s+los\s+dos\s+era\s+mayor)", "handle_relationship_and_older"),
            (r"(?:con\s+qu[eé]\s+(?:mujer|persona|hombre)\s+(?:form[oó]|enlaz[oó])\s+familia\s+.+|con\s+qu[eé]\s+(?:mujer|persona|hombre)\s+casó\s+.+)", "handle_spouse_with_person_type"),
            (r"(?:cu[aá]ndo\s+se\s+cas[oó]\s+.+|en\s+qu[eé]\s+(?:fecha|a[nñ]o|d[ií]a)\s+se\s+cas[oó]\s+.+|d[oó]nde\s+se\s+cas[oó]\s+.+|en\s+qu[eé]\s+(?:lugar|iglesia|sitio)\s+se\s+cas[oó]\s+.+)", "handle_marriage_date_place"),
            (r"(?:con\s+qui[eé]n\s+se\s+cas[oó]\s+.+\s+y\s+en\s+qu[eé]\s+fecha\s+fue\s+la\s+boda)", "handle_spouse_and_wedding_date"),
            (r"(?:qui[eé]n\s+era\s+el\s+padre\s+de\s+la\s+madre\s+de\s+.+)", "handle_father_of_mother"),
            (r"(?:qu[eé]\s+hijos\s+de\s+.+\s+nacieron\s+en\s+.+)", "handle_children_born_in_place"),
            (r"(?:qu[eé]\s+hijos\s+tuvo\s+la\s+pareja\s+que\s+se\s+cas[oó]\s+en\s+.+\s+formada\s+por\s+.+\s+y\s+.+)", "handle_children_of_couple_married_at_place"),
            (r"(?:qui[eé]n\s+era\s+mayor\s+cuando\s+se\s+casaron:\s*.+\s+o\s+.+)", "handle_who_older_when_married"),
            (r"(?:d[oó]nde\s+naci[oó]\s+.+\s+y\s+qu[eé]\s+ocupaci[oó]n\s+consta\s+en\s+su\s+ficha)", "handle_birth_place_and_occupation"),
            (r"(?:cu[aá]ntos?\s+hijos\s+sobrevivieron\s+a\s+.+)", "handle_surviving_children_count"),
            (r"(?:qui[eé]n\s+naci[oó]\s+en\s+(?:el\s+)?a[nñ]o|who\s+was\s+born\s+in\s+the\s+year|qui[eé]n\s+naci[oó]\s+en\s+\d{4})", "handle_birth_year_search"),
            (r"(?:qu[eé]\s+personas\s+murieron\s+en|which\s+people\s+died\s+in)", "handle_death_place_people"),
            (r"(?:qu[eé]\s+parejas\s+se\s+casaron\s+en|which\s+couples\s+married\s+in)", "handle_marriages_place"),
            (r"(?:nombre\s+de\s+pila\s+que\s+empieza\s+por|given\s+name\s+starts\s+with)", "handle_given_name_initial"),
            (r"(?:primer\s+apellido|first\s+surname)", "handle_first_surname"),
            (r"(?:nacieron\s+y\s+murieron\s+en|were\s+born\s+and\s+died\s+in)", "handle_birth_and_death_place_people"),
            (r"(?:ocupaci[oó]n\s+o\s+actividad\s+figura\s+registrada\s+para|occupation\s+for)", "handle_occupation_field"),
            (r"(?:residencia\s+o\s+direcci[oó]n\s+aparece\s+documentado|where\s+is\s+documented\s+the\s+residence)", "handle_residence_field"),
            (r"(?:notas?\s+(?:biogr[aá]ficas?\s+)?hay\s+(?:sobre|de|para|asociadas\s+a)\s+.+|observaciones?\s+(?:biogr[aá]ficas?\s+)?(?:de|sobre|aparecen\s+(?:en|para))\s+.+|(?:qu[eé]\s+)?(?:anotaciones?|comentarios?|apuntes?|detalles?\s+biogr[aá]ficos?|informaci[oó]n\s+adicional|texto)\s+(?:hay\s+)?(?:sobre|de|para|acompa[nñ]a)\s+.+|biographical\s+notes\s+for)", "handle_notes_field"),
            (r"(?:qui[eé]n\s+naci[oó]\s+el\s+\d{1,2}/\d{1,2}/\d{4}|who\s+was\s+born\s+on\s+\d{1,2}/\d{1,2}/\d{4})", "handle_birth_date_search"),
            (r"(?:qui[eé]n\s+(?:falleci[oó]|muri[oó])\s+el\s+\d{1,2}/\d{1,2}/\d{4}|who\s+died\s+on\s+\d{1,2}/\d{1,2}/\d{4})", "handle_death_date_search"),
            (r"(?:qui[eé]n\s+naci[oó]\s+en\s+.+\s+en\s+\d{4}|who\s+was\s+born\s+in\s+.+\s+in\s+\d{4})", "handle_birth_place_year_search"),
            (r"(?:qui[eé]n\s+muri[oó]\s+en\s+.+\s+en\s+\d{4}|who\s+died\s+in\s+.+\s+in\s+\d{4})", "handle_death_place_year_search"),
            (r"(?:nombre\s+compuesto\s+como|compound\s+name\s+like)", "handle_compound_given_name"),
            (r"(?:qu[eé]\s+registro\s+corresponde\s+a|which\s+record\s+matches)", "handle_record_lookup"),
            (r"(?:qu[eé]\s+personas\s+nacieron\s+en|which\s+people\s+were\s+born\s+in)", "handle_birth_place_people"),
            (r"(?:de\s+qu[eé]\s+(?:matrimonio(?:\s+o\s+pareja)?|pareja)\s+naci[oó])", "handle_birth_union"),
            (r"(?:padres\s+y\s+los\s+hijos|pares\s+i\s+els\s+fills)", "handle_parents_and_children"),
            (r"(?:cu[aá]ntos?\s+herman|quants?\s+germans?|qu[eé]\s+n[uú]mero\s+de\s+hermanos|qu[eé]\s+cantidad\s+de\s+hermanos|eran\s+muchos\s+los\s+hermanos|cu[aá]ntos\s+eran\s+en\s+total\s+los\s+hermanos|cu[aá]ntos?\s+hermanos\s+se\s+le\s+conocen)", "handle_siblings_count"),
            (r"(?:abuelo\s+paterno|avi\s+patern|abuelo\s+por\s+v[ií]a\s+paterna|abuelo\s+por\s+parte\s+de\s+padre|abuelo\s+de\s+l[ií]nea\s+paterna|qu[eé]\s+abuelo\s+ten[ií]a\s+por\s+v[ií]a\s+paterna|qu[eé]\s+abuelo\s+ten[ií]a\s+por\s+parte\s+de\s+padre)", "handle_paternal_grandfather"),
            (r"(?:abuela\s+materna|[àa]via\s+matern|abuela\s+por\s+v[ií]a\s+materna|abuela\s+por\s+parte\s+de\s+madre|abuela\s+de\s+l[ií]nea\s+materna|qu[eé]\s+abuela\s+ten[ií]a\s+por\s+v[ií]a\s+materna|qu[eé]\s+abuela\s+ten[ií]a\s+por\s+parte\s+de\s+madre)", "handle_maternal_grandmother"),
            (r"(?:t[ií]os?\s+(?:y\s+)?t[ií]as?\s+de|uncles\s+and\s+aunts\s+of)", "handle_uncles_and_aunts"),
            (r"(?:t[ií]os?|oncles?)\b", "handle_uncles"),
            (r"(?:n[oó]mbrame\s+los\s+primos\s+de\s+.+)", "handle_first_cousins"),
            (r"(?:primos\s+hermanos|cosins?\s+germans?|first\s+cousins)", "handle_first_cousins"),
            (r"(?:cas[oó]\s+o\s+emparej[oó]|casar\s+o\s+emparellar)", "handle_spouse_or_partner"),
            (r"(?:(?:con\s+)?qu[eé]\s+(?:persona|hombre|mujer)\s+enlaz[oó]\s+.+\s+(?:por\s+)?matrimonio|with\s+whom\s+did\s+.+\s+marry)", "handle_spouse"),
            (r"(?:cu[aá]ntos?\s+descendientes?\s+directos?\s+(?:tuvo|dej[oó])\s+.+|how\s+many\s+direct\s+descendants)", "handle_direct_descendants"),
            (r"(?:qu[eé]\s+hijos\s+(?:documentados?\s+)?tuvo\s+.+|what\s+children\s+did\s+.+\s+have)", "handle_children"),
            (r"(?:cu[aá]ntos?\s+hijos\s+(?:tuvo|tiene|ten[ií]a)|quants?\s+fills\s+va\s+tenir)", "handle_children_count"),
            (r"(?:qu[eé]?\s+hermanos?\s+(?:ten[ií]a|tuvo)\s+.+|hermanos?\s+de\s+.+|con\s+qu[eé]\s+hermanos?\s+convivi[oó]|qu[eé]\s+(?:grupo|familia)\s+de\s+hermanos\s+formaba|qu[eé]\s+hermanos\s+y\s+hermanas\s+tuvo|quién\s+iba\s+con\s+.+\s+entre\s+hermanos)", "handle_siblings"),
            (r"(?:eran\s+primos|were\s+.*cousins)", "handle_are_cousins"),
            (r"(?:era\s+.+\s+abuelo\s+o\s+abuela\s+de|was\s+.+\s+grandparent\s+of)", "handle_is_grandparent_of"),
            (r"(?:(?:ten[ií]a|tiene)\s+descendencia|had\s+descendants)", "handle_has_descendants"),
            (r"(?:suegra\s+o\s+el\s+suegro|suegra\s+o\s+suegro|father-in-law|mother-in-law)", "handle_parents_in_law"),
            (r"(?:qu[eé]\s+relaci[oó]n\s+ten[ií]a|qu[eé]\s+parentesco\s+(?:hab[ií]a|hay)|what\s+relationship)", "handle_relationship"),
            (r"(?:padres\s+de|pares\s+de|parents\s+of)", "handle_parents"),
            (r"(?:(?:qui[eé]n|quiénes)\s+era(?:n)?\s+(?:el\s+)?padre\s+de\s+.+|padre\s+de|pare\s+de|father\s+of)", "handle_father"),
            (r"(?:hermanos\s+de|germans\s+de|siblings\s+of)", "handle_siblings"),
            (r"(?:c[oó]nyuge\s+de|spouse\s+of|compa[ñn]era\s+de\s+vida\s+de|pareja\s+de)", "handle_spouse"),
            (r"(?:hijos\s+de|fills\s+de|children\s+of)", "handle_children"),
            (r"(?:primer\s+hij[oa]\s+de\s+.+|first\s+child\s+of)", "handle_first_child"),
            (r"(?:[úu]ltimo\s+hij[oa]\s+que\s+tuvo|last\s+child\s+of)", "handle_last_child"),
            (r"(?:hij[oa]\s+mayor\s+de\s+.+|oldest\s+son\s+of|oldest\s+daughter\s+of)", "handle_oldest_son"),
            (r"(?:hija\s+mayor\s+de\s+.+|oldest\s+daughter\s+of)", "handle_oldest_daughter"),
            (r"(?:ascendientes\s+inmediatos\s+de|immediate\s+ascendants\s+of)", "handle_immediate_ascendants"),
            (r"(?:busco\s+a\s+las\s+personas\s+que\s+nacieron\s+en\s+.+\s+y\s+tamb[ié]n\s+murieron\s+all[ií])", "handle_birth_and_death_same_place_natural"),
            (r"(?:qu[ií]ero\s+ver\s+si\s+.+\s+ten[ií]a\s+consuegros\s+documentados|consuegros\s+de\s+.+)", "handle_consuegros"),
            (r"(?:primos\s+segundos\s+de\s+.+)", "handle_second_cousins"),
            (r"(?:n[oó]mbrame\s+(?:las\s+)?nueras\s+de\s+.+|nueras?\s+de\s+.+|tuvo\s+.+\s+alguna\s+nuera)", "handle_daughters_in_law"),
            (r"(?:dime\s+c[oó]mo\s+se\s+llamaba\s+el\s+yerno\s+de\s+.+|yernos?\s+de\s+.+|hab[ií]a\s+alg[uú]n\s+yerno\s+en\s+la\s+familia\s+de\s+.+)", "handle_sons_in_law"),
            (r"(?:qu[eé]\s+relaci[oó]n\s+ten[ií]a\s+.+\s+con\s+los\s+padres\s+de\s+.+)", "handle_relationship_with_parents_of"),
            (r"(?:qui[eé]n\s+fue\s+la\s+cu[nñ]ada\s+de\s+.+)", "handle_sisters_in_law"),
            (r"(?:dime\s+si\s+.+\s+ten[ií]a\s+cu[nñ]ados\s+y\s+c[oó]mo\s+se\s+llamaban)", "handle_brothers_in_law"),
            (r"(?:t[ií]o\s+bisabuelo\s+conocido)", "handle_great_great_uncle"),
            (r"(?:t[ií]os\s+abuelos\s+de\s+.+)", "handle_great_uncles"),
            (r"(?:sobrinos\s+nietos\s+de\s+.+)", "handle_grandnephews"),
            (r"(?:prima\s+segunda\s+de\s+alguien\s+de\s+la\s+rama\s+Hurtado)", "handle_second_cousin_of_hurtado_branch"),
            (r"(?:bisnieto\s+mayor\s+de\s+.+)", "handle_oldest_great_grandson"),
            (r"(?:hay\s+tataranietos\s+documentados\s+de\s+.+)", "handle_has_great_great_grandchildren"),
            (r"(?:tatarabuelos\s+de\s+.+)", "handle_great_great_grandparents"),
            (r"(?:bisabuela\s+materna\s+de\s+.+)", "handle_maternal_great_grandmother"),
            (r"(?:bisabuelos\s+de\s+.+)", "handle_great_grandparents"),
            (r"(?:(?:qui[eé]n|quiénes)\s+era(?:n)?\s+(?:la\s+)?madre\s+de\s+.+|dime\s+c[oó]mo\s+se\s+llamaba\s+la\s+madre\s+de\s+.+)", "handle_mother"),
            (r"(?:qui[eé]n\s+fue\s+el\s+hijo\s+mayor\s+de\s+.+|dime\s+cu[aá]l\s+fue\s+la\s+primera\s+hija\s+de\s+.+)", "handle_child_extremes"),
            (r"(?:cu[aá]ntas\s+personas\s+(?:del\s+[aá]rbol\s+)?se\s+llaman\s+.+)", "handle_given_name_count"),
            (r"(?:dos\s+apellidos\s+iguales)", "handle_same_surname_twice"),
            (r"(?:qu[eé]\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+\s+nacieron\s+en\s+.+)", "handle_surname_born_in_place"),
            (r"(?:acab[oó]\s+cas[aá]ndose|con\s+qui[eé]n\s+acab[oó]\s+cas[aá]ndose)", "handle_last_spouse"),
            (r"(?:misma\s+ciudad\s+en\s+la\s+que\s+naci[oó])", "handle_same_birth_death_city"),
            (r"(?:tengan\s+.+\s+como\s+primer\s+apellido)", "handle_first_surname_natural"),
            (r"(?:(?:a\s+)?qu[eé]\s+oficio\s+(?:ten[ií]a|se\s+dedic[oó])\s+.+|en\s+qu[eé]\s+trabaja(?:ba)?\s+.+|(?:qu[eé]\s+)?empleo\s+consta\s+de\s+.+|c[oó]mo\s+se\s+ganaba\s+la\s+vida\s+.+)", "handle_occupation_natural"),
            (r"(?:d[oó]nde\s+viv[ií]a\s+.+\s+al\s+final\s+de\s+su\s+vida)", "handle_last_residence"),
            (r"(?:cu[aá]ntos\s+hijos\s+lleg[oó]\s+a\s+tener\s+.+)", "handle_children_total_natural"),
            (r"(?:dime\s+qu[eé]\s+personas\s+nacieron\s+en\s+.+\s+y\s+luego\s+murieron\s+fuera\s+de\s+.+)", "handle_born_in_and_died_outside"),
            (r"(?:qui[eé]n\s+(?:era|es)\s+mayor,?\s+.+\s+o\s+.+)", "handle_compare_older"),
            (r"(?:me\s+puedes\s+decir\s+c[oó]mo\s+se\s+llamaban\s+los\s+suegros\s+de\s+.+)", "handle_parents_in_law_natural"),
            (r"(?:qu[eé]\s+parejas\s+del\s+[aá]rbol\s+tuvieron\s+much[ií]simos\s+hijos|diez\s+o\s+m[aá]s)", "handle_large_families"),
            (r"(?:mismo\s+a[nñ]o\s+que\s+.+)", "handle_same_birth_year_as_person"),
            (r"(?:hay\s+(?:alguna\s+)?(?:tataranietos?|bisnietos?)\s+(?:documentados?\s+)?de\s+.+)", "handle_has_great_great_grandchildren"),
            (r"(?:hay\s+alguna\s+.+\s+con\s+descendencia\s+documentada)", "handle_has_descendance_named"),
            (r"(?:personas\s+que\s+no\s+tienen\s+fecha\s+de\s+nacimiento\s+conocida)", "handle_unknown_birth_date_people"),
            (r"(?:nombres\s+compuestos\s+m[aá]s\s+repetidos)", "handle_repeated_compound_names"),
            # Military
            (r"(?:(?:qu[eé]\s+)?actividad\s+militar\s+tuvo\s+.+|servicio\s+militar\s+de\s+.+|datos?\s+militar(?:es)?\s+de\s+.+)", "handle_military"),
            (r"(?:qui[eé]nes\s+participaron\s+en\s+(?:la\s+)?guerra|qui[eé]nes\s+fueron\s+a\s+la\s+guerra|combatientes\s+del\s+[aá]rbol)", "handle_military_all"),
            # Burial
            (r"(?:d[oó]nde\s+(?:fue\s+enterrad[oa]|est[aá]\s+(?:enterrad[oa]|sepultad[oa]))\s+.+|sepultura\s+de\s+.+|tumba\s+de\s+.+)", "handle_burial"),
            (r"(?:qui[eé]nes\s+(?:fueron\s+enterrados|est[aá]n\s+enterrados|est[aá]n\s+sepultados)\s+en\s+.+|enterramientos\s+en\s+.+)", "handle_burial_place"),
            # Baptism
            (r"(?:cu[aá]ndo\s+(?:fue\s+)?bautizad[oa]\s+.+|(?:fecha|d[ií]a)\s+(?:del?\s+)?bautismo\s+de\s+.+|bautismo\s+de\s+.+)", "handle_baptism"),
            (r"(?:d[oó]nde\s+(?:se\s+)?bautiz[oó]\s+.+|(?:lugar|iglesia)\s+(?:del?\s+)?bautismo\s+de\s+.+)", "handle_baptism_place"),
            (r"(?:qui[eé]nes\s+fueron\s+los\s+padrinos\s+de\s+.+|padrinos\s+de\s+.+)", "handle_godparents"),
            # Events
            (r"(?:(?:qu[eé]\s+)?eventos?\s+(?:hay\s+)?registrados?\s+(?:para|de)\s+.+|eventos?\s+de\s+.+)", "handle_events"),
            (r"(?:(?:hay\s+)?datos?\s+de\s+(?:estudios|educaci[oó]n)\s+de\s+.+|estudios\s+de\s+.+|educaci[oó]n\s+de\s+.+)", "handle_education"),
            # Bare forms for common questions
            (r"^(?:madre|father)\s+.+$", "handle_mother"),
            (r"^(?:padre|father)\s+.+$", "handle_father"),
            (r"^(?:hijos?|fills?)\s+.+$", "handle_children"),
            (r"^(?:hermanos?|germans?)\s+.+$", "handle_siblings"),
            (r"^(?:esposa?|spouse)\s+.+$", "handle_spouse"),
            (r"(?:con\s+qui[eé]n\s+(?:se\s+cas[oó]|form[oó]\s+pareja)|qui[eé]n\s+se\s+cas[oó]\s+con)\s+", "handle_spouse_or_partner"),
            (r"^(?:tíos?|oncles?)\s+.+$", "handle_uncles"),
            (r"^(?:abuelos?|grands?par[eè]nts?)\s+.+$", "handle_grandparents_names"),
            (r"^(?:bisabuelos?|great\s+grand[ps]ar[eè]nts?)\s+.+$", "handle_great_grandparents"),
            (r"^(?:primos?\s+(?:hermanos?)?|cosins?\s+germans?|first\s+cousins?)\s+.+$", "handle_first_cousins"),
            (r"^(?:primos?\s+segundos?|second\s+cousins?)\s+.+$", "handle_second_cousins"),
            (r"^(?:suegros?|in.laws?)\s+.+$", "handle_parents_in_law"),
            (r"^(?:nueras?|daughter[s-]in.law)\s+.+$", "handle_daughters_in_law"),
            (r"^(?:yernos?|son[s-]in.law)\s+.+$", "handle_sons_in_law"),
            (r"^(?:cu[nñ]adas?|sister[s-]in.law)\s+.+$", "handle_sisters_in_law"),
            (r"^(?:cu[nñ]ados?|brother[s-]in.law)\s+.+$", "handle_brothers_in_law"),
            (r"^(?:donde|d[oó]nde)\s+naci[oó]\s+.+$|(?:cu[aá]l\s+(?:fue|es)\s+(?:el\s+lugar|la\s+ciudad|la\s+localidad|el\s+pueblo)\s+(?:de\s+)?(?:nacimiento|origen|natal)|qu[eé]\s+lugar.*nacimiento)\s+.+", "handle_birth_place_of_person"),
            (r"(?:d[oó]nde\s+(?:falleci[oó]|muri[oó])|en\s+qu[eé]\s+(?:lugar|sitio|ciudad|pueblo)\s+(?:falleci[oó]|muri[oó])|cu[aá]l\s+fue\s+(?:el\s+lugar|la\s+ciudad)\s+de\s+(?:fallecimiento|defunci[oó]n)|qu[eé]\s+lugar\s+de\s+(?:fallecimiento|defunci[oó]n)\s+(?:tiene|consta)|lugar\s+de\s+defunci[oó]n\s+de)\s+.+", "handle_death_place_of_person"),
            (r"(?:(?:cuando|cu[aá]ndo|en\s+qu[eé]\s+momento)\s+(?:naci[oó]|fue\s+nacid[oa]|fue\s+born)|en\s+qu[eé]\s+fecha.*naci|cu[aá]l\s+(?:fue|es)\s+(?:la\s+)?fecha\s+(?:exacta\s+)?(?:de\s+)?nacimiento)\s+.+", "handle_birth_date_of_person"),
            (r"(?:cu[aá]ndo\s+(?:falleci[oó]|muri[oó])|en\s+qu[eé]\s+(?:fecha|a[nñ]o|d[ií]a)\s+(?:falleci[oó]|muri[oó])|cu[aá]l\s+fue\s+la\s+fecha\s+de\s+(?:fallecimiento|defunci[oó]n)|qu[eé]\s+fecha\s+de\s+defunci[oó]n\s+(?:tiene|consta)|hay\s+fecha\s+de\s+(?:fallecimiento|defunci[oó]n)\s+de|cu[aá]ndo\s+se\s+produjo\s+la\s+defunci[oó]n\s+de|fue\s+(?:enterrad[oa]|sepultad[oa]))\s+.+", "handle_death_date_of_person"),
            (r"^(?:ocupaci[oó]n|qu[eé]\s+oficio|trabajo|cu[aá]l\s+(?:era|fue)\s+(?:el\s+medio\s+de\s+vida|el\s+oficio))\s+(?:de\s+)?.+$", "handle_occupation_natural"),
            (r"(?:residencia|d[óo]nde\s+(?:viv[ií]a|vivia|vive|ha\s+vivido)|cu[aá]l\s+(?:fue|era|es)\s+(?:el\s+domicilio|la\s+direcci[oó]n|el\s+primer\s+domicilio))\s+", "handle_last_residence"),
            (r"^(?:notas?|apuntes?)\s+(?:biogr[aá]ficas?\s+)?de\s+.+$", "handle_notes_field"),
            (r"^(?:qu[eé]\s+)?descendencia\s+.+$", "handle_has_descendants"),
        ]

    def route(self, question):
        question = _clean_question(question)
        self._sql_trace = []
        try:
            self.conn.set_trace_callback(self._sql_trace.append)
        except Exception:
            pass
        try:
            result = self._route_internal(question)
        finally:
            try:
                self.conn.set_trace_callback(None)
            except Exception:
                pass

        if not result:
            result = {
                "answer": "No he sabido responder esta pregunta con las reglas actuales.",
                "people_mentioned": [],
                "people_with_photos": [],
                "source": "db",
                "_handler": "no_match",
            }

        result["answer"] = self._postprocess_answer(result.get("answer", ""), result.get("people_mentioned", []))
        result["source"] = "db"
        result.pop("_handler", None)
        return result

    def _route_internal(self, question):
        q = question.lower().strip()
        for pattern, handler_name in self.patterns:
            try:
                if re.search(pattern, q, re.I):
                    handler = getattr(self, handler_name)
                    result = handler(question)
                    if result:
                        result['_handler'] = handler_name
                        return result
            except Exception:
                continue
        try:
            fallback = self._try_name_fallback(question)
            if fallback:
                fallback['_handler'] = 'name_fallback'
                return fallback
        except Exception:
            pass
        return None

    def _postprocess_answer(self, answer: str, people_ids: List[str]) -> str:
        if not answer:
            return answer
        people = []
        seen = set()
        for pid in people_ids or []:
            if not pid or pid in seen:
                continue
            seen.add(pid)
            p = _as_dict(get_person(self.conn, pid))
            if p:
                people.append(p)
        for p in sorted(people, key=lambda x: len(x.get("name", "")), reverse=True):
            raw = p.get("name", "")
            pretty = _person_display_name(p)
            link = _person_link(p)
            if raw:
                answer = re.sub(rf"(?<![\w>]){re.escape(raw)}(?![^<]*</a>)(?![\w<])", link, answer)
            if pretty and pretty != raw:
                answer = re.sub(rf"(?<![\w>]){re.escape(pretty)}(?![^<]*</a>)(?![\w<])", link, answer)
        return answer

    def _build_debug_block(self, handler_name: str) -> str:
        lines = ["--- DEBUG ---", f"handler: {handler_name}"]
        if self._sql_trace:
            lines.append("sql:")
            for i, sql in enumerate(self._sql_trace, 1):
                lines.append(f"{i}. {sql}")
        else:
            lines.append("sql: (sin consultas SQLite capturadas)")
        return "\n".join(lines)

    def _extract_year_hint(self, text: str) -> Tuple[str, Optional[int]]:
        m = re.search(r"\((\d{4})\)", text)
        if not m:
            return text, None
        year = int(m.group(1))
        cleaned = re.sub(r"\(\d{4}\)", "", text).strip()
        return cleaned, year

    def _search_people(self, name_fragment: str, year_hint: Optional[int] = None, limit: int = 25):
        name_fragment = _normalize_name_fragment(name_fragment)
        name_fragment = re.sub(r"\((\d{4})\)", "", name_fragment).strip()
        if not name_fragment:
            return []
        select_cols = (
            "SELECT id, name, given_name, surname, birth_year, death_year, birth_place, death_place, photo_file, "
            "is_alive, father_id, mother_id, father_name, mother_name, sex, "
            "baptism_date, baptism_place, godparents, nickname "
        )
        # IMPORTANT: Fetch ALL people and do Python-level filtering with accent-insensitive matching
        # SQL LIKE with COLLATE NOCASE doesn't handle accents, so we need Python-level comparison
        rows = self.conn.execute(
            select_cols + "FROM people ORDER BY name",
        ).fetchall()

        # Use _norm_cmp for accent-insensitive comparison (it already strips accents)
        query_norm = _norm_cmp(name_fragment)
        query_tokens = set(_tokenize_name(name_fragment))
        query_token_list = _tokenize_name(name_fragment)

        def score(row):
            rr = _as_dict(row)
            name_norm = _norm_cmp(rr["name"])
            tokens = set(_tokenize_name(rr["name"]))
            s = 0
            if name_norm == query_norm:
                s += 1000
            # Nickname exact match
            nickname = rr.get("nickname") or ""
            if nickname and _norm_cmp(nickname) == query_norm:
                s += 900
            if query_tokens and query_tokens.issubset(tokens):
                s += 200
            s += 15 * len(query_tokens.intersection(tokens))
            s -= 6 * max(0, len(tokens) - len(query_tokens))
            if year_hint is not None and rr.get("birth_year") == year_hint:
                s += 500
            if query_token_list and query_token_list[-1] in tokens:
                s += 20
            # Nickname token match
            if nickname:
                nick_tokens = set(_tokenize_name(nickname))
                if query_tokens and query_tokens.intersection(nick_tokens):
                    s += 150
            return s

        rows = sorted(rows, key=lambda r: (-score(r), _norm_cmp(_as_dict(r)["name"])))
        if year_hint is not None:
            exact = [r for r in rows if _as_dict(r).get("birth_year") == year_hint]
            if exact:
                rows = exact + [r for r in rows if _as_dict(r).get("birth_year") != year_hint]
        return rows[:limit]

    def _resolve_person(self, raw_name: str):
        raw_name = _normalize_name_fragment(raw_name)
        raw_name, year_hint = self._extract_year_hint(raw_name)
        matches = self._search_people(raw_name, year_hint=year_hint)
        if not matches:
            return None, []
        return _as_dict(matches[0]), [_as_dict(m) for m in matches]

    def _extract_two_names(self, question: str) -> Optional[Tuple[str, str]]:
        q = _clean_question(question)
        patterns = [
            r"entre\s+(.+?)\s+y\s+(.+?)(?:\?|$)",
            r"(?:eran\s+primos|era[n]?\s+primos?)\s+(.+?)\s+y\s+(.+?)(?:\?|$)",
            r"(?:qu[eé]\s+parentesco\s+(?:hay|hab[ií]a|ten[ií]a))\s+(?:entre\s+)?(.+?)\s+con\s+(.+?)(?:\s+y\s+cu[aá]l|\?|$)",
            r"(?:qu[eé]\s+relaci[oó]n\s+ten[ií]a|qu[eé]\s+parentesco\s+(?:hab[ií]a|ten[ií]a))\s+(.+?)\s+con\s+(.+?)(?:\?|$)",
            r"(?:qui[eé]n\s+era\s+mayor,?)\s+(.+?)\s+o\s+(.+?)(?:\?|$)",
        ]
        for p in patterns:
            m = re.search(p, q, re.I)
            if m:
                return _normalize_name_fragment(m.group(1)), _normalize_name_fragment(m.group(2))
        return None

    def _extract_subject_name(self, question: str) -> Optional[str]:
        patterns = [
            r"padres\s+de\s+(.+?)(?:\?|$)",
            r"pares\s+de\s+(.+?)(?:\?|$)",
            r"padre\s+de\s+(.+?)(?:\?|$)",
            r"pare\s+de\s+(.+?)(?:\?|$)",
            # More specific patterns BEFORE general ones
            r"cu[aá]ntos?\s+hermanos(?:\s+y\s+hermanas)?\s+(?:ten[ií]a|tuvo)(?:\s+(?:realmente|aparentemente|exactamente|documentados?|seg[uú]n))?\s+(.+?)(?:\?|$)",
            r"con\s+qu[eé]\s+hermanos?\s+convivi[oó]\s+(.+?)(?:\?|$)",
            r"qu[eé]\s+(?:grupo|familia)\s+de\s+hermanos\s+formaba\s+(.+?)(?:\?|$)",
            r"qu[eé]\s+hermanos\s+y\s+hermanas\s+tuvo\s+(.+?)(?:\?|$)",
            # General patterns
            r"hermanos?\s+(?:ten[ií]a|tuvo)\s+(.+?)(?:\?|$)",
            r"hermanos\s+de\s+(.+?)(?:\?|$)",
            r"germans\s+de\s+(.+?)(?:\?|$)",
            r"(?:que\s+)?hijos?\s+(?:documentados?\s+)?(?:tuvo|tiene|ten[ií]a)\s+(.+?)(?:\?|$)",
            r"hijos\s+de\s+(.+?)(?:\?|$)",
            r"fills\s+de\s+(.+?)(?:\?|$)",
            r"t[ií]os\s+(?:abuelos\s+)?de\s+(.+?)(?:\s+(?:por\s+cada\s+lado|maternos|paternos)|\?|$)",
            r"oncles\s+de\s+(.+?)(?:\?|$)",
            r"primos\s+hermanos\s+de\s+(.+?)(?:\?|$)",
            r"cosins?\s+germans?\s+de\s+(.+?)(?:\?|$)",
            r"c[oó]nyuge\s+de\s+(.+?)(?:\?|$)",
            r"(?:ten[ií]a|tiene)\s+descendencia\s+(?:documentada\s+)?(.+?)(?:\?|$)",
            r"suegra\s+o\s+el\s+suegro\s+de\s+(.+?)(?:\?|$)",
            r"suegra\s+o\s+suegro\s+de\s+(.+?)(?:\?|$)",
            r"nueras?\s+de\s+(.+?)(?:\?|$)",
            r"yernos?\s+de\s+(.+?)(?:\?|$)",
            r"cu[aá]ntos?\s+hijos\s+tuvo\s+(.+?)(?:\?|$)",
            r"con\s+cu[aá]ntos?\s+hermanos\s+se\s+cr[ií]o\s+(.+?)(?:\?|$)",
            r"cu[aá]ntos?\s+hermanos?\s+le\s+salieron\s+a\s+(.+?)(?:\?|$)",
            r"qu[eé]\s+n[uú]mero\s+de\s+hermanos\s+(?:ten[ií]a|tuvo)\s+(.+?)(?:\?|$)",
            r"qu[eé]\s+cantidad\s+de\s+hermanos\s+(?:ten[ií]a|tuvo)\s+(.+?)(?:\?|$)",
            r"cu[aá]ntos?\s+eran\s+en\s+total\s+los\s+hermanos\s+de\s+(.+?)(?:\?|$)",
            r"cu[aá]ntos?\s+hermanos\s+se\s+le\s+conocen\s+a\s+(.+?)(?:\?|$)",
            r"abuelo\s+paterno\s+de\s+(.+?)(?:\?|$)",
            r"abuela\s+materna\s+de\s+(.+?)(?:\?|$)",
            r"suegros\s+de\s+(.+?)(?:\?|$)",
            r"consuegros\s+de\s+(.+?)(?:\?|$)",
            r"primos\s+segundos\s+de\s+(.+?)(?:\?|$)",
            r"t[ií]os\s+abuelos\s+(?:maternos|paternos)?\s+(?:de|que\s+ten[ií]a)\s+(.+?)(?:\?|$)",
            r"sobrinos\s+nietos\s+de\s+(.+?)(?:\?|$)",
            r"bisabuelos\s+de\s+(.+?)(?:\?|$)",
            r"tatarabuelos\s+de\s+(.+?)(?:\?|$)",
            r"tataranietos?\s+(?:documentados?\s+)?de\s+(.+?)(?:\?|$)",
            r"bisabuela\s+materna\s+de\s+(.+?)(?:\?|$)",
            r"bisnieto\s+mayor\s+de\s+(.+?)(?:\?|$)",
            r"ten[ií]a\s+consuegros\s+documentados\s+(.+?)(?:\?|$)",
        ]
        q = _clean_question(question)
        for p in patterns:
            m = re.search(p, q, re.I)
            if m:
                return _normalize_name_fragment(m.group(1))
        return None

    def _get_parent(self, person, which: str):
        person = _as_dict(person)
        if not person:
            return None
        pid = person["father_id"] if which == "father" else person["mother_id"]
        if not pid:
            return None
        return _as_dict(get_person(self.conn, pid))

    def _get_grandparent(self, person, line: str, side: str):
        parent = self._get_parent(person, line)
        if not parent:
            return None
        return self._get_parent(parent, side)

    def _get_marriage_or_partnership(self, p1_id: str, p2_id: str):
        row = self.conn.execute(
            "SELECT date, place, 'marriage' as kind FROM marriages "
            "WHERE (person1_id = ? AND person2_id = ?) OR (person1_id = ? AND person2_id = ?) LIMIT 1",
            (p1_id, p2_id, p2_id, p1_id),
        ).fetchone()
        if row:
            return _as_dict(row)
        row = self.conn.execute(
            "SELECT date, NULL as place, 'partnership' as kind FROM partnerships "
            "WHERE (person1_id = ? AND person2_id = ?) OR (person1_id = ? AND person2_id = ?) LIMIT 1",
            (p1_id, p2_id, p2_id, p1_id),
        ).fetchone()
        return _as_dict(row) if row else None

    def _children_of_ids(self, parent_ids: List[str]):
        if not parent_ids:
            return []
        placeholders = ",".join("?" for _ in parent_ids)
        rows = self.conn.execute(
            f"SELECT DISTINCT p.* FROM people p JOIN children c ON p.id = c.child_id WHERE c.parent_id IN ({placeholders}) ORDER BY p.birth_year, p.name",
            list(parent_ids),
        ).fetchall()
        return [_as_dict(r) for r in rows]

    def _all_descendants_count(self, person_id: str) -> int:
        seen = set()
        queue = [person_id]
        while queue:
            current = queue.pop(0)
            for row in self.conn.execute("SELECT child_id FROM children WHERE parent_id = ?", (current,)).fetchall():
                cid = row[0]
                if cid not in seen:
                    seen.add(cid)
                    queue.append(cid)
        return len(seen)

    def _get_aunts_uncles(self, person):
        father = self._get_parent(person, "father")
        mother = self._get_parent(person, "mother")
        paternal = []
        maternal = []
        if father:
            paternal = [_as_dict(s) for s in get_siblings(self.conn, father["id"]) if _as_dict(s)["id"] != father["id"]]
        if mother:
            maternal = [_as_dict(s) for s in get_siblings(self.conn, mother["id"]) if _as_dict(s)["id"] != mother["id"]]
        return paternal, maternal

    def _get_first_cousins(self, person):
        paternal, maternal = self._get_aunts_uncles(person)
        paternal_cousins = self._children_of_ids([p["id"] for p in paternal])
        maternal_cousins = self._children_of_ids([m["id"] for m in maternal])
        return paternal, maternal, paternal_cousins, maternal_cousins

    def _same_parents(self, a, b) -> bool:
        a = _as_dict(a)
        b = _as_dict(b)
        return bool(a and b and a.get("father_id") and a.get("father_id") == b.get("father_id") and a.get("mother_id") and a.get("mother_id") == b.get("mother_id"))

    def _is_parent_of(self, parent, child) -> bool:
        parent = _as_dict(parent)
        child = _as_dict(child)
        if not parent or not child:
            return False
        return bool((child.get("father_id") and child["father_id"] == parent["id"]) or (child.get("mother_id") and child["mother_id"] == parent["id"]))

    def _is_grandparent_of(self, gp, person) -> bool:
        return bool(self._is_parent_of(gp, self._get_parent(person, "father")) or self._is_parent_of(gp, self._get_parent(person, "mother")))

    def _is_uncle_aunt_of(self, maybe_uncle, person) -> bool:
        paternal, maternal = self._get_aunts_uncles(person)
        return any(x["id"] == _as_dict(maybe_uncle)["id"] for x in paternal + maternal)

    def _is_first_cousin(self, a, b) -> bool:
        a_gps = {gp["id"] for gp in [self._get_grandparent(a, "father", "father"), self._get_grandparent(a, "father", "mother"), self._get_grandparent(a, "mother", "father"), self._get_grandparent(a, "mother", "mother")] if gp}
        b_gps = {gp["id"] for gp in [self._get_grandparent(b, "father", "father"), self._get_grandparent(b, "father", "mother"), self._get_grandparent(b, "mother", "father"), self._get_grandparent(b, "mother", "mother")] if gp}
        return bool(a_gps and b_gps and a_gps.intersection(b_gps) and not self._same_parents(a, b))

    def _relationship_label(self, a, b) -> Optional[str]:
        a = _as_dict(a)
        b = _as_dict(b)
        if a["id"] == b["id"]:
            return "la misma persona"
        if self._is_parent_of(a, b):
            return _sexed_role(a, "padre", "madre", "progenitor/a")
        if self._is_parent_of(b, a):
            return _sexed_role(a, "hijo", "hija", "hijo/a")
        if self._same_parents(a, b):
            return "hermanos"
        if self._is_grandparent_of(a, b):
            return _sexed_role(a, "abuelo", "abuela", "abuelo/a")
        if self._is_grandparent_of(b, a):
            return _sexed_role(a, "nieto", "nieta", "nieto/a")
        if self._is_uncle_aunt_of(a, b):
            return "tío/tía y sobrino/a"
        if self._is_uncle_aunt_of(b, a):
            return "sobrino/a y tío/tía"
        if self._is_first_cousin(a, b):
            return "primos hermanos"
        rel = self._get_marriage_or_partnership(a["id"], b["id"])
        if rel:
            return "cónyuges o pareja"
        return None

    def _people_payload(self, rows):
        cards = []
        for r in rows:
            card = _person_card(r)
            if card:
                cards.append(card)
        return cards

    def _extract_date_parts(self, question: str):
        m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", question)
        if not m:
            return None
        return int(m.group(1)), int(m.group(2)), int(m.group(3))

    def _month_tokens(self, month: int):
        mapping = {
            1: ["ene", "ene.", "enero", "gen", "gen.", "gener"],
            2: ["feb", "feb.", "febrero", "febrer"],
            3: ["mar", "mar.", "marzo", "marc", "març"],
            4: ["abr", "abr.", "abril"],
            5: ["may", "may.", "mayo", "maig"],
            6: ["jun", "jun.", "junio", "juny"],
            7: ["jul", "jul.", "julio", "juliol"],
            8: ["ago", "ago.", "agosto", "agost"],
            9: ["sep", "sep.", "sept", "sept.", "septiembre", "set", "set.", "setembre"],
            10: ["oct", "oct.", "octubre"],
            11: ["nov", "nov.", "noviembre", "novembre"],
            12: ["dic", "dic.", "diciembre", "des", "des.", "desembre", "dec", "dec."],
        }
        return mapping.get(month, [])

    def _date_matches_text(self, text: str, day: int, month: int, year: int) -> bool:
        t = _norm_cmp(text or "")
        if not t or str(year) not in t:
            return False
        day_ok = re.search(rf"0?{day}", t) is not None
        month_ok = any(tok in t for tok in self._month_tokens(month))
        slash_ok = f"{day:02d}/{month:02d}/{year}" in (text or "") or f"{day}/{month}/{year}" in (text or "")
        return (day_ok and month_ok) or slash_ok

    def _extract_place_after(self, question: str, marker_regex: str) -> Optional[str]:
        m = re.search(marker_regex, _clean_question(question), re.I)
        if not m:
            return None
        return m.group(1).strip().rstrip("?.!,;:")


    def _extract_named_person_and_place(self, question: str):
        q = _clean_question(question)
        m = re.search(r"nacida?\s+en\s+(.+?)\s+llamada\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None, None
        return _normalize_name_fragment(m.group(2)), m.group(1).strip()

    def _resolve_person_with_birth_place(self, raw_name: str, birth_place: str):
        raw_name = _normalize_name_fragment(raw_name)
        raw_name, year_hint = self._extract_year_hint(raw_name)
        matches = self._search_people(raw_name, year_hint=year_hint)
        if not matches:
            return None, []
        place_norm = _norm_cmp(birth_place)
        filtered = [m for m in matches if place_norm in _norm_cmp(_as_dict(m).get('birth_place', ''))]
        final = filtered or matches
        return _as_dict(final[0]), [_as_dict(m) for m in final]

    def _children_rows_for_parent(self, parent_id: str):
        return [_as_dict(r) for r in self.conn.execute(
            "SELECT p.* FROM people p JOIN children c ON p.id = c.child_id WHERE c.parent_id = ? ORDER BY p.birth_year, p.name",
            (parent_id,),
        ).fetchall()]

    def _shared_children(self, p1_id: str, p2_id: str):
        rows = self.conn.execute(
            "SELECT p.* FROM people p WHERE p.id IN ("
            "SELECT c1.child_id FROM children c1 JOIN children c2 ON c1.child_id = c2.child_id "
            "WHERE c1.parent_id = ? AND c2.parent_id = ?) ORDER BY p.birth_year, p.name",
            (p1_id, p2_id),
        ).fetchall()
        return [_as_dict(r) for r in rows]

    def _extract_year_from_text(self, text: Optional[str]) -> Optional[int]:
        if not text:
            return None
        m = re.search(r"(\d{4})", str(text))
        return int(m.group(1)) if m else None

    def _age_from_years(self, birth_year: Optional[int], event_year: Optional[int]) -> Optional[int]:
        if birth_year is None or event_year is None:
            return None
        return event_year - birth_year

    def _common_children_union_fallback(self, p1_id: str, p2_id: str):
        shared = self._shared_children(p1_id, p2_id)
        if shared:
            return _sort_people(shared)
        ids = {c['id'] for c in self._children_rows_for_parent(p1_id)} | {c['id'] for c in self._children_rows_for_parent(p2_id)}
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        rows = self.conn.execute(
            f"SELECT * FROM people WHERE id IN ({placeholders}) ORDER BY birth_year, name",
            list(ids),
        ).fetchall()
        return [_as_dict(r) for r in rows]

    def _list_people_answer(self, prefix: str, people, limit: int = 25):
        people = _sort_people(people)
        if not people:
            return f"{prefix} 0."
        names = _join_names(people[:limit])
        suffix = "" if len(people) <= limit else f" (mostrando {limit} de {len(people)})"
        return f"{prefix} {len(people)}: {names}{suffix}."

    # Handlers

    def handle_parents(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        father = self._get_parent(person, "father")
        mother = self._get_parent(person, "mother")
        if not father and not mother:
            answer = f"No constan los padres de {person['name']}."
        elif father and mother:
            answer = f"Los padres de {person['name']} fueron { _person_brief(father) } y { _person_brief(mother) }."
        elif father:
            answer = f"De {person['name']} solo consta su padre: { _person_brief(father) }."
        else:
            answer = f"De {person['name']} solo consta su madre: { _person_brief(mother) }."
        return {"answer": answer, "people_mentioned": [x["id"] for x in [person, father, mother] if x], "people_with_photos": self._people_payload([person, father, mother])}

    def handle_father(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        father = self._get_parent(person, "father")
        answer = f"El padre de {person['name']} fue { _person_brief(father) }." if father else f"No consta el padre de {person['name']}."
        return {"answer": answer, "people_mentioned": [x["id"] for x in [person, father] if x], "people_with_photos": self._people_payload([person, father])}

    def handle_birth_union(self, question):
        m = re.search(r"(?:de\s+qu[eé]\s+(?:matrimonio(?:\s+o\s+pareja)?|pareja)\s+naci[oó])\s+(.+?)(?:\?|$)", _clean_question(question), re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        father = self._get_parent(person, "father")
        mother = self._get_parent(person, "mother")
        people = [person, father, mother]
        if not father and not mother:
            answer = f"No consta de qué matrimonio o pareja nació {person['name']}."
        elif father and mother:
            union = self._get_marriage_or_partnership(father["id"], mother["id"])
            if union and union["kind"] == "marriage":
                extra = ""
                if union.get("date"):
                    extra += f", celebrado el {union['date']}"
                if union.get("place"):
                    extra += f" en {union['place']}"
                answer = f"{person['name']} nació del matrimonio entre {father['name']} y {mother['name']}{extra}."
            elif union and union["kind"] == "partnership":
                extra = f" con inicio documentado en {union['date']}" if union.get("date") else ""
                answer = f"{person['name']} nació de la pareja formada por {father['name']} y {mother['name']}{extra}."
            else:
                answer = f"{person['name']} fue hija/o de {father['name']} y {mother['name']}, pero no consta un matrimonio o una pareja documentados entre ambos."
        else:
            answer = f"De {person['name']} solo consta un progenitor documentado: { _person_brief(father or mother) }."
        return {"answer": answer, "people_mentioned": [p["id"] for p in people if p], "people_with_photos": self._people_payload(people)}

    def handle_siblings(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        siblings = _sort_people(get_siblings(self.conn, person["id"]))
        if not siblings:
            answer = f"{person['name']} no tenía hermanos o hermanas documentados."
        else:
            answer = f"Los hermanos y hermanas de {person['name']} fueron { _join_names(siblings) }."
        return {"answer": answer, "people_mentioned": [person["id"]] + [s["id"] for s in siblings], "people_with_photos": self._people_payload([person] + siblings)}

    def handle_siblings_count(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        siblings = _sort_people(get_siblings(self.conn, person["id"]))
        if siblings:
            answer = f"{person['name']} tenía {len(siblings)} hermanos o hermanas documentados: { _join_names(siblings) }."
        else:
            answer = f"{person['name']} no tenía hermanos o hermanas documentados."
        return {"answer": answer, "people_mentioned": [person["id"]] + [s["id"] for s in siblings], "people_with_photos": self._people_payload([person] + siblings)}

    def handle_paternal_grandfather(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        gp = self._get_grandparent(person, "father", "father")
        answer = f"El abuelo paterno de {person['name']} fue { _person_brief(gp) }." if gp else f"No consta documentado el abuelo paterno de {person['name']}."
        return {"answer": answer, "people_mentioned": [x["id"] for x in [person, gp] if x], "people_with_photos": self._people_payload([person, gp])}

    def handle_maternal_grandmother(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        gm = self._get_grandparent(person, "mother", "mother")
        answer = f"La abuela materna de {person['name']} fue { _person_brief(gm) }." if gm else f"No consta documentada la abuela materna de {person['name']}."
        return {"answer": answer, "people_mentioned": [x["id"] for x in [person, gm] if x], "people_with_photos": self._people_payload([person, gm])}

    def handle_uncles_and_aunts(self, question):
        """Handle 'tíos y tías de [person]' or similar."""
        q = _clean_question(question)
        m = re.search(r"t[ií]os?\s+(?:y\s+)?t[ií]as?\s+de\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        subject = m.group(1)
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        paternal, maternal = self._get_aunts_uncles(person)
        paternal = _sort_people(paternal)
        maternal = _sort_people(maternal)
        sections = []
        if paternal:
            sections.append("por parte de padre: " + _join_names(paternal))
        if maternal:
            sections.append("por parte de madre: " + _join_names(maternal))
        if not sections:
            answer = f"No constan tíos o tías documentados de {_person_link(person)}."
        else:
            answer = f"Los tíos y tías de {_person_link(person)} fueron " + "; ".join(sections) + "."
        people = [person] + paternal + maternal
        return {"answer": answer, "people_mentioned": [p["id"] for p in people if p], "people_with_photos": self._people_payload(people)}

    def handle_uncles(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        paternal, maternal = self._get_aunts_uncles(person)
        paternal = _sort_people(paternal)
        maternal = _sort_people(maternal)
        sections = []
        if paternal:
            sections.append("por parte de padre: " + _join_names(paternal))
        if maternal:
            sections.append("por parte de madre: " + _join_names(maternal))
        if not sections:
            answer = f"No constan tíos o tías documentados de {person['name']}."
        else:
            answer = f"Los tíos y tías de {person['name']} fueron " + "; ".join(sections) + "."
        people = [person] + paternal + maternal
        return {"answer": answer, "people_mentioned": [p["id"] for p in people], "people_with_photos": self._people_payload(people)}

    def handle_first_cousins(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        _, _, paternal_cousins, maternal_cousins = self._get_first_cousins(person)
        paternal_cousins = _sort_people(paternal_cousins)
        maternal_cousins = _sort_people(maternal_cousins)
        sections = []
        if paternal_cousins:
            sections.append("por parte paterna: " + _join_names(paternal_cousins))
        if maternal_cousins:
            sections.append("por parte materna: " + _join_names(maternal_cousins))
        if not sections:
            answer = f"No constan primos hermanos documentados de {person['name']}."
        else:
            total = len(paternal_cousins) + len(maternal_cousins)
            answer = f"Los primos hermanos de {person['name']} fueron {total} en total: " + "; ".join(sections) + "."
        people = [person] + paternal_cousins + maternal_cousins
        return {"answer": answer, "people_mentioned": [p["id"] for p in people], "people_with_photos": self._people_payload(people)}

    def handle_spouse_or_partner(self, question):
        m = re.search(r"(?:con\s+qui[eé]n\s+(?:se\s+cas[oó]|form[oó]\s+pareja)(?:\s+o\s+emparej[oó])?|amb\s+qui\s+es\s+va\s+casar\s+o\s+emparellar)\s+(.+?)(?:\?|$)", _clean_question(question), re.I)
        subject = m.group(1) if m else self._extract_subject_name(question)
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        parts = []
        people = [person]
        for s in get_spouses(self.conn, person["id"]):
            sp = _as_dict(s["person"])
            txt = sp["name"]
            if s.get("marriage_date"):
                txt += f" (matrimonio: {s['marriage_date']})"
            if s.get("marriage_place"):
                txt += f" en {s['marriage_place']}"
            parts.append(txt)
            people.append(sp)
        partnerships = self.conn.execute(
            "SELECT CASE WHEN person1_id = ? THEN person2_id ELSE person1_id END AS partner_id, date FROM partnerships WHERE person1_id = ? OR person2_id = ?",
            (person["id"], person["id"], person["id"]),
        ).fetchall()
        for p in partnerships:
            partner = _as_dict(get_person(self.conn, p["partner_id"]))
            if partner:
                txt = partner["name"]
                if p["date"]:
                    txt += f" (pareja documentada desde {p['date']})"
                parts.append(txt)
                people.append(partner)
        if not parts:
            answer = f"No consta que {person['name']} se casara o tuviera una pareja documentada."
        else:
            answer = f"{person['name']} se casó o emparejó con { '; '.join(parts) }."
        return {"answer": answer, "people_mentioned": [p["id"] for p in people if p], "people_with_photos": self._people_payload(people)}

    def handle_spouse_with_person_type(self, question):
        q = _clean_question(question)
        m = re.search(r"(?:con\s+qu[eé]\s+(?:mujer|persona|hombre)\s+(?:form[oó]|enlaz[oó])\s+familia|con\s+qu[eé]\s+(?:mujer|persona|hombre)\s+casó)\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        subject = m.group(1)
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        spouses = get_spouses(self.conn, person["id"])
        if not spouses:
            answer = f"No consta que {_person_link(person)} se casara o formara pareja documentada."
            people = [person]
        else:
            parts = []
            people = [person]
            for s in spouses:
                sp = _as_dict(s["person"])
                txt = sp["name"]
                if s.get("marriage_date"):
                    txt += f" el {s['marriage_date']}"
                if s.get("marriage_place"):
                    txt += f" en {s['marriage_place']}"
                parts.append(txt)
                people.append(sp)
            answer = f"{_person_link(person)} formó pareja o matrimonio con { '; '.join(parts) }."
        return {"answer": answer, "people_mentioned": [p["id"] for p in people if p], "people_with_photos": self._people_payload(people)}

    def handle_spouse(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        spouses = get_spouses(self.conn, person["id"])
        if not spouses:
            answer = f"No consta cónyuge documentado de {person['name']}."
            people = [person]
        else:
            parts = []
            people = [person]
            for s in spouses:
                sp = _as_dict(s["person"])
                txt = sp["name"]
                if s.get("marriage_date"):
                    txt += f", casados el {s['marriage_date']}"
                if s.get("marriage_place"):
                    txt += f" en {s['marriage_place']}"
                parts.append(txt)
                people.append(sp)
            answer = f"El cónyuge de {person['name']} fue { '; '.join(parts) }."
        return {"answer": answer, "people_mentioned": [p["id"] for p in people if p], "people_with_photos": self._people_payload(people)}

    def handle_children(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        children = _sort_people(list(get_children(self.conn, person["id"])))
        if not children:
            answer = f"No constan hijos documentados de {person['name']}."
        else:
            if len(children) == 1:
                answer = f"El hijo de {person['name']} fue { _join_names(children) }."
            else:
                answer = f"Los hijos de {person['name']} fueron { _join_names(children) }."
        return {"answer": answer, "people_mentioned": [person["id"]] + [c["id"] for c in children], "people_with_photos": self._people_payload([person] + children)}

    def handle_children_count(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        children = _sort_people(list(get_children(self.conn, person["id"])))
        if children:
            count_word = "hijo o hija" if len(children) == 1 else "hijos o hijas"
            answer = f"{person['name']} tuvo {len(children)} {count_word} documentad{'o' if len(children) == 1 else 'os'}: { _join_names(children) }."
        else:
            answer = f"{person['name']} no tuvo hijos o hijas documentados."
        return {"answer": answer, "people_mentioned": [person["id"]] + [c["id"] for c in children], "people_with_photos": self._people_payload([person] + children)}

    def handle_first_child(self, question):
        q = _clean_question(question)
        m = re.search(r"(?:primer\s+hijo|primer\s+hija|first\s+child)\s+(?:de|of)\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        children = _sort_people(list(get_children(self.conn, person["id"])))
        if not children:
            return {"answer": f"No constan hijos documentados de {_person_link(person)}.", "people_mentioned": [person["id"]], "people_with_photos": self._people_payload([person])}
        first = children[0]
        return {"answer": f"El primer hijo de {_person_link(person)} fue {_person_link(first)}.", "people_mentioned": [person["id"], first["id"]], "people_with_photos": self._people_payload([person, first])}

    def handle_oldest_son(self, question):
        q = _clean_question(question)
        m = re.search(r"(?:hijo\s+mayor|oldest\s+son)\s+(?:de|of)\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        children = _sort_people(list(get_children(self.conn, person["id"])))
        sons = [c for c in children if c.get("sex") == "M"]
        if not sons:
            return {"answer": f"No constan hijos varones documentados de {_person_link(person)}.", "people_mentioned": [person["id"]], "people_with_photos": self._people_payload([person])}
        oldest = sons[0]
        return {"answer": f"El hijo mayor de {_person_link(person)} fue {_person_link(oldest)}.", "people_mentioned": [person["id"], oldest["id"]], "people_with_photos": self._people_payload([person, oldest])}

    def handle_oldest_daughter(self, question):
        q = _clean_question(question)
        m = re.search(r"(?:hija\s+mayor|oldest\s+daughter)\s+(?:de|of)\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        children = _sort_people(list(get_children(self.conn, person["id"])))
        daughters = [c for c in children if c.get("sex") == "F"]
        if not daughters:
            return {"answer": f"No constan hijas documentadas de {_person_link(person)}.", "people_mentioned": [person["id"]], "people_with_photos": self._people_payload([person])}
        oldest = daughters[0]
        return {"answer": f"La hija mayor de {_person_link(person)} fue {_person_link(oldest)}.", "people_mentioned": [person["id"], oldest["id"]], "people_with_photos": self._people_payload([person, oldest])}

    def handle_last_child(self, question):
        q = _clean_question(question)
        m = re.search(r"(?:[úu]ltimo\s+hij[oa]\s+que\s+tuvo|last\s+child\s+of)\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        children = _sort_people(list(get_children(self.conn, person["id"])))
        if not children:
            return {"answer": f"No constan hijos documentados de {_person_link(person)}.", "people_mentioned": [person["id"]], "people_with_photos": self._people_payload([person])}
        last = children[-1]
        return {"answer": f"El ultimo hijo de {_person_link(person)} fue {_person_link(last)}.", "people_mentioned": [person["id"], last["id"]], "people_with_photos": self._people_payload([person, last])}

    def handle_immediate_ascendants(self, question):
        q = _clean_question(question)
        m = re.search(r"(?:ascendientes\s+inmediatos\s+de|immediate\s+ascendants\s+of)\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        father = self._get_parent(person, "father")
        mother = self._get_parent(person, "mother")
        ascendants = [p for p in [father, mother] if p]
        if not ascendants:
            return {"answer": f"No constan ascendientes documentados de {_person_link(person)}.", "people_mentioned": [person["id"]], "people_with_photos": self._people_payload([person])}
        count = len(ascendants)
        links = ", ".join(_person_link(p) for p in ascendants)
        return {"answer": f"Los ascendientes inmediatos de {_person_link(person)} fueron {count}: {links}.", "people_mentioned": [person["id"]] + [p["id"] for p in ascendants], "people_with_photos": self._people_payload([person] + ascendants)}

    def handle_are_cousins(self, question):
        names = self._extract_two_names(question)
        if not names:
            return None
        a, _ = self._resolve_person(names[0])
        b, _ = self._resolve_person(names[1])
        if not a or not b:
            return None
        if self._is_first_cousin(a, b):
            answer = f"Sí, {a['name']} y {b['name']} eran primos hermanos."
        else:
            other = self._relationship_label(a, b)
            if other and other != "primos hermanos":
                answer = f"No, {a['name']} y {b['name']} no eran primos hermanos; la relación documentada entre ambos era de {other}."
            else:
                answer = f"No, {a['name']} y {b['name']} no constan como primos hermanos."
        return {"answer": answer, "people_mentioned": [a["id"], b["id"]], "people_with_photos": self._people_payload([a, b])}

    def handle_is_grandparent_of(self, question):
        m = re.search(r"era\s+(.+?)\s+abuelo\s+o\s+abuela\s+de\s+(.+?)(?:\?|$)", _clean_question(question), re.I)
        if not m:
            return None
        gp, _ = self._resolve_person(_normalize_name_fragment(m.group(1)))
        person, _ = self._resolve_person(_normalize_name_fragment(m.group(2)))
        if not gp or not person:
            return None
        role = _sexed_role(gp, "abuelo", "abuela", "abuelo/a")
        if self._is_grandparent_of(gp, person):
            answer = f"Sí. {gp['name']} era {role} de {person['name']}."
        else:
            answer = f"No. {gp['name']} no figura como abuelo o abuela de {person['name']}."
        return {"answer": answer, "people_mentioned": [gp["id"], person["id"]], "people_with_photos": self._people_payload([gp, person])}

    def handle_parents_and_children(self, question):
        m = re.search(r"padres\s+y\s+los\s+hijos\s+de\s+(.+?)(?:\?|$)", _clean_question(question), re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        father = self._get_parent(person, "father")
        mother = self._get_parent(person, "mother")
        children = _sort_people(list(get_children(self.conn, person["id"])))
        parts = []
        if father or mother:
            pp = []
            if father:
                pp.append(father["name"])
            if mother:
                pp.append(mother["name"])
            parts.append("sus padres fueron " + " y ".join(pp))
        else:
            parts.append("no constan sus padres")
        if children:
            parts.append("sus hijos fueron " + _join_names(children))
        else:
            parts.append("no constan hijos documentados")
        people = [person, father, mother] + children
        return {"answer": f"De {person['name']}, " + "; ".join(parts) + ".", "people_mentioned": [p["id"] for p in people if p], "people_with_photos": self._people_payload([p for p in people if p])}

    def handle_direct_descendants(self, question):
        """Handle 'cuántos descendientes directos dejó [person]'."""
        q = _clean_question(question)
        m = re.search(r"cu[aá]ntos?\s+descendientes?\s+directos?\s+(?:tuvo|dej[oó])\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        subject = m.group(1)
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        # Direct descendants = children
        children = _sort_people(list(get_children(self.conn, person["id"])))
        if not children:
            answer = f"{_person_link(person)} no tuvo descendientes directos documentados."
        else:
            answer = f"{_person_link(person)} tuvo {len(children)} descendiente(s) directo(s) documentado(s): {_join_names(children)}."
        return {"answer": answer, "people_mentioned": [person["id"]] + [c["id"] for c in children], "people_with_photos": self._people_payload([person] + children)}

    def handle_has_descendants(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        count = self._all_descendants_count(person["id"])
        if count > 0:
            answer = f"Sí. De {person['name']} consta descendencia documentada: al menos {count} descendientes en el árbol."
        else:
            answer = f"No consta descendencia documentada de {person['name']}."
        return {"answer": answer, "people_mentioned": [person["id"]], "people_with_photos": self._people_payload([person])}

    def handle_parents_in_law(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        spouses = get_spouses(self.conn, person["id"])
        if not spouses:
            answer = f"No consta cónyuge documentado de {person['name']}, así que no puedo determinar suegro o suegra."
            people = [person]
        else:
            sections = []
            people = [person]
            for s in spouses:
                sp = _as_dict(s["person"])
                sf = self._get_parent(sp, "father")
                sm = self._get_parent(sp, "mother")
                bits = []
                if sf:
                    bits.append(f"suegro: {sf['name']}")
                    people.append(sf)
                if sm:
                    bits.append(f"suegra: {sm['name']}")
                    people.append(sm)
                people.append(sp)
                if bits:
                    sections.append(f"para su relación con {sp['name']}, " + ", ".join(bits))
            answer = f"De {person['name']}, " + "; ".join(sections) + "." if sections else f"No constan los padres del cónyuge de {person['name']}."
        return {"answer": answer, "people_mentioned": [p["id"] for p in people if p], "people_with_photos": self._people_payload([p for p in people if p])}

    def handle_relationship(self, question):
        names = self._extract_two_names(question)
        if not names:
            return None
        a, _ = self._resolve_person(names[0])
        b, _ = self._resolve_person(names[1])
        if not a or not b:
            return None
        rel = self._relationship_label(a, b)
        if rel:
            answer = f"La relación entre {a['name']} y {b['name']} era de {rel}."
        else:
            answer = f"No he podido determinar con las reglas actuales la relación exacta entre {a['name']} y {b['name']}."
        return {"answer": answer, "people_mentioned": [a["id"], b["id"]], "people_with_photos": self._people_payload([a, b])}


    def handle_age_at_first_child(self, question):
        q = _clean_question(question)
        m = (re.search(r"(?:a\s+)?qu[eé]\s+edad\s+(?:tuvo|ten[ií]a.*cuando\s+naci[oó])\s+su\s+primer\s+hij[oa]\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"cu[aá]ntos?\s+a[nñ]os\s+ten[ií]a\s+(.+?)\s+cuando\s+naci[oó]\s+su\s+primer\s+hij[oa](?:,\s+(.+?))?(?:\?|$)", q, re.I))
        if not m:
            return None
        parent, _ = self._resolve_person(m.group(1))
        if not parent:
            return None
        children = _sort_people(self._children_rows_for_parent(parent['id']))
        if not children:
            answer = f"No constan hijos documentados de {parent['name']}."
            return {"answer": answer, "people_mentioned": [parent['id']], "people_with_photos": self._people_payload([parent])}
        child = children[0]
        named_child = _normalize_name_fragment(m.group(2)) if m.group(2) else None
        if named_child:
            chosen, _ = self._resolve_person(named_child)
            if chosen and any(c['id'] == chosen['id'] for c in children):
                child = chosen
        age = self._age_from_years(parent.get('birth_year'), child.get('birth_year'))
        if age is None:
            answer = f"No puedo calcular con precisión la edad de {parent['name']} cuando nació {child['name']} porque faltan años de nacimiento."
        else:
            answer = f"{parent['name']} tenía aproximadamente {age} años cuando nació {child['name']} ({child.get('birth_year')})."
        return {"answer": answer, "people_mentioned": [parent['id'], child['id']], "people_with_photos": self._people_payload([parent, child])}

    def handle_age_at_marriage(self, question):
        q = _clean_question(question)
        m = (re.search(r"(?:a\s+)?qu[eé]\s+edad\s+se\s+cas[oó]\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"qu[eé]\s+edad\s+ten[ií]a\s+(.+?)\s+cuando\s+se\s+cas[oó](?:\?|$)", q, re.I) or
             re.search(r"qu[eé]\s+edad\s+(?:ten[ií]a|gastaba)\s+(.+?)\s+al\s+casarse(?:\?|$)", q, re.I))
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        spouses = get_spouses(self.conn, person['id'])
        if not spouses:
            answer = f"No consta un matrimonio documentado de {person['name']}."
            return {"answer": answer, "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        first = min(spouses, key=lambda s: self._extract_year_from_text(s.get('marriage_date')) or 999999)
        marriage_year = self._extract_year_from_text(first.get('marriage_date'))
        age = self._age_from_years(person.get('birth_year'), marriage_year)
        spouse = _as_dict(first['person'])
        if age is None:
            answer = f"No puedo calcular con precisión la edad de {person['name']} al casarse con {spouse['name']} porque falta el año de nacimiento o de matrimonio."
        else:
            extra = f" el {first['marriage_date']}" if first.get('marriage_date') else ""
            answer = f"{person['name']} tenía aproximadamente {age} años cuando se casó con {spouse['name']}{extra}."
        return {"answer": answer, "people_mentioned": [person['id'], spouse['id']], "people_with_photos": self._people_payload([person, spouse])}

    def handle_spouse_disambiguated_by_birth_place(self, question):
        name, place = self._extract_named_person_and_place(question)
        if not name or not place:
            return None
        person, _ = self._resolve_person_with_birth_place(name, place)
        if not person:
            return None
        spouses = get_spouses(self.conn, person['id'])
        if not spouses:
            answer = f"No consta un cónyuge documentado de {person['name']}."
            return {"answer": answer, "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        parts = []
        people = [person]
        for s in spouses:
            sp = _as_dict(s['person'])
            txt = sp['name']
            if s.get('marriage_date'):
                txt += f" (matrimonio: {s['marriage_date']})"
            if s.get('marriage_place'):
                txt += f" en {s['marriage_place']}"
            parts.append(txt)
            people.append(sp)
        answer = f"La persona nacida en {place} llamada {person['name']} se casó con " + "; ".join(parts) + "."
        return {"answer": answer, "people_mentioned": [p['id'] for p in people], "people_with_photos": self._people_payload(people)}

    def handle_couple_children_count(self, question):
        q = _clean_question(question)
        m = (re.search(r"cu[aá]ntos?\s+hijos\s+tuvieron\s+(.+?)\s+y\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"cu[aá]ntos?\s+hijos\s+tuvo\s+el\s+matrimonio\s+de\s+(.+?)\s+y\s+(.+?)(?:\?|$)", q, re.I))
        if not m:
            return None
        p1, _ = self._resolve_person(m.group(1))
        p2, _ = self._resolve_person(m.group(2))
        if not p1 or not p2:
            return None
        children = self._common_children_union_fallback(p1['id'], p2['id'])
        if children:
            answer = f"El matrimonio de {p1['name']} y {p2['name']} tuvo {len(children)} hijos documentados: {_join_names(children)}."
        else:
            answer = f"No constan hijos documentados del matrimonio de {p1['name']} y {p2['name']}."
        return {"answer": answer, "people_mentioned": [p1['id'], p2['id']] + [c['id'] for c in children], "people_with_photos": self._people_payload([p1, p2] + children)}

    def handle_grandparents_with_years(self, question):
        q = _clean_question(question)
        m = re.search(r"abuelos\s+de\s+(.+?)\s+y\s+en\s+qu[eé]\s+a[nñ]os\s+nacieron(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        gps = [
            self._get_grandparent(person, 'father', 'father'),
            self._get_grandparent(person, 'father', 'mother'),
            self._get_grandparent(person, 'mother', 'father'),
            self._get_grandparent(person, 'mother', 'mother'),
        ]
        gps = _sort_people([g for g in gps if g])
        if not gps:
            answer = f"No constan abuelos documentados de {person['name']}."
        else:
            desc = ", ".join(f"{g['name']} ({g['birth_year']})" if g.get('birth_year') else g['name'] for g in gps)
            answer = f"Los abuelos de {person['name']} fueron {desc}."
        return {"answer": answer, "people_mentioned": [person['id']] + [g['id'] for g in gps], "people_with_photos": self._people_payload([person] + gps)}

    def handle_grandparents_names(self, question):
        q = _clean_question(question)
        m = (re.search(r"abuelos\s+de\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"qu[eé]\s+abuelos?\s+ten[ií]a\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"nombres\s+de\s+los\s+abuelos\s+de\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"abuelos\s+ten[ií]a\s+por\s+las\s+dos\s+ramas\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"abuelos?\s+(?:paternos?\s+y\s+maternos?|maternos?\s+y\s+paternos?)\s+de\s+(.+?)(?:\?|$)", q, re.I))
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        gps = [
            self._get_grandparent(person, 'father', 'father'),
            self._get_grandparent(person, 'father', 'mother'),
            self._get_grandparent(person, 'mother', 'father'),
            self._get_grandparent(person, 'mother', 'mother'),
        ]
        gps = _sort_people([g for g in gps if g])
        if not gps:
            answer = f"No constan abuelos documentados de {person['name']}."
        else:
            answer = f"Los abuelos de {person['name']} se llamaban {_join_names(gps)}."
        return {"answer": answer, "people_mentioned": [person['id']] + [g['id'] for g in gps], "people_with_photos": self._people_payload([person] + gps)}

    def handle_birth_order_among_siblings(self, question):
        q = _clean_question(question)
        m = (re.search(r"en\s+qu[eé]\s+posici[oó]n\s+(?:entre\s+)?sus\s+hermanos\s+naci[oó]\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"posici[oó]n\s+entre\s+sus\s+hermanos\s+naci[oó]\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"qu[eé]\s+lugar\s+(?:ocupaba|ocupa)\s+(?:dentro|entre)\s+sus\s+hermanos\s+(.+?)(?:\?|$)", q, re.I))
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        siblings = _sort_people(get_siblings(self.conn, person['id']))
        family = _sort_people(siblings + [person])
        if len(family) == 1:
            answer = f"{person['name']} era hijo o hija única según la documentación disponible."
        else:
            ids = [p['id'] for p in family]
            pos = ids.index(person['id']) + 1
            answer = f"{person['name']} ocupaba la posición {pos} de {len(family)} entre sus hermanos y hermanas por orden de nacimiento conocido."
        return {"answer": answer, "people_mentioned": [p['id'] for p in family], "people_with_photos": self._people_payload(family)}

    def handle_parents_and_marriage_place(self, question):
        q = _clean_question(question)
        m = re.search(r"padres\s+de\s+(.+?)\s+y\s+d[oó]nde\s+se\s+casaron(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        father = self._get_parent(person, 'father')
        mother = self._get_parent(person, 'mother')
        if not father and not mother:
            answer = f"No constan los padres de {person['name']}."
            people = [person]
        else:
            people = [person, father, mother]
            if father and mother:
                union = self._get_marriage_or_partnership(father['id'], mother['id'])
                if union and union.get('place'):
                    answer = f"Los padres de {person['name']} fueron {father['name']} y {mother['name']}, y se casaron en {union['place']}."
                elif union and union.get('date'):
                    answer = f"Los padres de {person['name']} fueron {father['name']} y {mother['name']}. Consta su unión el {union['date']}, pero no el lugar."
                else:
                    answer = f"Los padres de {person['name']} fueron {father['name']} y {mother['name']}, pero no consta dónde se casaron."
            else:
                only = father or mother
                answer = f"De {person['name']} solo consta un progenitor documentado: {only['name']}."
        return {"answer": answer, "people_mentioned": [p['id'] for p in people if p], "people_with_photos": self._people_payload([p for p in people if p])}

    def handle_relationship_and_older(self, question):
        names = self._extract_two_names(question)
        if not names:
            return None
        a, _ = self._resolve_person(names[0])
        b, _ = self._resolve_person(names[1])
        if not a or not b:
            return None
        rel = self._relationship_label(a, b) or "relación no determinada"
        if a.get('birth_year') and b.get('birth_year'):
            if a['birth_year'] < b['birth_year']:
                older = a['name']
            elif b['birth_year'] < a['birth_year']:
                older = b['name']
            else:
                older = "tenían la misma edad aproximada"
            older_text = older if older == "tenían la misma edad aproximada" else f"El mayor de los dos era {older}."
        else:
            older_text = "No puedo determinar cuál era mayor con los años de nacimiento disponibles."
        answer = f"La relación entre {a['name']} y {b['name']} era de {rel}. {older_text}"
        return {"answer": answer, "people_mentioned": [a['id'], b['id']], "people_with_photos": self._people_payload([a, b])}

    def handle_spouse_and_wedding_date(self, question):
        q = _clean_question(question)
        m = re.search(r"con\s+qui[eé]n\s+se\s+cas[oó]\s+(.+?)\s+y\s+en\s+qu[eé]\s+fecha\s+fue\s+la\s+boda(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        spouses = get_spouses(self.conn, person['id'])
        if not spouses:
            answer = f"No consta un matrimonio documentado de {person['name']}."
            return {"answer": answer, "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        parts = []
        people = [person]
        for s in spouses:
            sp = _as_dict(s['person'])
            txt = sp['name']
            if s.get('marriage_date'):
                txt += f"; la boda fue el {s['marriage_date']}"
            if s.get('marriage_place'):
                txt += f" en {s['marriage_place']}"
            parts.append(txt)
            people.append(sp)
        answer = f"{person['name']} se casó con " + "; y con ".join(parts) + "."
        return {"answer": answer, "people_mentioned": [p['id'] for p in people], "people_with_photos": self._people_payload(people)}

    def handle_marriage_date_place(self, question):
        """Handle 'cuándo/dónde se casó X?' - return marriage date/place."""
        q = _clean_question(question)
        m = (re.search(r"(?:cu[aá]ndo|en\s+qu[eé]\s+(?:fecha|a[nñ]o|d[ií]a))\s+se\s+cas[oó]\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"(?:d[oó]nde|en\s+qu[eé]\s+(?:lugar|iglesia|sitio))\s+se\s+cas[oó]\s+(.+?)(?:\?|$)", q, re.I))
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1).strip())
        if not person:
            return None

        # Determine if asking for date or place
        is_date_query = bool(re.search(r"cu[aá]ndo|fecha|a[nñ]o|d[ií]a", q, re.I))

        spouses = get_spouses(self.conn, person['id'])
        if not spouses:
            return {"answer": f"No consta ningún matrimonio documentado de {person['name']}.",
                    "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}

        parts = []
        people = [person]
        for sp in spouses:
            sp = _as_dict(sp)
            spouse = sp.get('person')
            if spouse:
                spouse = _as_dict(spouse)
                people.append(spouse)
                spouse_name = spouse.get('name', '?')
            else:
                spouse_name = '?'

            if is_date_query:
                date_str = sp.get('marriage_date') or ''
                if date_str:
                    parts.append(f"el {date_str}")
                else:
                    parts.append(f"sin fecha documentada")
            else:
                place_str = sp.get('marriage_place') or ''
                if place_str:
                    parts.append(f"en {place_str}")
                else:
                    parts.append(f"sin lugar documentado")

        if is_date_query:
            answer = f"{person['name']} se casó " + " y ".join(parts) + "."
        else:
            answer = f"{person['name']} se casó " + " y ".join(parts) + "."

        return {"answer": answer, "people_mentioned": [p['id'] for p in people], "people_with_photos": self._people_payload(people)}

    def handle_father_of_mother(self, question):
        q = _clean_question(question)
        m = re.search(r"padre\s+de\s+la\s+madre\s+de\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        mother = self._get_parent(person, 'mother')
        if not mother:
            answer = f"No consta la madre de {person['name']}."
            people = [person]
        else:
            mf = self._get_parent(mother, 'father')
            people = [person, mother, mf]
            if mf:
                answer = f"El padre de la madre de {person['name']} fue {mf['name']}."
            else:
                answer = f"Consta la madre de {person['name']} ({mother['name']}), pero no el padre de ella."
        return {"answer": answer, "people_mentioned": [p['id'] for p in people if p], "people_with_photos": self._people_payload([p for p in people if p])}

    def handle_children_born_in_place(self, question):
        q = _clean_question(question)
        m = re.search(r"qu[eé]\s+hijos\s+de\s+(.+?)\s+nacieron\s+en\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        place = m.group(2).strip()
        if not person:
            return None
        children = [c for c in self._children_rows_for_parent(person['id']) if _norm_cmp(place) in _norm_cmp(c.get('birth_place', ''))]
        children = _sort_people(children)
        if children:
            answer = f"Los hijos de {person['name']} nacidos en {place} fueron {_join_names(children)}."
        else:
            answer = f"No constan hijos de {person['name']} nacidos en {place}."
        return {"answer": answer, "people_mentioned": [person['id']] + [c['id'] for c in children], "people_with_photos": self._people_payload([person] + children)}

    def handle_children_of_couple_married_at_place(self, question):
        q = _clean_question(question)
        m = re.search(r"cas[oó]\s+en\s+(.+?)\s+formada\s+por\s+(.+?)\s+y\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        place = m.group(1).strip()
        p1, _ = self._resolve_person(m.group(2))
        p2, _ = self._resolve_person(m.group(3))
        if not p1 or not p2:
            return None
        union = self._get_marriage_or_partnership(p1['id'], p2['id'])
        if union and union.get('place') and _norm_cmp(place) not in _norm_cmp(union.get('place', '')):
            answer = f"Consta la pareja formada por {p1['name']} y {p2['name']}, pero su matrimonio no figura en {place}."
            return {"answer": answer, "people_mentioned": [p1['id'], p2['id']], "people_with_photos": self._people_payload([p1, p2])}
        children = self._common_children_union_fallback(p1['id'], p2['id'])
        if children:
            answer = f"La pareja formada por {p1['name']} y {p2['name']} tuvo estos hijos documentados: {_join_names(children)}."
        else:
            answer = f"No constan hijos documentados de la pareja formada por {p1['name']} y {p2['name']}."
        return {"answer": answer, "people_mentioned": [p1['id'], p2['id']] + [c['id'] for c in children], "people_with_photos": self._people_payload([p1, p2] + children)}

    def handle_who_older_when_married(self, question):
        q = _clean_question(question)
        m = re.search(r"mayor\s+cuando\s+se\s+casaron:\s*(.+?)\s+o\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        a, _ = self._resolve_person(m.group(1))
        b, _ = self._resolve_person(m.group(2))
        if not a or not b:
            return None
        if a.get('birth_year') is None or b.get('birth_year') is None:
            answer = f"No puedo determinar quién era mayor al casarse entre {m.group(1).strip()} y {m.group(2).strip()} porque faltan años de nacimiento."
        elif a['birth_year'] < b['birth_year']:
            answer = f"Cuando se casaron, la persona mayor era {a['name']}."
        elif b['birth_year'] < a['birth_year']:
            answer = f"Cuando se casaron, la persona mayor era {b['name']}."
        else:
            answer = f"Cuando se casaron, {a['name']} y {b['name']} tenían la misma edad aproximada."
        return {"answer": answer, "people_mentioned": [a['id'], b['id']], "people_with_photos": self._people_payload([a, b])}

    def handle_birth_place_and_occupation(self, question):
        q = _clean_question(question)
        m = re.search(r"d[oó]nde\s+naci[oó]\s+(.+?)\s+y\s+qu[eé]\s+ocupaci[oó]n\s+consta\s+en\s+su\s+ficha(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        full = _as_dict(get_person(self.conn, person['id'])) or person
        occs = _sort_people([])
        occupations = get_occupations(self.conn, person['id'])
        occ_text = "; ".join(
            (o['title'] + (f" ({o['date']})" if o.get('date') else "") + (f" en {o['place']}" if o.get('place') else ""))
            for o in (_as_dict(occ) for occ in occupations) if o.get('title')
        )
        bp = full.get('birth_place') or 'lugar de nacimiento no documentado'
        if occ_text:
            answer = f"{full['name']} nació en {bp} y en su ficha consta esta ocupación o actividad: {occ_text}."
        else:
            answer = f"{full['name']} nació en {bp} y no consta ninguna ocupación documentada en su ficha."
        return {"answer": answer, "people_mentioned": [full['id']], "people_with_photos": self._people_payload([full])}

    def handle_surviving_children_count(self, question):
        q = _clean_question(question)
        m = re.search(r"hijos\s+sobrevivieron\s+a\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        parent, _ = self._resolve_person(m.group(1))
        if not parent:
            return None
        children = self._children_rows_for_parent(parent['id'])
        if not children:
            answer = f"No constan hijos documentados de {parent['name']}."
            return {"answer": answer, "people_mentioned": [parent['id']], "people_with_photos": self._people_payload([parent])}
        death_year = parent.get('death_year')
        if death_year is None:
            answer = f"No puedo calcular cuántos hijos sobrevivieron a {parent['name']} porque no consta su año de defunción."
            return {"answer": answer, "people_mentioned": [parent['id']] + [c['id'] for c in children], "people_with_photos": self._people_payload([parent] + children)}
        survivors = [c for c in children if c.get('death_year') is None or c.get('death_year') > death_year]
        survivors = _sort_people(survivors)
        answer = f"Según las fechas disponibles, sobrevivieron a {parent['name']} {len(survivors)} hijos: {_join_names(survivors)}." if survivors else f"Según las fechas disponibles, no consta ningún hijo que sobreviviera a {parent['name']}."
        return {"answer": answer, "people_mentioned": [parent['id']] + [c['id'] for c in survivors], "people_with_photos": self._people_payload([parent] + survivors)}

    def handle_birth_year_search(self, question):
        q = _clean_question(question)
        m = re.search(r"(?:en|el\s+a[nñ]o)\s+(\d{4})", q, re.I) or re.search(r"(?:a[nñ]o|year)\s+(\d{4})", q, re.I)
        if not m:
            return None
        year = int(m.group(1))
        rows = [_as_dict(r) for r in self.conn.execute(
            "SELECT id, name, birth_year, death_year, birth_place, photo_file, is_alive FROM people WHERE birth_year = ? ORDER BY name",
            (year,),
        ).fetchall()]
        answer = self._list_people_answer(f"Las personas nacidas en {year} fueron", rows)
        return {"answer": answer, "people_mentioned": [r["id"] for r in rows], "people_with_photos": self._people_payload(rows)}

    def handle_death_place_people(self, question):
        place = self._extract_place_after(question, r"(?:murieron\s+en|died\s+in)\s+(.+?)(?:\?|$)")
        if not place:
            return None
        rows = [_as_dict(r) for r in self.conn.execute(
            "SELECT id, name, birth_year, death_year, death_place, photo_file, is_alive FROM people WHERE NORMALIZE(death_place) LIKE '%' || NORMALIZE(?) || '%' ORDER BY death_year, name LIMIT 100",
            (place,),
        ).fetchall()]
        answer = self._list_people_answer(f"Las personas fallecidas en {place} fueron", rows)
        return {"answer": answer, "people_mentioned": [r["id"] for r in rows], "people_with_photos": self._people_payload(rows[:25])}

    def handle_marriages_place(self, question):
        place = self._extract_place_after(question, r"(?:casaron\s+en|married\s+in)\s+(.+?)(?:\?|$)")
        if not place:
            return None
        rows = self.conn.execute(
            "SELECT m.person1_id, m.person2_id, m.date, m.place FROM marriages m WHERE NORMALIZE(m.place) LIKE '%' || NORMALIZE(?) || '%' ORDER BY m.date, m.id LIMIT 100",
            (place,),
        ).fetchall()
        if not rows:
            return {"answer": f"No he encontrado parejas casadas en {place}.", "people_mentioned": [], "people_with_photos": []}
        parts=[]; people=[]
        for r in rows[:25]:
            r=_as_dict(r)
            p1=_as_dict(get_person(self.conn,r['person1_id'])) if r['person1_id'] else None
            p2=_as_dict(get_person(self.conn,r['person2_id'])) if r['person2_id'] else None
            if p1: people.append(p1)
            if p2: people.append(p2)
            label = f"{p1['name'] if p1 else '?'} y {p2['name'] if p2 else '?'}"
            if r.get('date'):
                label += f" ({r['date']})"
            parts.append(label)
        answer = f"Las parejas que se casaron en {place} fueron {len(rows)}: " + ", ".join(parts) + "."
        up=_unique_people(people)
        return {"answer": answer, "people_mentioned": [p['id'] for p in up], "people_with_photos": self._people_payload(up[:25])}

    def handle_given_name_initial(self, question):
        m = re.search(r"empieza\s+por\s+([A-ZÁÉÍÓÚÀÈÌÒÙÑÇ])", _clean_question(question), re.I)
        if not m:
            return None
        initial = _strip_accents(m.group(1).upper())
        rows = [_as_dict(r) for r in self.conn.execute(
            "SELECT id, name, given_name, birth_year, death_year, birth_place, photo_file, is_alive FROM people WHERE given_name IS NOT NULL ORDER BY birth_year, name LIMIT 500"
        ).fetchall()]
        filtered=[r for r in rows if _strip_accents((r.get('given_name') or '').strip()).upper().startswith(initial)]
        answer = self._list_people_answer(f"Las personas cuyo nombre de pila empieza por {m.group(1).upper()} son", filtered)
        return {"answer": answer, "people_mentioned": [r['id'] for r in filtered], "people_with_photos": self._people_payload(filtered[:25])}

    def handle_first_surname(self, question):
        m = re.search(r"tienen\s+(.+?)\s+como\s+primer\s+apellido", _clean_question(question), re.I)
        if not m:
            return None
        surname = _normalize_name_fragment(m.group(1))
        rows = [_as_dict(r) for r in self.conn.execute(
            "SELECT id, name, birth_year, death_year, birth_place, photo_file, is_alive FROM people WHERE NORMALIZE(surname) = NORMALIZE(?) OR NORMALIZE(surname) LIKE NORMALIZE(?) || '%' ORDER BY birth_year, name LIMIT 200",
            (surname, surname),
        ).fetchall()]
        answer = self._list_people_answer(f"Las personas con {surname} como primer apellido son", rows)
        return {"answer": answer, "people_mentioned": [r['id'] for r in rows], "people_with_photos": self._people_payload(rows[:25])}

    def handle_birth_and_death_place_people(self, question):
        m = re.search(r"nacieron\s+y\s+murieron\s+en\s+(.+?)(?:\?|$)", _clean_question(question), re.I)
        if not m:
            return None
        place = m.group(1).strip()
        rows = [_as_dict(r) for r in self.conn.execute(
            "SELECT id, name, birth_year, death_year, birth_place, death_place, photo_file, is_alive FROM people WHERE NORMALIZE(birth_place) LIKE '%' || NORMALIZE(?) || '%' AND NORMALIZE(death_place) LIKE '%' || NORMALIZE(?) || '%' ORDER BY birth_year, name LIMIT 100",
            (place, place),
        ).fetchall()]
        answer = self._list_people_answer(f"Las personas nacidas y fallecidas en {place} fueron", rows)
        return {"answer": answer, "people_mentioned": [r['id'] for r in rows], "people_with_photos": self._people_payload(rows[:25])}

    def handle_occupation_field(self, question):
        m = re.search(r"(?:registrada\s+para|occupation\s+for)\s+(.+?)(?:\?|$)", _clean_question(question), re.I)
        if not m:
            return None
        person,_ = self._resolve_person(m.group(1))
        if not person:
            return None
        occupations=[_as_dict(o) for o in get_occupations(self.conn, person['id'])]
        if not occupations:
            answer=f"No constan ocupaciones o actividades registradas para {person['name']}."
        else:
            parts=[]
            for o in occupations:
                t=o['title']
                if o.get('date'): t += f" ({o['date']})"
                if o.get('place'): t += f" en {o['place']}"
                parts.append(t)
            answer=f"Las ocupaciones o actividades registradas para {person['name']} fueron: " + "; ".join(parts) + "."
        return {"answer": answer, "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}

    def handle_residence_field(self, question):
        m = re.search(r"documentado\s+(.+?)(?:\?|$)", _clean_question(question), re.I)
        if not m:
            return None
        person,_ = self._resolve_person(m.group(1))
        if not person:
            return None
        residences=[_as_dict(r) for r in get_residences(self.conn, person['id'])]
        if not residences:
            answer=f"No constan residencias o direcciones documentadas de {person['name']}."
        else:
            parts=[]
            for r in residences:
                frag = r.get('address') or ''
                if r.get('address2'): frag += (' ' if frag else '') + r['address2']
                if r.get('city'): frag += (', ' if frag else '') + r['city']
                if r.get('country'): frag += (', ' if frag else '') + r['country']
                if r.get('date'): frag += f" ({r['date']})"
                parts.append(frag)
            answer=f"Las residencias o direcciones documentadas de {person['name']} fueron: " + "; ".join(parts) + "."
        return {"answer": answer, "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}

    def handle_notes_field(self, question):
        q = _clean_question(question)
        m = (re.search(r"(?:notas?|apuntes?)\s+(?:biogr[aá]ficas?\s+)?de\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"asociadas\s+a\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"(?:qu[eé]\s+)?notas?\s+(?:hay\s+)?(?:sobre|de)\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"observaciones?\s+(?:biogr[aá]ficas?\s+)?(?:de|sobre|aparecen\s+(?:en|para))\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"(?:qu[eé]\s+)?(?:anotaciones?|comentarios?|apuntes?|detalles?\s+biogr[aá]ficos?|informaci[oó]n\s+adicional|texto)\s+(?:hay\s+)?(?:sobre|de|para)\s+(.+?)(?:\?|$)", q, re.I))
        if not m:
            return None
        person,_ = self._resolve_person(m.group(1))
        if not person:
            return None
        notes=[_as_dict(n) for n in get_notes(self.conn, person['id'])]
        if not notes:
            answer=f"No constan notas biográficas asociadas a {person['name']}."
        else:
            parts=[]
            for n in notes[:3]:
                c=n['content']
                if len(c)>220: c=c[:220]+'...'
                parts.append(c)
            answer=f"Las notas biográficas asociadas a {person['name']} son: " + " | ".join(parts)
        return {"answer": answer, "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}

    def handle_birth_date_search(self, question):
        parts = self._extract_date_parts(question)
        if not parts:
            return None
        day,month,year = parts
        rows=[_as_dict(r) for r in self.conn.execute(
            "SELECT id, name, birth_year, death_year, birth_place, photo_file, is_alive FROM people WHERE birth_day = ? AND birth_month = ? AND birth_year = ? ORDER BY name",
            (day,month,year),
        ).fetchall()]
        if not rows:
            answer=f"No he encontrado ninguna persona nacida el {day:02d}/{month:02d}/{year}."
        elif len(rows)==1:
            r=rows[0]
            place=f" en {r['birth_place']}" if r.get('birth_place') else ''
            answer=f"La persona nacida el {day:02d}/{month:02d}/{year} fue {r['name']}{place}."
        else:
            answer=self._list_people_answer(f"Las personas nacidas el {day:02d}/{month:02d}/{year} fueron", rows)
        return {"answer": answer, "people_mentioned": [r['id'] for r in rows], "people_with_photos": self._people_payload(rows)}

    def handle_death_date_search(self, question):
        parts = self._extract_date_parts(question)
        if not parts:
            return None
        day,month,year=parts
        candidates=[_as_dict(r) for r in self.conn.execute(
            "SELECT id, name, death_date, death_year, death_place, photo_file, is_alive FROM people WHERE death_year = ? ORDER BY name",
            (year,),
        ).fetchall()]
        rows=[r for r in candidates if self._date_matches_text(r.get('death_date') or '', day, month, year)]
        if not rows:
            answer=f"No he encontrado ninguna persona fallecida el {day:02d}/{month:02d}/{year}."
        elif len(rows)==1:
            r=rows[0]
            place=f" en {r['death_place']}" if r.get('death_place') else ''
            answer=f"La persona fallecida el {day:02d}/{month:02d}/{year} fue {r['name']}{place}."
        else:
            answer=self._list_people_answer(f"Las personas fallecidas el {day:02d}/{month:02d}/{year} fueron", rows)
        return {"answer": answer, "people_mentioned": [r['id'] for r in rows], "people_with_photos": self._people_payload(rows)}

    def handle_birth_place_year_search(self, question):
        m = re.search(r"naci[oó]\s+en\s+(.+?)\s+en\s+(\d{4})(?:\?|$)", _clean_question(question), re.I)
        if not m:
            return None
        place = m.group(1).strip(); year = int(m.group(2))
        rows=[_as_dict(r) for r in self.conn.execute(
            "SELECT id, name, birth_year, death_year, birth_place, photo_file, is_alive FROM people WHERE birth_year = ? AND NORMALIZE(birth_place) LIKE '%' || NORMALIZE(?) || '%' ORDER BY name",
            (year, place),
        ).fetchall()]
        if not rows:
            answer=f"No he encontrado ninguna persona nacida en {place} en {year}."
        elif len(rows)==1:
            answer=f"La persona nacida en {place} en {year} fue {rows[0]['name']}."
        else:
            answer=self._list_people_answer(f"Las personas nacidas en {place} en {year} fueron", rows)
        return {"answer": answer, "people_mentioned": [r['id'] for r in rows], "people_with_photos": self._people_payload(rows)}

    def handle_death_place_year_search(self, question):
        m = re.search(r"muri[oó]\s+en\s+(.+?)\s+en\s+(\d{4})(?:\?|$)", _clean_question(question), re.I)
        if not m:
            return None
        place = m.group(1).strip(); year = int(m.group(2))
        rows=[_as_dict(r) for r in self.conn.execute(
            "SELECT id, name, death_year, death_place, photo_file, is_alive FROM people WHERE death_year = ? AND NORMALIZE(death_place) LIKE '%' || NORMALIZE(?) || '%' ORDER BY name",
            (year, place),
        ).fetchall()]
        if not rows:
            answer=f"No he encontrado ninguna persona fallecida en {place} en {year}."
        elif len(rows)==1:
            answer=f"La persona fallecida en {place} en {year} fue {rows[0]['name']}."
        else:
            answer=self._list_people_answer(f"Las personas fallecidas en {place} en {year} fueron", rows)
        return {"answer": answer, "people_mentioned": [r['id'] for r in rows], "people_with_photos": self._people_payload(rows)}

    def handle_compound_given_name(self, question):
        m = re.search(r"compuesto\s+como\s+(.+?)(?:\?|$)", _clean_question(question), re.I)
        if not m:
            return None
        name = m.group(1).strip()
        rows=[_as_dict(r) for r in self.conn.execute(
            "SELECT id, name, given_name, birth_year, death_year, birth_place, photo_file, is_alive FROM people WHERE NORMALIZE(given_name) LIKE NORMALIZE(?) || '%' ORDER BY birth_year, name LIMIT 100",
            (name,),
        ).fetchall()]
        answer=self._list_people_answer(f"Las personas con un nombre compuesto como {name} son", rows)
        return {"answer": answer, "people_mentioned": [r['id'] for r in rows], "people_with_photos": self._people_payload(rows[:25])}

    def handle_record_lookup(self, question):
        m = re.search(r"corresponde\s+a\s+(.+?)(?:\?|$)", _clean_question(question), re.I)
        if not m:
            return None
        person, matches = self._resolve_person(m.group(1))
        if not person:
            return None
        if len(matches) > 1:
            answer = "He encontrado varias coincidencias para ese registro: " + ", ".join(_person_brief(x) for x in matches[:10]) + "."
            return {"answer": answer, "people_mentioned": [x['id'] for x in matches[:10]], "people_with_photos": self._people_payload(matches[:10])}
        return self._build_info_response(person)

    def handle_birth_place_people(self, question):
        place = self._extract_place_after(question, r"(?:personas\s+nacieron\s+en|people\s+were\s+born\s+in)\s+(.+?)(?:\?|$)")
        if not place:
            return None
        rows=[_as_dict(r) for r in self.conn.execute(
            "SELECT id, name, birth_year, death_year, birth_place, photo_file, is_alive FROM people WHERE NORMALIZE(birth_place) LIKE '%' || NORMALIZE(?) || '%' ORDER BY birth_year, name LIMIT 100",
            (place,),
        ).fetchall()]
        answer=self._list_people_answer(f"Las personas nacidas en {place} fueron", rows)
        return {"answer": answer, "people_mentioned": [r['id'] for r in rows], "people_with_photos": self._people_payload(rows[:25])}


    def _all_people_basic(self):
        rows = self.conn.execute(
            "SELECT id, name, birth_year, death_year, birth_place, death_place, surname, given_name, father_id, mother_id, photo_file, is_alive, sex "
            "FROM people"
        ).fetchall()
        return [_as_dict(r) for r in rows]

    def _children_count(self, person_id: str) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM children WHERE parent_id = ?", (person_id,)).fetchone()
        return int(row[0]) if row else 0

    def _distinct_parent_ids(self):
        return [r[0] for r in self.conn.execute("SELECT DISTINCT parent_id FROM children").fetchall() if r[0]]

    def _couple_rows(self):
        rows = self.conn.execute(
            "SELECT m.person1_id, m.person2_id, m.date, m.place, p1.name AS person1_name, p2.name AS person2_name "
            "FROM marriages m "
            "LEFT JOIN people p1 ON p1.id = m.person1_id "
            "LEFT JOIN people p2 ON p2.id = m.person2_id"
        ).fetchall()
        return [_as_dict(r) for r in rows]

    def _couple_children_count_rows(self):
        out = []
        for r in self._couple_rows():
            kids = self._shared_children(r["person1_id"], r["person2_id"])
            out.append({**r, "children_count": len(kids), "children": kids})
        out.sort(key=lambda x: (-x["children_count"], _norm_cmp((x.get("person1_name") or "") + " " + (x.get("person2_name") or ""))))
        return out

    def _couple_descendants_count(self, p1_id: str, p2_id: str) -> int:
        roots = [c["id"] for c in self._shared_children(p1_id, p2_id)]
        seen = set()
        queue = list(roots)
        while queue:
            current = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            for row in self.conn.execute("SELECT child_id FROM children WHERE parent_id = ?", (current,)).fetchall():
                cid = row[0]
                if cid and cid not in seen:
                    queue.append(cid)
        return len(seen)

    def _rank_position(self, sorted_values, target_value):
        rank = 1
        prev = None
        for idx, val in enumerate(sorted_values):
            if idx == 0:
                prev = val
            elif val != prev:
                rank = idx + 1
                prev = val
            if val == target_value:
                return rank
        return None

    def handle_max_children_person(self, question):
        rows = self.conn.execute(
            "SELECT p.*, COUNT(c.child_id) AS n_children FROM people p JOIN children c ON p.id = c.parent_id "
            "GROUP BY p.id ORDER BY n_children DESC, p.birth_year, p.name LIMIT 1"
        ).fetchall()
        if not rows:
            return None
        person = _as_dict(rows[0])
        answer = f"La persona con más hijos registrados en el árbol es {person['name']}, con {person['n_children']} hijos documentados."
        return {"answer": answer, "people_mentioned": [person["id"]], "people_with_photos": self._people_payload([person])}

    def handle_descendance_rank(self, question):
        m = re.search(r"sit[uú]a\s+(.+?)(?:\?|$)", _clean_question(question), re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        parent_ids = self._distinct_parent_ids()
        counts = {pid: self._all_descendants_count(pid) for pid in parent_ids}
        counts[person["id"]] = self._all_descendants_count(person["id"])
        values = sorted(counts.values(), reverse=True)
        rank = self._rank_position(values, counts[person["id"]])
        answer = f"{person['name']} se sitúa en el puesto {rank} del ranking de descendencia, con {counts[person['id']]} descendientes documentados."
        return {"answer": answer, "people_mentioned": [person["id"]], "people_with_photos": self._people_payload([person])}

    def handle_children_vs_average(self, question):
        m = re.search(r"cu[aá]ntos?\s+hijos\s+tuvo\s+(.+?)\s+en\s+comparaci[oó]n\s+con\s+la\s+media", _clean_question(question), re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        own = self._children_count(person["id"])
        parent_ids = self._distinct_parent_ids()
        values = [self._children_count(pid) for pid in parent_ids] if parent_ids else []
        avg = sum(values) / len(values) if values else 0
        cmp = "por encima" if own > avg else "por debajo" if own < avg else "en la media"
        answer = f"{person['name']} tuvo {own} hijos. La media del árbol entre personas con descendencia documentada es {avg:.1f}, así que está {cmp}."
        return {"answer": answer, "people_mentioned": [person["id"]], "people_with_photos": self._people_payload([person])}

    def handle_siblings_vs_generation(self, question):
        m = re.search(r"cu[aá]ntos?\s+hermanos\s+ten[ií]a\s+(.+?)\s+y\s+c[oó]mo\s+se\s+compara", _clean_question(question), re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        own = len([_as_dict(s) for s in get_siblings(self.conn, person["id"])])
        decade = (person.get("birth_year") // 10) * 10 if person.get("birth_year") else None
        cohort = []
        if decade is not None:
            rows = self.conn.execute("SELECT id FROM people WHERE birth_year BETWEEN ? AND ? AND father_id IS NOT NULL AND mother_id IS NOT NULL", (decade, decade + 9)).fetchall()
            for r in rows:
                cohort.append(len([_as_dict(s) for s in get_siblings(self.conn, r["id"])]))
        if cohort:
            avg = sum(cohort) / len(cohort)
            cmp = "por encima" if own > avg else "por debajo" if own < avg else "en la media"
            answer = f"{person['name']} tenía {own} hermanos. Entre personas de su misma década de nacimiento, la media es {avg:.1f}, así que está {cmp}."
        else:
            answer = f"{person['name']} tenía {own} hermanos."
        return {"answer": answer, "people_mentioned": [person["id"]], "people_with_photos": self._people_payload([person])}

    def handle_longevity_rank(self, question):
        m = re.search(r"edad\s+vivi[oó]\s+(.+?)\s+y\s+est[aá]\s+entre", _clean_question(question), re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        age = self._age_from_years(person.get("birth_year"), person.get("death_year"))
        if age is None:
            return {"answer": f"No puedo calcular con fiabilidad la longevidad de {person['name']} porque faltan años de nacimiento o defunción.", "people_mentioned": [person["id"]], "people_with_photos": self._people_payload([person])}
        rows = self.conn.execute("SELECT id, name, birth_year, death_year, photo_file FROM people WHERE birth_year IS NOT NULL AND death_year IS NOT NULL").fetchall()
        ages = [(r["id"], r["name"], r["death_year"] - r["birth_year"]) for r in rows]
        ages.sort(key=lambda x: (-x[2], _norm_cmp(x[1])))
        rank = self._rank_position([a[2] for a in ages], age)
        answer = f"{person['name']} vivió aproximadamente {age} años y ocupa el puesto {rank} entre las longevidades más altas documentadas del árbol."
        return {"answer": answer, "people_mentioned": [person["id"]], "people_with_photos": self._people_payload([person])}

    def handle_age_first_child_vs_average(self, question):
        m = re.search(r"edad\s+ten[ií]a\s+(.+?)\s+cuando\s+naci[oó]\s+su\s+primer\s+hijo", _clean_question(question), re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        children = self._children_rows_for_parent(person["id"])
        first = next((c for c in children if c.get("birth_year") is not None), None)
        if not first:
            return {"answer": f"No constan hijos con año de nacimiento conocido para {person['name']}.", "people_mentioned": [person["id"]], "people_with_photos": self._people_payload([person])}
        own_age = self._age_from_years(person.get("birth_year"), first.get("birth_year"))
        if own_age is None:
            return {"answer": f"No puedo calcular con fiabilidad la edad de {person['name']} al nacer su primer hijo porque faltan años.", "people_mentioned": [person["id"], first["id"]], "people_with_photos": self._people_payload([person, first])}
        values = []
        for pid in self._distinct_parent_ids():
            prow = _as_dict(get_person(self.conn, pid))
            if not prow or prow.get("birth_year") is None:
                continue
            kids = self._children_rows_for_parent(pid)
            fk = next((c for c in kids if c.get("birth_year") is not None), None)
            if fk and fk.get("birth_year") is not None:
                age = self._age_from_years(prow.get("birth_year"), fk.get("birth_year"))
                if age is not None:
                    values.append(age)
        avg = sum(values) / len(values) if values else None
        cmp = "por encima" if avg is not None and own_age > avg else "por debajo" if avg is not None and own_age < avg else "en la media"
        answer = f"{person['name']} tenía aproximadamente {own_age} años cuando nació su primer hijo."
        if avg is not None:
            answer += f" La media del árbol es {avg:.1f}, así que está {cmp}."
        return {"answer": answer, "people_mentioned": [person["id"], first["id"]], "people_with_photos": self._people_payload([person, first])}

    def handle_couple_exact_children_rank(self, question):
        m = re.search(r"exactamente\s+(\d+)\s+hijos", _clean_question(question), re.I)
        if not m:
            return None
        target = int(m.group(1))
        rows = self._couple_children_count_rows()
        exact = [r for r in rows if r["children_count"] == target]
        if not exact:
            return {"answer": f"No he encontrado ninguna pareja con exactamente {target} hijos documentados.", "people_mentioned": [], "people_with_photos": []}
        row = exact[0]
        values = [r["children_count"] for r in rows]
        rank = self._rank_position(values, target)
        answer = f"La primera pareja que encuentro con exactamente {target} hijos es {row.get('person1_name')} y {row.get('person2_name')}. Con {target} hijos, ocupa el puesto {rank} por tamaño familiar."
        people = []
        for pid in [row["person1_id"], row["person2_id"]]:
            p = _as_dict(get_person(self.conn, pid))
            if p:
                people.append(p)
        return {"answer": answer, "people_mentioned": [p["id"] for p in people], "people_with_photos": self._people_payload(people)}

    def handle_birth_place_share(self, question):
        m = re.search(r"nacieron\s+en\s+(.+?)\s+y\s+qu[eé]\s+peso\s+tiene", _clean_question(question), re.I)
        if not m:
            return None
        place = m.group(1).strip()
        total = self.conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
        count = self.conn.execute("SELECT COUNT(*) FROM people WHERE NORMALIZE(birth_place) LIKE '%' || NORMALIZE(?) || '%'", (place,)).fetchone()[0]
        pct = (count / total * 100) if total else 0
        return {"answer": f"{count} personas nacieron en {place}. Eso representa aproximadamente el {pct:.1f}% del árbol.", "people_mentioned": [], "people_with_photos": []}

    def handle_death_place_share(self, question):
        m = re.search(r"murieron\s+en\s+(.+?)\s+y\s+qu[eé]\s+relevancia\s+tiene", _clean_question(question), re.I)
        if not m:
            return None
        place = m.group(1).strip()
        total = self.conn.execute("SELECT COUNT(*) FROM people WHERE death_place IS NOT NULL AND death_place != ''").fetchone()[0]
        count = self.conn.execute("SELECT COUNT(*) FROM people WHERE NORMALIZE(death_place) LIKE '%' || NORMALIZE(?) || '%'", (place,)).fetchone()[0]
        pct = (count / total * 100) if total else 0
        return {"answer": f"{count} personas murieron en {place}. Sobre el conjunto de defunciones con lugar conocido, eso representa aproximadamente el {pct:.1f}%.", "people_mentioned": [], "people_with_photos": []}

    def handle_births_by_decade(self, question):
        m = re.search(r"d[eé]cada\s+de\s+(\d{4})", _clean_question(question), re.I)
        if not m:
            return None
        decade = int(m.group(1))
        count = self.conn.execute("SELECT COUNT(*) FROM people WHERE birth_year BETWEEN ? AND ?", (decade, decade+9)).fetchone()[0]
        return {"answer": f"Hay {count} nacimientos registrados en la década de {decade}.", "people_mentioned": [], "people_with_photos": []}

    def handle_deaths_by_decade(self, question):
        m = re.search(r"d[eé]cada\s+de\s+(\d{4})", _clean_question(question), re.I)
        if not m:
            return None
        decade = int(m.group(1))
        count = self.conn.execute("SELECT COUNT(*) FROM people WHERE death_year BETWEEN ? AND ?", (decade, decade+9)).fetchone()[0]
        return {"answer": f"Hay {count} fallecimientos registrados en la década de {decade}.", "people_mentioned": [], "people_with_photos": []}

    def handle_first_surname_percentage(self, question):
        m = re.search(r"primer\s+apellido\s+(.+?)(?:\?|$)", _clean_question(question), re.I)
        if not m:
            return None
        surname = _normalize_name_fragment(m.group(1))
        total = self.conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
        count = self.conn.execute("SELECT COUNT(*) FROM people WHERE NORMALIZE(surname) = NORMALIZE(?) OR NORMALIZE(surname) LIKE NORMALIZE(?) || '%'", (surname, surname)).fetchone()[0]
        pct = (count / total * 100) if total else 0
        return {"answer": f"Aproximadamente {count} personas tienen {surname} como primer apellido, lo que supone alrededor del {pct:.1f}% del árbol.", "people_mentioned": [], "people_with_photos": []}

    def handle_known_birth_date_stats(self, question):
        known = self.conn.execute("SELECT COUNT(*) FROM people WHERE birth_year IS NOT NULL").fetchone()[0]
        total = self.conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
        unknown = total - known
        return {"answer": f"{known} personas tienen fecha o año de nacimiento informado y {unknown} no lo tienen.", "people_mentioned": [], "people_with_photos": []}

    def handle_compare_births(self, question):
        m = re.search(r"nacimiento\s+de\s+(.+?)\s+o\s+el\s+de\s+(.+?)(?:\?|$)", _clean_question(question), re.I)
        if not m:
            return None
        a, _ = self._resolve_person(m.group(1))
        b, _ = self._resolve_person(m.group(2))
        if not a or not b:
            return None
        ay, by = a.get("birth_year"), b.get("birth_year")
        if ay is None or by is None:
            return {"answer": f"No puedo comparar con fiabilidad los nacimientos de {a['name']} y {b['name']} porque faltan años.", "people_mentioned": [a["id"], b["id"]], "people_with_photos": self._people_payload([a, b])}
        if ay < by:
            answer = f"El nacimiento anterior fue el de {a['name']} ({ay})."
        elif by < ay:
            answer = f"El nacimiento anterior fue el de {b['name']} ({by})."
        else:
            answer = f"{a['name']} y {b['name']} nacieron en el mismo año ({ay})."
        return {"answer": answer, "people_mentioned": [a["id"], b["id"]], "people_with_photos": self._people_payload([a,b])}

    def handle_branch_vs_next_couple(self, question):
        m = re.search(r"formada\s+por\s+(.+?)\s+y\s+(.+?)\s+o\s+la\s+siguiente\s+pareja", _clean_question(question), re.I)
        if not m:
            return None
        p1, _ = self._resolve_person(m.group(1))
        p2, _ = self._resolve_person(m.group(2))
        if not p1 or not p2:
            return None
        rows = self._couple_children_count_rows()
        target_idx = None
        for idx, row in enumerate(rows):
            if {row["person1_id"], row["person2_id"]} == {p1["id"], p2["id"]}:
                target_idx = idx
                target = row
                break
        if target_idx is None:
            return {"answer": f"No encuentro esa pareja en el ranking de familias con hijos documentados.", "people_mentioned": [p1["id"], p2["id"]], "people_with_photos": self._people_payload([p1,p2])}
        answer = f"La pareja formada por {p1['name']} y {p2['name']} tuvo {target['children_count']} hijos."
        if target_idx + 1 < len(rows):
            nxt = rows[target_idx + 1]
            answer += f" La siguiente pareja en el ranking es {nxt.get('person1_name')} y {nxt.get('person2_name')}, con {nxt['children_count']} hijos."
        return {"answer": answer, "people_mentioned": [p1["id"], p2["id"]], "people_with_photos": self._people_payload([p1,p2])}

    def handle_birth_place_variants(self, question):
        rows = self.conn.execute("SELECT birth_place FROM people WHERE birth_place IS NOT NULL AND birth_place != ''").fetchall()
        counts = {}
        for r in rows:
            place = (r[0] or "").strip()
            key = _norm_cmp(place.split(",")[0])
            counts.setdefault(key, set()).add(place)
        if not counts:
            return None
        key, variants = max(counts.items(), key=lambda kv: len(kv[1]))
        shown = sorted(variants)[:5]
        answer = f"El topónimo con más variantes de escritura parece ser '{shown[0]}', con {len(variants)} variantes registradas. Ejemplos: " + "; ".join(shown) + "."
        return {"answer": answer, "people_mentioned": [], "people_with_photos": []}

    def handle_marriage_max_descendants(self, question):
        rows = self._couple_rows()
        best = None
        best_count = -1
        for row in rows:
            cnt = self._couple_descendants_count(row["person1_id"], row["person2_id"])
            if cnt > best_count:
                best = row
                best_count = cnt
        if not best:
            return None
        people = []
        for pid in [best["person1_id"], best["person2_id"]]:
            p = _as_dict(get_person(self.conn, pid))
            if p:
                people.append(p)
        answer = f"El matrimonio con más descendencia documentada es {best.get('person1_name')} y {best.get('person2_name')}, con {best_count} descendientes documentados desde su unión."
        return {"answer": answer, "people_mentioned": [p["id"] for p in people], "people_with_photos": self._people_payload(people)}


    def handle_max_longevity_person(self, question):
        rows = self.conn.execute(
            "SELECT id, name, birth_year, death_year, photo_file "
            "FROM people "
            "WHERE birth_year IS NOT NULL AND death_year IS NOT NULL AND death_year >= birth_year "
            "ORDER BY (death_year - birth_year) DESC, birth_year ASC, name ASC LIMIT 1"
        ).fetchall()
        if not rows:
            return {"answer": "No puedo determinar la persona más longeva porque faltan fechas de nacimiento o defunción suficientes.", "people_mentioned": [], "people_with_photos": []}
        person = _as_dict(rows[0])
        age = person["death_year"] - person["birth_year"]
        answer = f"La persona más longeva del árbol es {person['name']}, con una longevidad documentada aproximada de {age} años."
        return {"answer": answer, "people_mentioned": [person["id"]], "people_with_photos": self._people_payload([person])}

    def handle_average_children(self, question):
        parent_ids = self._distinct_parent_ids()
        if not parent_ids:
            return {"answer": "No hay suficiente información para calcular la media de hijos.", "people_mentioned": [], "people_with_photos": []}
        values = [self._children_count(pid) for pid in parent_ids]
        avg = sum(values) / len(values) if values else 0
        answer = f"La media de hijos es de {avg:.1f} por persona con descendencia documentada."
        return {"answer": answer, "people_mentioned": [], "people_with_photos": []}

    def handle_sex_balance(self, question):
        male = self.conn.execute("SELECT COUNT(*) FROM people WHERE sex = 'M'").fetchone()[0]
        female = self.conn.execute("SELECT COUNT(*) FROM people WHERE sex = 'F'").fetchone()[0]
        unknown = self.conn.execute("SELECT COUNT(*) FROM people WHERE sex IS NULL OR sex NOT IN ('M','F')").fetchone()[0]
        if male > female:
            lead = male - female
            answer = f"Hay más hombres que mujeres: {male} hombres frente a {female} mujeres."
        elif female > male:
            lead = female - male
            answer = f"Hay más mujeres que hombres: {female} mujeres frente a {male} hombres."
        else:
            answer = f"Hay el mismo número de hombres y mujeres: {male} y {female}, respectivamente."
        if unknown:
            answer += f" Además, {unknown} personas no tienen el sexo informado."
        return {"answer": answer, "people_mentioned": [], "people_with_photos": []}

    def handle_youngest_person(self, question):
        # Prioriza la fecha más reciente de nacimiento; si no existe día/mes, usa el año.
        row = self.conn.execute(
            "SELECT id, name, birth_year, birth_month, birth_day, photo_file "
            "FROM people "
            "WHERE birth_year IS NOT NULL "
            "ORDER BY birth_year DESC, COALESCE(birth_month, 0) DESC, COALESCE(birth_day, 0) DESC, name ASC LIMIT 1"
        ).fetchone()
        if not row:
            return {"answer": "No puedo determinar la persona más joven porque faltan fechas de nacimiento.", "people_mentioned": [], "people_with_photos": []}
        person = _as_dict(row)
        answer = f"La persona más joven del árbol es {person['name']}"
        if person.get("birth_year"):
            if person.get("birth_month") and person.get("birth_day"):
                answer += f", nacida el {person['birth_day']:02d}/{person['birth_month']:02d}/{person['birth_year']}."
            else:
                answer += f", nacida en {person['birth_year']}."
        else:
            answer += "."
        return {"answer": answer, "people_mentioned": [person["id"]], "people_with_photos": self._people_payload([person])}


    def _descendants_at_generation(self, person_id: str, generation: int):
        if generation < 1:
            return []
        current = [person_id]
        seen = set()
        for _ in range(generation):
            next_ids = []
            for pid in current:
                for row in self.conn.execute("SELECT child_id FROM children WHERE parent_id = ?", (pid,)).fetchall():
                    cid = row[0]
                    if cid and cid not in seen:
                        next_ids.append(cid)
                        seen.add(cid)
            current = next_ids
            if not current:
                break
        if not current:
            return []
        placeholders = ",".join("?" for _ in current)
        rows = self.conn.execute(f"SELECT * FROM people WHERE id IN ({placeholders})", current).fetchall()
        return _sort_people([_as_dict(r) for r in rows])

    def _ancestors_at_generation(self, person_id: str, generation: int):
        if generation < 1:
            return []
        current = [person_id]
        seen = set()
        for _ in range(generation):
            next_ids = []
            for pid in current:
                p = _as_dict(get_person(self.conn, pid)) if pid else None
                if not p:
                    continue
                for par in [p.get('father_id'), p.get('mother_id')]:
                    if par and par not in seen:
                        next_ids.append(par)
                        seen.add(par)
            current = next_ids
            if not current:
                break
        if not current:
            return []
        placeholders = ",".join("?" for _ in current)
        rows = self.conn.execute(f"SELECT * FROM people WHERE id IN ({placeholders})", current).fetchall()
        return _sort_people([_as_dict(r) for r in rows])

    def _is_second_cousin(self, a, b) -> bool:
        a = _as_dict(a); b = _as_dict(b)
        if not a or not b or a['id'] == b['id']:
            return False
        ag = {x['id'] for x in self._ancestors_at_generation(a['id'], 3)}
        bg = {x['id'] for x in self._ancestors_at_generation(b['id'], 3)}
        return bool(ag and bg and ag.intersection(bg)) and not self._is_first_cousin(a, b) and not self._same_parents(a, b)

    def _second_cousins_for(self, person_id: str):
        person = _as_dict(get_person(self.conn, person_id))
        if not person:
            return []
        rows = []
        for cand in self._all_people_basic():
            if cand['id'] != person_id and self._is_second_cousin(person, cand):
                rows.append(cand)
        return _sort_people(rows)

    def _children_in_law_for(self, person_id: str, sex: Optional[str] = None):
        out = []
        children = self._children_rows_for_parent(person_id)
        for child in children:
            for s in get_spouses(self.conn, child['id']):
                sp = _as_dict(s['person'])
                if not sp:
                    continue
                if sex and sp.get('sex') != sex:
                    continue
                out.append(sp)
        return _sort_people(out)

    def _consuegros_for(self, person_id: str):
        out = []
        children = self._children_rows_for_parent(person_id)
        for child in children:
            for s in get_spouses(self.conn, child['id']):
                sp = _as_dict(s['person'])
                if not sp:
                    continue
                sf = self._get_parent(sp, 'father')
                sm = self._get_parent(sp, 'mother')
                if sf:
                    out.append(sf)
                if sm:
                    out.append(sm)
        return _sort_people(out)

    def _siblings_in_law_for(self, person_id: str):
        out = []
        person = _as_dict(get_person(self.conn, person_id))
        if not person:
            return []
        # hermanos de los cónyuges
        for s in get_spouses(self.conn, person_id):
            sp = _as_dict(s['person'])
            if sp:
                out.extend([_as_dict(x) for x in get_siblings(self.conn, sp['id'])])
        # cónyuges de los hermanos propios
        for sib in get_siblings(self.conn, person_id):
            sib = _as_dict(sib)
            if not sib:
                continue
            for s in get_spouses(self.conn, sib['id']):
                sp = _as_dict(s['person'])
                if sp:
                    out.append(sp)
        return _sort_people(out)

    def _great_uncles_for(self, person_id: str):
        rows = []
        gps = self._ancestors_at_generation(person_id, 2)
        for gp in gps:
            rows.extend([_as_dict(x) for x in get_siblings(self.conn, gp['id'])])
        return _sort_people(rows)

    def _great_great_uncle_for(self, person_id: str):
        rows = []
        ggps = self._ancestors_at_generation(person_id, 3)
        for ggp in ggps:
            rows.extend([_as_dict(x) for x in get_siblings(self.conn, ggp['id'])])
        return _sort_people(rows)

    def _grandnephews_for(self, person_id: str):
        rows = []
        for sib in get_siblings(self.conn, person_id):
            sib = _as_dict(sib)
            if not sib:
                continue
            nephews = self._children_rows_for_parent(sib['id'])
            for n in nephews:
                rows.extend(self._children_rows_for_parent(n['id']))
        return _sort_people(rows)

    def handle_birth_and_death_same_place_natural(self, question):
        q = _clean_question(question)
        m = re.search(r"nacieron\s+en\s+(.+?)\s+y\s+tamb[ié]n\s+murieron\s+all[ií](?:\?|$)", q, re.I)
        if not m:
            return None
        place = m.group(1).strip()
        rows = [_as_dict(r) for r in self.conn.execute(
            "SELECT id,name,birth_year,death_year,birth_place,death_place,photo_file,is_alive FROM people WHERE NORMALIZE(birth_place) LIKE '%' || NORMALIZE(?) || '%' AND NORMALIZE(death_place) LIKE '%' || NORMALIZE(?) || '%' ORDER BY birth_year,name LIMIT 200",
            (place, place)
        ).fetchall()]
        return {"answer": self._list_people_answer(f"Las personas nacidas en {place} y fallecidas allí fueron", rows), "people_mentioned": [r['id'] for r in rows], "people_with_photos": self._people_payload(rows[:25])}

    def handle_consuegros(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            q = _clean_question(question)
            m = re.search(r"consuegros\s+de\s+(.+?)(?:\?|$)", q, re.I) or re.search(r"ver\s+si\s+(.+?)\s+ten[ií]a\s+consuegros\s+documentados(?:\?|$)", q, re.I)
            subject = m.group(1) if m else None
        if not subject:
            return None
        person,_ = self._resolve_person(subject)
        if not person:
            return None
        rows = self._consuegros_for(person['id'])
        if rows:
            ans = self._list_people_answer(f"Los consuegros de {_person_link(person)} son", rows)
        else:
            ans = f"No constan consuegros documentados de {_person_link(person)}."
        return {"answer": ans, "people_mentioned": [person['id']] + [r['id'] for r in rows], "people_with_photos": self._people_payload([person] + rows[:25])}

    def handle_second_cousins(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        rows = self._second_cousins_for(person['id'])
        if not rows:
            return {"answer": f"No constan primos segundos documentados de {_person_link(person)}.", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        return {"answer": self._list_people_answer(f"Los primos segundos de {_person_link(person)} son", rows), "people_mentioned": [person['id']] + [r['id'] for r in rows], "people_with_photos": self._people_payload([person] + rows[:25])}

    def handle_daughters_in_law(self, question):
        q = _clean_question(question)
        m = re.search(r"n[oó]mbrame\s+(?:las\s+)?nueras\s+de\s+(.+?)(?:\?|$)", q, re.I) or re.search(r"nueras?\s+de\s+(.+?)(?:\?|$)", q, re.I) or re.search(r"tuvo\s+(.+?)\s+alguna\s+nuera(?:\?|$)", q, re.I)
        if not m:
            return None
        person,_ = self._resolve_person(m.group(1))
        if not person:
            return None
        rows = self._children_in_law_for(person['id'], sex='F')
        if not rows:
            return {"answer": f"No constan nueras documentadas de {_person_link(person)}.", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        return {"answer": self._list_people_answer(f"Las nueras de {_person_link(person)} son", rows), "people_mentioned": [person['id']] + [r['id'] for r in rows], "people_with_photos": self._people_payload([person] + rows[:25])}

    def handle_sons_in_law(self, question):
        q = _clean_question(question)
        m = re.search(r"yernos?\s+de\s+(.+?)(?:\?|$)", q, re.I) or re.search(r"yerno\s+en\s+la\s+familia\s+de\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        rows = self._children_in_law_for(person['id'], sex='M')
        if not rows:
            return {"answer": f"No constan yernos documentados de {_person_link(person)}.", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        return {"answer": self._list_people_answer(f"Los yernos de {_person_link(person)} son", rows), "people_mentioned": [person['id']] + [r['id'] for r in rows], "people_with_photos": self._people_payload([person] + rows[:25])}

    def handle_relationship_with_parents_of(self, question):
        q = _clean_question(question)
        m = re.search(r"qu[eé]\s+relaci[oó]n\s+ten[ií]a\s+(.+?)\s+con\s+los\s+padres\s+de\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        a,_ = self._resolve_person(m.group(1))
        target,_ = self._resolve_person(m.group(2))
        if not a or not target:
            return None
        father = self._get_parent(target, 'father')
        mother = self._get_parent(target, 'mother')
        parts = []
        people = [a, target]
        if father:
            parts.append(f"con el padre ({_person_link(father)}): {self._relationship_label(a, father) or 'sin parentesco directo documentado'}")
            people.append(father)
        if mother:
            parts.append(f"con la madre ({_person_link(mother)}): {self._relationship_label(a, mother) or 'sin parentesco directo documentado'}")
            people.append(mother)
        ans = f"La relación de {_person_link(a)} con los padres de {_person_link(target)} era: " + "; ".join(parts) + "."
        return {"answer": ans, "people_mentioned": [p['id'] for p in people if p], "people_with_photos": self._people_payload([p for p in people if p])}

    def handle_sisters_in_law(self, question):
        q = _clean_question(question)
        m = re.search(r"cu[nñ]ada\s+de\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person,_ = self._resolve_person(m.group(1))
        if not person:
            return None
        rows = [p for p in self._siblings_in_law_for(person['id']) if p.get('sex') == 'F']
        if not rows:
            return {"answer": f"No constan cuñadas documentadas de {_person_link(person)}.", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        return {"answer": self._list_people_answer(f"Las cuñadas de {_person_link(person)} son", rows), "people_mentioned": [person['id']] + [r['id'] for r in rows], "people_with_photos": self._people_payload([person] + rows[:25])}

    def handle_brothers_in_law(self, question):
        q = _clean_question(question)
        m = re.search(r"cu[nñ]ados?\s+de\s+(.+?)(?:\?|$)", q, re.I) or re.search(r"si\s+(.+?)\s+ten[ií]a\s+cu[nñ]ados\s+y\s+c[oó]mo\s+se\s+llamaban(?:\?|$)", q, re.I)
        if not m:
            return None
        person,_ = self._resolve_person(m.group(1))
        if not person:
            return None
        rows = self._siblings_in_law_for(person['id'])
        if not rows:
            return {"answer": f"No constan cuñados documentados de {_person_link(person)}.", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        return {"answer": self._list_people_answer(f"Los cuñados de {_person_link(person)} son", rows), "people_mentioned": [person['id']] + [r['id'] for r in rows], "people_with_photos": self._people_payload([person] + rows[:25])}

    def handle_great_great_uncle(self, question):
        q = _clean_question(question)
        m = re.search(r"tuvo\s+(.+?)\s+alg[uú]n\s+t[ií]o\s+bisabuelo\s+conocido(?:\?|$)", q, re.I)
        if not m:
            return None
        person,_ = self._resolve_person(m.group(1))
        if not person:
            return None
        rows = self._great_great_uncle_for(person['id'])
        if not rows:
            ans = f"No constan tíos bisabuelos documentados de {_person_link(person)}."
        else:
            ans = self._list_people_answer(f"Los tíos bisabuelos de {_person_link(person)} son", rows)
        return {"answer": ans, "people_mentioned": [person['id']] + [r['id'] for r in rows], "people_with_photos": self._people_payload([person] + rows[:25])}

    def handle_great_uncles(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person,_ = self._resolve_person(subject)
        if not person:
            return None
        rows = self._great_uncles_for(person['id'])
        return {"answer": self._list_people_answer(f"Los tíos abuelos de {_person_link(person)} son", rows), "people_mentioned": [person['id']] + [r['id'] for r in rows], "people_with_photos": self._people_payload([person] + rows[:25])}

    def handle_grandnephews(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person,_ = self._resolve_person(subject)
        if not person:
            return None
        rows = self._grandnephews_for(person['id'])
        return {"answer": self._list_people_answer(f"Los sobrinos nietos de {_person_link(person)} son", rows), "people_mentioned": [person['id']] + [r['id'] for r in rows], "people_with_photos": self._people_payload([person] + rows[:25])}

    def handle_second_cousin_of_hurtado_branch(self, question):
        q = _clean_question(question)
        m = re.search(r"era\s+(.+?)\s+prima\s+segunda\s+de\s+alguien\s+de\s+la\s+rama\s+Hurtado(?:\?|$)", q, re.I)
        if not m:
            return None
        person,_ = self._resolve_person(m.group(1))
        if not person:
            return None
        candidates = []
        for cand in self._all_people_basic():
            if 'hurtado' in _tokenize_name(cand.get('surname') or '') and self._is_second_cousin(person, cand):
                candidates.append(cand)
        if candidates:
            ans = f"Sí. {_person_link(person)} era prima segunda de: " + _join_names(candidates) + "."
        else:
            ans = f"No consta que {_person_link(person)} fuera prima segunda de alguien de la rama Hurtado."
        return {"answer": ans, "people_mentioned": [person['id']] + [c['id'] for c in candidates], "people_with_photos": self._people_payload([person] + candidates[:25])}

    def handle_oldest_great_grandson(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person,_ = self._resolve_person(subject)
        if not person:
            return None
        rows = [r for r in self._descendants_at_generation(person['id'], 3) if r.get('sex') == 'M']
        rows = _sort_people(rows)
        if not rows:
            ans = f"No constan bisnietos varones documentados de {_person_link(person)}."
            people = [person]
        else:
            ans = f"El bisnieto mayor de {_person_link(person)} fue {_person_brief(rows[0])}."
            people = [person, rows[0]]
        return {"answer": ans, "people_mentioned": [p['id'] for p in people], "people_with_photos": self._people_payload(people)}

    def handle_has_great_great_grandchildren(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person,_ = self._resolve_person(subject)
        if not person:
            return None
        rows = self._descendants_at_generation(person['id'], 4)
        ans = f"Sí. Constan tataranietos documentados de {_person_link(person)}: {_join_names(rows)}." if rows else f"No constan tataranietos documentados de {_person_link(person)}."
        return {"answer": ans, "people_mentioned": [person['id']] + [r['id'] for r in rows], "people_with_photos": self._people_payload([person] + rows[:25])}

    def handle_great_great_grandparents(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person,_ = self._resolve_person(subject)
        if not person:
            return None
        rows = self._ancestors_at_generation(person['id'], 4)
        return {"answer": self._list_people_answer(f"Los tatarabuelos de {_person_link(person)} son", rows), "people_mentioned": [person['id']] + [r['id'] for r in rows], "people_with_photos": self._people_payload([person] + rows[:25])}

    def handle_maternal_great_grandmother(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person,_ = self._resolve_person(subject)
        if not person:
            return None
        mother = self._get_parent(person, 'mother')
        gm = self._get_parent(mother, 'mother') if mother else None
        gg = self._get_parent(gm, 'mother') if gm else None
        ans = f"La bisabuela materna de {_person_link(person)} fue {_person_brief(gg)}." if gg else f"No consta la bisabuela materna de {_person_link(person)}."
        return {"answer": ans, "people_mentioned": [x['id'] for x in [person, gg] if x], "people_with_photos": self._people_payload([person, gg])}

    def handle_great_grandparents(self, question):
        subject = self._extract_subject_name(question)
        if not subject:
            return None
        person,_ = self._resolve_person(subject)
        if not person:
            return None
        rows = self._ancestors_at_generation(person['id'], 3)
        return {"answer": self._list_people_answer(f"Los bisabuelos de {_person_link(person)} son", rows), "people_mentioned": [person['id']] + [r['id'] for r in rows], "people_with_photos": self._people_payload([person] + rows[:25])}

    def handle_first_surname_natural(self, question):
        m = re.search(r"tengan\s+(.+?)\s+como\s+primer\s+apellido(?:\?|$)", _clean_question(question), re.I)
        if not m:
            return None
        surname = _normalize_name_fragment(m.group(1))
        rows = [_as_dict(r) for r in self.conn.execute(
            "SELECT id,name,birth_year,death_year,birth_place,photo_file,is_alive FROM people WHERE NORMALIZE(surname) = NORMALIZE(?) OR NORMALIZE(surname) LIKE NORMALIZE(?) || '%' ORDER BY birth_year,name LIMIT 200",
            (surname, surname)
        ).fetchall()]
        return {"answer": self._list_people_answer(f"Las personas con {surname} como primer apellido son", rows), "people_mentioned": [r['id'] for r in rows], "people_with_photos": self._people_payload(rows[:25])}

    def handle_occupation_natural(self, question):
        q = _clean_question(question)
        m = (re.search(r"(?:a\s+)?qu[eé]\s+oficio\s+(?:ten[ií]a|se\s+dedic[oó])\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"en\s+qu[eé]\s+trabaja(?:ba)?\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"(?:qu[eé]\s+)?empleo\s+consta\s+de\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"c[oó]mo\s+se\s+ganaba\s+la\s+vida\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"cu[aá]l\s+(?:era|fue)\s+(?:el\s+medio\s+de\s+vida|el\s+oficio)\s+(?:de\s+)?(.+?)(?:\?|$)", q, re.I))
        if not m:
            return None
        person,_ = self._resolve_person(m.group(1))
        if not person:
            return None
        occupations = [_as_dict(o) for o in get_occupations(self.conn, person['id'])]
        if not occupations:
            return {"answer": f"No consta ninguna ocupación o actividad registrada para {_person_link(person)}.", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        parts=[]
        for o in occupations:
            txt=o.get('title','')
            if o.get('date'): txt += f" ({o['date']})"
            if o.get('place'): txt += f" en {o['place']}"
            if txt: parts.append(txt)
        return {"answer": f"La ocupación o actividad registrada para {_person_link(person)} es: " + "; ".join(parts) + ".", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}

    def handle_last_spouse(self, question):
        q = _clean_question(question)
        m = re.search(r"con\s+qui[eé]n\s+acab[oó]\s+cas[aá]ndose\s+(.+?)(?:\?|$)", q, re.I) or re.search(r"acab[oó]\s+cas[aá]ndose\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person,_ = self._resolve_person(m.group(1))
        if not person:
            return None
        spouses = get_spouses(self.conn, person['id'])
        if not spouses:
            return {"answer": f"No consta matrimonio documentado de {_person_link(person)}.", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        def keyfn(s):
            return (self._extract_year_from_text(s.get('marriage_date')) or -1, _norm_cmp(_as_dict(s['person']).get('name','')))
        last = sorted(spouses, key=keyfn)[-1]
        sp = _as_dict(last['person'])
        extra=[]
        if last.get('marriage_date'): extra.append(f"boda en {last['marriage_date']}")
        if last.get('marriage_place'): extra.append(f"en {last['marriage_place']}")
        ans = f"{_person_link(person)} acabó casándose con {_person_link(sp)}"
        if extra: ans += ", " + ", ".join(extra)
        ans += "."
        return {"answer": ans, "people_mentioned": [person['id'], sp['id']], "people_with_photos": self._people_payload([person, sp])}

    def handle_same_birth_death_city(self, question):
        rows = [_as_dict(r) for r in self.conn.execute(
            "SELECT id,name,birth_year,death_year,birth_place,death_place,photo_file,is_alive FROM people WHERE birth_place IS NOT NULL AND death_place IS NOT NULL AND TRIM(LOWER(birth_place)) = TRIM(LOWER(death_place)) ORDER BY birth_year,name LIMIT 200"
        ).fetchall()]
        return {"answer": self._list_people_answer("Las personas que murieron en la misma ciudad en la que nacieron fueron", rows), "people_mentioned": [r['id'] for r in rows], "people_with_photos": self._people_payload(rows[:25])}

    def handle_large_families(self, question):
        q = _clean_question(question)
        m = re.search(r"(\d+)\s+o\s+m[aá]s", q, re.I)
        threshold = int(m.group(1)) if m else 10
        rows = [r for r in self._couple_children_count_rows() if r['children_count'] >= threshold]
        if not rows:
            return {"answer": f"No he encontrado parejas con {threshold} o más hijos documentados.", "people_mentioned": [], "people_with_photos": []}
        people=[]; parts=[]
        for r in rows[:25]:
            p1 = _as_dict(get_person(self.conn, r['person1_id'])) if r.get('person1_id') else None
            p2 = _as_dict(get_person(self.conn, r['person2_id'])) if r.get('person2_id') else None
            if p1: people.append(p1)
            if p2: people.append(p2)
            parts.append(f"{_person_link(p1)} y {_person_link(p2)} ({r['children_count']} hijos)")
        return {"answer": "Las parejas con muchísimos hijos documentados son: " + "; ".join(parts) + ".", "people_mentioned": [p['id'] for p in _unique_people(people)], "people_with_photos": self._people_payload(_unique_people(people)[:25])}

    def handle_same_birth_year_as_person(self, question):
        m = re.search(r"mismo\s+a[nñ]o\s+que\s+(.+?)(?:\?|$)", _clean_question(question), re.I)
        if not m:
            return None
        person,_ = self._resolve_person(m.group(1))
        if not person or person.get('birth_year') is None:
            return None
        rows = [_as_dict(r) for r in self.conn.execute(
            "SELECT id,name,birth_year,death_year,birth_place,photo_file,is_alive FROM people WHERE birth_year = ? AND id != ? ORDER BY name",
            (person['birth_year'], person['id'])
        ).fetchall()]
        return {"answer": self._list_people_answer(f"Las personas nacidas el mismo año que {_person_link(person)} ({person['birth_year']}) fueron", rows), "people_mentioned": [person['id']] + [r['id'] for r in rows], "people_with_photos": self._people_payload([person] + rows[:25])}

    def handle_has_descendance_named(self, question):
        m = re.search(r"hay\s+alguna\s+(.+?)\s+con\s+descendencia\s+documentada(?:\?|$)", _clean_question(question), re.I)
        if not m:
            return None
        matches = [_as_dict(r) for r in self._search_people(m.group(1), limit=50)]
        rows = [p for p in matches if self._all_descendants_count(p['id']) > 0]
        return {"answer": self._list_people_answer(f"Las personas que coinciden con '{m.group(1)}' y tienen descendencia documentada son", rows), "people_mentioned": [r['id'] for r in rows], "people_with_photos": self._people_payload(rows[:25])}

    def handle_unknown_birth_date_people(self, question):
        rows = [_as_dict(r) for r in self.conn.execute(
            "SELECT id,name,birth_year,death_year,birth_place,photo_file,is_alive FROM people WHERE birth_year IS NULL ORDER BY name LIMIT 200"
        ).fetchall()]
        return {"answer": self._list_people_answer("Las personas sin fecha o año de nacimiento conocido son", rows), "people_mentioned": [r['id'] for r in rows], "people_with_photos": self._people_payload(rows[:25])}

    def handle_repeated_compound_names(self, question):
        rows = [_as_dict(r) for r in self.conn.execute("SELECT given_name FROM people WHERE given_name IS NOT NULL").fetchall()]
        from collections import Counter
        c = Counter()
        for r in rows:
            gn = (r.get('given_name') or '').strip()
            toks = [t for t in gn.split() if t]
            if len(toks) >= 2:
                c[gn] += 1
        if not c:
            return {"answer": "No he encontrado nombres compuestos repetidos en el árbol.", "people_mentioned": [], "people_with_photos": []}
        top = c.most_common(10)
        parts = [f"{_smart_title_name(name)} ({count})" for name, count in top]
        return {"answer": "Los nombres compuestos más repetidos del árbol son: " + "; ".join(parts) + ".", "people_mentioned": [], "people_with_photos": []}

    def handle_parents_in_law_natural(self, question):
        m = re.search(r"suegros\s+de\s+(.+?)(?:\?|$)", _clean_question(question), re.I)
        if not m:
            return None
        return self.handle_parents_in_law(f"suegra o suegro de {m.group(1)}")

    def _build_targeted_response(self, person, question):
        """Build a targeted response based on what the question asks about (birth, death, occupation, etc.)"""
        full = _as_dict(get_person(self.conn, person["id"]))
        if not full:
            return None

        q = _clean_question(question)

        # Check if asking about birth place/date
        if re.search(r"(?:donde|dónde|lugar).+(?:nac[ií]|nacimiento)", q, re.I) or \
           re.search(r"(?:nac[ií]|nacimiento).+(?:donde|dónde|lugar)", q, re.I) or \
           re.search(r"sit[úu]a.*(?:árbol|arbol).*(?:nacer|nacimiento)", q, re.I):  # "sitúa el árbol en el momento de nacer"
            if full.get("birth_date") and full.get("birth_place"):
                return {"answer": f"{full['name']} nació el {full['birth_date']} en {full['birth_place']}.",
                        "people_mentioned": [full["id"]], "people_with_photos": self._people_payload([full])}
            elif full.get("birth_place"):
                return {"answer": f"{full['name']} nació en {full['birth_place']}.",
                        "people_mentioned": [full["id"]], "people_with_photos": self._people_payload([full])}
            elif full.get("birth_date"):
                return {"answer": f"{full['name']} nació el {full['birth_date']}.",
                        "people_mentioned": [full["id"]], "people_with_photos": self._people_payload([full])}

        # Check if asking about death place/date
        if re.search(r"(?:donde|dónde|lugar).+(?:mur[ií]|murió|defunción)", q, re.I) or \
           re.search(r"(?:mur[ií]|murió|defunción).+(?:donde|dónde|lugar)", q, re.I):
            if full.get("death_date") and full.get("death_place"):
                return {"answer": f"{full['name']} murió el {full['death_date']} en {full['death_place']}.",
                        "people_mentioned": [full["id"]], "people_with_photos": self._people_payload([full])}
            elif full.get("death_place"):
                return {"answer": f"{full['name']} murió en {full['death_place']}.",
                        "people_mentioned": [full["id"]], "people_with_photos": self._people_payload([full])}
            elif full.get("death_date"):
                return {"answer": f"{full['name']} murió el {full['death_date']}.",
                        "people_mentioned": [full["id"]], "people_with_photos": self._people_payload([full])}

        # Check if asking about occupation
        if re.search(r"(?:en\s+qu[eé]|ocupaci[óo]n|profesi[óo]n|trabajo|oficio)", q, re.I):
            occupations = [_as_dict(r) for r in self.conn.execute(
                "SELECT description FROM occupations WHERE person_id = ? ORDER BY year",
                (full["id"],)
            ).fetchall()]
            if occupations:
                occ_str = "; ".join(o.get("description", "") for o in occupations if o.get("description"))
                return {"answer": f"{full['name']} trabajaba como {occ_str}.",
                        "people_mentioned": [full["id"]], "people_with_photos": self._people_payload([full])}

        # Default to full response
        return self._build_info_response(person)

    def _build_info_response(self, person):
        full = _as_dict(get_person(self.conn, person["id"]))
        if not full:
            return None
        lines = [full["name"]]
        if full.get("birth_date") or full.get("birth_place"):
            birth = "Nacimiento: " + (full.get("birth_date") or "?")
            if full.get("birth_place"):
                birth += f", {full['birth_place']}"
            lines.append(birth)
        if full.get("death_date") or full.get("death_place"):
            death = "Defunción: " + (full.get("death_date") or "?")
            if full.get("death_place"):
                death += f", {full['death_place']}"
            lines.append(death)
        return {"answer": "\n".join(lines), "people_mentioned": [full["id"]], "people_with_photos": self._people_payload([full])}

    # --- Military handlers ---

    def handle_military(self, question):
        q = _clean_question(question)
        m = re.search(r"(?:actividad\s+militar\s+(?:tuvo|de)\s+|servicio\s+militar\s+de\s+|datos?\s+militar(?:es)?\s+de\s+)(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        records = [_as_dict(r) for r in get_military(self.conn, person['id'])]
        if not records:
            return {"answer": f"No constan datos militares de {_person_link(person)}.", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        parts = []
        for r in records:
            frag = r.get('description') or ''
            if r.get('date'):
                frag += f" ({r['date']})"
            if r.get('place'):
                frag += f" — {r['place']}"
            parts.append(frag.strip())
        ans = f"Datos militares de {_person_link(person)}: " + "; ".join(parts) + "."
        return {"answer": ans, "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}

    def handle_military_all(self, question):
        rows = []
        for r in self.conn.execute(
            "SELECT DISTINCT p.id, p.name, p.birth_year, p.death_year, p.birth_place, p.photo_file, p.is_alive, m.description "
            "FROM military m JOIN people p ON p.id = m.person_id ORDER BY p.birth_year, p.name"
        ).fetchall():
            rows.append(_as_dict(r))
        if not rows:
            return {"answer": "No constan registros militares en el árbol.", "people_mentioned": [], "people_with_photos": []}
        # Group by person (one person may have multiple records)
        seen = {}
        for r in rows:
            pid = r['id']
            if pid not in seen:
                seen[pid] = {'person': r, 'descriptions': []}
            if r.get('description'):
                seen[pid]['descriptions'].append(r['description'])
        parts = []
        people = []
        for pid, info in seen.items():
            p = info['person']
            people.append(p)
            desc = ", ".join(info['descriptions']) if info['descriptions'] else "servicio militar"
            parts.append(f"- {_person_brief(p)}: {desc}")
        ans = f"Personas con registros militares en el árbol ({len(people)}):\n" + "\n".join(parts)
        return {"answer": ans, "people_mentioned": [p['id'] for p in people], "people_with_photos": self._people_payload(people[:25])}

    # --- Burial handlers ---

    def handle_burial(self, question):
        q = _clean_question(question)
        m = re.search(r"(?:enterrad[oa]|sepultad[oa]|sepultura\s+de|tumba\s+de)\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        records = [_as_dict(r) for r in get_burial(self.conn, person['id'])]
        if not records:
            return {"answer": f"No constan datos de sepultura de {_person_link(person)}.", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        parts = []
        for r in records:
            frag = r.get('place') or ''
            if r.get('place_detail'):
                frag += f" — {r['place_detail']}"
            if r.get('date'):
                frag += f" ({r['date']})"
            parts.append(frag.strip())
        ans = f"Sepultura de {_person_link(person)}: " + "; ".join(parts) + "."
        return {"answer": ans, "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}

    def handle_burial_place(self, question):
        q = _clean_question(question)
        m = re.search(r"(?:enterrados|sepultados|enterramientos)\s+en\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        place = m.group(1).strip()
        rows = []
        for r in self.conn.execute(
            "SELECT p.id, p.name, p.birth_year, p.death_year, p.birth_place, p.photo_file, p.is_alive, b.place, b.date "
            "FROM burial b JOIN people p ON p.id = b.person_id "
            "WHERE NORMALIZE(b.place) LIKE '%' || NORMALIZE(?) || '%' ORDER BY b.date, p.name",
            (place,)
        ).fetchall():
            rows.append(_as_dict(r))
        if not rows:
            return {"answer": f"No constan enterramientos en {place}.", "people_mentioned": [], "people_with_photos": []}
        # Deduplicate by person
        seen = set()
        unique = []
        for r in rows:
            if r['id'] not in seen:
                seen.add(r['id'])
                unique.append(r)
        return {"answer": self._list_people_answer(f"Las personas enterradas en {place} son", unique), "people_mentioned": [r['id'] for r in unique], "people_with_photos": self._people_payload(unique[:25])}

    # --- Baptism handlers ---

    def handle_baptism(self, question):
        q = _clean_question(question)
        m = re.search(r"(?:bautizad[oa]|bautismo\s+de)\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        bdate = person.get('baptism_date') or ''
        bplace = person.get('baptism_place') or ''
        if not bdate and not bplace:
            return {"answer": f"No constan datos de bautismo de {_person_link(person)}.", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        parts = []
        if bdate:
            parts.append(f"fecha: {bdate}")
        if bplace:
            parts.append(f"lugar: {bplace}")
        ans = f"Bautismo de {_person_link(person)}: " + ", ".join(parts) + "."
        return {"answer": ans, "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}

    def handle_baptism_place(self, question):
        q = _clean_question(question)
        m = re.search(r"(?:bautiz[oó]|(?:lugar|iglesia)\s+(?:del?\s+)?bautismo\s+de)\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        bplace = person.get('baptism_place') or ''
        if not bplace:
            return {"answer": f"No consta el lugar de bautismo de {_person_link(person)}.", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        ans = f"{_person_link(person)} fue bautizado/a en {bplace}."
        return {"answer": ans, "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}

    def handle_godparents(self, question):
        q = _clean_question(question)
        m = re.search(r"padrinos\s+de\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        godparents = person.get('godparents') or ''
        if not godparents:
            return {"answer": f"No constan los padrinos de {_person_link(person)}.", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        ans = f"Los padrinos de {_person_link(person)} fueron: {godparents}."
        return {"answer": ans, "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}

    # --- Events handlers ---

    def handle_events(self, question):
        q = _clean_question(question)
        m = re.search(r"eventos?\s+(?:hay\s+)?(?:registrados?\s+)?(?:para|de)\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        records = [_as_dict(r) for r in get_events(self.conn, person['id'])]
        if not records:
            return {"answer": f"No constan eventos registrados para {_person_link(person)}.", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        parts = []
        for r in records:
            frag = r.get('type') or r.get('tag') or ''
            if r.get('description'):
                frag += f": {r['description']}"
            if r.get('date'):
                frag += f" ({r['date']})"
            if r.get('place'):
                frag += f" — {r['place']}"
            parts.append("- " + frag.strip())
        ans = f"Eventos registrados para {_person_link(person)} ({len(records)}):\n" + "\n".join(parts)
        return {"answer": ans, "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}

    def handle_education(self, question):
        q = _clean_question(question)
        m = re.search(r"(?:estudios|educaci[oó]n)\s+de\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            m = re.search(r"datos?\s+de\s+(?:estudios|educaci[oó]n)\s+de\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        records = [_as_dict(r) for r in get_events(self.conn, person['id'], 'Educación')]
        if not records:
            return {"answer": f"No constan datos de estudios o educación de {_person_link(person)}.", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        parts = []
        for r in records:
            frag = r.get('description') or 'Educación'
            if r.get('date'):
                frag += f" ({r['date']})"
            if r.get('place'):
                frag += f" — {r['place']}"
            parts.append("- " + frag.strip())
        ans = f"Datos de educación de {_person_link(person)}:\n" + "\n".join(parts)
        return {"answer": ans, "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}

    def handle_mother(self, question):
        q = _clean_question(question)
        m = re.search(r"madre\s+de\s+(.+?)(?:\?|$)", q, re.I) or re.search(r"dime\s+c[oó]mo\s+se\s+llamaba\s+la\s+madre\s+de\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        mother = self._get_parent(person, 'mother')
        if mother:
            ans = f"La madre de {_person_link(person)} fue {_person_brief(mother)}."
            ppl = [person, mother]
        else:
            ans = f"No consta la madre de {_person_link(person)}."
            ppl = [person]
        return {"answer": ans, "people_mentioned": [p['id'] for p in ppl if p], "people_with_photos": self._people_payload(ppl)}

    def handle_child_extremes(self, question):
        q = _clean_question(question)
        m = re.search(r"qui[eé]n\s+fue\s+el\s+hijo\s+mayor\s+de\s+(.+?)(?:\?|$)", q, re.I)
        mode = 'son_oldest'
        if not m:
            m = re.search(r"dime\s+cu[aá]l\s+fue\s+la\s+primera\s+hija\s+de\s+(.+?)(?:\?|$)", q, re.I)
            mode = 'first_daughter'
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        kids = _sort_people([_as_dict(c) for c in get_children(self.conn, person['id'])])
        if mode == 'son_oldest':
            kids = [k for k in kids if k.get('sex') == 'M']
            label = 'El hijo mayor'
        else:
            kids = [k for k in kids if k.get('sex') == 'F']
            label = 'La primera hija'
        if not kids:
            return {"answer": f"No consta {'ningún hijo varón' if mode == 'son_oldest' else 'ninguna hija'} de {_person_link(person)}.", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        kid = kids[0]
        return {"answer": f"{label} de {_person_link(person)} fue {_person_brief(kid)}.", "people_mentioned": [person['id'], kid['id']], "people_with_photos": self._people_payload([person, kid])}

    def handle_given_name_count(self, question):
        q = _clean_question(question)
        m = re.search(r"se\s+llaman\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        target = _strip_accents(m.group(1).strip().lower())
        rows = []
        for r in self.conn.execute("SELECT id,name,given_name,birth_year,death_year,birth_place,photo_file,is_alive FROM people WHERE given_name IS NOT NULL ORDER BY name").fetchall():
            rr = _as_dict(r)
            toks = [_strip_accents(t.lower()) for t in re.split(r"\s+", rr.get('given_name') or '') if t]
            if target in toks:
                rows.append(rr)
        return {"answer": f"Hay {len(rows)} personas del árbol que se llaman {_smart_title_name(m.group(1).strip())}.", "people_mentioned": [r['id'] for r in rows], "people_with_photos": self._people_payload(rows[:25])}

    def handle_same_surname_twice(self, question):
        rows = []
        for r in self.conn.execute("SELECT id,name,surname,birth_year,death_year,birth_place,photo_file,is_alive FROM people WHERE surname IS NOT NULL AND surname != '' ORDER BY name").fetchall():
            rr = _as_dict(r)
            parts = [p for p in re.split(r"\s+", rr.get('surname') or '') if p]
            if len(parts) >= 2 and _norm_cmp(parts[0]) == _norm_cmp(parts[1]):
                rows.append(rr)
        return {"answer": self._list_people_answer("Las personas cuyos dos apellidos son iguales son", rows), "people_mentioned": [r['id'] for r in rows], "people_with_photos": self._people_payload(rows[:25])}

    def handle_surname_born_in_place(self, question):
        q = _clean_question(question)
        m = re.search(r"qu[eé]\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)\s+nacieron\s+en\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        surname = m.group(1).strip()
        place = m.group(2).strip()
        rows = []
        for r in self.conn.execute("SELECT id,name,surname,birth_year,death_year,birth_place,photo_file,is_alive FROM people WHERE NORMALIZE(birth_place) LIKE '%' || NORMALIZE(?) || '%' ORDER BY birth_year,name", (place,)).fetchall():
            rr = _as_dict(r)
            sp = (rr.get('surname') or '').split()
            if sp and _norm_cmp(sp[0]) == _norm_cmp(surname):
                rows.append(rr)
        return {"answer": self._list_people_answer(f"Las personas con primer apellido {surname} nacidas en {place} son", rows), "people_mentioned": [r['id'] for r in rows], "people_with_photos": self._people_payload(rows[:25])}

    def handle_last_residence(self, question):
        q = _clean_question(question)
        m = (re.search(r"(?:ultima|[uú]ltima)\s+residencia\s+de\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"d[oó]nde\s+viv[ií]a\s+(.+?)\s+al\s+final\s+de\s+su\s+vida(?:\?|$)", q, re.I) or
             re.search(r"(?:residencia|d[óo]nde\s+(?:vivia|viv[ií]a|vive|ha\s+vivido))\s+(.+?)(?:\?|$)", q, re.I) or
             re.search(r"cu[aá]l\s+(?:fue|era|es)\s+(?:el\s+domicilio|la\s+direcci[oó]n|el\s+primer\s+domicilio)\s+(?:de\s+)?(.+?)(?:\?|$)", q, re.I))
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        res = [_as_dict(r) for r in get_residences(self.conn, person['id'])]
        if not res:
            return {"answer": f"No constan residencias documentadas de {_person_link(person)}.", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}
        def yr(r):
            vals = re.findall(r"(\d{4})", str(r.get('date') or ''))
            return int(vals[-1]) if vals else -1
        last = sorted(res, key=lambda r: (yr(r), str(r.get('date') or '')))[-1]
        frag = last.get('address') or ''
        if last.get('address2'):
            frag += (' ' if frag else '') + last['address2']
        if last.get('city'):
            frag += (', ' if frag else '') + last['city']
        if last.get('country'):
            frag += (', ' if frag else '') + last['country']
        if last.get('date'):
            frag += f" ({last['date']})"
        return {"answer": f"Al final de su vida, {_person_link(person)} vivía en {frag}.", "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}

    def handle_children_total_natural(self, question):
        q = _clean_question(question)
        m = re.search(r"cu[aá]ntos\s+hijos\s+lleg[oó]\s+a\s+tener\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        person, _ = self._resolve_person(m.group(1))
        if not person:
            return None
        kids = _sort_people([_as_dict(c) for c in get_children(self.conn, person['id'])])
        if not kids:
            ans = f"No constan hijos documentados de {_person_link(person)}."
        else:
            ans = f"{_person_link(person)} llegó a tener {len(kids)} hijos documentados: " + _join_names(kids) + "."
        return {"answer": ans, "people_mentioned": [person['id']] + [k['id'] for k in kids], "people_with_photos": self._people_payload([person] + kids[:25])}

    def handle_born_in_and_died_outside(self, question):
        q = _clean_question(question)
        m = re.search(r"nacieron\s+en\s+(.+?)\s+y\s+luego\s+murieron\s+fuera\s+de\s+(.+?)(?:\?|$)", q, re.I)
        if m:
            birth_place = m.group(1).strip()
            death_excl = m.group(2).strip()
        else:
            m = re.search(r"nacieron\s+en\s+(.+?)\s+y\s+luego\s+murieron\s+fuera\s+de\s+all[ií](?:\?|$)", q, re.I)
            if not m:
                return None
            birth_place = m.group(1).strip()
            death_excl = birth_place
        rows = []
        for r in self.conn.execute("SELECT id,name,birth_year,death_year,birth_place,death_place,photo_file,is_alive FROM people WHERE NORMALIZE(birth_place) LIKE '%' || NORMALIZE(?) || '%' AND death_place IS NOT NULL AND death_place != '' ORDER BY birth_year,name", (birth_place,)).fetchall():
            rr = _as_dict(r)
            if _norm_cmp(death_excl) not in _norm_cmp(rr.get('death_place', '')):
                rows.append(rr)
        return {"answer": self._list_people_answer(f"Las personas nacidas en {birth_place} y luego murieron fuera de {death_excl} fueron", rows), "people_mentioned": [r['id'] for r in rows], "people_with_photos": self._people_payload(rows[:25])}

    def handle_compare_older(self, question):
        q = _clean_question(question)
        m = re.search(r"qui[eé]n\s+(?:era|es)\s+mayor,?\s+(.+?)\s+o\s+(.+?)(?:\?|$)", q, re.I)
        if not m:
            return None
        a, _ = self._resolve_person(m.group(1))
        b, _ = self._resolve_person(m.group(2))
        if not a or not b:
            return None
        if a.get('birth_year') is None or b.get('birth_year') is None:
            ans = f"No puedo determinar quién era mayor entre {_person_link(a)} y {_person_link(b)} porque faltan años de nacimiento."
        elif a['birth_year'] < b['birth_year']:
            ans = f"La persona mayor era {_person_link(a)}."
        elif b['birth_year'] < a['birth_year']:
            ans = f"La persona mayor era {_person_link(b)}."
        else:
            ans = f"{_person_link(a)} y {_person_link(b)} tenían la misma edad aproximada."
        return {"answer": ans, "people_mentioned": [a['id'], b['id']], "people_with_photos": self._people_payload([a, b])}

    def handle_birth_place_of_person(self, question):
        """Handle 'Donde nacio X?' or 'Cual fue el lugar de nacimiento de X?' - return X's birthplace"""
        subject = (self._extract_subject_name_from_pattern(question, r"(?:donde|d[oó]nde)\s+naci[oó]\s+(.+?)(?:\?|$)") or
                  self._extract_subject_name_from_pattern(question, r"(?:cu[aá]l\s+(?:fue|es)\s+(?:el\s+lugar|la\s+ciudad|la\s+localidad|el\s+pueblo)\s+(?:de\s+)?(?:nacimiento|origen|natal)\s+de)\s+(.+?)(?:\?|$)") or
                  self._extract_subject_name_from_pattern(question, r"(?:qu[eé]\s+lugar.*nacimiento\s+(?:tiene|tiene|tuvo)\s+(?:de\s+)?)\s*(.+?)(?:\?|$)"))
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        if person.get('birth_place'):
            answer = f"{person['name']} nació en {person['birth_place']}."
        else:
            answer = f"No consta el lugar de nacimiento de {person['name']}."
        return {"answer": answer, "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}

    def handle_death_place_of_person(self, question):
        """Handle 'Donde/falleció X?' - return X's death place"""
        subject = (self._extract_subject_name_from_pattern(question, r"(?:d[oó]nde|en\s+qu[eé]\s+(?:lugar|sitio|ciudad|pueblo))\s+(?:falleci[oó]|muri[oó])\s+(.+?)(?:\?|$)") or
                  self._extract_subject_name_from_pattern(question, r"(?:cu[aá]l\s+fue\s+(?:el\s+lugar|la\s+ciudad)\s+de\s+(?:fallecimiento|defunci[oó]n)\s+de|lugar\s+de\s+(?:fallecimiento|defunci[oó]n)\s+de)\s+(.+?)(?:\?|$)") or
                  self._extract_subject_name_from_pattern(question, r"(?:qu[eé]\s+lugar\s+de\s+(?:fallecimiento|defunci[oó]n)\s+(?:tiene|consta)\s+(?:de\s+)?)\s*(.+?)(?:\?|$)"))
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        if person.get('death_place'):
            answer = f"{person['name']} murió en {person['death_place']}."
        else:
            answer = f"No consta el lugar de muerte de {person['name']}."
        return {"answer": answer, "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}

    def handle_birth_date_of_person(self, question):
        """Handle 'Cuando nacio X?' or 'Cual fue la fecha de nacimiento de X?' - return X's birth date"""
        subject = (self._extract_subject_name_from_pattern(question, r"(?:(?:cuando|cu[aá]ndo|en\s+qu[eé]\s+momento)\s+(?:naci[oó]|fue\s+nacid[oa]|fue\s+born)|en\s+qu[eé]\s+fecha.*naci)\s+(.+?)(?:\?|$)") or
                  self._extract_subject_name_from_pattern(question, r"(?:cu[aá]l\s+(?:fue|es)\s+(?:la\s+)?fecha\s+(?:exacta\s+)?(?:de\s+)?nacimiento\s+de)\s+(.+?)(?:\?|$)"))
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        if person.get('birth_year'):
            answer = f"{person['name']} nació en {person['birth_year']}."
        else:
            answer = f"No consta la fecha de nacimiento de {person['name']}."
        return {"answer": answer, "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}

    def handle_death_date_of_person(self, question):
        """Handle 'Cuando murio/falleció X?' - return X's death date"""
        subject = (self._extract_subject_name_from_pattern(question, r"(?:cu[aá]ndo|en\s+qu[eé]\s+(?:fecha|a[nñ]o|d[ií]a))\s+(?:falleci[oó]|muri[oó]|fue\s+enterrad[oa])\s+(.+?)(?:\?|$)") or
                  self._extract_subject_name_from_pattern(question, r"(?:cu[aá]l\s+fue\s+la\s+fecha\s+de\s+(?:fallecimiento|defunci[oó]n)\s+de)\s+(.+?)(?:\?|$)") or
                  self._extract_subject_name_from_pattern(question, r"(?:qu[eé]\s+fecha\s+de\s+defunci[oó]n\s+(?:tiene|consta)\s+(?:de\s+)?)\s*(.+?)(?:\?|$)") or
                  self._extract_subject_name_from_pattern(question, r"(?:hay\s+fecha\s+de\s+(?:fallecimiento|defunci[oó]n)\s+de)\s+(.+?)(?:\?|$)") or
                  self._extract_subject_name_from_pattern(question, r"(?:cu[aá]ndo\s+se\s+produjo\s+la\s+defunci[oó]n\s+de)\s+(.+?)(?:\?|$)"))
        if not subject:
            return None
        person, _ = self._resolve_person(subject)
        if not person:
            return None
        if person.get('death_year'):
            answer = f"{person['name']} murió en {person['death_year']}."
        else:
            answer = f"No consta la fecha de muerte de {person['name']}."
        return {"answer": answer, "people_mentioned": [person['id']], "people_with_photos": self._people_payload([person])}

    def _extract_subject_name_from_pattern(self, question: str, pattern: str) -> Optional[str]:
        """Extract subject name from a specific pattern"""
        m = re.search(pattern, _clean_question(question), re.I)
        if m:
            return m.group(1)
        return None

    def _try_name_fallback(self, question):
        blockers = [
            r"t[ií]os?", r"primos", r"suegr", r"descendencia", r"abuelo", r"abuela",
            r"parentesco", r"relaci[oó]n", r"cu[aá]ntos?\s+herman", r"padres\s+y\s+los\s+hijos",
            r"de\s+qu[eé]\s+matrimonio", r"cas[oó]\s+o\s+emparej", r"era\s+.+\s+abuelo\s+o\s+abuela",
            r"ranking", r"porcentaje", r"longevidad", r"d[eé]cada", r"comparaci[oó]n\s+con\s+la\s+media", r"persona\s+con\s+m[aá]s\s+hijos",
        ]
        q = _clean_question(question)
        if any(re.search(b, q, re.I) for b in blockers):
            return None
        capitalized = re.findall(r"[A-ZÁÉÍÓÚÀÈÌÒÙÑÇ][^?!.;,]+", q)
        if capitalized:
            candidate = _normalize_name_fragment(capitalized[-1])
            person, matches = self._resolve_person(candidate)
            if person:
                if len(matches) == 1:
                    return self._build_targeted_response(person, question)
                parts = ["He encontrado varias coincidencias:"]
                for m in matches[:10]:
                    parts.append(f"- {_person_brief(m)}")
                return {"answer": "\n".join(parts), "people_mentioned": [m["id"] for m in matches[:10]], "people_with_photos": self._people_payload(matches[:10])}
        return None
