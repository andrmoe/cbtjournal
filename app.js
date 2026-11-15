const app = document.querySelector('#app');
const login = document.querySelector('#login');
const view = document.querySelector('#view');
const status = document.querySelector('#status');
let content;
let page = 'home';
let lessonId = '';
let entries = [];
let progress = {};

const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const date = value => new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value));
const today = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10); };

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: 'same-origin', ...options, headers: { 'Content-Type': 'application/json', ...options.headers } });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && path !== '/api/login') showLogin();
    throw new Error(result.error || 'Request failed');
  }
  return result;
}

function showLogin() {
  app.hidden = true;
  login.hidden = false;
  document.querySelector('#login-error').textContent = '';
  document.querySelector('#password').focus();
}

async function refresh() {
  const [journal, saved] = await Promise.all([api('/api/entries'), api('/api/course-progress')]);
  entries = journal;
  progress = Object.fromEntries(saved.map(item => [item.lesson_id, item]));
}

function go(next, id = '') {
  page = next;
  lessonId = id;
  document.querySelectorAll('[data-view]').forEach(button => {
    if (button.dataset.view === (next === 'lesson' ? 'learn' : next)) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  status.textContent = '';
  render();
}

function rows(items) {
  if (!items.length) return '<p>No entries yet.</p>';
  return `<ul class="entry-list">${items.map(item => `<li><button data-entry="${escapeHTML(item.id)}"><span class="entry-title">${escapeHTML(item.title)}</span><small>${item.kind === 'thought' ? 'Thought record' : 'Activity plan'}</small><time>${date(item.created_at)}</time></button></li>`).join('')}</ul>`;
}

function field(item) {
  const id = `f-${item.name}`;
  const type = item.type || 'textarea';
  let input;
  if (type === 'textarea') input = `<textarea id="${id}" name="${item.name}" ${item.required ? 'required' : ''}></textarea>`;
  else if (type === 'select') input = `<select id="${id}" name="${item.name}">${item.values.map(value => `<option>${escapeHTML(value)}</option>`).join('')}</select>`;
  else if (type === 'range') input = `<div class="range"><input id="${id}" name="${item.name}" type="range" min="0" max="100" value="${item.value}"><output for="${id}">${item.value}%</output></div>`;
  else input = `<input id="${id}" name="${item.name}" type="${type}" ${item.value === 'today' ? `value="${today()}"` : item.value ? `value="${escapeHTML(item.value)}"` : ''} ${item.required ? 'required' : ''}>`;
  return `<div class="field"><label for="${id}">${escapeHTML(item.label)}</label>${input}</div>`;
}

function sourceNote(source) {
  return `<p class="source">Adapted from ${escapeHTML(source.author)}’s <a href="${escapeHTML(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(source.title)}${source.year ? ` (${source.year})` : ''}</a>, ${escapeHTML(source.license)}. <a href="/CONTENT_LICENSE.md">Attribution</a>.</p>`;
}

function renderExercise(kind) {
  const exercise = content.exercises[kind];
  return `<h1>${escapeHTML(exercise.title)}</h1><form class="exercise" data-kind="${kind}">${exercise.fields.map(field).join('')}<button>Save</button>${sourceNote(exercise.source)}</form>`;
}

function renderLearn() {
  const complete = content.lessons.filter(item => progress[item.id]?.completed).length;
  return `<h1>${escapeHTML(content.title)}</h1><p>${escapeHTML(content.description)}</p><p>${complete} of ${content.lessons.length} complete</p><ol class="entry-list">${content.lessons.map((item, index) => `<li><button data-lesson="${item.id}"><span class="entry-title">${index + 1}. ${escapeHTML(item.title)}</span><small>${progress[item.id]?.completed ? 'Done' : 'Open'}</small></button></li>`).join('')}</ol><p class="source"><a href="/CONTENT_LICENSE.md">Content and sources</a></p>`;
}

function renderLesson() {
  const index = content.lessons.findIndex(item => item.id === lessonId);
  const lesson = content.lessons[index];
  if (!lesson) return renderLearn();
  const saved = progress[lesson.id] || {};
  const sources = (lesson.sources || []).map(sourceNote).join('');
  const exerciseLink = lesson.exercise ? `<p><button data-go="${lesson.exercise}">Open ${escapeHTML(content.exercises[lesson.exercise].title)}</button></p>` : '';
  return `<p><button data-go="learn">Learn</button> · ${index + 1} of ${content.lessons.length}</p><h1>${escapeHTML(lesson.title)}</h1><h2>Key points</h2><ul>${lesson.points.map(text => `<li>${escapeHTML(text)}</li>`).join('')}</ul><h2>Try it</h2><ol>${lesson.practice.map(text => `<li>${escapeHTML(text)}</li>`).join('')}</ol>${exerciseLink}${sources}<form class="field" data-lesson-form="${lesson.id}"><label for="lesson-reflection">Notes</label><textarea id="lesson-reflection" name="reflection" maxlength="4000">${escapeHTML(saved.reflection || '')}</textarea><label><input type="checkbox" name="completed" ${saved.completed ? 'checked' : ''}> Mark complete</label><button>Save</button></form><p>${index ? `<button data-lesson="${content.lessons[index - 1].id}">Previous</button>` : ''} ${index < content.lessons.length - 1 ? `<button data-lesson="${content.lessons[index + 1].id}">Next</button>` : ''}</p>`;
}

function render() {
  if (page === 'home') view.innerHTML = `<h1>Today</h1><div class="actions"><button data-go="learn">CBT skills path</button><button data-go="thought">Thought record</button><button data-go="activity">Activity plan</button></div><h2>Recent</h2>${rows(entries.slice(0, 5))}`;
  else if (page === 'learn') view.innerHTML = renderLearn();
  else if (page === 'lesson') view.innerHTML = renderLesson();
  else if (page === 'thought' || page === 'activity') view.innerHTML = renderExercise(page);
  else if (page === 'journal') view.innerHTML = `<h1>Journal</h1>${rows(entries)}`;
  else if (page === 'settings') view.innerHTML = `<h1>Data</h1><p>Entries and learning notes are stored on this server.</p><div class="actions"><button id="export">Export JSON</button><button id="clear">Delete all entries</button><button id="reset-course">Reset learning progress</button></div>`;
}

function showEntry(entry) {
  if (!entry) return;
  const fields = content.exercises[entry.kind].fields;
  const details = fields.filter(item => entry.body[item.name]).map(item => `<dt>${escapeHTML(item.label)}</dt><dd>${escapeHTML(entry.body[item.name])}${item.type === 'range' ? '%' : ''}</dd>`).join('');
  view.innerHTML = `<h1>${escapeHTML(entry.title)}</h1><p>${date(entry.created_at)}</p><dl>${details}</dl><button data-go="journal">Back</button> <button data-delete="${escapeHTML(entry.id)}">Delete</button>`;
}

document.querySelector('#login-form').addEventListener('submit', async event => {
  event.preventDefault();
  const password = document.querySelector('#password');
  try {
    await api('/api/login', { method: 'POST', body: JSON.stringify({ password: password.value }) });
    password.value = '';
    login.hidden = true;
    app.hidden = false;
    await refresh();
    go('home');
  } catch (error) { document.querySelector('#login-error').textContent = error.message; }
});

app.addEventListener('click', async event => {
  const nav = event.target.closest('[data-view]');
  if (nav) { go(nav.dataset.view); return; }
  const destination = event.target.closest('[data-go]');
  if (destination) { go(destination.dataset.go); return; }
  const lesson = event.target.closest('[data-lesson]');
  if (lesson) { go('lesson', lesson.dataset.lesson); return; }
  const row = event.target.closest('[data-entry]');
  if (row) { showEntry(entries.find(item => item.id === row.dataset.entry)); return; }
  if (event.target.closest('#export')) {
    try {
      const [journal, saved] = await Promise.all([api('/api/entries'), api('/api/course-progress')]);
      const data = { exportedAt: new Date().toISOString(), entries: journal, courseProgress: saved };
      const link = document.createElement('a');
      link.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
      link.download = `cbt-journal-${today()}.json`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    } catch (error) { status.textContent = error.message; }
  }
  const remove = event.target.closest('[data-delete]');
  if (remove && confirm('Delete this entry?')) {
    try { await api(`/api/entries/${encodeURIComponent(remove.dataset.delete)}`, { method: 'DELETE' }); await refresh(); go('journal'); }
    catch (error) { status.textContent = error.message; }
  }
  if (event.target.closest('#clear') && confirm('Delete all journal entries?')) {
    try { await api('/api/entries/clear', { method: 'POST', body: '{}' }); await refresh(); go('settings'); }
    catch (error) { status.textContent = error.message; }
  }
  if (event.target.closest('#reset-course') && confirm('Delete all saved learning notes and completion marks?')) {
    try { await api('/api/course-progress/clear', { method: 'POST', body: '{}' }); await refresh(); go('settings'); }
    catch (error) { status.textContent = error.message; }
  }
});

view.addEventListener('input', event => {
  if (event.target.type === 'range') view.querySelector(`output[for="${event.target.id}"]`).textContent = `${event.target.value}%`;
});

view.addEventListener('submit', async event => {
  const lessonForm = event.target.closest('form[data-lesson-form]');
  if (lessonForm) {
    event.preventDefault();
    const data = new FormData(lessonForm);
    try {
      await api(`/api/course-progress/${lessonForm.dataset.lessonForm}`, { method: 'PUT', body: JSON.stringify({ reflection: data.get('reflection') || '', completed: data.has('completed') }) });
      await refresh();
      render();
      status.textContent = 'Saved.';
    } catch (error) { status.textContent = error.message; }
    return;
  }
  const form = event.target.closest('form[data-kind]');
  if (!form) return;
  event.preventDefault();
  const body = Object.fromEntries(new FormData(form));
  const kind = form.dataset.kind;
  const title = (body.thought || body.activity || '').trim().slice(0, 72) || content.exercises[kind].title;
  try {
    await api('/api/entries', { method: 'POST', body: JSON.stringify({ kind, title, body }) });
    await refresh();
    go('journal');
  } catch (error) { status.textContent = error.message; }
});

document.querySelector('#logout').addEventListener('click', async () => {
  try { await api('/api/logout', { method: 'POST', body: '{}' }); } catch (_) {}
  showLogin();
});

(async () => {
  try {
    const response = await fetch('/content.json');
    if (!response.ok) throw new Error('Course content unavailable');
    content = await response.json();
    const session = await api('/api/session');
    if (session.authenticated) {
      login.hidden = true;
      app.hidden = false;
      await refresh();
      go('home');
    } else showLogin();
  } catch (_) { showLogin(); }
})();
