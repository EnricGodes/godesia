#!/usr/bin/env python3
"""Verifica respuestas de parentesco del banco GEDCOM contra la BD.

Calcula el parentesco desde las tablas (people/children/marriages) SIN pasar por
el router, para poder decidir quién tiene razón cuando regression_check.py marca
una diferencia: si el oráculo coincide con el router, lo que está viejo es el
banco (p.ej. gente añadida en una importación posterior) y toca refrescar sus
answer_entity_ids; si al banco le FALTAN personas que el oráculo sí encuentra,
el bug es del router.

Las relaciones de abajo son las que hubo que arbitrar el 17-sep-2026; añade las
que necesites siguiendo el mismo patrón.

    python3 scripts/verify_kinship_answers.py
"""
import sqlite3, json, sys

c = sqlite3.connect('data/godesia.db'); c.row_factory = sqlite3.Row
name = {r['id']: r['name'] for r in c.execute("select id,name from people")}
sex  = {r['id']: r['sex'] for r in c.execute("select id,sex from people")}

kids, parents = {}, {}
for r in c.execute("select parent_id, child_id from children"):
    kids.setdefault(r['parent_id'], set()).add(r['child_id'])
    parents.setdefault(r['child_id'], set()).add(r['parent_id'])
for r in c.execute("select id, father_id, mother_id from people"):
    for p in (r['father_id'], r['mother_id']):
        if p:
            parents.setdefault(r['id'], set()).add(p)
            kids.setdefault(p, set()).add(r['id'])

spouses = {}
for r in c.execute("select person1_id, person2_id from marriages"):
    spouses.setdefault(r['person1_id'], set()).add(r['person2_id'])
    spouses.setdefault(r['person2_id'], set()).add(r['person1_id'])

def up(s):    return {p for x in s for p in parents.get(x, ())}
def down(s):  return {k for x in s for k in kids.get(x, ())}
def sib(x):   return {s for p in parents.get(x, ()) for s in kids.get(p, ())} - {x}
def sp(s):    return {y for x in s for y in spouses.get(x, ())}

def ancestors(x):
    out, frontier = set(), {x}
    while frontier:
        frontier = up(frontier) - out
        out |= frontier
    return out

def gen_up(x, n):
    s = {x}
    for _ in range(n): s = up(s)
    return s

def gen_down(x, n):
    s = {x}
    for _ in range(n): s = down(s)
    return s

CASES = {
 "q0213 cuñados de Salvador Cabestany Carreras": (
     "@I500069@", lambda x: sp(sib(x)) | {s for y in spouses.get(x, ()) for s in sib(y)}),
 "q0265 tataranietos de Emili Godes Hurtado": ("@I10@", lambda x: gen_down(x, 4)),
 "q0480 antepasados de Clara Sisternas Mestre": ("@I141@", ancestors),
 "q0494 primos segundos de Bruna Cabestany Pallejà": (
     "@I500124@", lambda x: {y for y in down(down(down(gen_up(x, 3))))
                             if y != x and y not in sib(x)
                             and not (gen_up(x, 2) & gen_up(y, 2))}),
 "q0676 tatarabuelos de Joel Mestre Montaner": ("@I145@", lambda x: gen_up(x, 4)),
 "q0804 nietos varones de Ana Bausis Llestas": (
     "@I501269@", lambda x: {y for y in gen_down(x, 2) if sex.get(y) == 'M'}),
 "q0921 consuegros de Dolores Carreras Moyá": (
     "@I500068@", lambda x: {p for ch in kids.get(x, ()) for s in spouses.get(ch, ())
                             for p in parents.get(s, ())}),
 "q0939 tíos abuelos de Martin Fernando Eiras Cabestany": (
     "@I500973@", lambda x: {t for g in gen_up(x, 2) for t in sib(g)}),
}

bank = {q["id"]: q for q in json.load(open('data/gedcom_test_bank_es.json'))}
for label, (pid, fn) in CASES.items():
    qid = label.split()[0]
    got = fn(pid)
    old = set(bank[qid]["answer_entity_ids"])
    print(f"\n=== {label}")
    print(f"  oráculo: {len(got)} | banco: {len(old)}")
    print(f"  faltan respecto al banco (grave): {sorted(old - got)}")
    print(f"  nuevos respecto al banco: {[(i, name.get(i)) for i in sorted(got - old)]}")
