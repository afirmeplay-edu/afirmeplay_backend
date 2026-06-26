"""
Rotas administrativas para gerenciar o catálogo de municípios mobile (mobile_city_directory).
Apenas para usuários com role 'admin'.

Dois fluxos principais:
1. Adicionar município da VPS central (shared) - referencia public.city
2. Adicionar município de VPS dedicada (dedicated) - dados manuais
"""
import logging
import os
from urllib.parse import urlparse
from flask import jsonify, request
from sqlalchemy.exc import IntegrityError

from app import db
from app.routes.mobile.blueprint import mobile_bp
from app.decorators.role_required import role_required
from app.models.mobile_city_directory import MobileCityDirectory
from app.models.city import City

logger = logging.getLogger(__name__)

VALID_HOSTING_MODES = {"shared", "dedicated"}
CENTRAL_API_URL = os.getenv("MOBILE_CENTRAL_API_URL", "https://prod-api.afirmeplay.com.br")


def _generate_tenant_code(city_id: str) -> str:
    """Gera tenant_code a partir do city_id (primeiros 8 caracteres sem hífens)."""
    return city_id.replace("-", "")[:8].upper()


def _validate_url_format(url: str) -> bool:
    """Valida se a URL tem formato válido."""
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def _normalize_api_base_url(url: str) -> str:
    """Normaliza URL da API removendo barra final."""
    return (url or "").strip().rstrip("/")


def _serialize_city_directory(entry: MobileCityDirectory) -> dict:
    """Serializa uma entrada do catálogo mobile."""
    return {
        "id": str(entry.id),
        "city_id": str(entry.city_id) if entry.city_id else None,
        "city_name": entry.city_name,
        "city_slug": entry.city_slug,
        "tenant_code": entry.tenant_code,
        "api_base_url": entry.api_base_url,
        "hosting_mode": entry.hosting_mode,
        "is_active": entry.is_active,
        "mobile_visible": entry.mobile_visible,
        "sort_order": entry.sort_order,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }


@mobile_bp.route("/admin/cities/available-for-mobile", methods=["GET"])
@role_required("admin")
def list_cities_available_for_mobile():
    """
    Lista municípios da VPS central que ainda NÃO estão no catálogo mobile.
    Útil para o admin selecionar qual município adicionar ao app mobile.
    Requer role 'admin'.
    """
    try:
        # Buscar IDs de municípios que já estão no catálogo mobile
        cities_in_mobile = set(
            row.city_id for row in MobileCityDirectory.query
            .filter(MobileCityDirectory.city_id.isnot(None))
            .with_entities(MobileCityDirectory.city_id)
            .all()
        )
        
        # Buscar municípios que NÃO estão no catálogo
        available_cities = City.query.filter(
            ~City.id.in_(cities_in_mobile) if cities_in_mobile else True
        ).order_by(City.name).all()
        
        return jsonify({
            "total": len(available_cities),
            "cities": [
                {
                    "id": city.id,
                    "name": city.name,
                    "state": city.state,
                    "slug": city.slug,
                    "plan_code": city.plan_code,
                }
                for city in available_cities
            ]
        }), 200
        
    except Exception as e:
        logger.exception("Erro ao listar municípios disponíveis para mobile")
        return jsonify({"erro": "Erro ao listar municípios", "detalhes": str(e)}), 500


@mobile_bp.route("/admin/cities", methods=["POST"])
@role_required("admin")
def create_mobile_city():
    """
    Adiciona um município ao catálogo mobile.
    
    Modo 1 (shared): Forneça city_id para adicionar município da VPS central
    Modo 2 (dedicated): Forneça dados manuais para VPS dedicada do cliente
    
    Requer role 'admin'.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"erro": "Nenhum dado fornecido"}), 400

        hosting_mode = data.get("hosting_mode", "").strip().lower()
        
        if hosting_mode not in VALID_HOSTING_MODES:
            return jsonify({
                "erro": f"hosting_mode inválido ou ausente. Use: {', '.join(VALID_HOSTING_MODES)}"
            }), 400

        # ============================================
        # MODO SHARED: Adicionar município da VPS central
        # ============================================
        if hosting_mode == "shared":
            city_id = data.get("city_id")
            if not city_id:
                return jsonify({
                    "erro": "city_id é obrigatório para hosting_mode='shared'",
                    "dica": "Forneça o ID do município existente em public.city"
                }), 400
            
            # Buscar município em public.city
            city = City.query.get(city_id)
            if not city:
                return jsonify({
                    "erro": "Município não encontrado",
                    "detalhes": f"Não existe município com id={city_id} na VPS central"
                }), 404
            
            # Verificar se já está no catálogo mobile
            existing = MobileCityDirectory.query.filter_by(city_id=city_id).first()
            if existing:
                return jsonify({
                    "erro": "Município já está no catálogo mobile",
                    "detalhes": f"{city.name} já foi adicionado ao app mobile",
                    "mobile_entry_id": str(existing.id)
                }), 409
            
            # Gerar tenant_code automaticamente
            tenant_code = _generate_tenant_code(city_id)
            
            # Criar entrada no catálogo
            new_entry = MobileCityDirectory(
                city_id=city_id,
                city_name=city.name,
                city_slug=city.slug,
                tenant_code=tenant_code,
                api_base_url=CENTRAL_API_URL,
                hosting_mode="shared",
                mobile_visible=data.get("mobile_visible", True),
                is_active=data.get("is_active", True),
                sort_order=data.get("sort_order", 0),
            )
            
            db.session.add(new_entry)
            db.session.commit()
            
            logger.info(
                "Município VPS central adicionado ao mobile: %s (city_id=%s, tenant=%s)",
                city.name,
                city_id,
                tenant_code,
            )
            
            return jsonify({
                "mensagem": f"Município '{city.name}' adicionado ao catálogo mobile com sucesso",
                "info": "Dados preenchidos automaticamente a partir do município da VPS central",
                "data": _serialize_city_directory(new_entry),
            }), 201

        # ============================================
        # MODO DEDICATED: Município em VPS dedicada
        # ============================================
        else:  # dedicated
            required_fields = ["city_name", "city_slug", "tenant_code", "api_base_url"]
            missing = [f for f in required_fields if not data.get(f)]
            if missing:
                return jsonify({
                    "erro": f"Campos obrigatórios faltando para hosting_mode='dedicated': {', '.join(missing)}"
                }), 400
            
            # Validar URL
            api_base_url = data["api_base_url"].strip()
            if not _validate_url_format(api_base_url):
                return jsonify({
                    "erro": "api_base_url inválida. Use formato: https://dominio.com.br"
                }), 400
            
            # Validar que URL não é a central
            normalized_url = _normalize_api_base_url(api_base_url).lower()
            central_normalized = _normalize_api_base_url(CENTRAL_API_URL).lower()
            if normalized_url == central_normalized:
                return jsonify({
                    "erro": f"URL de VPS dedicada não pode ser igual à API central ({CENTRAL_API_URL})",
                    "dica": "Para municípios na API central, use hosting_mode='shared' com city_id"
                }), 400
            
            # Criar entrada no catálogo
            new_entry = MobileCityDirectory(
                city_id=None,  # NULL para VPS dedicada
                city_name=data["city_name"].strip(),
                city_slug=data["city_slug"].strip().lower(),
                tenant_code=data["tenant_code"].strip(),
                api_base_url=_normalize_api_base_url(api_base_url),
                hosting_mode="dedicated",
                mobile_visible=data.get("mobile_visible", True),
                is_active=data.get("is_active", True),
                sort_order=data.get("sort_order", 0),
            )
            
            db.session.add(new_entry)
            db.session.commit()
            
            logger.info(
                "Município VPS dedicada adicionado ao mobile: %s (tenant=%s, url=%s)",
                new_entry.city_name,
                new_entry.tenant_code,
                new_entry.api_base_url,
            )
            
            return jsonify({
                "mensagem": f"Município '{new_entry.city_name}' (VPS dedicada) adicionado ao catálogo mobile",
                "data": _serialize_city_directory(new_entry),
            }), 201

    except IntegrityError as e:
        db.session.rollback()
        logger.error("Erro de integridade ao criar município mobile: %s", str(e))
        
        error_msg = str(e.orig).lower() if hasattr(e, 'orig') else str(e).lower()
        if "city_slug" in error_msg:
            return jsonify({
                "erro": "Já existe um município com este slug no catálogo mobile",
                "detalhes": "city_slug deve ser único"
            }), 409
        elif "tenant_code" in error_msg:
            return jsonify({
                "erro": "Já existe um município com este tenant_code no catálogo mobile",
                "detalhes": "tenant_code deve ser único"
            }), 409
        
        return jsonify({"erro": "Erro ao criar município", "detalhes": str(e)}), 500

    except Exception as e:
        db.session.rollback()
        logger.exception("Erro ao criar município mobile")
        return jsonify({"erro": "Erro interno ao criar município", "detalhes": str(e)}), 500


@mobile_bp.route("/admin/cities", methods=["GET"])
@role_required("admin")
def list_all_mobile_cities():
    """
    Lista todos os municípios do catálogo mobile (incluindo inativos e invisíveis).
    Requer role 'admin'.
    """
    try:
        entries = (
            MobileCityDirectory.query
            .order_by(
                MobileCityDirectory.sort_order.asc(),
                MobileCityDirectory.city_name.asc()
            )
            .all()
        )

        return jsonify({
            "total": len(entries),
            "cities": [_serialize_city_directory(entry) for entry in entries],
        }), 200

    except Exception as e:
        logger.exception("Erro ao listar municípios mobile")
        return jsonify({"erro": "Erro ao listar municípios", "detalhes": str(e)}), 500


@mobile_bp.route("/admin/cities/<city_id>", methods=["GET"])
@role_required("admin")
def get_mobile_city(city_id: str):
    """
    Busca um município específico do catálogo mobile.
    Requer role 'admin'.
    """
    try:
        entry = MobileCityDirectory.query.get(city_id)
        if not entry:
            return jsonify({"erro": "Município não encontrado"}), 404

        return jsonify(_serialize_city_directory(entry)), 200

    except Exception as e:
        logger.exception("Erro ao buscar município mobile: %s", city_id)
        return jsonify({"erro": "Erro ao buscar município", "detalhes": str(e)}), 500


@mobile_bp.route("/admin/cities/<city_id>", methods=["PUT"])
@role_required("admin")
def update_mobile_city(city_id: str):
    """
    Atualiza um município do catálogo mobile.
    
    Nota: Não é possível alterar city_id ou hosting_mode após criação.
    Para mudar de shared para dedicated ou vice-versa, remova e recrie a entrada.
    
    Requer role 'admin'.
    """
    try:
        entry = MobileCityDirectory.query.get(city_id)
        if not entry:
            return jsonify({"erro": "Município não encontrado"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"erro": "Nenhum dado fornecido"}), 400

        updated_fields = []

        # Campos editáveis (exceto city_id e hosting_mode que são imutáveis)
        if "mobile_visible" in data:
            new_value = bool(data["mobile_visible"])
            if entry.mobile_visible != new_value:
                entry.mobile_visible = new_value
                updated_fields.append("mobile_visible")
        
        if "is_active" in data:
            new_value = bool(data["is_active"])
            if entry.is_active != new_value:
                entry.is_active = new_value
                updated_fields.append("is_active")
        
        if "sort_order" in data:
            new_value = int(data["sort_order"])
            if entry.sort_order != new_value:
                entry.sort_order = new_value
                updated_fields.append("sort_order")

        if not updated_fields:
            return jsonify({
                "mensagem": "Nenhuma alteração detectada",
                "data": _serialize_city_directory(entry),
            }), 200

        db.session.commit()

        logger.info(
            "Município mobile atualizado: %s (id=%s, campos=%s)",
            entry.city_name,
            city_id,
            ", ".join(updated_fields),
        )

        return jsonify({
            "mensagem": "Município atualizado com sucesso",
            "updated_fields": updated_fields,
            "data": _serialize_city_directory(entry),
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.exception("Erro ao atualizar município mobile: %s", city_id)
        return jsonify({"erro": "Erro interno ao atualizar município", "detalhes": str(e)}), 500


@mobile_bp.route("/admin/cities/<city_id>", methods=["DELETE"])
@role_required("admin")
def deactivate_mobile_city(city_id: str):
    """
    Desativa um município do catálogo mobile (soft delete).
    Define is_active=False e mobile_visible=False.
    Requer role 'admin'.
    """
    try:
        entry = MobileCityDirectory.query.get(city_id)
        if not entry:
            return jsonify({"erro": "Município não encontrado"}), 404

        entry.is_active = False
        entry.mobile_visible = False

        db.session.commit()

        logger.info(
            "Município mobile desativado: %s (id=%s, slug=%s)",
            entry.city_name,
            city_id,
            entry.city_slug,
        )

        return jsonify({
            "mensagem": "Município desativado com sucesso",
            "data": _serialize_city_directory(entry),
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.exception("Erro ao desativar município mobile: %s", city_id)
        return jsonify({"erro": "Erro ao desativar município", "detalhes": str(e)}), 500


@mobile_bp.route("/admin/cities/config/central-api-url", methods=["GET"])
@role_required("admin")
def get_central_api_url():
    """
    Retorna a URL da API central configurada.
    Útil para o frontend saber qual é a URL padrão para municípios 'shared'.
    Requer role 'admin'.
    """
    try:
        return jsonify({
            "central_api_url": CENTRAL_API_URL,
            "description": "URL da API central usada para municípios com hosting_mode='shared'",
        }), 200
    except Exception as e:
        logger.exception("Erro ao obter URL central")
        return jsonify({"erro": "Erro ao obter configuração", "detalhes": str(e)}), 500
