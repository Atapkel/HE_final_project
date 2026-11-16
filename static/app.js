// Lesson Ready: small progressive enhancements. Every page also works without JavaScript.
(function () {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function toast(text) {
    const t = $('#toast');
    if (!t) return;
    t.innerHTML = '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.2 4.2L19 7"/></svg>';
    t.append(document.createTextNode(text));
    t.classList.add('show');
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.classList.remove('show'), 3500);
  }

  // ---- AI forms: show progress while Claude works ----
  $$('form[data-ai]').forEach(form => {
    form.addEventListener('submit', () => {
      const button = form.querySelector('button[type=submit]');
      const status = form.querySelector('.ai-status');
      if (button) { button.disabled = true; button.dataset.label = button.innerHTML; button.textContent = 'AI is working…'; }
      if (status) status.innerHTML = '<span class="spinner"></span> This usually takes 5–30 seconds. Please keep this page open.';
    });
  });
  window.addEventListener('pageshow', () => {
    $$('form[data-ai] button[type=submit]').forEach(b => {
      if (b.dataset.label) { b.innerHTML = b.dataset.label; b.disabled = false; }
    });
  });

  // ---- Confirm dangerous actions ----
  $$('form[data-confirm]').forEach(form => form.addEventListener('submit', e => {
    if (!confirm(form.dataset.confirm)) e.preventDefault();
  }));

  // ---- Copy link ----
  $$('[data-copy]').forEach(btn => btn.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(btn.dataset.copy); toast('Link copied'); }
    catch { prompt('Copy this link:', btn.dataset.copy); }
  }));

  // ---- Live dashboard: poll for new results and swap only the changed regions ----
  const live = $('[data-live-url]');
  if (live) {
    let signature = live.dataset.signature || '';
    let busy = false;
    async function poll() {
      if (busy || document.hidden) return;
      busy = true;
      try {
        const res = await fetch(live.dataset.liveUrl + '?sig=' + encodeURIComponent(signature), { headers: { Accept: 'application/json' } });
        if (!res.ok) return;
        const data = await res.json();
        if (!data.changed) return;
        const first = signature === '';
        signature = data.signature;
        for (const [name, html] of Object.entries(data.regions || {})) {
          const el = $(`[data-live="${name}"]`);
          if (!el) continue;
          const open = new Set($$('details[open][data-key]', el).map(d => d.dataset.key));
          el.innerHTML = html;
          $$('details[data-key]', el).forEach(d => { if (open.has(d.dataset.key)) d.open = true; });
          if (!first) { el.classList.remove('flash-new'); void el.offsetWidth; el.classList.add('flash-new'); }
        }
        $$('[data-joined]').forEach(el => { el.textContent = data.joined; });
        for (const [kind, n] of Object.entries(data.counts || {})) {
          $$(`[data-count="${kind}"]`).forEach(el => { el.textContent = n; });
        }
        if (!first && data.newest) toast(`New result from ${data.newest}`);
      } catch (e) { /* offline for a moment: try again next tick */ }
      finally { busy = false; }
    }
    if (!signature) poll();
    setInterval(poll, 4000);
  }

  // ---- Quiz: answered counter ----
  const quiz = $('#quiz-form');
  if (quiz) {
    const total = new Set($$('input[type=radio]', quiz).map(i => i.name)).size;
    const update = () => {
      const answered = new Set($$('input[type=radio]:checked', quiz).map(i => i.name)).size;
      $('[data-answered]').textContent = answered;
      $('[data-progress]').style.width = (100 * answered / total) + '%';
    };
    quiz.addEventListener('change', update);
    update();
  }

  // ---- Review: edit AI drafts in place ----
  const review = $('#review-form');
  if (review) {
    const list = $('#questions');
    const letters = 'ABCDEF';
    const esc = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

    function renumber() {
      let n = 0;
      $$('.review-card', list).forEach(card => {
        const keep = $('[data-keep]', card).checked;
        card.classList.toggle('excluded', !keep);
        $('[data-num]', card).textContent = keep ? ++n : '–';
      });
      $('[data-count]').textContent = n;
    }

    function refreshView(card) {
      const id = card.dataset.qid;
      const val = name => (review.elements[`${id}_${name}`] || {}).value || '';
      const correct = (review.querySelector(`input[name="${id}_correct"]:checked`) || {}).value;
      $('[data-view-text]', card).textContent = val('text');
      $('[data-view-topic]', card).textContent = val('topic');
      const expl = $('[data-view-expl]', card);
      expl.textContent = val('expl');
      expl.hidden = !val('expl');
      $('[data-view-options]', card).innerHTML = [0, 1, 2, 3].map(j => {
        const text = val('opt' + j);
        if (!text) return '';
        const ok = String(j) === correct;
        return `<li${ok ? ' class="correct"' : ''}><span class="letter">${letters[j]}</span><span>${esc(text)}</span>${ok ? ' ✓' : ''}</li>`;
      }).join('');
      const badge = $('[data-badge]', card);
      if (badge && card.dataset.dirty) badge.hidden = false;
    }

    list.addEventListener('click', e => {
      const card = e.target.closest('.review-card');
      if (!card) return;
      if (e.target.closest('[data-edit]')) {
        card.classList.add('editing');
        $('textarea', card).focus();
      } else if (e.target.closest('[data-done]')) {
        refreshView(card);
        card.classList.remove('editing');
      }
    });
    list.addEventListener('input', e => { const c = e.target.closest('.review-card'); if (c && !e.target.matches('[data-keep]')) c.dataset.dirty = '1'; });
    list.addEventListener('change', e => { if (e.target.matches('[data-keep]')) renumber(); else { const c = e.target.closest('.review-card'); if (c) c.dataset.dirty = '1'; } });

    let added = 0;
    $('#add-question').addEventListener('click', () => {
      const id = 'n' + Date.now().toString(36) + (added++);
      const html = $('#new-question').innerHTML.replaceAll('__ID__', id);
      list.insertAdjacentHTML('beforeend', html);
      const card = list.lastElementChild;
      renumber();
      card.scrollIntoView({ behavior: 'smooth', block: 'center' });
      $('textarea', card).focus();
    });

    review.addEventListener('submit', e => {
      const open = $$('.review-card.editing', list);
      open.forEach(refreshView);
      if (e.submitter && e.submitter.value === 'publish') {
        const n = Number($('[data-count]').textContent);
        if (!confirm(`Publish ${n} question${n === 1 ? '' : 's'} to students now?`)) e.preventDefault();
      }
    });
    renumber();
  }
})();
