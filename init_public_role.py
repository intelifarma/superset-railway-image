"""
Grant the Public role all permissions needed for Superset Embedded dashboards.
Run after `superset init` so the role already exists.
"""
import logging
from superset.app import create_app

logger = logging.getLogger(__name__)

EMBEDDED_PERMISSIONS = [
    ("can_read", "Dashboard"),
    ("can_read", "DashboardFilterStateRestApi"),
    ("can_read", "EmbeddedDashboard"),
    ("can_read", "Chart"),
    ("can_read", "Datasource"),
    ("can_read", "Dataset"),
    ("can_read", "DashboardPermalinkRestApi"),
    ("can_dashboard", "Superset"),
    ("can_explore_json", "Superset"),
    ("can_fave_dashboards", "Superset"),
    ("can_csv", "Superset"),
    ("menu_access", "Dashboards"),
    ("can_read", "Explore"),
    ("can_read", "FilterSets"),
    ("can_read", "SavedQuery"),
    ("can_read", "CssTemplate"),
    ("can_read", "AvailableDomains"),
    ("can_time_range", "Api"),
    ("can_query", "Api"),
    ("can_get", "DashboardFilterStateRestApi"),
    ("can_get", "EmbeddedDashboard"),
    ("can_warm_up_cache", "Superset"),
    ("can_recent_activity", "Superset"),
    ("can_get_embedded", "Dashboard"),
    ("can_read", "SecurityRestApi"),
]


def init():
    app = create_app()
    with app.app_context():
        from superset import security_manager

        sm = security_manager
        public_role = sm.find_role("Public")
        if not public_role:
            logger.warning("Public role not found — skipping embedded permissions")
            return

        added = 0
        for perm_name, view_name in EMBEDDED_PERMISSIONS:
            pv = sm.find_permission_view_menu(perm_name, view_name)
            if pv and pv not in public_role.permissions:
                public_role.permissions.append(pv)
                added += 1
            elif not pv:
                logger.debug(f"Permission {perm_name} on {view_name} not found — skipping")

        sm.get_session.commit()
        logger.info(f"Public role: added {added} embedded-dashboard permissions")


if __name__ == "__main__":
    init()
