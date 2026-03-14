import logging
import os
from flask import Flask, request as flask_request

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

# Public role gets Alpha permissions (full read access to all datasources/charts)
PUBLIC_ROLE_LIKE = "Alpha"


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

// Block OS dark mode from leaking into Superset
(function(){
  var _mm = window.matchMedia;
  window.matchMedia = function(q) {
    if (q === '(prefers-color-scheme: dark)') {
      return {matches: false, media: q,
        addListener:function(){}, removeListener:function(){},
        addEventListener:function(){}, removeEventListener:function(){},
        dispatchEvent:function(){}};
    }
    return _mm.call(this, q);
  };
})();

// --- CSS Theme Injection via postMessage ---
// Parent sends: { type: 'setTheme', theme: 'dark'|'light' }
// This injects/updates a <style> tag with the appropriate overrides
(function(){
  // Nuclear approach: override ALL divs background, then refine
  // #app may not exist in embedded mode, so use body > div chain
  var LIGHT_CSS = [
    ':root { color-scheme: normal !important; }',
    'html, body, body > div, body > div > div, body > div > div > div, body > div > div > div > div { background: transparent !important; background-color: transparent !important; }',
    'div[class*="ant-layout"] { background: transparent !important; }',
    'div[class*="dashboard"] { background: transparent !important; }',
    'div[class*="grid-container"] { background: transparent !important; }',
    'div[class*="chart-container"] { background: transparent !important; }',
    'div[class*="filter-bar"] { background: transparent !important; }',
    'div[class*="Header"] { background: transparent !important; }',
    'div[class*="tabs-content"] { background: transparent !important; }',
    'div[data-test] { background: transparent !important; }',
    'section { background: transparent !important; }',
    'main { background: transparent !important; }'
  ].join('\\n');

  var DARK_CSS = [
    ':root { color-scheme: normal !important; }',
    'html, body, body > div, body > div > div, body > div > div > div, body > div > div > div > div { background: transparent !important; background-color: transparent !important; color: #e0e0e0 !important; }',
    'div[class*="ant-layout"] { background: transparent !important; }',
    'div[class*="dashboard"] { background: transparent !important; }',
    'div[class*="grid-container"] { background: transparent !important; }',
    'div[class*="chart-container"] { background: transparent !important; }',
    'div[class*="filter-bar"] { background: rgba(255,255,255,0.04) !important; }',
    'div[class*="Header"] { background: transparent !important; color: #e0e0e0 !important; }',
    'div[class*="tabs-content"] { background: transparent !important; }',
    'div[data-test] { background: transparent !important; }',
    'section { background: transparent !important; }',
    'main { background: transparent !important; }',
    '* { color: #e0e0e0 !important; }',
    'text, tspan { fill: #c0c0c0 !important; }',
    'svg text { fill: #c0c0c0 !important; }',
    '.header-title, .header-title span, [class*="header-title"] { color: #ffffff !important; }',
    '[class*="big_number"], [class*="BigNumber"], [class*="number"] { color: #ffffff !important; }',
    'div[class*="slice_container"] * { color: #e0e0e0 !important; }',
    'input, select, textarea { background: rgba(255,255,255,0.08) !important; color: #e0e0e0 !important; border-color: rgba(255,255,255,0.15) !important; }',
    'table { color: #e0e0e0 !important; }',
    'th { background: rgba(255,255,255,0.06) !important; }',
    'tr:hover td { background: rgba(255,255,255,0.04) !important; }',
    'a { color: #8ab4f8 !important; }',
    '[class*="tooltip"] { background: #1e1e2e !important; color: #e0e0e0 !important; }'
  ].join('\\n');

  // Debug: dump DOM structure after React renders
  setTimeout(function() {
    var el = document.body;
    var path = [];
    var current = el ? el.firstElementChild : null;
    for (var i = 0; i < 8 && current; i++) {
      var id = current.id ? '#' + current.id : '';
      var cls = current.className ? '.' + String(current.className).split(' ')[0].substring(0, 20) : '';
      var bg = window.getComputedStyle(current).backgroundColor;
      path.push(current.tagName + id + cls + ' [bg:' + bg + ']');
      current = current.firstElementChild;
    }
    console.log('[TradeAudit] DOM structure:', path.join(' > '));
    // Also find all elements with non-transparent background
    var allBg = document.querySelectorAll('*');
    var grays = [];
    for (var j = 0; j < allBg.length && grays.length < 10; j++) {
      var bgc = window.getComputedStyle(allBg[j]).backgroundColor;
      if (bgc && bgc !== 'rgba(0, 0, 0, 0)' && bgc !== 'transparent') {
        var tag = allBg[j].tagName + (allBg[j].id ? '#' + allBg[j].id : '') + (allBg[j].className ? '.' + String(allBg[j].className).split(' ')[0].substring(0, 25) : '');
        grays.push(tag + ' → ' + bgc);
      }
    }
    console.log('[TradeAudit] Elements with background:', grays);
  }, 5000);

  var styleEl = null;

  function applyTheme(theme) {
    if (!styleEl) {
      styleEl = document.createElement('style');
      styleEl.id = 'tradeaudit-theme';
      document.head.appendChild(styleEl);
    }
    styleEl.textContent = (theme === 'dark') ? DARK_CSS : LIGHT_CSS;
    localStorage.setItem('_embedded_theme', theme);
    console.log('[TradeAudit] Style tag injected, length:', styleEl.textContent.length, 'theme:', theme);
  }

  // Apply saved theme immediately (before React renders)
  var savedTheme = localStorage.getItem('_embedded_theme') || 'light';
  console.log('[TradeAudit] Applying saved theme:', savedTheme);
  applyTheme(savedTheme);

  // Listen for theme changes from parent
  window.addEventListener('message', function(e) {
    console.log('[TradeAudit] postMessage received:', e.data);
    if (e.data && e.data.type === 'setTheme') {
      console.log('[TradeAudit] Switching theme to:', e.data.theme);
      applyTheme(e.data.theme === 'dark' ? 'dark' : 'light');
    }
  });
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

def FLASK_APP_MUTATOR(app: Flask):
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
