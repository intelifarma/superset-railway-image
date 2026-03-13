import logging
import os
from flask import Flask

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
GUEST_TOKEN_JWT_EXP_SECONDS = 600

# Allow embedding in iframes
HTTP_HEADERS = {
    "X-Frame-Options": "ALLOWALL",
}
SESSION_COOKIE_SAMESITE = "None"
SESSION_COOKIE_SECURE = True

# Public role gets Alpha permissions (full read access to all datasources/charts)
PUBLIC_ROLE_LIKE = "Alpha"


# ---------------------------------------------------------------------------
# Inject light-theme CSS + suppress console errors on embedded pages
# ---------------------------------------------------------------------------
LIGHT_THEME_CSS = """<style>
body, #app, .embedded-page, [data-test="embedded-page"],
div[id^="root"], main, .dashboard-content, .grid-container,
.dashboard, .dashboard-component, .css-dashboard {
  background-color: #f5f5f5 !important;
  color-scheme: light !important;
}
.header-with-actions, .dashboard-header { background: #fff !important; }
.chart-container { background: #fff !important; border-radius: 8px; }
</style>"""

SUPPRESS_ERRORS_JS = """<script>
// Suppress non-critical embedded errors (feature flags, language pack)
(function(){
  var origFetch = window.fetch;
  window.fetch = function(url, opts) {
    var u = typeof url === 'string' ? url : (url && url.url) || '';
    if (u.includes('feature_flags') || u.includes('language_pack')) {
      if (u.includes('feature_flags')) {
        return Promise.resolve(new Response(JSON.stringify({result:{}}),
          {status:200, headers:{'Content-Type':'application/json'}}));
      }
      if (u.includes('language_pack')) {
        return Promise.resolve(new Response(JSON.stringify({}),
          {status:200, headers:{'Content-Type':'application/json'}}));
      }
    }
    return origFetch.apply(this, arguments);
  };
})();
</script>"""

def FLASK_APP_MUTATOR(app: Flask):
    @app.after_request
    def inject_embedded_overrides(response):
        if response.content_type and 'text/html' in response.content_type:
            data = response.get_data(as_text=True)
            if '</head>' in data:
                data = data.replace('</head>', LIGHT_THEME_CSS + SUPPRESS_ERRORS_JS + '</head>')
                response.set_data(data)
        return response
