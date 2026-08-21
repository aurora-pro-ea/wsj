(function () {
  const body = document.body;
  const theme = document.getElementById('theme-toggle');
  const search = document.getElementById('site-search');
  const panel = document.getElementById('search-panel');
  const results = document.getElementById('search-results');
  const meta = document.getElementById('search-meta');
  const progress = document.getElementById('reading-progress');
  let indexPromise;

  const escapeHtml = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function loadIndex() {
    if (!indexPromise) indexPromise = fetch('/search-index.json').then(r => r.json());
    return indexPromise;
  }
  function highlight(text, query) {
    const safe = escapeHtml(text);
    if (!query) return safe;
    return safe.replace(new RegExp('(' + query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig'), '<mark>$1</mark>');
  }
  function renderResults(items, query) {
    if (!panel || !results || !meta) return;
    panel.hidden = !query;
    if (!query) return;
    meta.textContent = items.length ? `找到 ${items.length} 篇相关文章` : '没有找到匹配文章';
    results.innerHTML = items.slice(0, 40).map(item => `<a class="search-result" href="${item.url}"><small>${item.date} · ${item.year}年</small><strong>${highlight(item.title, query)}</strong><span>${highlight(item.excerpt, query)}</span></a>`).join('');
  }
  if (search) {
    search.addEventListener('input', async () => {
      const query = search.value.trim().toLowerCase();
      if (query.length < 2) { renderResults([], ''); return; }
      const items = await loadIndex();
      const found = items.filter(item => `${item.title} ${item.search} ${item.date}`.toLowerCase().includes(query));
      renderResults(found, query);
    });
    search.addEventListener('keydown', e => { if (e.key === 'Escape') { search.value=''; renderResults([], ''); search.blur(); } });
  }

  if (theme) {
    const saved = localStorage.getItem('wsj-theme');
    if (saved === 'dark') { body.classList.add('dark'); theme.textContent='☀'; }
    theme.addEventListener('click', () => { body.classList.toggle('dark'); const dark=body.classList.contains('dark'); localStorage.setItem('wsj-theme',dark?'dark':'light'); theme.textContent=dark?'☀':'☾'; });
  }
  const menu = document.getElementById('menu-toggle');
  if (menu) menu.addEventListener('click', () => body.classList.toggle('menu-open'));

  const article = document.querySelector('.reading-article');
  const articleKey = body.dataset.articleUrl || '';
  function updateProgress() {
    if (!progress || !article) return;
    const scrollable = document.documentElement.scrollHeight - window.innerHeight;
    const pct = scrollable > 0 ? Math.min(100, window.scrollY / scrollable * 100) : 0;
    progress.style.width = pct + '%';
    if (articleKey) localStorage.setItem('wsj-progress:' + articleKey, String(Math.round(pct)));
  }
  window.addEventListener('scroll', updateProgress, {passive:true});
  updateProgress();

  // Reading settings
  const readerPanel=document.getElementById('reader-panel'), readerBtn=document.getElementById('reader-settings');
  const closeReader=document.getElementById('reader-close'), fs=document.getElementById('font-size-range'), lh=document.getElementById('line-height-range');
  const fsv=document.getElementById('font-size-value'), lhv=document.getElementById('line-height-value'), reset=document.getElementById('reader-reset');
  function applyReader() {
    const size=Number(localStorage.getItem('wsj-font-size')||18), line=Number(localStorage.getItem('wsj-line-height')||2);
    if(fs){fs.value=size;fsv.textContent=size+'px';} if(lh){lh.value=line;lhv.textContent=line;}
    if(article){article.style.setProperty('--reader-font-size',size+'px');article.style.setProperty('--reader-line-height',line);}
    document.documentElement.style.setProperty('--reader-font-size',size+'px'); document.documentElement.style.setProperty('--reader-line-height',line);
  }
  if(readerBtn){readerBtn.addEventListener('click',()=>{readerPanel.hidden=!readerPanel.hidden;}); applyReader();}
  if(closeReader) closeReader.addEventListener('click',()=>readerPanel.hidden=true);
  if(fs) fs.addEventListener('input',()=>{localStorage.setItem('wsj-font-size',fs.value);applyReader();});
  if(lh) lh.addEventListener('input',()=>{localStorage.setItem('wsj-line-height',lh.value);applyReader();});
  if(reset) reset.addEventListener('click',()=>{localStorage.removeItem('wsj-font-size');localStorage.removeItem('wsj-line-height');applyReader();});

  // Favorites
  const save=document.getElementById('save-article');
  if(save && articleKey){
    const key='wsj-favorites', fav=JSON.parse(localStorage.getItem(key)||'[]'), saved=fav.includes(articleKey);
    const paint=()=>{const yes=fav.includes(articleKey);save.classList.toggle('saved',yes);save.textContent=yes?'♥ 已收藏':'♡ 收藏';}; paint();
    save.addEventListener('click',()=>{const i=fav.indexOf(articleKey); if(i>=0) fav.splice(i,1); else fav.push(articleKey); localStorage.setItem(key,JSON.stringify(fav));paint();});
  }

  // Share links
  const shareBtn=document.getElementById('share-button'), sharePanel=document.getElementById('share-panel'), shareClose=document.getElementById('share-close');
  if(shareBtn){shareBtn.addEventListener('click',()=>{sharePanel.hidden=!sharePanel.hidden; const u=encodeURIComponent(location.href), t=encodeURIComponent(document.title.replace(' · WSJ文章档案','')); document.getElementById('share-x').href='https://twitter.com/intent/tweet?text='+t+'&url='+u; document.getElementById('share-facebook').href='https://www.facebook.com/sharer/sharer.php?u='+u; document.getElementById('share-telegram').href='https://t.me/share/url?url='+u+'&text='+t;});}
  if(shareClose) shareClose.addEventListener('click',()=>sharePanel.hidden=true);
  const copy=document.getElementById('copy-link'); if(copy) copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(location.href);copy.textContent='✓ 已复制';setTimeout(()=>copy.textContent='🔗 复制链接',1200);}catch(e){prompt('复制链接：',location.href);}});

  const random=document.getElementById('random-article');
  if(random) random.addEventListener('click',async()=>{const items=await loadIndex(); if(items.length) location.href=items[Math.floor(Math.random()*items.length)].url;});

  // Highlight current section in the desktop TOC.
  if(article){const headings=[...article.querySelectorAll('.article-content h3')], links=[...document.querySelectorAll('.article-toc a')]; const obs=new IntersectionObserver(entries=>{entries.forEach(e=>{if(e.isIntersecting){links.forEach(a=>a.classList.toggle('current',a.getAttribute('href')==='#'+e.target.id));}})},{rootMargin:'-18% 0px -70% 0px'});headings.forEach(h=>obs.observe(h));}
})();
