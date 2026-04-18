const chat = document.getElementById("chat");
const form = document.getElementById("query-form");
const input = document.getElementById("question");
const sendBtn = document.getElementById("send-btn");

let conversationHistory = [];

// --- Birthday widget ---
async function loadBirthdays() {
  try {
    const res = await fetch("/api/birthdays");
    if (!res.ok) return;
    const data = await res.json();
    if (!data.birthdays || data.birthdays.length === 0) return;

    const widget = document.getElementById("birthday-widget");
    const list = document.getElementById("birthday-list");
    widget.style.display = "block";

    list.innerHTML = data.birthdays
      .map((b) => {
        const photoHtml = b.photo
          ? `<img src="/photos/${b.photo}" alt="${b.name}" onerror="this.style.display='none'">`
          : `<div class="no-photo">${b.name.charAt(0)}</div>`;
        const ageText = b.age ? `${b.age} anys` : "";
        const aliveTag = b.is_alive ? '<span class="alive-tag">viu/a</span>' : "";
        const todayClass = b.is_today ? "today" : "";
        return `
        <div class="birthday-card ${todayClass}">
          ${photoHtml}
          <div class="birthday-name">${b.name}</div>
          <div class="birthday-date">${b.date_label} ${ageText}</div>
          ${aliveTag}
        </div>`;
      })
      .join("");
  } catch (e) {
    // silently fail
  }
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
    const photosHtml = buildPhotosHtml(data.people_with_photos);
    const sourceTag = '<span class="source-tag llm">IA</span>';
    container.innerHTML = `${sourceTag}<p>${data.answer.replace(/\n/g, "<br>")}</p>${photosHtml}`;

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

function buildPhotosHtml(people) {
  if (!people || people.length === 0) return "";
  const cards = people
    .filter((p) => p.photo)
    .map(
      (p) => `
    <div class="photo-card">
      <img src="/photos/${p.photo}" alt="${p.name}" onerror="this.style.display='none'">
      <div class="photo-name">${p.name}</div>
    </div>`
    )
    .join("");
  if (!cards) return "";
  return `<div class="photos-strip">${cards}</div>`;
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
    const photosHtml = buildPhotosHtml(data.people_with_photos);
    const sourceTag = data.source === "db" ? '<span class="source-tag db">Directa</span>' : "";
    addMessage(data.answer, "assistant", photosHtml, sourceTag);

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

// Load birthdays on page load
loadBirthdays();

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
