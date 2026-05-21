import logging

from flask import jsonify, request

from app.routes.mobile.blueprint import mobile_bp
from app.services.mobile import tenant_discovery_service as discovery_svc

logger = logging.getLogger(__name__)


@mobile_bp.route("/available-cities", methods=["GET", "OPTIONS"])
def mobile_available_cities():
    if request.method == "OPTIONS":
        return "", 200

    try:
        payload = discovery_svc.build_available_cities_response()
        logger.debug(
            "mobile available-cities: %d entries",
            len(payload.get("cities") or []),
        )
        return jsonify(payload), 200
    except Exception:
        logger.exception("mobile available-cities failed")
        return jsonify({"error": "Erro ao listar municípios disponíveis"}), 500
