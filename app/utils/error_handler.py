from flask import Flask, jsonify
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)

# Tratamento de erro genérico (erro interno do servidor)
@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Erro interno no servidor', 'details': str(error)}), 500

# Tratamento de erro 404 (recurso não encontrado)
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Recurso não encontrado'}), 404

# Tratamento de exceções do SQLAlchemy
@app.errorhandler(SQLAlchemyError)
def sqlalchemy_error_handler(error):
    return jsonify({'error': 'Erro de banco de dados', 'details': str(error)}), 500
