const chat = document.getElementById("chat");
const form = document.getElementById("query-form");
const input = document.getElementById("question");
const sendBtn = document.getElementById("send-btn");

let conversationHistory = [];

// --- Person panel ---
async function showPersonPanel(personId) {
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

    const fatherHtml = d.father ? `<a href="/dossier.html?id=${encodeURIComponent(d.father.id)}">${d.father.name}</a>` : '';
    const motherHtml = d.mother ? `<a href="/dossier.html?id=${encodeURIComponent(d.mother.id)}">${d.mother.name}</a>` : '';
    const parentsHtml = [fatherHtml, motherHtml].filter(Boolean).join(' · ');

    const spousesHtml = (d.spouses || []).map(s =>
      `<a href="/dossier.html?id=${encodeURIComponent(s.id)}">${s.name}</a>`
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
        ${birthLine ? `<div class="panel-field"><span class="panel-label">Nacimiento</span><span class="panel-value">${birthLine}</span></div>` : ''}
        ${deathLine ? `<div class="panel-field"><span class="panel-label">Defunción</span><span class="panel-value">${deathLine}</span></div>` : ''}
        ${parentsHtml ? `<div class="panel-field"><span class="panel-label">Padres</span><span class="panel-value">${parentsHtml}</span></div>` : ''}
        ${spousesHtml ? `<div class="panel-field"><span class="panel-label">Cónyuge${(d.spouses||[]).length > 1 ? 's' : ''}</span><span class="panel-value">${spousesHtml}</span></div>` : ''}
        ${d.children && d.children.length > 0 ? `<div class="panel-field"><span class="panel-label">Hijos</span><span class="panel-value">${d.children.length}</span></div>` : ''}
      </div>
      <div class="panel-actions">
        <a href="/dossier.html?id=${encodeURIComponent(p.id)}" class="panel-btn">Ver dossier completo</a>
        <a href="/arbol2.html?id=${cleanId}" class="panel-btn panel-btn-secondary">Ver en árbol</a>
      </div>
    `;
  } catch(e) {
    panel.classList.remove('open');
  }
}

function closePersonPanel() {
  document.getElementById('person-panel').classList.remove('open');
}

// --- Chat ---
function addMessage(content, role, photosHtml = "", sourceTag = "") {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.innerHTML = `
    <div class="message-content">
      ${sourceTag}
      <p>${content.replace(/\n/g, "<br>")}</p>
      ${photosHtml}
    </div>
  `;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function addLLMConfirmation(message, question, history) {
  const div = document.createElement("div");
  div.className = "message assistant";
  div.innerHTML = `
    <div class="message-content llm-confirm">
      <p class="cost-warning">${message}</p>
      <div class="confirm-buttons">
        <button class="btn-confirm" onclick="confirmLLM(this, '${btoa(encodeURIComponent(question))}')">Si, consultar</button>
        <button class="btn-cancel" onclick="cancelLLM(this)">No, cancel-lar</button>
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
      body: JSON.stringify({ question, history: conversationHistory }),
    });

    container.querySelector(".loading").remove();

    if (!res.ok) {
      container.innerHTML += "<p>Error al consultar la IA.</p>";
      sendBtn.disabled = false;
      return;
    }

    const data = await res.json();
    const peopleLlm = data.people_with_photos || [];
    const pillsLlm = buildPeoplePills(peopleLlm);
    const sourceTag = '<span class="source-tag llm">IA</span>';
    container.innerHTML = `${sourceTag}<p>${data.answer.replace(/\n/g, "<br>")}</p>${pillsLlm}`;

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
    container.innerHTML += "<p>Error de connexió.</p>";
  }

  sendBtn.disabled = false;
  input.focus();
}

function cancelLLM(btn) {
  const container = btn.closest(".llm-confirm");
  container.querySelector(".confirm-buttons").remove();
  container.innerHTML += "<p class='hint'>Consulta cancel-lada. Cap cost generat.</p>";
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

function buildPeoplePills(people) {
  if (!people || people.length === 0) return "";
  const pills = people.map(p => {
    const id = p.id.replace(/@/g, '');
    const name = p.name.trim();
    return `<button class="person-pill" onclick="showPersonPanel('${id}')">${name}</button>`;
  }).join("");
  return `<div class="person-pills">${pills}</div>`;
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
      body: JSON.stringify({ question, history: conversationHistory }),
    });

    removeLoading();

    if (!res.ok) {
      addMessage("Error al consultar. Inténtalo de nuevo.", "assistant");
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
    const pillsHtml = buildPeoplePills(people);
    addMessage(data.answer, "assistant", pillsHtml);

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
    addMessage("Error de connexió. Està el servidor actiu?", "assistant");
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
    return `<li style="margin:4px 0"><a href="/dossier.html?id=${encodeURIComponent(p.id)}" style="color:#2D4B33;font-weight:600;text-decoration:none">${p.name}</a>${yearsLabel}</li>`;
  }).join('');
  const asstDiv = document.createElement('div');
  asstDiv.className = 'message assistant';
  const hasMore = results.length === 50;
  const moreMsg = hasMore ? '<p style="margin-top:12px;color:#666;font-size:0.9em"><em>He encontrado más de 50 resultados. Te muestro los primeros 50. Intenta refinar tu búsqueda para obtener resultados más específicos.</em></p>' : '';
  asstDiv.innerHTML = `<div class="message-content">He encontrado ${results.length} personas que coinciden con "<strong>${q}</strong>". Haz clic sobre la que buscas:<ul style="margin-top:8px;padding-left:20px">${list}</ul>${moreMsg}</div>`;
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
