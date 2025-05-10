from flask import Blueprint, request, jsonify,abort
from app.models.avaliacao import Avaliacao
from app import db
from app.utils.auth import get_current_tenant_id
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required

bp = Blueprint('avaliacoes', __name__, url_prefix="/avaliacao")

@bp.route('/', methods=['POST'])
@jwt_required()
@role_required("admin","professor", "coordenador","diretor")
def criar_avaliacao():
    data = request.get_json()
    nova_avaliacao = Avaliacao(
        titulo=data.get('titulo'),
        descricao=data.get('descricao'),
        tipo=data.get('tipo'),
        assunto=data.get('assunto'),
        grade_level=data.get('grade_level'),
        status=data.get('status'),
        total_points=data.get('total_points'),
        time_limit=data.get('time_limit'),
        passing_score=data.get('passing_score'),
        random_questions=data.get('random_questions'),
        show_results_immediately=data.get('show_results_immediately'),
        allow_review=data.get('allow_review'),
        instructions=data.get('instructions'),
        data_aplicacao=data.get('data_aplicacao'),
        tenant_id=data.get('tenant_id'),
        created_by=data.get('created_by')
    )

    db.session.add(nova_avaliacao)
    db.session.commit()
    return jsonify({"mensagem": "Avaliação criada com sucesso!","id": nova_avaliacao.id})

@bp.route('/', methods=['GET'])
@jwt_required()
@role_required("admin","professor", "coordenador","diretor")
def listar_avaliacoes():
    escola_id = get_current_tenant_id()
    avaliacoes = Avaliacao.query.filter_by(escola_id=escola_id).all()
        
    resultado = []
    for a in avaliacoes:
        resultado.append({
            'id': a.id,
            'titulo': a.titulo,
            'descricao': a.descricao,
            'tipo': a.tipo,
            'assunto': a.assunto,
            'grade_level': a.grade_level,
            'status': a.status,
            'total_points': a.total_points,
            'time_limit': a.time_limit.isoformat() if a.time_limit else None,
            'passing_score': a.passing_score,
            'random_questions': a.random_questions,
            'show_results_immediately': a.show_results_immediately,
            'allow_review': a.allow_review,
            'instructions': a.instructions,
            'data_aplicacao': a.data_aplicacao.isoformat() if a.data_aplicacao else None,
            'tenant_id': a.tenant_id,
            'created_by': a.created_by,
            'criado_em': a.criado_em.isoformat() if a.criado_em else None,
            'updated_at': a.updated_at.isoformat() if a.updated_at else None,
            'questoes': [
                {
                    'id': q.id,
                    'title': q.title,
                    'question_type': q.question_type,
                    'command': q.command,
                    'alternativas': q.alternativas,
                    'correct_answer': q.correct_answer
                }
                for q in a.questoes
            ]
        })
    return jsonify(resultado), 200

#Obter uma avaliação específica
@bp.route('/<string:avaliacao_id>',methods=["GET"])
def obter_avaliacao(avaliacao_id):
    a = Avaliacao.query.get_or_404(avaliacao_id)

    return jsonify({
        'id': a.id,
        'titulo': a.titulo,
        'descricao': a.descricao,
        'tipo': a.tipo,
        'assunto': a.assunto,
        'grade_level': a.grade_level,
        'status': a.status,
        'total_points': a.total_points,
        'time_limit': a.time_limit.isoformat() if a.time_limit else None,
        'passing_score': a.passing_score,
        'random_questions': a.random_questions,
        'show_results_immediately': a.show_results_immediately,
        'allow_review': a.allow_review,
        'instructions': a.instructions,
        'data_aplicacao': a.data_aplicacao.isoformat() if a.data_aplicacao else None,
        'tenant_id': a.tenant_id,
        'created_by': a.created_by,
        'criado_em': a.criado_em.isoformat() if a.criado_em else None,
        'updated_at': a.updated_at.isoformat() if a.updated_at else None,
        'questoes': [
            {
                'id': q.id,
                'title': q.title,
                'question_type': q.question_type,
                'command': q.command,
                'alternativas': q.alternativas,
                'correct_answer': q.correct_answer
            }
            for q in a.questoes
        ]
    }), 200

@bp.route('/<string:avaliacao_id>', methods=['PUT'])
def atualizar_avaliacao(avaliacao_id):
    avaliacao = Avaliacao.query.get_or_404(avaliacao_id)
    data = request.get_json()

    campos = [
        'titulo', 'descricao', 'tipo', 'assunto', 'grade_level', 'status', 'total_points',
        'time_limit', 'passing_score', 'random_questions', 'show_results_immediately',
        'allow_review', 'instructions', 'data_aplicacao', 'tenant_id', 'created_by'
    ]

    for campo in campos:
        if campo in data:
            setattr(avaliacao, campo, data[campo])

    db.session.commit()
    return jsonify({'message': 'Avaliação atualizada com sucesso!'}), 200

@bp.route('/<string:avaliacao_id>', methods=['DELETE'])
def deletar_avaliacao(avaliacao_id):
    avaliacao = Avaliacao.query.get_or_404(avaliacao_id)
    db.session.delete(avaliacao)
    db.session.commit()
    return jsonify({'message': 'Avaliação deletada com sucesso!'}), 200