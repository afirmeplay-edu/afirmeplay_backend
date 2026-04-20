"""
Rotas para verificação de subdomínio (slug de município).
Usado pelo frontend para validar se o subdomínio atual existe antes de seguir o fluxo.
"""

from flask import Blueprint, request, jsonify
from app.utils.tenant_middleware import resolve_city_from_slug
import re

bp = Blueprint('subdomain', __name__, url_prefix='/subdomain')


def _is_valid_slug(slug):
    """Aceita apenas slugs no mesmo formato usado pelo tenant_middleware (a-z, 0-9, hífen)."""
    if not slug or not isinstance(slug, str):
        return False
    slug = slug.strip().lower()
    return bool(slug and re.match(r'^[a-z0-9-]+$', slug))


@bp.route('/check', methods=['GET', 'OPTIONS'])
def check_subdomain():
    """
    Verifica se um subdomínio (slug de município) existe.

    Query params:
        subdomain (str): slug extraído do host (ex.: jiparana em jiparana.localhost:8080).

    Returns:
        200: { "exists": true } se o município existe.
        200: { "exists": false } se não existe (ou 404, conforme preferência do cliente).
        400: subdomain ausente ou formato inválido.
    """
    if request.method == 'OPTIONS':
        return '', 200

    subdomain = request.args.get('subdomain')
    if not subdomain or not subdomain.strip():
        return jsonify({"error": "Parâmetro 'subdomain' é obrigatório"}), 400

    subdomain = subdomain.strip().lower()
    if not _is_valid_slug(subdomain):
        return jsonify({"error": "Formato de subdomínio inválido (use apenas letras minúsculas, números e hífens)"}), 400

    city = resolve_city_from_slug(subdomain)
    if city:
        return jsonify({"exists": True}), 200
    return jsonify({"exists": False}), 200
