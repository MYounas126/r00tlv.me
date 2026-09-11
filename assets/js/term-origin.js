/* On a tag/category page, if we arrived from a specific post
   (#from=/posts/slug/), lift that post to the top of the list.

   This marker is a fragment, not a query string, deliberately. A query string
   makes /tags/xss/?from=... a distinct URL that Google crawls and indexes
   alongside the clean /tags/xss/, producing duplicates it then has to fold
   away via the canonical. A fragment is never sent to the server and never
   indexed, so only one URL per tag ever exists.

   The trade-off a fragment brings: navigating from /tags/xss/ to
   /tags/xss/#from=... changes only the hash, which is a same-document
   navigation and fires no page load. So the reorder also runs on hashchange. */
(function () {
  var list = document.getElementById('term-list');
  if (!list) return;

  var norm = function (u) { return (u || '').replace(/\/+$/, ''); };

  function apply() {
    var from;
    try {
      var h = window.location.hash || '';
      if (h.charAt(0) === '#') h = h.slice(1);
      from = new URLSearchParams(h).get('from');
    } catch (e) { return; }

    var prev = list.querySelector('.pe-origin');
    if (prev) prev.classList.remove('pe-origin');
    if (!from) return;

    var want = norm(from);
    var arts = list.querySelectorAll('article[data-url]');
    for (var i = 0; i < arts.length; i++) {
      if (norm(arts[i].getAttribute('data-url')) === want) {
        if (arts[i] !== list.firstElementChild) {
          list.insertBefore(arts[i], list.firstElementChild);
        }
        arts[i].classList.add('pe-origin');
        break;
      }
    }
  }

  apply();
  window.addEventListener('hashchange', apply);
})();
