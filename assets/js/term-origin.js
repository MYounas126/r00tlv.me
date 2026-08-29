/* On a tag/category page, if we arrived from a specific post
   (?from=/posts/slug/), lift that post to the top of the list. */
(function () {
  var list = document.getElementById('term-list');
  if (!list) return;

  var from;
  try { from = new URLSearchParams(window.location.search).get('from'); }
  catch (e) { return; }
  if (!from) return;

  var norm = function (u) { return (u || '').replace(/\/+$/, ''); };
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
})();
