from flask import Blueprint, jsonify

bp = Blueprint('logout', __name__, url_prefix='/logout')

@bp.route('/', methods=['POST'])
def logout():
    return jsonify({"mensagem": "Logout realizado com sucesso"}), 200
