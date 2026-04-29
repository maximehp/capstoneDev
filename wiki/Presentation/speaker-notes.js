const statusEl = document.getElementById("connection-status");
const countEl = document.getElementById("slide-count");
const speakerEl = document.getElementById("speaker");
const titleEl = document.getElementById("slide-title");
const notesEl = document.getElementById("notes");

async function loadSpeakerNotes() {
  try {
    const response = await fetch("speaker-notes.yaml", { cache: "no-store" });
    if (!response.ok || !window.jsyaml) {
      return {};
    }
    return window.jsyaml.load(await response.text())?.slides || {};
  } catch {
    return {};
  }
}

function plainNotes(html) {
  const container = document.createElement("div");
  container.innerHTML = html || "";
  return container.textContent?.trim() || "";
}

function renderState(state, notesBySlide) {
  const yamlNotes = notesBySlide[state.file] || {};
  const speaker = yamlNotes.speaker || state.speaker || "Speaker notes";
  const notes = yamlNotes.notes || plainNotes(state.notes) || "No notes for this slide yet.";

  document.body.classList.remove("offline");
  statusEl.textContent = "Connected to presenter";
  countEl.textContent = `${Number(state.index) + 1} / ${state.total}`;
  speakerEl.textContent = speaker.replace(/^Speaker:\s*/i, "");
  titleEl.textContent = yamlNotes.title || state.title || "Untitled slide";
  notesEl.textContent = notes;
}

function setOffline(message) {
  document.body.classList.add("offline");
  statusEl.textContent = message;
}

const notesBySlide = await loadSpeakerNotes();

if (window.EventSource) {
  const events = new EventSource("speaker/events");
  events.addEventListener("message", (event) => {
    renderState(JSON.parse(event.data), notesBySlide);
  });
  events.addEventListener("open", () => setOffline("Connected, waiting for presenter"));
  events.addEventListener("error", () => setOffline("Notes server disconnected"));
} else {
  setOffline("This browser does not support live notes");
}
