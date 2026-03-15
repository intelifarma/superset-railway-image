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
// This round-trip is virtually instant (<1ms same-process), React init takes ~50-200ms.
if (window.parent !== window) {
  window.parent.postMessage({ type: 'requestTheme' }, '*');
}

// matchMedia override: reflect the platform theme instead of OS preference.
// Reads _embedded_theme from sessionStorage (set by the requestTheme response above
// and by subsequent setTheme messages). sessionStorage resets per page load.
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

// Block ALL navigation out of the embedded iframe
(function(){
  function isExternalNav(url) {
    if (!url || typeof url !== 'string') return false;
    return url.indexOf('/explore') !== -1 || url.indexOf('/chart/') !== -1 ||
           (url.indexOf('/superset/') !== -1 && url.indexOf('/embedded/') === -1);
  }

  // 1. Block <a> link clicks
  document.addEventListener('click', function(e) {
    var a = e.target.closest('a[href]');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    if (href !== '#' && !href.startsWith('#')) {
      console.log('[TradeAudit] blocked link click:', href);
      e.preventDefault(); e.stopPropagation();
    }
  }, true);

  // 2. Block window.open
  window.open = function(u) { console.log('[TradeAudit] blocked window.open:', u); return null; };

  // 3. Block location.assign / replace
  try { window.location.assign = function(u) { console.log('[TradeAudit] blocked assign:', u); }; } catch(e) {}
  try { window.location.replace = function(u) { console.log('[TradeAudit] blocked replace:', u); }; } catch(e) {}

  // 4. Block location.href setter
  try {
    var locDesc = Object.getOwnPropertyDescriptor(Location.prototype, 'href');
    if (locDesc && locDesc.set) {
      Object.defineProperty(Location.prototype, 'href', {
        get: locDesc.get,
        set: function(v) {
          if (typeof v === 'string' && v.startsWith('#')) locDesc.set.call(this, v);
          else console.log('[TradeAudit] blocked href=', v);
        }
      });
    }
  } catch(e) {}

  // 5. Block React Router history.pushState for external paths
  try {
    var _push = history.pushState.bind(history);
    var _rep = history.replaceState.bind(history);
    history.pushState = function(s, t, url) {
      if (isExternalNav(url)) { console.log('[TradeAudit] blocked pushState:', url); return; }
      return _push(s, t, url);
    };
    history.replaceState = function(s, t, url) {
      if (isExternalNav(url)) { console.log('[TradeAudit] blocked replaceState:', url); return; }
      return _rep(s, t, url);
    };
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

  var DARK_OVERRIDE_CSS = [
    ':root { color-scheme: normal !important; }',
    TRANSPARENT_BG,
    'div[class*="filter-bar"] { background: rgba(255,255,255,0.04) !important; }',
    'div[class*="Header"] { background: transparent !important; }',
    '* { color: #e0e0e0 !important; }',
    'canvas { background: transparent !important; }',
    // Fullscreen: solid background so platform doesn't bleed through
    ':fullscreen, :-webkit-full-screen, :-moz-full-screen { background-color: #141414 !important; }',
    '::backdrop { background-color: #141414 !important; }',
    ':fullscreen > div, :-webkit-full-screen > div { background-color: #141414 !important; }',
    // Dropdown menus: solid background (prevent transparent "floating" look)
    '.ant-dropdown-menu { background-color: #262626 !important; border: 1px solid #3a3a3a !important; }',
    '.ant-dropdown-menu-item { color: #e0e0e0 !important; }',
    '.ant-dropdown-menu-item:hover { background-color: #3a3a3a !important; }',
    '.ant-tooltip-inner { background-color: #262626 !important; color: #e0e0e0 !important; }'
  ].join('\\n');

  var LIGHT_OVERRIDE_CSS = [
    ':root { color-scheme: normal !important; }',
    TRANSPARENT_BG,
    'div[class*="filter-bar"], div[class*="Header"] { background: transparent !important; }',
    'canvas { background: transparent !important; }',
    // Fullscreen: solid background
    ':fullscreen, :-webkit-full-screen, :-moz-full-screen { background-color: #f5f5f5 !important; }',
    '::backdrop { background-color: #f5f5f5 !important; }',
    ':fullscreen > div, :-webkit-full-screen > div { background-color: #f5f5f5 !important; }',
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
    'Share', 'Embed dashboard', 'Save as', 'Edit dashboard', 'Edit chart',
    'Compartir', 'Editar dashboard', 'Editar gráfico', 'Guardar como', 'Incrustar dashboard'
  ];

  function hideElements() {
    HIDE_SELECTORS.forEach(function(sel) {
      document.querySelectorAll(sel).forEach(function(el) {
        el.style.setProperty('display', 'none', 'important');
      });
    });
    // Hide menu items AND submenu parents (Compartir is a submenu, not a plain item)
    document.querySelectorAll(
      '.ant-dropdown-menu-item, .ant-dropdown-menu-submenu, li[role="menuitem"]'
    ).forEach(function(li) {
      // For submenus, the text is in the title div
      var titleEl = li.querySelector('.ant-dropdown-menu-submenu-title') || li;
      var text = (titleEl.firstChild && titleEl.firstChild.nodeType === 3)
        ? titleEl.firstChild.textContent.trim()
        : (titleEl.innerText || '').split('\\n')[0].trim();
      if (text && HIDE_MENU_TEXTS.some(function(t){ return text.indexOf(t) !== -1; })) {
        console.log('[TradeAudit] hiding menu item:', text);
        li.style.setProperty('display', 'none', 'important');
      }
    });
    // Remove href from ALL internal Superset links
    document.querySelectorAll('a[href]').forEach(function(a) {
      var href = a.getAttribute('href') || '';
      if (href.startsWith('/') || href.startsWith(window.location.origin)) {
        a.removeAttribute('href');
        a.style.cursor = 'default';
        a.title = '';
      }
    });
  }

  var hideObserver = new MutationObserver(function() { hideElements(); });
  document.addEventListener('DOMContentLoaded', function() {
    hideElements();
    hideObserver.observe(document.body, { childList: true, subtree: true });
  });
  // Also run immediately in case DOM is already ready
  if (document.body) {
    hideElements();
    hideObserver.observe(document.body, { childList: true, subtree: true });
  }
})();

// Translate hardcoded English strings in React components
(function(){
  var TRANSLATIONS = {
    'No results were returned for this query': 'No hay datos para mostrar',
    'There is currently no information to display.': 'No hay información disponible.',
    'No data': 'Sin datos',
    'Loading...': 'Cargando...',
    'No Results': 'Sin resultados',
    'An error occurred while loading this chart.': 'Ocurrió un error al cargar este gráfico.',
    'Try again': 'Reintentar',
    'Force refresh': 'Forzar actualización',
    'Edit chart': 'Editar gráfico',
    'View query': 'Ver consulta',
    'Download': 'Descargar',
    'Share': 'Compartir',
    'Enter fullscreen': 'Pantalla completa',
    'Exit fullscreen': 'Salir de pantalla completa',
    'View as table': 'Ver como tabla',
    'View query': 'Ver consulta',
    'Refresh dashboard': 'Actualizar dashboard',
    'Enter fullscreen mode': 'Modo pantalla completa',
    'Force refresh': 'Forzar actualización',
    'Set auto-refresh interval': 'Intervalo de actualización automática',
    'Fetched': 'Actualizado',
    'seconds ago': 'hace unos segundos',
    'minutes ago': 'hace minutos',
    'an hour ago': 'hace una hora',
    'rows': 'filas',
    'row': 'fila',
    'Rows per page': 'Filas por página',
    'of': 'de',
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

// Fullscreen: force solid background via JS (CSS :fullscreen alone is unreliable in iframes)
(function(){
  function onFullscreenChange() {
    var el = document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement;
    var theme = sessionStorage.getItem('_embedded_theme') || 'light';
    var bg = theme === 'dark' ? '#141414' : '#ffffff';
    console.log('[TradeAudit] fullscreenchange — el:', el ? el.tagName + '.' + (el.className || '').split(' ')[0] : 'none', '| theme:', theme);
    if (el) {
      el.style.setProperty('background-color', bg, 'important');
      el.style.setProperty('background', bg, 'important');
      // Also fix direct children (chart wrappers)
      Array.prototype.forEach.call(el.children, function(child) {
        child.style.setProperty('background-color', bg, 'important');
      });
      var cs = window.getComputedStyle(el);
      console.log('[TradeAudit] fullscreen bg after fix:', cs.backgroundColor);
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
