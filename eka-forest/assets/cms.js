/* EKA Forest – Google Sheets CMS loader.
   Reads the sheet "EKA Forest – Website Content" (tabs: contact, about, stays, gallery, reach, faq, footer;
   columns key | value | notes) and fills elements tagged data-cms="tab.key".
   The HTML text stays as the fallback: if the fetch fails or a cell is empty, nothing changes. */
(function () {
  var SHEET_ID = '1SGwnRwcCm8O7QgaROm5XQ4jnb8fO22u_ZLt2iEytGUw';
  // data-cms prefix -> sheet tab title (friendly tab names in the sheet)
  var TABS = { about: 'About', stays: 'Stays', gallery: 'Gallery', reach: 'Getting here',
               faq: 'FAQ', contact: 'Contact', footer: 'Footer',
               events: 'Events', blog: 'Journals' };
  var ALLOWED = { BR: 1, STRONG: 1, EM: 1, A: 1 };

  function url(tab) {
    return 'https://docs.google.com/spreadsheets/d/' + SHEET_ID +
      '/gviz/tq?tqx=out:json&headers=1&sheet=' + encodeURIComponent(tab);
  }
  function parse(txt) {                       // gviz wraps JSON in a JS callback
    var json = JSON.parse(txt.slice(txt.indexOf('{'), txt.lastIndexOf('}') + 1));
    var out = {}, cols = json.table.cols.map(function (c) { return (c.label || '').trim().toLowerCase(); });
    var ki = cols.indexOf('key'), vi = -1;            // columns found by header, so layout can change
    cols.forEach(function (l, i) { if (vi < 0 && /^(your content|value)/.test(l)) vi = i; });
    if (ki < 0) ki = 0; if (vi < 0) vi = 1;
    (json.table.rows || []).forEach(function (r) {
      var k = r.c[ki] && r.c[ki].v, v = r.c[vi] && r.c[vi].v;
      if (k && v !== null && v !== undefined && String(v).trim() !== '') out[String(k).trim()] = String(v);
    });
    return out;
  }
  function safeHTML(el, html) {               // allow only br/strong/em/a(href http/mailto)
    var tpl = document.createElement('template'); tpl.innerHTML = html;
    (function clean(node) {
      Array.prototype.slice.call(node.childNodes).forEach(function (n) {
        if (n.nodeType === 1) {
          if (!ALLOWED[n.tagName]) { n.replaceWith(document.createTextNode(n.textContent)); return; }
          Array.prototype.slice.call(n.attributes).forEach(function (a) {
            if (!(n.tagName === 'A' && /^(href|target|rel)$/.test(a.name))) n.removeAttribute(a.name);
          });
          if (n.tagName === 'A' && !/^(https?:|mailto:|#)/.test(n.getAttribute('href') || '')) n.removeAttribute('href');
          clean(n);
        }
      });
    })(tpl.content);
    el.replaceChildren(tpl.content);
  }
  function apply(d) {
    var n = 0;
    // Footer Address block removed: never render footer.address from CMS
    document.querySelectorAll('[data-cms="footer.address"]').forEach(function (el) { el.remove(); });
    var get = function (path) { var p = path.split('.'); return d[p[0]] && d[p[0]][p[1]]; };
    document.querySelectorAll('[data-cms]').forEach(function (el) {
      if (el.getAttribute('data-cms') === 'footer.address') { el.remove(); return; }
      var v = get(el.getAttribute('data-cms')); if (v === undefined) return; n++;
      if (/[<&]/.test(v)) safeHTML(el, v.replace(/\n/g, '<br>'));
      else { el.textContent = ''; v.split('\n').forEach(function (line, i) {
        if (i) el.appendChild(document.createElement('br')); el.appendChild(document.createTextNode(line)); }); }
    });
    document.querySelectorAll('[data-cms-href]').forEach(function (el) {
      var v = get(el.getAttribute('data-cms-href')); if (v && /^https?:/.test(v)) el.href = v;
    });
    document.querySelectorAll('[data-cms-mailto]').forEach(function (el) {
      var v = get(el.getAttribute('data-cms-mailto')); if (v) el.href = 'mailto:' + v.trim();
    });
    var num = (get('contact.whatsapp_number') || '').replace(/\D/g, '');
    if (num) {
      var msg = get('contact.whatsapp_message');
      document.querySelectorAll('[data-cms-wa]').forEach(function (el) {
        var u = new URL(el.href); u.pathname = '/' + num;
        if (msg && el.getAttribute('data-cms-wa') !== 'keep') u.searchParams.set('text', msg);
        el.href = u.toString();
      });
    }
    document.querySelectorAll('[data-cms-img]').forEach(function (el) {
      var v = get(el.getAttribute('data-cms-img')); if (!v || !/^(https?:|assets\/)/.test(v)) return;
      el.style.backgroundImage = 'url("' + v.replace(/"/g, '%22') + '")';
      el.style.backgroundSize = 'cover'; el.style.backgroundPosition = 'center';
      el.classList.add('has-photo');
      var cap = el.querySelector('span, figcaption'); if (cap) cap.classList.add('visually-hidden');
    });
    document.documentElement.setAttribute('data-cms-loaded', '');
    document.documentElement.setAttribute('data-cms-count', n);  // fields filled from the sheet
  }

  // Only fetch the tabs this page actually uses (keeps inner pages light)
  var used = { contact: 1 };
  document.querySelectorAll('[data-cms],[data-cms-href],[data-cms-img],[data-cms-mailto]').forEach(function (el) {
    ['data-cms', 'data-cms-href', 'data-cms-img', 'data-cms-mailto'].forEach(function (a) {
      var v = el.getAttribute(a); if (v) used[v.split('.')[0]] = 1;
    });
  });
  Promise.all(Object.keys(TABS).filter(function (t) { return used[t]; }).map(function (t) {
    return fetch(url(TABS[t])).then(function (r) { if (!r.ok) throw r.status; return r.text(); })
      .then(parse).then(function (rows) { return [t, rows]; })
      .catch(function () { return [t, {}]; });       // one bad tab never breaks the page
  })).then(function (pairs) {
    var d = {}; pairs.forEach(function (p) { d[p[0]] = p[1]; }); apply(d);
  }).catch(function () {});
})();
