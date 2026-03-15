import logging
import os
from flask import Flask, request as flask_request, redirect

logger = logging.getLogger()

SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI", "sqlite:////app/superset.db")

RATELIMIT_STORAGE_URI = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_URL": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
}
DATA_CACHE_CONFIG = CACHE_CONFIG

class CeleryConfig(object):
    BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0") + "/1"
    CELERY_IMPORTS = ("superset.sql_lab",)
    CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0") + "/0"
    CELERY_ANNOTATIONS = {"tasks.add": {"rate_limit": "10/s"}}

CELERY_CONFIG = CeleryConfig

# Language / Idioma
BABEL_DEFAULT_LOCALE = "es"
LANGUAGES = {
    "es": {"flag": "es", "name": "Español"},
    "en": {"flag": "us", "name": "English"},
}

SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "CHANGE_ME")
SUPERSET_WEBSERVER_PORT = int(os.environ.get("SUPERSET_PORT", "8088"))

WTF_CSRF_ENABLED = False
TALISMAN_ENABLED = False
CONTENT_SECURITY_POLICY_WARNING = False

# --- Theming ---
# Theme is controlled via CSS injection from the parent platform (postMessage).
# THEME_DEFAULT/THEME_DARK and setThemeMode are NOT used — they don't work
# reliably for embedded dashboards (AbortError: Transition was skipped).

# --- Embedded Superset & Guest Tokens ---
FEATURE_FLAGS = {
    "EMBEDDED_SUPERSET": True,
    "DASHBOARD_RBAC": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "ENABLE_EXPLORE_DRAG_AND_DROP": True,
    "ENABLE_JAVASCRIPT_CONTROLS": True,
}

# CORS — allow TradeAudit to embed dashboards
ENABLE_CORS = True
CORS_OPTIONS = {
    "supports_credentials": True,
    "allow_headers": ["*"],
    "resources": ["*"],
    "origins": os.environ.get("CORS_ORIGINS", "*").split(","),
}

# Guest token config
GUEST_ROLE_NAME = "Public"
GUEST_TOKEN_JWT_SECRET = os.environ.get("SUPERSET_SECRET_KEY", "CHANGE_ME")
GUEST_TOKEN_JWT_ALGO = "HS256"
GUEST_TOKEN_HEADER_NAME = "X-GuestToken"
GUEST_TOKEN_JWT_EXP_SECONDS = 3600  # 1 hour — reduces refresh failures

# Allow embedding in iframes
HTTP_HEADERS = {
    "X-Frame-Options": "ALLOWALL",
}
SESSION_COOKIE_SAMESITE = "None"
SESSION_COOKIE_SECURE = True

# Do NOT set PUBLIC_ROLE_LIKE — anonymous direct access to Superset shows nothing/login.
# The "Public" role is used for guest tokens (GUEST_ROLE_NAME = "Public").
# Grant permissions to that role manually in Superset admin:
# Admin → Security → List Roles → Public → add only the datasource/chart rows needed.


# ---------------------------------------------------------------------------
# Embedded pages: feature flags + error suppression + CSS theme injection
# Approach: parent sends CSS via postMessage, script injects <style> tags
# Based on: https://github.com/apache/superset/issues/32357#issuecomment
# ---------------------------------------------------------------------------
EMBEDDED_SCRIPT = """<script>
console.log('[TradeAudit EMBEDDED_SCRIPT] Script loaded inside iframe');

// Feature flags — Superset reads window.featureFlags
window.featureFlags = {
  ENABLE_JAVASCRIPT_CONTROLS: true,
  EMBEDDED_SUPERSET: true,
  DASHBOARD_NATIVE_FILTERS: true,
  DASHBOARD_CROSS_FILTERS: true,
  ENABLE_TEMPLATE_PROCESSING: true,
  ENABLE_EXPLORE_DRAG_AND_DROP: true
};

// Request the correct theme from the parent IMMEDIATELY — before React boots.
// The parent responds with setTheme which sets sessionStorage._embedded_theme.
// matchMedia reads sessionStorage, so React's ThemeProvider gets the right value on init.
if (window.parent !== window) {
  window.parent.postMessage({ type: 'requestTheme' }, '*');
}

// matchMedia override: reflect the platform theme instead of OS preference.
(function(){
  var _mm = window.matchMedia;
  window.matchMedia = function(q) {
    if (q === '(prefers-color-scheme: dark)') {
      var t = sessionStorage.getItem('_embedded_theme') || 'light';
      return {matches: t === 'dark', media: q,
        addListener:function(){}, removeListener:function(){},
        addEventListener:function(){}, removeEventListener:function(){},
        dispatchEvent:function(){}};
    }
    return _mm.call(this, q);
  };
})();

// Block navigation out of the embedded iframe.
// CRITICAL: Do NOT block history.pushState/replaceState globally — Superset uses them
// for filter params and Redux state. Blocking them causes React Router to dispatch
// a navigation action that never completes → "TypeError: payload undefined" in core.js.
//
// For chart title click-to-explore: intercept in the capture phase BEFORE React handles
// it via stopImmediatePropagation(). CSS pointer-events:none is added as a second layer.
(function(){
  // 1. Capture-phase click interceptor — stops chart title navigation before React fires
  // Logs every click so we can see exactly what element is being clicked in the console.
  document.addEventListener('click', function(e) {
    var el = e.target;
    console.log('[TradeAudit] click fired on:', el.tagName, '| data-test:', el.getAttribute && el.getAttribute('data-test'), '| class:', el.className && el.className.toString && el.className.toString().substring(0,80));
    var depth = 0;
    while (el && el !== document.body) {
      depth++;
      var dt = el.getAttribute && el.getAttribute('data-test');
      var titleAttr = (el.getAttribute && el.getAttribute('title')) || '';
      var cls = (el.className && typeof el.className === 'string') ? el.className : '';
      // Log first 5 levels so we can see the ancestor chain
      if (depth <= 5) {
        console.log('[TradeAudit]   depth=' + depth, el.tagName, '| dt=' + dt, '| title=' + titleAttr.substring(0,60), '| cls=' + cls.substring(0,60));
      }
      if (dt === 'editable-title' ||
          titleAttr.toLowerCase().indexOf('click to edit') !== -1 ||
          cls.indexOf('chart-header__title') !== -1 ||
          (el.tagName === 'H3' && el.closest && el.closest('[class*="chart-header"]')) ||
          (el.tagName === 'A' && el.closest && el.closest('[class*="chart-header"]'))) {
        console.log('[TradeAudit] BLOCKED chart title click at depth=' + depth, '| el:', el.tagName, dt || titleAttr.substring(0,40));
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        return;
      }
      // Also block any <a> with internal href
      if (el.tagName === 'A') {
        var href = el.getAttribute('href') || '';
        if (href && href !== '#' && !href.startsWith('#')) {
          console.log('[TradeAudit] BLOCKED link click:', href);
          e.preventDefault();
          e.stopPropagation();
          return;
        }
      }
      el = el.parentElement;
    }
    console.log('[TradeAudit] click NOT blocked (walked ' + depth + ' levels)');
  }, true);

  // 2. Block window.open
  window.open = function(u) { return null; };

  // 3. Block location.assign / replace
  try { window.location.assign = function(u) {}; } catch(e) {}
  try { window.location.replace = function(u) {}; } catch(e) {}

  // 4. Block location.href setter
  try {
    var locDesc = Object.getOwnPropertyDescriptor(Location.prototype, 'href');
    if (locDesc && locDesc.set) {
      Object.defineProperty(Location.prototype, 'href', {
        get: locDesc.get,
        set: function(v) {
          if (typeof v === 'string' && v.startsWith('#')) locDesc.set.call(this, v);
        }
      });
    }
  } catch(e) {}
})();

// --- Theme: CSS transparency + Superset native dark mode for ECharts canvas text ---
// ECharts uses canvas renderer (no SVG text elements) → CSS fill has zero effect.
// Solution: send Superset's native SELECT_THEME:'dark' so ECharts re-renders with light text.
// We keep CSS only for background transparency and HTML text color (tables, Big Number, etc.)
(function(){
  var TRANSPARENT_BG = [
    'html, body { overflow-x: hidden !important; margin: 0 !important; padding: 0 !important; }',
    'html, body, body > div, body > div > div { background: transparent !important; background-color: transparent !important; }',
    'div[class*="ant-layout"], div[class*="dashboard"], div[class*="grid-container"] { background: transparent !important; }',
    'div[class*="chart-container"], div[class*="tabs-content"] { background: transparent !important; }',
    'div[data-test], section, main { background: transparent !important; }',
    'div[class*="dashboard-content"], div[class*="dragdroppable"], div[class*="grid-content"] { padding: 0 !important; margin: 0 !important; }',
    '::-webkit-scrollbar-corner { display: none !important; }'
  ].join('\\n');

  // Chart title: block click-to-explore (CSS is secondary; JS capture handler is primary)
  // Disabled menu items (e.g. "Cached X ago") and dividers are hidden outright
  var BLOCK_NAV_CSS = [
    // Prevent chart title hover/click — broad selectors to cover all Superset versions
    '.chart-header__title, .chart-header__title *, [data-test="editable-title"], a.title-panel { pointer-events: none !important; cursor: default !important; }',
    // Hide "Cached X ago" disabled info row and menu dividers
    '.ant-dropdown-menu-item-disabled, .ant-dropdown-menu-item-divider { display: none !important; }',
    // Also hide the freshness badge in chart toolbar
    '[data-test="data-last-updated"], [class*="last-updated"], [class*="dataLastUpdated"], [class*="dataSourceInfo"] { display: none !important; }'
  ].join('\\n');

  var DARK_OVERRIDE_CSS = [
    ':root { color-scheme: normal !important; }',
    TRANSPARENT_BG,
    BLOCK_NAV_CSS,
    'div[class*="filter-bar"] { background: rgba(255,255,255,0.04) !important; }',
    'div[class*="Header"] { background: transparent !important; }',
    '* { color: #e0e0e0 !important; }',
    'canvas { background: transparent !important; }',
    // Fullscreen: solid background so platform doesn't bleed through
    ':fullscreen { background-color: #141414 !important; }',
    ':fullscreen > * { background-color: #141414 !important; }',
    ':-webkit-full-screen { background-color: #141414 !important; }',
    ':-webkit-full-screen > * { background-color: #141414 !important; }',
    ':-moz-full-screen { background-color: #141414 !important; }',
    '::backdrop { background-color: #141414 !important; }',
    // Dropdown menus: solid background (prevent transparent "floating" look)
    '.ant-dropdown-menu { background-color: #262626 !important; border: 1px solid #3a3a3a !important; }',
    '.ant-dropdown-menu-item { color: #e0e0e0 !important; }',
    '.ant-dropdown-menu-item:hover { background-color: #3a3a3a !important; }',
    '.ant-tooltip-inner { background-color: #262626 !important; color: #e0e0e0 !important; }'
  ].join('\\n');

  var LIGHT_OVERRIDE_CSS = [
    ':root { color-scheme: normal !important; }',
    TRANSPARENT_BG,
    BLOCK_NAV_CSS,
    'div[class*="filter-bar"], div[class*="Header"] { background: transparent !important; }',
    'canvas { background: transparent !important; }',
    // Fullscreen: solid background
    ':fullscreen { background-color: #f5f5f5 !important; }',
    ':fullscreen > * { background-color: #f5f5f5 !important; }',
    ':-webkit-full-screen { background-color: #f5f5f5 !important; }',
    ':-webkit-full-screen > * { background-color: #f5f5f5 !important; }',
    ':-moz-full-screen { background-color: #f5f5f5 !important; }',
    '::backdrop { background-color: #f5f5f5 !important; }',
    // Dropdown menus: solid background
    '.ant-dropdown-menu { background-color: #ffffff !important; border: 1px solid #e0e0e0 !important; box-shadow: 0 4px 12px rgba(0,0,0,0.12) !important; }',
    '.ant-dropdown-menu-item:hover { background-color: #f5f5f5 !important; }',
    '.ant-tooltip-inner { background-color: #ffffff !important; color: #141414 !important; border: 1px solid #e0e0e0 !important; }'
  ].join('\\n');

  var styleEl = null;

  function applyTransparencyCss(theme) {
    if (!styleEl) {
      styleEl = document.createElement('style');
      styleEl.id = 'tradeaudit-theme';
      document.head.appendChild(styleEl);
    }
    styleEl.textContent = (theme === 'dark') ? DARK_OVERRIDE_CSS : LIGHT_OVERRIDE_CSS;
    sessionStorage.setItem('_embedded_theme', theme);
  }

  // Always start light — parent will send correct theme via setTheme message
  applyTransparencyCss('light');

  window.addEventListener('message', function(e) {
    if (e.data && e.data.type === 'setTheme') {
      applyTransparencyCss(e.data.theme === 'dark' ? 'dark' : 'light');
    }
  });
})();

// Hide edit/share/embed controls — these should not be visible to end users
(function(){
  var HIDE_SELECTORS = [
    '[data-test="edit-alt-button"]',
    '[data-test="dashboard-header-add-component"]',
    '[aria-label="Add components"]',
  ];

  var HIDE_MENU_TEXTS = [
    'Share', 'Embed dashboard', 'Save as', 'Edit dashboard', 'Edit chart', 'View query',
    'Compartir', 'Editar dashboard', 'Editar gráfico', 'Guardar como', 'Incrustar dashboard', 'Ver consulta'
  ];

  function hideElements() {
    HIDE_SELECTORS.forEach(function(sel) {
      document.querySelectorAll(sel).forEach(function(el) {
        if (el.style.display !== 'none') el.style.setProperty('display', 'none', 'important');
      });
    });

    // Force inline pointer-events:none on chart title elements (beats any stylesheet override)
    document.querySelectorAll(
      '[data-test="editable-title"], .chart-header__title, .chart-header__title *'
    ).forEach(function(el) {
      if (el.style.pointerEvents !== 'none') {
        el.style.setProperty('pointer-events', 'none', 'important');
        el.style.cursor = 'default';
        el.title = ''; // remove tooltip
      }
    });

    // Hide menu items AND submenu parents (Compartir is a submenu, not a plain item)
    document.querySelectorAll(
      '.ant-dropdown-menu-item, .ant-dropdown-menu-submenu, li[role="menuitem"]'
    ).forEach(function(li) {
      if (li.style.display === 'none') return; // already hidden — skip to avoid loop
      var titleEl = li.querySelector('.ant-dropdown-menu-submenu-title') || li;
      var text = (titleEl.firstChild && titleEl.firstChild.nodeType === 3)
        ? titleEl.firstChild.textContent.trim()
        : (titleEl.innerText || '').split('\\n')[0].trim();
      if (!text) return;
      var shouldHide = HIDE_MENU_TEXTS.some(function(t){ return text.indexOf(t) !== -1; })
        // Also hide "Cached …" / "Fetched …" freshness info rows regardless of language
        || /cached|fetched|updated|en cach|actualizado/i.test(text)
        || /hace (unos|un|[0-9]+)|ago/i.test(text);
      if (shouldHide) {
        console.log('[TradeAudit] hiding menu item:', JSON.stringify(text));
        li.style.setProperty('display', 'none', 'important');
      }
    });

    // Remove href and title tooltip from ALL internal Superset links
    document.querySelectorAll('a[href]').forEach(function(a) {
      var href = a.getAttribute('href') || '';
      if (href.startsWith('/') || href.startsWith(window.location.origin)) {
        a.removeAttribute('href');
        a.style.cursor = 'default';
        a.title = '';
      }
    });
  }

  // Use 0ms debounce (next tick) — prevents infinite loop AND hides items immediately
  var _hideTimer = null;
  var hideObserver = new MutationObserver(function() {
    if (_hideTimer) return;
    _hideTimer = setTimeout(function() { _hideTimer = null; hideElements(); }, 0);
  });
  document.addEventListener('DOMContentLoaded', function() {
    hideElements();
    hideObserver.observe(document.body, { childList: true, subtree: true });
  });
  if (document.body) {
    hideElements();
    hideObserver.observe(document.body, { childList: true, subtree: true });
  }
})();

// Translate hardcoded English strings in React components
(function(){
  var TRANSLATIONS = {
    // Chart states
    'No results were returned for this query': 'No hay datos para mostrar',
    'There is currently no information to display.': 'No hay información disponible.',
    'No data': 'Sin datos',
    'Loading...': 'Cargando...',
    'No Results': 'Sin resultados',
    'An error occurred while loading this chart.': 'Ocurrió un error al cargar este gráfico.',
    'Try again': 'Reintentar',
    // Chart context menu
    'Force refresh': 'Forzar actualización',
    'Edit chart': 'Editar gráfico',
    'View query': 'Ver consulta',
    'View as table': 'Ver como tabla',
    'Download': 'Descargar',
    'Share': 'Compartir',
    'Enter fullscreen': 'Pantalla completa',
    'Exit fullscreen': 'Salir de pantalla completa',
    'Copy permalink to clipboard': 'Copiar enlace',
    'Share permalink by email': 'Compartir por correo',
    'Export to .CSV': 'Exportar a CSV',
    'Export to .XLSX': 'Exportar a Excel',
    'Export to original format': 'Exportar formato original',
    'Download as image': 'Descargar como imagen',
    'Copy to clipboard': 'Copiar al portapapeles',
    // Dashboard header
    'Refresh dashboard': 'Actualizar dashboard',
    'Enter fullscreen mode': 'Modo pantalla completa',
    'Set auto-refresh interval': 'Intervalo de actualización automática',
    // Data freshness
    'Fetched': 'Actualizado',
    'Updated': 'Actualizado',
    'seconds ago': 'hace unos segundos',
    'a minute ago': 'hace un minuto',
    'minutes ago': 'hace minutos',
    'an hour ago': 'hace una hora',
    'Cached': 'En caché',
    // Table pagination
    'rows': 'filas',
    'row': 'fila',
    'Rows per page': 'Filas por página',
    'Show': 'Mostrar',
    'entries': 'registros',
    'records': 'registros',
    'Showing': 'Mostrando',
    'to': 'a',
    'of': 'de',
    'Previous': 'Anterior',
    'Next': 'Siguiente',
    'First': 'Primero',
    'Last': 'Último',
    // Filters
    'Search': 'Buscar',
    'Reset': 'Restablecer',
    'Apply': 'Aplicar',
    'Filter': 'Filtrar',
    'Filters': 'Filtros',
    'Add filter': 'Agregar filtro',
    'Clear all': 'Limpiar todo',
    'Select value': 'Seleccionar valor',
    'All': 'Todos'
  };

  function translateNode(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      var text = node.textContent.trim();
      if (TRANSLATIONS[text]) {
        node.textContent = node.textContent.replace(text, TRANSLATIONS[text]);
      }
    }
  }

  function translateTree(root) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null, false);
    var node;
    while ((node = walker.nextNode())) {
      translateNode(node);
    }
  }

  var observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
      mutation.addedNodes.forEach(function(node) {
        if (node.nodeType === Node.ELEMENT_NODE) {
          translateTree(node);
        } else {
          translateNode(node);
        }
      });
    });
  });

  document.addEventListener('DOMContentLoaded', function() {
    translateTree(document.body);
    observer.observe(document.body, { childList: true, subtree: true });
  });
})();

// Fullscreen: inject a high-specificity <style> that beats TRANSPARENT_BG's !important rules.
// CSS specificity: :fullscreen div[class] = (0,2,1) > div[class*="..."] = (0,1,1)
// Also set inline !important on all ancestors (inline always beats any stylesheet rule).
(function(){
  var fsStyleEl = null;

  function onFullscreenChange() {
    var el = document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement;
    var theme = sessionStorage.getItem('_embedded_theme') || 'light';
    var bg = theme === 'dark' ? '#141414' : '#f5f5f5';
    console.log('[TradeAudit] fullscreenchange | el:', el ? (el.tagName + ' id=' + el.id + ' cls=' + (el.className||'').toString().substring(0,80)) : 'null (exiting)', '| theme:', theme, '| bg:', bg);

    if (el) {
      // 1. Inject high-specificity stylesheet rules
      if (!fsStyleEl) {
        fsStyleEl = document.createElement('style');
        fsStyleEl.id = 'ta-fullscreen-style';
        document.head.appendChild(fsStyleEl);
      }
      fsStyleEl.textContent = [
        ':fullscreen, :-webkit-full-screen, :-moz-full-screen { background-color: ' + bg + ' !important; }',
        ':fullscreen div[class], :-webkit-full-screen div[class] { background-color: ' + bg + ' !important; }',
        ':fullscreen canvas, :-webkit-full-screen canvas { background-color: ' + bg + ' !important; }',
        'html:has(:fullscreen), body:has(:fullscreen) { background-color: ' + bg + ' !important; }'
      ].join('\\n');
      console.log('[TradeAudit] fullscreen style injected:', fsStyleEl.textContent.substring(0,120));

      // 2. Inline !important on every ancestor (inline beats any stylesheet rule)
      document.documentElement.style.setProperty('background-color', bg, 'important');
      document.body.style.setProperty('background-color', bg, 'important');
      var ancestorCount = 0;
      var cur = el;
      while (cur && cur !== document.documentElement) {
        cur.style.setProperty('background-color', bg, 'important');
        cur = cur.parentElement;
        ancestorCount++;
      }
      // Verify: read back computed style
      var computed = window.getComputedStyle(el).backgroundColor;
      console.log('[TradeAudit] fullscreen el computed bg AFTER fix:', computed, '| ancestors patched:', ancestorCount);
      console.log('[TradeAudit] fullscreen body computed bg:', window.getComputedStyle(document.body).backgroundColor);
    } else {
      // Exiting fullscreen — clear injected rules and inline overrides
      if (fsStyleEl) fsStyleEl.textContent = '';
      document.documentElement.style.removeProperty('background-color');
      document.body.style.removeProperty('background-color');
      console.log('[TradeAudit] fullscreen exited, styles cleared');
    }
  }
  document.addEventListener('fullscreenchange', onFullscreenChange);
  document.addEventListener('webkitfullscreenchange', onFullscreenChange);
  document.addEventListener('mozfullscreenchange', onFullscreenChange);
})();

// Intercept non-critical API calls that fail for guest tokens
(function(){
  var _f = window.fetch;
  Object.defineProperty(window, 'fetch', {configurable:true, writable:true,
    value: function(u, o) {
      var s = (typeof u === 'string') ? u : (u && u.url) || '';
      if (s.indexOf('feature_flag') !== -1)
        return Promise.resolve(new Response(JSON.stringify({result:{}}),
          {status:200, headers:{'Content-Type':'application/json'}}));
      if (s.indexOf('language_pack') !== -1)
        return Promise.resolve(new Response(
          JSON.stringify({domain:"superset",locale_data:{superset:{"":{"domain":"superset","lang":"es","plural_forms":"nplurals=2; plural=(n != 1)"}}}}),
          {status:200, headers:{'Content-Type':'application/json'}}));
      return _f.apply(this, arguments);
    }
  });
})();
</script>"""

PLATFORM_URL = os.environ.get("PLATFORM_URL", "https://tu-plataforma.com")
ADMIN_ACCESS_KEY = os.environ.get("SUPERSET_ADMIN_KEY", "CHANGE_ME_ADMIN_KEY")

def FLASK_APP_MUTATOR(app: Flask):
    @app.before_request
    def block_direct_login():
        path = flask_request.path
        # Block the HTML login page — redirect to the platform
        # Admin can still access via /login?key=SECRET
        if path in ("/login/", "/login"):
            key = flask_request.args.get("key", "")
            if key != ADMIN_ACCESS_KEY:
                return redirect(PLATFORM_URL, code=302)

    @app.after_request
    def inject_embedded_overrides(response):
        if '/embedded/' not in flask_request.path:
            return response
        if response.content_type and 'text/html' in response.content_type:
            data = response.get_data(as_text=True)
            if '<head>' in data:
                data = data.replace('<head>', '<head>' + EMBEDDED_SCRIPT, 1)
                response.set_data(data)
        return response
