#!/usr/bin/env python3
"""Externaliza las frases de respuesta de query_router.py a answers_es.json.

Transformación mecánica por AST: localiza literales de respuesta (f-strings y
strings) en los contextos donde se construyen respuestas y los sustituye por
llamadas a _t("clave", a=..., b=...). La clave se deriva de la función
contenedora (p.ej. "handle_parents.2") y la plantilla española se vuelca a
backend/answers/answers_es.json con placeholders {a}, {b}, ...

Contextos considerados:
  - answer = <str>/<fstr>  (también +=, y ambas ramas de un ternario)
  - "answer": <str>/<fstr> en dicts
  - <lista>.append(<str>/<fstr>)

Se excluyen: raw strings (regex de matching), literales sin palabras (solo
formato), f-strings con format_spec o !conversion.

Verificación: scripts/baseline_router_answers.py antes y después debe dar
salida byte-idéntica.
"""

import ast
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
SRC = BASE / "backend" / "query_router.py"
OUT = BASE / "backend" / "answers" / "answers_es.json"

PLACEHOLDERS = "abcdefghijklmnopqrstuvwxyz"

# Al menos una palabra de 2+ letras en el texto estático (fuera de placeholders)
WORD_RE = re.compile(r"[A-Za-zÀ-ÿ]{2}")


def has_words(text: str) -> bool:
    return bool(WORD_RE.search(text))


def is_raw_literal(source_segment: str) -> bool:
    prefix = source_segment[:2].lower()
    return prefix.startswith("r") or prefix in ("rf", "fr", "rb")


class Candidate:
    def __init__(self, node, func_name):
        self.node = node
        self.func_name = func_name


def find_candidates(tree):
    # Mapa de padres para localizar la función contenedora
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def enclosing_function(node):
        cur = parents.get(node)
        while cur is not None:
            if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return cur.name
            cur = parents.get(cur)
        return "module"

    def string_leaves(node):
        """Devuelve los nodos string externalizables de una expresión."""
        if isinstance(node, ast.JoinedStr):
            return [node]
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node]
        if isinstance(node, ast.IfExp):
            return string_leaves(node.body) + string_leaves(node.orelse)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return string_leaves(node.left) + string_leaves(node.right)
        return []

    SPANISH_RE = re.compile(r"[áéíóúñÁÉÍÓÚ¿¡]")
    TARGET_NAMES = {"answer", "ans", "older", "older_text", "yr", "death", "birth", "header"}

    candidates = []
    for node in ast.walk(tree):
        exprs = []
        # answer = ... / answer += ...
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id in TARGET_NAMES for t in node.targets):
                exprs.append(node.value)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name) and node.target.id in TARGET_NAMES:
                exprs.append(node.value)
        # dict {"answer": ...}
        elif isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == "answer":
                    exprs.append(v)
        # llamadas: <lista>.append(...), keyword answer=..., _list_people_answer(msg, ...)
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == "append" and len(node.args) == 1:
                exprs.append(node.args[0])
            if isinstance(f, ast.Attribute) and f.attr == "_list_people_answer" and node.args:
                exprs.append(node.args[0])
            for kw in node.keywords:
                if kw.arg == "answer":
                    exprs.append(kw.value)
        # return "..." — solo con evidencia clara de español (etiquetas de parentesco)
        elif isinstance(node, ast.Return) and node.value is not None:
            for leaf in string_leaves(node.value):
                text = leaf.value if isinstance(leaf, ast.Constant) else "".join(
                    v.value for v in leaf.values if isinstance(v, ast.Constant))
                if SPANISH_RE.search(text or ""):
                    candidates.append(Candidate(leaf, enclosing_function(node)))
            continue

        for expr in exprs:
            for leaf in string_leaves(expr):
                candidates.append(Candidate(leaf, enclosing_function(node)))
    return candidates


def build_template(node, source):
    """(plantilla, [(nombre, expresión_fuente)]) para un nodo string; None si no aplica."""
    if isinstance(node, ast.Constant):
        return node.value, []

    template = []
    args = []
    for value in node.values:
        if isinstance(value, ast.Constant):
            template.append(str(value.value))
        elif isinstance(value, ast.FormattedValue):
            # ast.unparse: en Python <3.12 las posiciones de las expresiones
            # internas de un f-string no son fiables para get_source_segment
            try:
                expr_src = ast.unparse(value.value)
            except Exception:
                return None
            # !s/!r → str()/repr(); :spec constante → format(expr, 'spec')
            if value.conversion == 115:
                expr_src = f"str({expr_src})"
            elif value.conversion == 114:
                expr_src = f"repr({expr_src})"
            elif value.conversion != -1:
                return None
            if value.format_spec is not None:
                spec = value.format_spec
                if (isinstance(spec, ast.JoinedStr) and len(spec.values) == 1
                        and isinstance(spec.values[0], ast.Constant)):
                    expr_src = f"format({expr_src}, '{spec.values[0].value}')"
                else:
                    return None  # spec dinámica: se deja inline
            name = PLACEHOLDERS[len(args)] if len(args) < len(PLACEHOLDERS) else f"p{len(args)}"
            template.append("{" + name + "}")
            args.append((name, expr_src))
        else:
            return None
    return "".join(template), args


def main():
    source = SRC.read_text(encoding="utf-8")
    tree = ast.parse(source)
    # ast usa offsets de columna en BYTES utf-8: trabajar sobre bytes
    source_bytes = source.encode("utf-8")
    lines = source_bytes.splitlines(keepends=True)
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln))

    def span(node):
        return (offsets[node.lineno - 1] + node.col_offset,
                offsets[node.end_lineno - 1] + node.end_col_offset)

    candidates = find_candidates(tree)

    # Filtrado + preparación
    prepared = []
    counters = {}
    skipped = {"raw": 0, "no_words": 0, "complex": 0}
    for cand in candidates:
        start, end = span(cand.node)
        segment = source_bytes[start:end].decode("utf-8")
        if is_raw_literal(segment):
            skipped["raw"] += 1
            continue
        built = build_template(cand.node, source)
        if built is None:
            skipped["complex"] += 1
            continue
        template, args = built
        static_text = re.sub(r"\{[a-z]\}|\{p\d+\}", "", template)
        if not has_words(static_text):
            skipped["no_words"] += 1
            continue
        counters[cand.func_name] = counters.get(cand.func_name, 0) + 1
        key = f"{cand.func_name}.{counters[cand.func_name]}"
        prepared.append((start, end, key, template, args))

    # Reescritura de atrás hacia delante (sobre bytes, offsets ast)
    prepared.sort(key=lambda x: -x[0])
    templates = {}
    new_bytes = source_bytes
    for start, end, key, template, args in prepared:
        templates[key] = template
        arg_src = "".join(f", {name}={expr}" for name, expr in args)
        replacement = f'_t("{key}"{arg_src})'.encode("utf-8")
        new_bytes = new_bytes[:start] + replacement + new_bytes[end:]

    SRC.write_text(new_bytes.decode("utf-8"), encoding="utf-8")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(dict(sorted(templates.items())), ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"✓ {len(prepared)} plantillas externalizadas → {OUT.relative_to(BASE)}")
    print(f"  omitidos: {skipped['raw']} raw, {skipped['no_words']} sin palabras, {skipped['complex']} formato complejo")


if __name__ == "__main__":
    sys.exit(main())
