# Guía de traducción (i18n)

Listado de todo lo que hay que traducir para añadir un idioma a la web pública.
El **español es siempre la base y el fallback**: lo que no traduzcas se muestra
en español, así que se puede ir por partes sin romper nada.

Para cada idioma nuevo (`ca`, `en`, `fr`…) se copia cada archivo `.es.json` con
el sufijo del idioma (`.ca.json`, `.en.json`…) y se traducen los **valores**,
nunca las claves.

> **Antes de empezar con un idioma que no sea `ca`/`en`:** darlo de alta en
> **admin › Configuración › Idiomas activos** (código de 2-3 letras + etiqueta).

---

## 1. UI de la web — 1 archivo (357 claves) HECHO!

| Origen | Crear |
|---|---|
| `frontend/locales/ui.es.json` | `frontend/locales/ui.ca.json`, `ui.en.json`, … |

**Reglas:**
- No traduzcas los placeholders `{name}`, `{count}`, `{from}`, `{to}`… — solo el texto alrededor.
- No traduzcas el HTML embebido (`<strong>`, `<em>`, `<span>`), solo su contenido de texto.
- Las claves **`pages.chat.q_*`** (preguntas que generan los chips del chat) se traducen **solo si ese idioma tiene un reescritor de preguntas** en `backend/routing/rewrite_<código>.py` (hoy: catalán, inglés y francés). Al pulsar el chip, la pregunta se muestra en el chat y se envía al router; con reescritor, se traduce a español y resuelve. Para idiomas **sin** reescritor todavía (alemán), déjalas **en español** para que sigan resolviendo (la respuesta ya sale en el idioma de la interfaz). Tras traducir un `q_*`, valídalo: `python3 scripts/parity_check.py --lang <código>`.
- Los arrays `dates.months` y `dates.months_short` conservan el primer elemento vacío `""`.

---

## 2. Respuestas del chat (QueryRouter) — 1 archivo (337 plantillas) HECHO!

| Origen | Crear |
|---|---|
| `backend/answers/answers_es.json` | `backend/answers/answers_ca.json`, `answers_en.json`, … |

**Reglas:**
- Conserva exactamente los placeholders `{a}`, `{b}`, `{c}`…
- Conserva el HTML (`<strong>`, `<br>`) y los emojis.
- Un archivo `answers_*.json` nuevo requiere **reiniciar el servidor** la primera vez (se cachea al arrancar).

---

## 3. Sagas / ramas — 20 archivos (634 bloques) HECHO

Carpeta `frontend/locales/sagas/`, uno por saga e idioma
(p. ej. `godes_diago.ca.json`). Se puede ir **saga a saga**: lo no traducido
queda en español.

| Origen (`.es.json`) | Bloques | | Origen (`.es.json`) | Bloques |
|---|---:|---|---|---:|
| `godes_hurtado` | 62 | | `godes_mate` | 19 |
| `godes_caballeria` | 58 | | `garrido_godes` | 19 |
| `godes_segura` | 56 | | `pujol_perez` | 16 |
| `godes_molina` | 46 | | `mestre_godes` | 15 |
| `godes_schmid` | 45 | | `nolla_godes` | 13 |
| `pujol_godes` | 44 | | `millan_godes` | 12 |
| `godes_hospital` | 42 | | `cabestany_godes` | 11 |
| `godes_terrats` | 41 | | `godes_faura` | 11 |
| `godes_diago` | 40 | | `puig_godes` | 11 |
| `godes_guell` | 40 | | | |
| `godes_ferrer` | 33 | | **Total** | **634** |

**Reglas:**
- Los valores son **fragmentos HTML**. Conserva intactos los enlaces
  `<a href="/dossier.html?id=IXX" class="saga-person-link">…</a>`: traduce solo
  el texto, nunca los nombres de persona ni los IDs.
- Los arrays (p. ej. `timeline`) mantienen un `<li>…</li>` por elemento.

---

## 4. Contenidos editables desde el admin (no se copian archivos)

Se traducen dentro del panel de administración; el modal genera un campo por
idioma activo.

| Contenido | Dónde | Volumen | Estado |
|---|---|---|---|
| Minibiografías | admin › Minibios (`data/minibios.json`) | 922 registros | **catalán completo** (922/922); falta inglés |
| Anécdotas | admin › Anécdotas (`data/anecdotas.json`) | 54 × (título + texto + CTA) | solo español |

**Reglas:**
- En el CTA de las anécdotas conserva la palabra marcador de la clave
  `pages.index.cta_marker` de ese idioma (en español es `"sobre "`, p. ej.
  «Saber más **sobre** Artur…»): el dashboard la usa para enlazar al dossier.

---

## Resumen por idioma

| Idioma | Archivos JSON | Admin |
|---|---|---|
| **Catalán (`ca`)** | 22 (`ui.ca.json` + `answers_ca.json` + 20 sagas) | 54 anécdotas (minibios ya hechas) |
| **Inglés (`en`)** | 22 | 54 anécdotas + 922 minibios |
| **Otros (`fr`, `de`…)** | 22 | 54 anécdotas + 922 minibios |

**Total por idioma:** 357 + 337 + 634 = **1.328 cadenas** en JSON, más los
contenidos del admin.

## Notas de despliegue

- Al colocar un `ui.*.json` o una saga `*.json` nuevos, el backend los recoge
  solos (detecta el cambio por fecha de modificación). Solo los `answers_*.json`
  nuevos requieren reiniciar el servidor la primera vez.
- Estos archivos van **en el repo** (git). Tras traducir, commit + push para que
  Railway los sirva.
- Regenerar un `.es.json` (cuando se añaden textos nuevos al código) se hace con
  scripts, nunca a mano: `scripts/extract_ui_strings.py` (UI),
  `scripts/extract_saga_content.py` (sagas),
  `scripts/externalize_router_strings.py` (respuestas del router).
