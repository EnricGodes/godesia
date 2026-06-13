#!/usr/bin/env python3
"""100 preguntas DIFÍCILES pero NO analíticas (sin Tier 4-5): estresan la
extracción y la clasificación de intención, no los agregados. Ancladas en datos
reales. FAIL = el router no entiende ("No he sabido responder…")."""

import re
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "backend"))
import database  # noqa: E402
from query_router import QueryRouter  # noqa: E402

QUESTIONS = [
    # --- Indirecto / coloquial (1-20) ---
    "Me podrías decir quiénes fueron los padres de Mercè Godes Caballeria, por favor.",
    "Tengo curiosidad, ¿sabes de qué trabajaba Ramón Godes Hurtado?",
    "Oye, ¿recuerdas dónde nació exactamente Pasqual Godes Segura?",
    "Dime una cosa, ¿quién era la madre de Pau Godes Caballeria?",
    "¿Sabrías decirme cuántos hermanos llegó a tener Dolors Godes Caballeria?",
    "A ver, ¿qué hijos tuvo Nicómedes Diago Marín a lo largo de su vida?",
    "¿Me sacas los nombres de los abuelos de Artur Godes Caballeria?",
    "¿Te suena con quién se casó Maria Rosa Godes Diago?",
    "Quisiera saber dónde está enterrado Artur Godes Caballeria.",
    "¿Podrías confirmarme en qué año murió Pasqual Godes Gomis?",
    "Perdona, ¿quién fue el padre de Antònia Diago Almuzara?",
    "¿No sabrás dónde vivía Jesus Godes Diago?",
    "Cuéntame, ¿qué hermanos tenía Ramona Godes Caballeria?",
    "¿Tú sabes qué oficio ejercía Pasqual Godes Segura?",
    "Si te acuerdas, ¿cuándo nació Emilia Hurtado Giró?",
    "¿Me dirías quiénes eran los hijos de Rosa Caballeria Madiroles?",
    "Una pregunta tonta: ¿dónde murió Emilia Hurtado Giró?",
    "¿Sería posible saber la profesión de Enric Cabestany Godes?",
    "¿Me confirmas quién era la esposa de Pasqual Godes Gomis?",
    "¿Sabes algo de los domicilios de Pau Godes Caballeria?",
    # --- Multi-salto / cadenas soportadas (21-30) ---
    "¿Quién era el padre de la madre de Mercè Godes Caballeria?",
    "¿Quién era el padre de la madre de Emili Godes Hurtado?",
    "¿Quiénes eran los abuelos paternos y maternos de Rosa Godes Hurtado?",
    "¿Cómo se llamaba el abuelo materno de Mercè Godes Caballeria?",
    "¿Quién fue la abuela paterna de Artur Godes Caballeria?",
    "¿Quién era el padre de la madre de Pau Godes Caballeria?",
    "¿Qué relación tenía Emili Godes Hurtado con los padres de Mercè Godes Caballeria?",
    "¿Quiénes eran los bisabuelos por la rama paterna de Emili Godes Hurtado?",
    "¿Cómo se llamaba la madre del padre de Ernest Godes Hurtado?",
    "¿Quién era el abuelo paterno por parte de padre de Rosa Godes Hurtado?",
    # --- Parentescos compuestos / políticos (31-45) ---
    "¿Quiénes eran los tíos abuelos de Mercè Godes Caballeria?",
    "¿Quiénes son los sobrinos nietos de Francesc Godes Martí?",
    "¿Quiénes eran los primos segundos de Rosa Godes Hurtado?",
    "¿Tenía consuegros documentados Francesc Godes Martí?",
    "¿Quiénes eran los suegros de Ernest Godes Hurtado?",
    "¿Tuvo algún yerno Pasqual Godes Gomis?",
    "¿Quién fue la nuera de Rosa Segura Falomir?",
    "¿Tenía cuñados Emili Godes Hurtado y cómo se llamaban?",
    "¿Quién era la cuñada de Mercè Godes Caballeria?",
    "¿Quiénes eran los primos hermanos de Pau Godes Caballeria?",
    "¿Me nombras los primos de Dolors Godes Caballeria?",
    "¿Quiénes eran los tíos y tías de Artur Godes Caballeria por parte de padre?",
    "¿Quiénes son los nietos de Pasqual Godes Segura?",
    "¿Quiénes eran los tatarabuelos de Ernest Godes Hurtado?",
    "¿Hay tataranietos de Francesc Godes Martí documentados?",
    # --- Bautismo / padrinos / militar / eventos / estudios / sepultura (46-65) ---
    "¿En qué fecha fue bautizada Mercè Godes Caballeria?",
    "¿Dónde se bautizó Artur Godes Caballeria?",
    "¿Cuándo recibió el bautismo Pasqual Godes Gomis?",
    "¿Quiénes fueron los padrinos de Emilia Hurtado Giró?",
    "¿Quién apadrinó a Ernest Godes Hurtado en su bautizo?",
    "¿Qué servicio militar consta de Ramón Godes Hurtado?",
    "¿Qué actividad militar tuvo Josep Maria Godes Hurtado?",
    "¿Hizo el servicio militar Artur Godes Hurtado?",
    "¿Qué eventos hay registrados en la ficha de Ramona Godes Caballeria?",
    "¿Qué acontecimientos figuran para Rosa Caballeria Madiroles?",
    "¿Hay datos de estudios de Josep Maria Godes Hurtado?",
    "¿Qué educación consta de Enric Godes Maté?",
    "¿Dónde está sepultado Pasqual Godes Gomis?",
    "¿En qué nicho descansa Artur Godes Caballeria?",
    "¿Quiénes fueron los padrinos de bautismo de Mercè Godes Caballeria?",
    "¿Qué notas biográficas constan sobre Ernest Godes Hurtado?",
    "¿Hay alguna observación biográfica sobre Emili Godes Hurtado?",
    "¿Qué información adicional hay sobre Artur Godes Caballeria?",
    "¿Cuándo fue bautizado Artur Godes Hurtado?",
    "¿Dónde recibió bautismo Emilia Hurtado Giró?",
    # --- Residencia: sub-modos y fraseo (66-72) ---
    "¿Cuál fue el primer domicilio de Mercè Godes Caballeria?",
    "¿Dónde vivía Emilia Hurtado Giró al final de su vida?",
    "¿En qué casa residió Antònia Diago Almuzara?",
    "¿Cuántas direcciones distintas tuvo Jesus Godes Diago?",
    "¿En qué domicilios estuvo Pau Godes Caballeria a lo largo de su vida?",
    "¿Cuál fue la última residencia de Emili Godes Hurtado?",
    "¿Dónde residió Mercè Godes Caballeria durante su vida?",
    # --- Matrimonio: ramas y fraseo (73-82) ---
    "¿En qué iglesia se casó Pasqual Godes Gomis?",
    "¿Con quién acabó casándose Maria Rosa Godes Diago?",
    "¿Dónde se celebró la boda de Artur Godes Caballeria?",
    "¿En qué fecha se casó Pasqual Godes Gomis?",
    "¿Con qué persona contrajo matrimonio Ernest Godes Hurtado?",
    "¿A qué edad se casó Artur Godes Caballeria?",
    "¿Quién fue el cónyuge de Rosa Caballeria Madiroles?",
    "¿Se casó más de una vez Maria Rosa Godes Diago?",
    "¿En qué lugar se casó Emili Godes Hurtado?",
    "¿Cuándo contrajo matrimonio Mercè Godes Caballeria?",
    # --- Variantes de nombre / desambiguación (83-90) ---
    "¿De qué trabajaba Ernesto Godes Molina?",
    "¿Quiénes fueron los padres de Ernesto Garrido Godes?",
    "¿Dónde nació Ernesto Godes Molina?",
    "¿Quién era el padre de Josep Godes Caballeria?",
    "¿Con quién se casó Jeroni Godes Sebastià?",
    "¿Qué hijos de Francesc Godes Martí nacieron en Morella?",
    "¿De qué matrimonio nació Mercè Godes Caballeria?",
    "¿Quién falleció en Barcelona en 1986?",
    # --- Coletillas / tiempos verbales / comparaciones entre dos (91-100) ---
    "¿Qué oficios tuvo Pasqual Godes Gomis durante toda su vida?",
    "¿Dónde residió Antònia Diago Almuzara a lo largo de su vida?",
    "¿Qué profesión ejerció Ramón Godes Hurtado según consta?",
    "¿En qué trabajaba Emili Godes Hurtado por aquel entonces?",
    "¿Cuántos hermanos se le conocen a Ernest Godes Hurtado?",
    "¿Qué hermanos y hermanas tuvo realmente Dolors Godes Caballeria?",
    "¿Sabes a qué se dedicaba el bueno de Jesus Godes Diago?",
    "¿Quién era mayor, Mercè Godes Caballeria o Dolors Godes Caballeria?",
    "¿Quién nació antes, Pau Godes Caballeria o Ramona Godes Caballeria?",
    "¿Eran primos Ernest Godes Hurtado y Maria Rosa Godes Diago?",
]


def main():
    assert len(QUESTIONS) == 100, f"esperaba 100, hay {len(QUESTIONS)}"
    conn = database.get_connection(str(BASE / "data" / "godesia.db"))
    router = QueryRouter(conn)
    fails = []
    for i, q in enumerate(QUESTIONS, 1):
        plain = re.sub(r"<[^>]+>", "", router.route(q).get("answer", "") or "")
        if plain.startswith("No he sabido responder"):
            fails.append((i, q))
    print(f"Resueltas: {100 - len(fails)}/100  ·  No entendidas: {len(fails)}")
    for i, q in fails:
        print(f"  ❌ #{i}: {q}")
    return fails


if __name__ == "__main__":
    main()
