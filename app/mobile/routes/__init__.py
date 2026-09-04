from app.mobile.routes.blueprint import mobile_bp
from app.mobile.routes import auth_routes  # noqa: F401
from app.mobile.routes import sync_routes  # noqa: F401
from app.mobile.routes import offline_pack_routes  # noqa: F401
from app.mobile.routes import discovery_routes  # noqa: F401
from app.mobile.routes import answer_sheet_routes  # noqa: F401
from app.mobile.routes import socioeconomic_form_routes  # noqa: F401
from app.mobile.routes import admin_routes  # noqa: F401

__all__ = ["mobile_bp"]
