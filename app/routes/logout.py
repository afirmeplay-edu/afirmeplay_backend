from flask import Blueprint, jsonify, make_response

bp = Blueprint('logout', __name__, url_prefix='/logout')

@bp.route('/', methods=['POST'])
def logout():
    response = make_response(jsonify({"mensagem": "Logout bem-sucedido."}))
    response.set_cookie("access_token", "", max_age=0, httponly=True, secure=True, samesite='Strict')
    return response
