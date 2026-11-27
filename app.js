let allEvents = [];
let totalStudents = 0;
let selectedGenre = 'ALL';
let selectedNeed = 'ALL';
let searchQuery = '';
let sortMode = 'cv_desc';
let visibleCount = 30;
const PAGE_SIZE = 30;

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const res = await fetch('./data.json');
    if (!res.ok) throw new Error('data.json の読み込みに失敗しました');
    const data = await res.json();

    allEvents = data.events || [];
    totalStudents = data.totalStudents || 0;

    renderStats();
    buildFilterChips();
    setupEventListeners();
    renderList();
  } catch (err) {
    document.getElementById('rankingList').innerHTML = `
      <div class="empty-state">
        <p><strong>データの読み込みエラー</strong></p>
        <p style="font-size:13px;margin-top:6px;">
          <code>python scripts/build_data.py</code> を実行して <code>data.json</code> を生成した上で、<br>
          ローカルサーバー経由で開いてください。
        </p>
      </div>
    `;
    console.error(err);
  }
});

function renderStats() {
  const totalCv = allEvents.reduce((sum, e) => sum + (e.cv || 0), 0);
  document.getElementById('statTotalEvents').textContent = `${allEvents.length}件`;
  document.getElementById('statTotalStudents').textContent = `${totalStudents}名`;
  document.getElementById('statTotalCv').textContent = `${totalCv}件`;
}

function buildFilterChips() {
  const genreMap = new Map();
  allEvents.forEach(ev => {
    (ev.genres || []).forEach(g => {
      genreMap.set(g, (genreMap.get(g) || 0) + 1);
    });
  });
  const topGenres = [...genreMap.entries()].sort((a, b) => b[1] - a[1]).slice(0, 15);

  const genreContainer = document.getElementById('genreChips');
  genreContainer.innerHTML = `<button type="button" class="chip active" data-genre="ALL">すべて</button>`;
  topGenres.forEach(([genre, count]) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'chip';
    btn.dataset.genre = genre;
    btn.textContent = `${genre} (${count})`;
    genreContainer.appendChild(btn);
  });

  const needMap = new Map();
  allEvents.forEach(ev => {
    if (!ev.needs) return;
    ev.needs.split(' / ').forEach(n => {
      const clean = n.trim();
      if (clean) needMap.set(clean, (needMap.get(clean) || 0) + 1);
    });
  });
  const topNeeds = [...needMap.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12);

  const needContainer = document.getElementById('needChips');
  needContainer.innerHTML = `<button type="button" class="chip active" data-need="ALL">すべて</button>`;
  topNeeds.forEach(([need, count]) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'chip';
    btn.dataset.need = need;
    btn.textContent = `${need} (${count})`;
    needContainer.appendChild(btn);
  });
}

function setupEventListeners() {
  const searchInput = document.getElementById('searchInput');
  const clearBtn = document.getElementById('clearSearchBtn');

  searchInput.addEventListener('input', (e) => {
    searchQuery = e.target.value.trim().toLowerCase();
    clearBtn.classList.toggle('hidden', searchQuery === '');
    visibleCount = PAGE_SIZE;
    renderList();
  });

  clearBtn.addEventListener('click', () => {
    searchInput.value = '';
    searchQuery = '';
    clearBtn.classList.add('hidden');
    visibleCount = PAGE_SIZE;
    renderList();
  });

  document.getElementById('sortSelect').addEventListener('change', (e) => {
    sortMode = e.target.value;
    visibleCount = PAGE_SIZE;
    renderList();
  });

  document.getElementById('genreChips').addEventListener('click', (e) => {
    const btn = e.target.closest('.chip');
    if (!btn) return;
    document.querySelectorAll('#genreChips .chip').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    selectedGenre = btn.dataset.genre;
    visibleCount = PAGE_SIZE;
    renderList();
  });

  document.getElementById('needChips').addEventListener('click', (e) => {
    const btn = e.target.closest('.chip');
    if (!btn) return;
    document.querySelectorAll('#needChips .chip').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    selectedNeed = btn.dataset.need;
    visibleCount = PAGE_SIZE;
    renderList();
  });

  document.getElementById('resetFiltersBtn').addEventListener('click', () => {
    searchInput.value = '';
    searchQuery = '';
    clearBtn.classList.add('hidden');
    selectedGenre = 'ALL';
    selectedNeed = 'ALL';
    sortMode = 'cv_desc';
    document.getElementById('sortSelect').value = 'cv_desc';

    document.querySelectorAll('#genreChips .chip').forEach((c, i) => c.classList.toggle('active', i === 0));
    document.querySelectorAll('#needChips .chip').forEach((c, i) => c.classList.toggle('active', i === 0));
    visibleCount = PAGE_SIZE;
    renderList();
  });

  document.getElementById('loadMoreBtn').addEventListener('click', () => {
    visibleCount += PAGE_SIZE;
    renderList();
  });
}

function getFilteredEvents() {
  let filtered = allEvents.filter(ev => {
    if (selectedGenre !== 'ALL' && !(ev.genres || []).includes(selectedGenre)) {
      return false;
    }
    if (selectedNeed !== 'ALL') {
      const needsArr = (ev.needs || '').split(' / ').map(s => s.trim());
      if (!needsArr.includes(selectedNeed)) return false;
    }
    if (searchQuery) {
      const pastText = (ev.pastTitles || []).map(p => p.title).join(' ');
      const haystack = `${ev.title} ${pastText} ${(ev.genres || []).join(' ')} ${ev.needs || ''}`.toLowerCase();
      if (!haystack.includes(searchQuery)) return false;
    }
    return true;
  });

  filtered.sort((a, b) => {
    const appA = a.applicants ?? a.cv;
    const appB = b.applicants ?? b.cv;
    const exA = a.exactCv ?? a.cv;
    const exB = b.exactCv ?? b.cv;

    switch (sortMode) {
      case 'cv_desc':
        return b.cv - a.cv || appB - appA || b.totalDates - a.totalDates;
      case 'cv_asc':
        return a.cv - b.cv || appA - appB || b.totalDates - a.totalDates;
      case 'app_desc':
        return appB - appA || b.cv - a.cv || b.totalDates - a.totalDates;
      case 'app_asc':
        return appA - appB || a.cv - b.cv || b.totalDates - a.totalDates;
      case 'exact_cv_desc':
        return exB - exA || b.cv - a.cv || b.totalDates - a.totalDates;
      case 'dates_desc':
        return b.totalDates - a.totalDates || b.cv - a.cv;
      default:
        return 0;
    }
  });

  return filtered;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderList() {
  const listEl = document.getElementById('rankingList');
  const filtered = getFilteredEvents();
  document.getElementById('resultCount').textContent = filtered.length;

  const loadMoreWrap = document.getElementById('loadMoreWrap');
  if (filtered.length <= visibleCount) {
    loadMoreWrap.style.display = 'none';
  } else {
    loadMoreWrap.style.display = 'block';
    document.getElementById('loadMoreBtn').textContent = `さらに表示する（残り ${filtered.length - visibleCount} 件）`;
  }

  if (filtered.length === 0) {
    listEl.innerHTML = `<div class="empty-state">条件に一致するイベントが見つかりませんでした。検索条件を変更してみてください。</div>`;
    return;
  }

  const isAsc = sortMode === 'cv_asc' || sortMode === 'app_asc';
  const slice = filtered.slice(0, visibleCount);

  listEl.innerHTML = slice.map((ev, index) => {
    const rank = index + 1;
    const rankClass = (!isAsc && rank <= 3) ? `rank-${rank}` : '';
    const applicants = ev.applicants ?? ev.cv;
    const exactCv = ev.exactCv ?? ev.cv;
    const pastCv = ev.pastCv ?? 0;
    const rate = totalStudents > 0 ? ((applicants / totalStudents) * 100).toFixed(1) : '0.0';

    const cvBreakdown = pastCv > 0
      ? `（現行 ${exactCv} + 旧枠 ${pastCv}）`
      : '';

    const pastHtml = (ev.pastTitles && ev.pastTitles.length > 0)
      ? `<div style="font-size:11px;color:#64748b;background:#f8fafc;border-left:3px solid #94a3b8;padding:4px 8px;margin-bottom:8px;border-radius:4px;">
          📌 旧枠・関連実績: ${ev.pastTitles.map(p => `${escapeHtml(p.title)}（${p.cv}件）`).join(' / ')}
         </div>`
      : '';

    const genresHtml = (ev.genres || [])
      .map(g => `<span class="genre-tag">${escapeHtml(g)}</span>`)
      .join('');

    const datesHtml = (ev.dates || [])
      .map(d => `<span class="date-chip">📅 ${escapeHtml(d)}</span>`)
      .join('');

    const extraDates = ev.totalDates > (ev.dates || []).length
      ? `<span class="date-more">他 ${ev.totalDates - ev.dates.length} 日程</span>`
      : '';

    const hasValidUrl = ev.url && ev.url.startsWith('http');

    return `
      <article class="event-card ${rankClass}">
        <div class="rank-badge">
          <span class="rank-num">${rank}</span>
          <span class="rank-unit">位</span>
        </div>
        <div class="card-body">
          <div class="card-meta-top">
            <span class="cv-pill ${ev.cv === 0 ? 'zero' : ''}">🔥 累計CV ${ev.cv}件${cvBreakdown}</span>
            <span class="rate-pill">👤 申込実人数 ${applicants}名（${rate}%）</span>
            ${genresHtml}
          </div>
          <h2 class="event-title">${escapeHtml(ev.title)}</h2>
          ${pastHtml}
          ${ev.needs ? `<div class="event-needs">🎯 対象ニーズ: <strong>${escapeHtml(ev.needs)}</strong></div>` : ''}
          ${datesHtml ? `<div class="dates-box">${datesHtml}${extraDates}</div>` : ''}
          ${hasValidUrl ? `
            <div class="card-actions">
              <a href="${escapeHtml(ev.url)}" target="_blank" rel="noopener noreferrer" class="detail-btn">
                イベント詳細・予約へ ↗
              </a>
            </div>
          ` : ''}
        </div>
      </article>
    `;
  }).join('');
}
