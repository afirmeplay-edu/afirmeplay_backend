from flask import Blueprint, request, jsonify, abort
from app.models.questao import Questao
from app import db
from app.utils.auth import get_current_tenant_id
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required

bp = Blueprint('questoes', __name__, url_prefix='/questoes')

@bp.route('/', methods=['POST'])
@jwt_required()
@role_required("admin","professor","coordenador","diretor")
def criar_questao():
    data = request.get_json()
    questao = Questao(
        title=data.get('title'),
        description=data.get('description'),
        resource_type=data.get('resource_type'),
        resource_content=data.get('resource_content'),
        command=data.get('command'),
        question_type=data.get('question_type'),
        subject=data.get('subject'),
        grade_level=data.get('grade_level'),
        difficulty_level=data.get('difficulty_level'),
        status=data.get('status', 'active'),
        correct_answer=data.get('correct_answer'),
        tags=data.get('tags'),
        avaliacao_id=data.get('avaliacao_id'),
        alternativas=data.get('alternativas'),
        escola_id=data.get('escola_id'),
        created_by=data.get('created_by')
    )
    db.session.add(questao)
    db.session.commit()
    return jsonify({"mensagem": "Questão criada com sucesso!","id": questao.id}),201

@bp.route('/', methods=['GET'])
@jwt_required()
def listar_questoes():
    escola_id = get_current_tenant_id()
    avaliacao_id = request.args.get('avaliacao_id')
    
    query = Questao.query.filter_by(escola_id=escola_id)
    
    if not escola_id or not avaliacao_id or not query:
        abort(404)
    
    if avaliacao_id:
        query = query.filter_by(avaliacao_id=avaliacao_id)

    questoes = query.all()
    resultado = []
    for q in questoes:
        resultado.append({
            'id': q.id,
            'title': q.title,
            'description': q.description,
            'resource_type': q.resource_type,
            'resource_content': q.resource_content,
            'command': q.command,
            'question_type': q.question_type,
            'subject': q.subject,
            'grade_level': q.grade_level,
            'difficulty_level': q.difficulty_level,
            'status': q.status,
            'correct_answer': q.correct_answer,
            'tags': q.tags,
            'avaliacao_id': q.avaliacao_id,
            'alternativas': q.alternativas,
            'escola_id': q.escola_id,
            'criado_em': q.criado_em,
            'created_by': q.created_by,
            'updated_at': q.updated_at
        })
    return jsonify(resultado), 200


#Questão específica

@bp.route("/<string:questao_id>",methods=["GET"])
def obter_questao(questao_id):
    q = Questao.query.get_or_404(questao_id)

    return jsonify({
        'id': q.id,
        'title': q.title,
        'description': q.description,
        'resource_type': q.resource_type,
        'resource_content': q.resource_content,
        'command': q.command,
        'question_type': q.question_type,
        'subject': q.subject,
        'grade_level': q.grade_level,
        'difficulty_level': q.difficulty_level,
        'status': q.status,
        'correct_answer': q.correct_answer,
        'tags': q.tags,
        'avaliacao_id': q.avaliacao_id,
        'alternativas': q.alternativas,
        'escola_id': q.escola_id,
        'criado_em': q.criado_em,
        'created_by': q.created_by,
        'updated_at': q.updated_at
    }), 200

@bp.route('/<string:questao_id>', methods=['PUT'])
def atualizar_questao(questao_id):
    questao = Questao.query.get_or_404(questao_id)
    data = request.get_json()

    for field in ['title', 'description', 'resource_type', 'resource_content', 'command',
                  'question_type', 'subject', 'grade_level', 'difficulty_level', 'status',
                  'correct_answer', 'tags', 'avaliacao_id', 'alternativas', 'escola_id']:
        if field in data:
            setattr(questao, field, data[field])

    db.session.commit()
    return jsonify({'message': 'Questão atualizada com sucesso'}),200

@bp.route('/<string:questao_id>', methods=['DELETE'])
def deletar_questao(questao_id):
    questao = Questao.query.get_or_404(questao_id)
    db.session.delete(questao)
    db.session.commit()
    return jsonify({'message': 'Questão removida com sucesso'}),200