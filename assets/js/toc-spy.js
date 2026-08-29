/* Scroll-spy for the post table of contents.
   Marks the heading the reader is currently inside, the way bootstrap-toc
   does on 0xdf. Plain scroll maths rather than IntersectionObserver: it
   stays correct for headings taller than the viewport and when several
   headings share one screen. */
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
      return { link: a, el: document.getElementById(id) };
    })
    .filter(function (i) { return i.el; });

  if (!items.length) return;

  var OFFSET = 110;          // a heading counts as current once within this of the top
  var current = null;
  var ticking = false;

  function apply(found) {
    if (found === current) return;
    if (current) current.link.classList.remove('active');
    found.link.classList.add('active');
    current = found;

    // keep the active entry in view if the TOC itself is scrolling
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
    // at the very bottom of the page the last section is the one being read
    var atEnd = window.innerHeight + window.scrollY >=
                document.documentElement.scrollHeight - 2;
    if (atEnd) found = items[items.length - 1];
    apply(found);
  }

  function onScroll() {
    if (!ticking) { ticking = true; requestAnimationFrame(update); }
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll, { passive: true });

  // collapsed on narrow screens, always open on desktop
  if (box) {
    var mq = window.matchMedia('(min-width: 1100px)');
    function syncBox(e) { box.open = (e || mq).matches; }
    syncBox();
    if (mq.addEventListener) mq.addEventListener('change', syncBox);
    else if (mq.addListener) mq.addListener(syncBox);

    // tapping a link on mobile should close the drawer
    toc.addEventListener('click', function (ev) {
      if (ev.target.tagName === 'A' && !mq.matches) box.open = false;
    });
  }

  update();
})();
