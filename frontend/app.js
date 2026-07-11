const chat = document.getElementById("chat");
const form = document.getElementById("query-form");
const input = document.getElementById("question");
const sendBtn = document.getElementById("send-btn");

/* i18n: t()/I18N vienen de i18n.js (inyectado por el backend) */
const _i18nT = window.t || function (k, p, f) { return f !== undefined ? f : k; };
const _lhref = window.I18N ? window.I18N.href : function (p) { return p; };
const _lang = window.I18N ? window.I18N.lang() : 'es';

let conversationHistory = [];
let _lastAssistantMsg = null;

// Build the ?id= param for a dossier link, stripping GEDCOM @ wrappers (@I104@ → I104).
function dossierIdParam(id) {
  return encodeURIComponent((id || '').replace(/@/g, ''));
}

// --- Person panel ---
function markActivePill(personId) {
  const cleanId = personId.replace(/@/g, '');
  document.querySelectorAll('.person-pill').forEach(pill => {
    const href = pill.getAttribute('href') || '';
    try {
      const id = (new URL(href, location.origin).searchParams.get('id') || '').replace(/@/g, '');
      pill.classList.toggle('active', id === cleanId);
    } catch(e) {}
  });
}

async function showPersonPanel(personId) {
  markActivePill(personId);
  const panel = document.getElementById('person-panel');
  const content = document.getElementById('person-panel-content');
  panel.classList.add('open');
  content.innerHTML = '<div class="panel-loading"><span></span><span></span><span></span></div>';

  try {
    const res = await fetch(`/api/dossier/${encodeURIComponent(personId)}`);
    if (!res.ok) { panel.classList.remove('open'); return; }
    const d = await res.json();
    const p = d.person;

    const photoSrc = p.photo_file ? `/photos/${p.photo_file}` : null;
    const initials = (p.given_name || p.name || '?')[0].toUpperCase();

    let years = '';
    if (p.birth_year && p.death_year) years = `${p.birth_year} – ${p.death_year}`;
    else if (p.birth_year && p.is_alive) years = `n. ${p.birth_year}`;
    else if (p.birth_year) years = `${p.birth_year} – ?`;

    const birthLine = [p.birth_date, p.birth_city || p.birth_place].filter(Boolean).join(', ');
    const deathLine = [p.death_date, p.death_city || p.death_place].filter(Boolean).join(', ');

    const fatherHtml = d.father ? `<a href="${_lhref('/dossier.html?id=' + dossierIdParam(d.father.id))}">${d.father.name}</a>` : '';
    const motherHtml = d.mother ? `<a href="${_lhref('/dossier.html?id=' + dossierIdParam(d.mother.id))}">${d.mother.name}</a>` : '';
    const parentsHtml = [fatherHtml, motherHtml].filter(Boolean).join(' · ');

    const spousesHtml = (d.spouses || []).map(s =>
      `<a href="${_lhref('/dossier.html?id=' + dossierIdParam(s.id))}">${s.name}</a>`
    ).join(' · ');

    const cleanId = personId.replace(/@/g, '');

    content.innerHTML = `
      <div class="panel-header">
        ${photoSrc
          ? `<img class="panel-photo" src="${photoSrc}" alt="${p.name}" onerror="this.src=''; this.outerHTML='<div class=panel-photo-placeholder>${initials}</div>'">`
          : `<div class="panel-photo-placeholder">${initials}</div>`}
        <h2 class="panel-name">${p.name}</h2>
        ${p.nickname ? `<p class="panel-nickname">"${p.nickname}"</p>` : ''}
        ${years ? `<p class="panel-years">${years}</p>` : ''}
      </div>
      <div class="panel-fields">
        ${birthLine ? `<div class="panel-field"><span class="panel-label">${_i18nT('common.birth', null, 'Nacimiento')}</span><span class="panel-value">${birthLine}</span></div>` : ''}
        ${deathLine ? `<div class="panel-field"><span class="panel-label">${_i18nT('common.death', null, 'Defunción')}</span><span class="panel-value">${deathLine}</span></div>` : ''}
        ${parentsHtml ? `<div class="panel-field"><span class="panel-label">${_i18nT('common.parents', null, 'Padres')}</span><span class="panel-value">${parentsHtml}</span></div>` : ''}
        ${spousesHtml ? `<div class="panel-field"><span class="panel-label">${(d.spouses||[]).length > 1 ? _i18nT('common.spouses', null, 'Cónyuges') : _i18nT('common.spouse', null, 'Cónyuge')}</span><span class="panel-value">${spousesHtml}</span></div>` : ''}
        ${d.children && d.children.length > 0 ? `<div class="panel-field"><span class="panel-label">${_i18nT('common.children', null, 'Hijos')}</span><span class="panel-value">${d.children.length}</span></div>` : ''}
      </div>
      <div class="panel-actions">
        <a href="${_lhref('/dossier.html?id=' + dossierIdParam(p.id))}" class="panel-btn">${_i18nT('pages.chat.view_dossier', null, 'Ver dossier completo')}</a>
        <a href="${_lhref('/arbol2.html?id=' + cleanId)}" class="panel-btn panel-btn-secondary">${_i18nT('pages.chat.view_tree', null, 'Ver en árbol')}</a>
      </div>
    `;

    if (_lastAssistantMsg) {
      addFollowUpChips(_lastAssistantMsg, p.name, d);
    }
  } catch(e) {
    panel.classList.remove('open');
  }
}

function closePersonPanel() {
  document.getElementById('person-panel').classList.remove('open');
  document.querySelectorAll('.person-pill.active').forEach(p => p.classList.remove('active'));
}

// --- Chat ---
function addMessage(content, role, sourceTag = "") {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.innerHTML = `
    <div class="message-content">
      ${sourceTag}
      <p>${content.replace(/\n/g, "<br>")}</p>
    </div>
  `;
  if (window.I18N) I18N.localizeLinks(div);
  // Style dossier links as pills that open the person panel
  div.querySelectorAll('a[href*="/dossier.html"]').forEach(a => {
    const id = new URL(a.href, location.origin).searchParams.get('id');
    if (!id) return;
    a.classList.add('person-pill');
    a.addEventListener('click', e => { e.preventDefault(); showPersonPanel(id); });
  });
  chat.appendChild(div);
  if (role === 'assistant') _lastAssistantMsg = div;
  chat.scrollTop = chat.scrollHeight;
}

function addFollowUpChips(msgDiv, personName, dossier) {
  const content = msgDiv.querySelector('.message-content');
  if (!content) return;
  content.querySelectorAll('.followup-chips').forEach(el => el.remove());

  const chips = [];
  const n = personName;
  chips.push({ label: _i18nT('pages.chat.chip_parents', null, 'Padres'), q: _i18nT('pages.chat.q_parents', {name: n}, 'Padres de {name}') });
  chips.push({ label: _i18nT('pages.chat.chip_siblings', null, 'Hermanos'), q: _i18nT('pages.chat.q_siblings', {name: n}, 'Hermanos de {name}') });
  chips.push({ label: _i18nT('pages.chat.chip_birthplace', null, 'Dónde nació'), q: _i18nT('pages.chat.q_birthplace', {name: n}, 'Dónde nació {name}') });
  if (dossier.children && dossier.children.length > 0) {
    chips.push({ label: _i18nT('pages.chat.chip_children', null, 'Hijos'), q: _i18nT('pages.chat.q_children', {name: n}, 'Hijos de {name}') });
    chips.push({ label: _i18nT('pages.chat.chip_first_child', null, 'Edad primer hijo'), q: _i18nT('pages.chat.q_first_child', {name: n}, 'A qué edad tuvo su primer hijo {name}') });
  }
  if (dossier.spouses && dossier.spouses.length > 0) {
    chips.push({ label: _i18nT('pages.chat.chip_spouse', null, 'Cónyuge'), q: _i18nT('pages.chat.q_spouse', {name: n}, 'Con quién se casó {name}') });
    chips.push({ label: _i18nT('pages.chat.chip_marriage_age', null, 'Edad al casarse'), q: _i18nT('pages.chat.q_marriage_age', {name: n}, 'A qué edad se casó {name}') });
  }
  if (dossier.occupations && dossier.occupations.length > 0) {
    chips.push({ label: _i18nT('pages.chat.chip_occupation', null, 'Profesión'), q: _i18nT('pages.chat.q_occupation', {name: n}, 'De qué trabajaba {name}') });
  }
  if (!dossier.person.is_alive) {
    chips.push({ label: _i18nT('pages.chat.chip_deathplace', null, 'Dónde murió'), q: _i18nT('pages.chat.q_deathplace', {name: n}, 'Dónde murió {name}') });
  }

  const row = document.createElement('div');
  row.className = 'followup-chips';
  chips.forEach(({ label, q }) => {
    const btn = document.createElement('button');
    btn.className = 'followup-chip';
    btn.textContent = label;
    btn.addEventListener('click', () => submitFollowUp(q));
    row.appendChild(btn);
  });
  content.appendChild(row);
}

function submitFollowUp(question) {
  input.value = question;
  form.dispatchEvent(new Event('submit'));
}

function addLLMConfirmation(message, question, history) {
  const div = document.createElement("div");
  div.className = "message assistant";
  div.innerHTML = `
    <div class="message-content llm-confirm">
      <p class="cost-warning">${message}</p>
      <div class="confirm-buttons">
        <button class="btn-confirm" onclick="confirmLLM(this, '${btoa(encodeURIComponent(question))}')">${_i18nT('pages.chat.llm_confirm', null, 'Sí, consultar')}</button>
        <button class="btn-cancel" onclick="cancelLLM(this)">${_i18nT('pages.chat.llm_cancel', null, 'No, cancelar')}</button>
      </div>
    </div>
  `;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

async function confirmLLM(btn, encodedQuestion) {
  const question = decodeURIComponent(atob(encodedQuestion));
  const container = btn.closest(".llm-confirm");
  container.querySelector(".confirm-buttons").remove();
  container.innerHTML += '<div class="loading"><span></span><span></span><span></span></div>';

  try {
    const res = await fetch("/api/query/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history: conversationHistory, lang: _lang }),
    });

    container.querySelector(".loading").remove();

    if (!res.ok) {
      container.innerHTML += `<p>${_i18nT('pages.chat.llm_error', null, 'Error al consultar la IA.')}</p>`;
      sendBtn.disabled = false;
      return;
    }

    const data = await res.json();
    const peopleLlm = data.people_with_photos || [];
    const sourceTag = '<span class="source-tag llm">IA</span>';
    container.innerHTML = `${sourceTag}<p>${data.answer.replace(/\n/g, "<br>")}</p>`;
    if (window.I18N) I18N.localizeLinks(container);
    container.querySelectorAll('a[href*="/dossier.html"]').forEach(a => {
      const id = new URL(a.href, location.origin).searchParams.get('id');
      if (!id) return;
      a.classList.add('person-pill');
      a.addEventListener('click', e => { e.preventDefault(); showPersonPanel(id); });
    });

    if (peopleLlm.length === 1) {
      showPersonPanel(peopleLlm[0].id.replace(/@/g, ''));
    } else {
      closePersonPanel();
    }

    conversationHistory.push({ role: "user", content: question });
    conversationHistory.push({ role: "assistant", content: data.answer });
    if (conversationHistory.length > 20) {
      conversationHistory = conversationHistory.slice(-20);
    }
  } catch (e) {
    container.innerHTML += `<p>${_i18nT('common.connection_error', null, 'Error de conexión.')}</p>`;
  }

  sendBtn.disabled = false;
  input.focus();
}

function cancelLLM(btn) {
  const container = btn.closest(".llm-confirm");
  container.querySelector(".confirm-buttons").remove();
  container.innerHTML += `<p class='hint'>${_i18nT('pages.chat.llm_cancelled', null, 'Consulta cancelada. Sin coste generado.')}</p>`;
  sendBtn.disabled = false;
  input.focus();
}

function addLoading() {
  const div = document.createElement("div");
  div.className = "message assistant";
  div.id = "loading-msg";
  div.innerHTML = `<div class="message-content"><div class="loading"><span></span><span></span><span></span></div></div>`;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function removeLoading() {
  const el = document.getElementById("loading-msg");
  if (el) el.remove();
}


form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = input.value.trim();
  if (!question) return;

  addMessage(question, "user");
  input.value = "";
  sendBtn.disabled = true;
  addLoading();

  try {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history: conversationHistory, lang: _lang }),
    });

    removeLoading();

    if (!res.ok) {
      addMessage(_i18nT('pages.chat.query_error', null, 'Error al consultar. Inténtalo de nuevo.'), "assistant");
      sendBtn.disabled = false;
      return;
    }

    const data = await res.json();

    // LLM confirmation required?
    if (data.requires_llm) {
      addLLMConfirmation(data.message, question, conversationHistory);
      return;
    }

    // Direct DB answer
    const people = data.people_with_photos || [];
    addMessage(data.answer, "assistant");

    // Auto-open panel if exactly 1 person, otherwise close
    if (people.length === 1) {
      showPersonPanel(people[0].id.replace(/@/g, ''));
    } else {
      closePersonPanel();
    }

    conversationHistory.push({ role: "user", content: question });
    conversationHistory.push({ role: "assistant", content: data.answer });
    if (conversationHistory.length > 20) {
      conversationHistory = conversationHistory.slice(-20);
    }
  } catch (err) {
    removeLoading();
    addMessage(_i18nT('common.connection_error_server', null, 'Error de conexión. ¿Está el servidor activo?'), "assistant");
  }

  sendBtn.disabled = false;
  input.focus();
});

// Render a list of people as an assistant message with clickable links
function renderPeopleList(q, results) {
  input.value = q;
  // Echo user's search
  const userDiv = document.createElement('div');
  userDiv.className = 'message user';
  userDiv.innerHTML = `<div class="message-content"><p>${q}</p></div>`;
  chat.appendChild(userDiv);

  // List of matches
  const list = results.map(p => {
    let years;
    if (p.birth_year && p.death_year) years = `${p.birth_year}–${p.death_year}`;
    else if (p.birth_year && !p.death_year && !p.is_alive) years = `${p.birth_year}–?`;
    else if (p.birth_year) years = `${p.birth_year}`;
    else if (p.death_year) years = `?–${p.death_year}`;
    else if (!p.is_alive) years = `?–?`;
    else years = '';
    const yearsLabel = years ? ` (${years})` : '';
    return `<li style="margin:4px 0"><a href="${_lhref('/dossier.html?id=' + dossierIdParam(p.id))}" style="color:#2D4B33;font-weight:600;text-decoration:none">${p.name}</a>${yearsLabel}</li>`;
  }).join('');
  const asstDiv = document.createElement('div');
  asstDiv.className = 'message assistant';
  const hasMore = results.length === 50;
  const moreMsg = hasMore ? `<p style="margin-top:12px;color:#666;font-size:0.9em"><em>${_i18nT('pages.chat.more_results', null, 'He encontrado más de 50 resultados. Te muestro los primeros 50. Intenta refinar tu búsqueda para obtener resultados más específicos.')}</em></p>` : '';
  asstDiv.innerHTML = `<div class="message-content">${_i18nT('pages.chat.matches_intro', {count: results.length, query: q}, 'He encontrado {count} personas que coinciden con "<strong>{query}</strong>". Haz clic sobre la que buscas:')}<ul style="margin-top:8px;padding-left:20px">${list}</ul>${moreMsg}</div>`;
  chat.appendChild(asstDiv);
  chat.scrollTop = chat.scrollHeight;
}

// Handle search matches: fetch results fresh from API and render
const urlParams = new URLSearchParams(window.location.search);
const matchesQ = urlParams.get('matches');
if (matchesQ) {
  (async () => {
    try {
      const res = await fetch('/api/search?q=' + encodeURIComponent(matchesQ) + '&limit=50');
      const data = await res.json();
      if (data.results && data.results.length > 0) {
        renderPeopleList(matchesQ, data.results);
      }
    } catch (e) {}
  })();
} else {
  // Auto-submit query from URL param (e.g. ?q=who+is...)
  const urlQ = urlParams.get('q');
  if (urlQ) {
    input.value = urlQ;
    form.dispatchEvent(new Event('submit'));
    window.history.replaceState({}, '', window.location.pathname);
  }
}
