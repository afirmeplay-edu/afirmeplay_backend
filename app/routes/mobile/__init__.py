from app.routes.mobile.blueprint import mobile_bp
from app.routes.mobile import auth_routes  # noqa: F401
from app.routes.mobile import sync_routes  # noqa: F401
from app.routes.mobile import offline_pack_routes  # noqa: F401

__all__ = ["mobile_bp"]
