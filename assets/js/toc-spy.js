/* Scroll-spy for the post table of contents.

   Mirrors bootstrap-toc (what 0xdf uses): sub-headings stay hidden until the
   reader is inside their parent section, then that branch expands. The active
   heading and every ancestor on its path are highlighted. */
(function () {
  var toc = document.getElementById('toc');
  if (!toc) return;

  var box = document.getElementById('toc-box');
  var items = Array.prototype.slice
    .call(toc.querySelectorAll('a[href^="#"]'))
    .map(function (a) {
      var id;
      try { id = decodeURIComponent(a.getAttribute('href').slice(1)); }
      catch (e) { id = a.getAttribute('href').slice(1); }
      return { link: a, li: a.parentElement, el: document.getElementById(id) };
    })
    .filter(function (i) { return i.el && i.li; });

  if (!items.length) return;

  var OFFSET = 110;
  var current = null;
  var ticking = false;

  function clear() {
    var i, n;
    n = toc.querySelectorAll('a.active, a.in-path');
    for (i = 0; i < n.length; i++) n[i].classList.remove('active', 'in-path');
    n = toc.querySelectorAll('li.expanded');
    for (i = 0; i < n.length; i++) n[i].classList.remove('expanded');
  }

  function apply(found) {
    if (found === current) return;
    clear();
    found.link.classList.add('active');

    // expand this branch and mark every ancestor on the path
    var li = found.li;
    while (li && toc.contains(li)) {
      li.classList.add('expanded');
      var parentList = li.parentElement;                 // the <ul>
      var parentLi = parentList && parentList.parentElement;
      if (parentLi && parentLi.tagName === 'LI' && toc.contains(parentLi)) {
        var pa = parentLi.querySelector('a');
        if (pa && pa !== found.link) pa.classList.add('in-path');
        li = parentLi;
      } else {
        li = null;
      }
    }
    current = found;

    if (toc.scrollHeight > toc.clientHeight + 4) {
      var lt = found.link.offsetTop, lh = found.link.offsetHeight;
      if (lt < toc.scrollTop) toc.scrollTop = lt - 8;
      else if (lt + lh > toc.scrollTop + toc.clientHeight) {
        toc.scrollTop = lt + lh - toc.clientHeight + 8;
      }
    }
  }

  function update() {
    ticking = false;
    var found = items[0];
    for (var i = 0; i < items.length; i++) {
      if (items[i].el.getBoundingClientRect().top <= OFFSET) found = items[i];
      else break;
    }
    if (window.innerHeight + window.scrollY >=
        document.documentElement.scrollHeight - 2) {
      found = items[items.length - 1];
    }
    apply(found);
  }

  function onScroll() {
    if (!ticking) { ticking = true; requestAnimationFrame(update); }
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll, { passive: true });

  if (box) {
    var mq = window.matchMedia('(min-width: 1000px)');
    function syncBox(e) { box.open = (e || mq).matches; }
    syncBox();
    if (mq.addEventListener) mq.addEventListener('change', syncBox);
    else if (mq.addListener) mq.addListener(syncBox);
    toc.addEventListener('click', function (ev) {
      if (ev.target.tagName === 'A' && !mq.matches) box.open = false;
    });
  }

  update();
})();
