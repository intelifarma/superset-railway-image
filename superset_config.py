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
# Embedded pages: set light theme + suppress non-critical errors
# ---------------------------------------------------------------------------
# Must be FIRST in <head> so it runs before Superset's bundle captures window.fetch
EMBEDDED_SCRIPT = """<meta name="color-scheme" content="light only">
<script>
// Force light theme
localStorage.setItem('theme','light');
localStorage.setItem('ss_theme','light');
document.documentElement.setAttribute('data-theme','light');
document.documentElement.style.colorScheme='light';
// Intercept fetch BEFORE Superset bundle loads
(function(){
  var _f=window.fetch;
  Object.defineProperty(window,'fetch',{
    configurable:true,writable:true,
    value:function(u,o){
      var s=(typeof u==='string')?u:(u&&u.url)||'';
      if(s.indexOf('feature_flag')!==-1)
        return Promise.resolve(new Response(JSON.stringify({result:{}}),{status:200,headers:{'Content-Type':'application/json'}}));
      if(s.indexOf('language_pack')!==-1)
        return Promise.resolve(new Response(JSON.stringify({domain:"superset",locale_data:{superset:{"":{"domain":"superset","lang":"es","plural_forms":"nplurals=2; plural=(n != 1)"}}}}),{status:200,headers:{'Content-Type':'application/json'}}));
      return _f.apply(this,arguments);
    }
  });
})();
</script>"""

def FLASK_APP_MUTATOR(app: Flask):
    @app.after_request
    def inject_embedded_theme(response):
        # Only on /embedded/ pages
        if '/embedded/' not in flask_request.path:
            return response
        if response.content_type and 'text/html' in response.content_type:
            data = response.get_data(as_text=True)
            # Inject at the START of <head> so it runs before any Superset scripts
            if '<head>' in data:
                data = data.replace('<head>', '<head>' + EMBEDDED_SCRIPT, 1)
                response.set_data(data)
        return response
