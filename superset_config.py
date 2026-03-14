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

// --- Theme: CSS transparency + Superset native dark mode for ECharts canvas text ---
// ECharts uses canvas renderer (no SVG text elements) → CSS fill has zero effect.
// Solution: send Superset's native SELECT_THEME:'dark' so ECharts re-renders with light text.
// We keep CSS only for background transparency and HTML text color (tables, Big Number, etc.)
(function(){
  var TRANSPARENT_BG = [
    'html, body, body > div, body > div > div { background: transparent !important; background-color: transparent !important; }',
    'div[class*="ant-layout"], div[class*="dashboard"], div[class*="grid-container"] { background: transparent !important; }',
    'div[class*="chart-container"], div[class*="tabs-content"] { background: transparent !important; }',
    'div[data-test], section, main { background: transparent !important; }'
  ].join('\\n');

  // In dark mode Superset sets dark backgrounds — we override back to transparent.
  // HTML text color is handled by Superset's own dark theme (correct colors per component).
  var DARK_OVERRIDE_CSS = [
    ':root { color-scheme: normal !important; }',
    TRANSPARENT_BG,
    'div[class*="filter-bar"] { background: rgba(255,255,255,0.04) !important; }',
    'div[class*="Header"] { background: transparent !important; }',
    // Superset dark theme sets correct text colors; we only reinforce for elements it misses
    'canvas { background: transparent !important; }'
  ].join('\\n');

  var LIGHT_OVERRIDE_CSS = [
    ':root { color-scheme: normal !important; }',
    TRANSPARENT_BG,
    'div[class*="filter-bar"], div[class*="Header"] { background: transparent !important; }',
    'canvas { background: transparent !important; }'
  ].join('\\n');

  var styleEl = null;

  function applyTransparencyCss(theme) {
    if (!styleEl) {
      styleEl = document.createElement('style');
      styleEl.id = 'tradeaudit-theme';
      document.head.appendChild(styleEl);
    }
    styleEl.textContent = (theme === 'dark') ? DARK_OVERRIDE_CSS : LIGHT_OVERRIDE_CSS;
    localStorage.setItem('_embedded_theme', theme);
  }

  // Apply transparency immediately
  var savedTheme = localStorage.getItem('_embedded_theme') || 'light';
  applyTransparencyCss(savedTheme);

  // Listen for theme from parent platform
  window.addEventListener('message', function(e) {
    if (e.data && e.data.type === 'setTheme') {
      applyTransparencyCss(e.data.theme === 'dark' ? 'dark' : 'light');
    }
    // Superset's own SELECT_THEME is handled natively by Superset's React app —
    // no extra code needed here.
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
