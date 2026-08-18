(function () {
  var el = document.getElementById('view-count');
  if (!el) return;
  fetch('/.netlify/functions/views')
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (typeof data.views === 'number') {
        el.textContent = data.views.toLocaleString() + ' views';
      }
    })
    .catch(function () {});
})();
