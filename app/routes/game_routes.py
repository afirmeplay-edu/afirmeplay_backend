from flask import Blueprint, jsonify, request
from app.models.game import Game, GameClass
from app.models.subject import Subject
from app.models.studentClass import Class
from app.models.teacher import Teacher
from app.models.teacherClass import TeacherClass
from app.models.manager import Manager
from app.models.student import Student
from app.models.school import School
from app.utils.uuid_helpers import ensure_uuid, ensure_uuid_list
from app.decorators.role_required import role_required, get_current_user_from_token
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError
import logging
from app import db
from app.permissions.utils import get_teacher_classes, get_manager_school

bp = Blueprint('games', __name__, url_prefix='/games')

def validate_subject(subject_name):
    """Valida se a disciplina existe no sistema"""
    subject = Subject.query.filter_by(name=subject_name).first()
    return subject is not None

def validate_and_collect_classes(data, user_role, current_user):
    """
    Valida e coleta todas as turmas baseado nos critérios fornecidos.
    Suporta múltiplas seleções através de arrays.
    
    Args:
        data: Dados da requisição
        user_role: Role do usuário
        current_user: Dados do usuário autenticado
    
    Returns:
        tuple: (set de class_ids válidos, lista de erros)
    """
    class_ids_to_link = set()
    errors = []
    
    # Normalizar campos singulares para arrays (compatibilidade)
    class_ids = data.get("class_ids") or (data.get("class_id") and [data.get("class_id")]) or []
    school_ids = data.get("school_ids") or (data.get("school_id") and [data.get("school_id")]) or []
    grade_ids = data.get("grade_ids") or (data.get("grade_id") and [data.get("grade_id")]) or []
    
    # Garantir que são listas
    if not isinstance(class_ids, list):
        class_ids = [class_ids] if class_ids else []
    if not isinstance(school_ids, list):
        school_ids = [school_ids] if school_ids else []
    if not isinstance(grade_ids, list):
        grade_ids = [grade_ids] if grade_ids else []
    
    # 1. Processar class_ids (turmas específicas) - maior prioridade
    if class_ids:
        # Converter class_ids para UUID (Class.id é UUID)
        class_ids_uuids = ensure_uuid_list(class_ids)
        
        # Verificar se todos os class_ids foram convertidos corretamente
        if len(class_ids_uuids) != len(class_ids):
            invalid_ids = []
            for class_id in class_ids:
                uuid_val = ensure_uuid(class_id)
                if uuid_val is None:
                    invalid_ids.append(str(class_id))
            if invalid_ids:
                errors.append(f"IDs de turma inválidos: {', '.join(invalid_ids)}")
        
        if class_ids_uuids:
            classes = Class.query.filter(Class.id.in_(class_ids_uuids)).all()
            found_ids = {c.id for c in classes}
            missing_ids = set(class_ids_uuids) - found_ids
            
            if missing_ids:
                # Converter UUIDs para string para exibição
                missing_ids_str = [str(uuid) for uuid in missing_ids]
                errors.append(f"Turmas não encontradas: {', '.join(missing_ids_str)}")
        
        # Validar permissões por role
        for class_obj in classes:
            has_permission = True
            
            if user_role in ["diretor", "coordenador"]:
                manager = Manager.query.filter_by(user_id=current_user["id"]).first()
                if not manager or not manager.school_id:
                    errors.append("Você não está vinculado a uma escola")
                    has_permission = False
                elif class_obj.school_id != manager.school_id:
                    errors.append(f"Turma {class_obj.name} não pertence à sua escola")
                    has_permission = False
            elif user_role == "tecadm":
                city_id = current_user.get('tenant_id') or current_user.get('city_id')
                if city_id:
                    school = School.query.get(class_obj.school_id)
                    if not school or school.city_id != city_id:
                        errors.append(f"Turma {class_obj.name} não pertence ao seu município")
                        has_permission = False
            
            if has_permission:
                class_ids_to_link.add(class_obj.id)
    
    # 2. Processar school_ids + grade_ids (séries em escolas específicas)
    if school_ids and grade_ids and not errors:
        for school_id in school_ids:
            school = School.query.get(school_id)
            if not school:
                errors.append(f"Escola {school_id} não encontrada")
                continue
            
            # Validar permissões para escola
            if user_role == "tecadm":
                city_id = current_user.get('tenant_id') or current_user.get('city_id')
                if city_id and school.city_id != city_id:
                    errors.append(f"Escola {school.name} não pertence ao seu município")
                    continue
            
            for grade_id in grade_ids:
                # Converter school_id para UUID (Class.school_id é UUID)
                school_id_uuid = ensure_uuid(school_id)
                if school_id_uuid:
                    classes = Class.query.filter_by(school_id=school_id_uuid, grade_id=grade_id).all()
                else:
                    continue
                for class_obj in classes:
                    class_ids_to_link.add(class_obj.id)
    
    # 3. Processar apenas school_ids (todas as turmas das escolas)
    elif school_ids and not grade_ids and not errors:
        for school_id in school_ids:
            school = School.query.get(school_id)
            if not school:
                errors.append(f"Escola {school_id} não encontrada")
                continue
            
            # Validar permissões para escola
            if user_role == "tecadm":
                city_id = current_user.get('tenant_id') or current_user.get('city_id')
                if city_id and school.city_id != city_id:
                    errors.append(f"Escola {school.name} não pertence ao seu município")
                    continue
            
            # Converter school_id para UUID (Class.school_id é UUID)
            school_id_uuid = ensure_uuid(school_id)
            if school_id_uuid:
                classes = Class.query.filter_by(school_id=school_id_uuid).all()
            else:
                continue
            for class_obj in classes:
                class_ids_to_link.add(class_obj.id)
    
    # 4. Processar apenas grade_ids (apenas para diretor/coordenador - séries na sua escola)
    elif grade_ids and not school_ids and not class_ids and user_role in ["diretor", "coordenador"] and not errors:
        manager = Manager.query.filter_by(user_id=current_user["id"]).first()
        if not manager or not manager.school_id:
            errors.append("Você não está vinculado a uma escola")
        else:
            for grade_id in grade_ids:
                # manager.school_id pode ser string, converter para UUID (Class.school_id é UUID)
                manager_school_id_uuid = ensure_uuid(manager.school_id)
                if manager_school_id_uuid:
                    classes = Class.query.filter_by(school_id=manager_school_id_uuid, grade_id=grade_id).all()
                else:
                    continue
                for class_obj in classes:
                    class_ids_to_link.add(class_obj.id)
    
    # Validar que pelo menos uma turma foi encontrada
    if not class_ids_to_link and not errors:
        if not class_ids and not school_ids and not grade_ids:
            errors.append("É necessário fornecer pelo menos um critério: class_ids, school_ids ou grade_ids")
        else:
            errors.append("Nenhuma turma encontrada para os critérios fornecidos")
    
    return class_ids_to_link, errors

@bp.route('', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def create_game():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400

        # Campos obrigatórios
        required_fields = ["url", "title", "iframeHtml", "subject"]
        for field in required_fields:
            if field not in data:
                return jsonify({"erro": f"Campo obrigatório ausente: {field}"}), 400

        # Validar disciplina
        if not validate_subject(data["subject"]):
            return jsonify({"erro": "Disciplina inválida"}), 400

        # Obter usuário autenticado
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não autenticado"}), 401

        user_role = current_user.get("role")
        class_ids_to_link = []

        # Lógica por role para determinar turmas
        if user_role == "professor":
            # Professor: usar turmas vinculadas automaticamente
            teacher_class_ids = get_teacher_classes(current_user["id"])
            if not teacher_class_ids:
                return jsonify({"erro": "Você não possui turmas vinculadas. Vincule-se a uma turma primeiro."}), 400
            class_ids_to_link = list(teacher_class_ids)

        elif user_role in ["diretor", "coordenador", "admin", "tecadm"]:
            # Usar função auxiliar para validar e coletar turmas (suporta múltiplas seleções)
            class_ids_to_link, errors = validate_and_collect_classes(data, user_role, current_user)
            
            if errors:
                return jsonify({"erro": "Erro na validação", "detalhes": errors}), 400
            
            if not class_ids_to_link:
                return jsonify({"erro": "Nenhuma turma encontrada para os critérios fornecidos"}), 404
            
            # Converter set para lista
            class_ids_to_link = list(class_ids_to_link)

        # Criar novo jogo
        novo_jogo = Game(
            url=data["url"],
            title=data["title"],
            iframeHtml=data["iframeHtml"],
            thumbnail=data.get("thumbnail"),
            author=data.get("author"),
            provider="wordwall",  # Valor fixo
            subject=data["subject"],
            userId=current_user["id"]
        )

        db.session.add(novo_jogo)
        db.session.flush()  # Para obter o ID antes de criar associações

        # Criar associações com turmas
        for class_id in class_ids_to_link:
            game_class = GameClass(
                game_id=novo_jogo.id,
                class_id=class_id
            )
            db.session.add(game_class)

        db.session.commit()

        # Buscar informações das turmas vinculadas
        linked_classes = Class.query.filter(Class.id.in_(class_ids_to_link)).all()

        return jsonify({
            "mensagem": "Jogo criado com sucesso!",
            "jogo": {
                "id": novo_jogo.id,
                "url": novo_jogo.url,
                "title": novo_jogo.title,
                "iframeHtml": novo_jogo.iframeHtml,
                "thumbnail": novo_jogo.thumbnail,
                "author": novo_jogo.author,
                "provider": novo_jogo.provider,
                "subject": novo_jogo.subject,
                "userId": novo_jogo.userId,
                "classes": [{"id": c.id, "name": c.name} for c in linked_classes],
                "createdAt": novo_jogo.createdAt.isoformat() if novo_jogo.createdAt else None,
                "updatedAt": novo_jogo.updatedAt.isoformat() if novo_jogo.updatedAt else None
            }
        }), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados: {str(e)}")
        return jsonify({"erro": "Erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao criar jogo: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao criar jogo", "detalhes": str(e)}), 500

@bp.route('', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
def list_games():
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        user_role = user.get("role")
        
        # Verificar se deve filtrar apenas jogos criados pelo usuário
        my_games = request.args.get('my_games', '').lower() == 'true'
        
        # Se my_games=true, filtrar apenas jogos criados pelo usuário
        if my_games:
            # Apenas usuários que podem criar jogos podem usar este filtro
            if user_role not in ["admin", "professor", "coordenador", "diretor", "tecadm"]:
                return jsonify({"erro": "Você não tem permissão para usar este filtro"}), 403
            
            query = db.session.query(Game).filter(Game.userId == user["id"])
        else:
            # Lógica existente de filtros por permissão
            query = db.session.query(Game).join(GameClass, Game.id == GameClass.game_id).distinct()
            
            # Aplicar filtros de permissão por role
            if user_role == "aluno":
                # Aluno: apenas jogos da sua turma
                student = Student.query.filter_by(user_id=user["id"]).first()
                if student and student.class_id:
                    query = query.filter(GameClass.class_id == student.class_id)
                else:
                    return jsonify({"jogos": []}), 200
            
            elif user_role == "professor":
                # Professor: jogos das suas turmas
                teacher_class_ids = get_teacher_classes(user["id"])
                if teacher_class_ids:
                    query = query.filter(GameClass.class_id.in_(teacher_class_ids))
                else:
                    return jsonify({"jogos": []}), 200
            
            elif user_role in ["diretor", "coordenador"]:
                # Diretor/Coordenador: jogos das turmas da sua escola
                manager = Manager.query.filter_by(user_id=user["id"]).first()
                if manager and manager.school_id:
                    school_classes = Class.query.filter_by(school_id=manager.school_id).all()
                    class_ids = [c.id for c in school_classes]
                    if class_ids:
                        query = query.filter(GameClass.class_id.in_(class_ids))
                    else:
                        return jsonify({"jogos": []}), 200
                else:
                    return jsonify({"jogos": []}), 200
            
            elif user_role == "tecadm":
                # Tecadm: jogos das escolas da sua cidade
                city_id = user.get('tenant_id') or user.get('city_id')
                if city_id:
                    schools = School.query.filter_by(city_id=city_id).all()
                    school_ids = [s.id for s in schools]
                    if school_ids:
                        school_classes = Class.query.filter(Class.school_id.in_(school_ids)).all()
                        class_ids = [c.id for c in school_classes]
                        if class_ids:
                            query = query.filter(GameClass.class_id.in_(class_ids))
                        else:
                            return jsonify({"jogos": []}), 200
                    else:
                        return jsonify({"jogos": []}), 200
                else:
                    return jsonify({"jogos": []}), 200
            
            # Admin: não precisa filtrar, retorna todos
        
        games = query.all()
        
        # Formatar resposta com informações das turmas
        result = []
        for game in games:
            result.append({
                "id": game.id,
                "url": game.url,
                "title": game.title,
                "iframeHtml": game.iframeHtml,
                "thumbnail": game.thumbnail,
                "author": game.author,
                "provider": game.provider,
                "subject": game.subject,
                "userId": game.userId,
                "classes": [{"id": gc.class_.id, "name": gc.class_.name} for gc in game.game_classes],
                "createdAt": game.createdAt.isoformat() if game.createdAt else None,
                "updatedAt": game.updatedAt.isoformat() if game.updatedAt else None
            })
        
        return jsonify({"jogos": result}), 200

    except Exception as e:
        logging.error(f"Erro ao listar jogos: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao listar jogos", "detalhes": str(e)}), 500

@bp.route('/<string:game_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
def get_game_by_id(game_id):
    try:
        game = Game.query.get(game_id)
        
        if not game:
            return jsonify({"erro": "Jogo não encontrado"}), 404

        # Verificar permissões de acesso
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        user_role = user.get("role")
        has_access = False
        
        # Obter IDs das turmas do jogo
        game_class_ids = [gc.class_id for gc in game.game_classes]
        
        if user_role == "admin":
            has_access = True
        elif user_role == "aluno":
            student = Student.query.filter_by(user_id=user["id"]).first()
            if student and student.class_id in game_class_ids:
                has_access = True
        elif user_role == "professor":
            teacher_class_ids = get_teacher_classes(user["id"])
            if any(cid in teacher_class_ids for cid in game_class_ids):
                has_access = True
        elif user_role in ["diretor", "coordenador"]:
            manager = Manager.query.filter_by(user_id=user["id"]).first()
            if manager and manager.school_id:
                school_classes = Class.query.filter_by(school_id=manager.school_id).all()
                school_class_ids = [c.id for c in school_classes]
                if any(cid in school_class_ids for cid in game_class_ids):
                    has_access = True
        elif user_role == "tecadm":
            city_id = user.get('tenant_id') or user.get('city_id')
            if city_id:
                schools = School.query.filter_by(city_id=city_id).all()
                school_ids = [s.id for s in schools]
                if school_ids:
                    school_classes = Class.query.filter(Class.school_id.in_(school_ids)).all()
                    school_class_ids = [c.id for c in school_classes]
                    if any(cid in school_class_ids for cid in game_class_ids):
                        has_access = True
        
        if not has_access:
            return jsonify({"erro": "Você não tem permissão para acessar este jogo"}), 403

        return jsonify({
            "id": game.id,
            "url": game.url,
            "title": game.title,
            "iframeHtml": game.iframeHtml,
            "thumbnail": game.thumbnail,
            "author": game.author,
            "provider": game.provider,
            "subject": game.subject,
            "userId": game.userId,
            "classes": [{"id": gc.class_.id, "name": gc.class_.name} for gc in game.game_classes],
            "createdAt": game.createdAt.isoformat() if game.createdAt else None,
            "updatedAt": game.updatedAt.isoformat() if game.updatedAt else None
        }), 200

    except Exception as e:
        logging.error(f"Erro ao buscar jogo: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao buscar jogo", "detalhes": str(e)}), 500

@bp.route('/<string:game_id>', methods=['PUT'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def update_game(game_id):
    try:
        game = Game.query.get(game_id)
        
        if not game:
            return jsonify({"erro": "Jogo não encontrado"}), 404

        # Verificar permissões
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não autenticado"}), 401

        user_role = current_user.get("role")
        
        # Apenas o criador do jogo ou admin/tecadm podem editar
        if game.userId != current_user["id"] and user_role not in ["admin", "tecadm"]:
            return jsonify({"erro": "Sem permissão para editar este jogo. Apenas o criador pode editar seus próprios jogos."}), 403

        data = request.get_json()
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400

        # Validar disciplina se fornecida
        if "subject" in data and not validate_subject(data["subject"]):
            return jsonify({"erro": "Disciplina inválida"}), 400

        # Atualizar campos básicos
        if "url" in data:
            game.url = data["url"]
        if "title" in data:
            game.title = data["title"]
        if "iframeHtml" in data:
            game.iframeHtml = data["iframeHtml"]
        if "thumbnail" in data:
            game.thumbnail = data["thumbnail"]
        if "author" in data:
            game.author = data["author"]
        if "subject" in data:
            game.subject = data["subject"]

        # Atualizar turmas vinculadas (apenas admin/tecadm ou criador)
        if "classes" in data and (user_role in ["admin", "tecadm"] or game.userId == current_user["id"]):
            new_class_ids = data["classes"]
            if isinstance(new_class_ids, list):
                # Validar que todas as turmas existem
                classes = Class.query.filter(Class.id.in_(new_class_ids)).all()
                if len(classes) != len(new_class_ids):
                    return jsonify({"erro": "Uma ou mais turmas não encontradas"}), 404
                
                # Validar permissões para as novas turmas
                if user_role == "tecadm":
                    city_id = current_user.get('tenant_id') or current_user.get('city_id')
                    if city_id:
                        for class_obj in classes:
                            school = School.query.get(class_obj.school_id)
                            if not school or school.city_id != city_id:
                                return jsonify({"erro": f"Você não tem permissão para vincular a turma {class_obj.name}"}), 403
                elif user_role in ["diretor", "coordenador"]:
                    manager = Manager.query.filter_by(user_id=current_user["id"]).first()
                    if manager and manager.school_id:
                        for class_obj in classes:
                            if class_obj.school_id != manager.school_id:
                                return jsonify({"erro": f"Você não tem permissão para vincular a turma {class_obj.name}"}), 403
                
                # Remover associações antigas
                GameClass.query.filter_by(game_id=game.id).delete()
                
                # Criar novas associações
                for class_id in new_class_ids:
                    game_class = GameClass(
                        game_id=game.id,
                        class_id=class_id
                    )
                    db.session.add(game_class)

        db.session.commit()

        # Buscar informações atualizadas das turmas
        linked_classes = [gc.class_ for gc in game.game_classes]

        return jsonify({
            "mensagem": "Jogo atualizado com sucesso!",
            "jogo": {
                "id": game.id,
                "url": game.url,
                "title": game.title,
                "iframeHtml": game.iframeHtml,
                "thumbnail": game.thumbnail,
                "author": game.author,
                "provider": game.provider,
                "subject": game.subject,
                "userId": game.userId,
                "classes": [{"id": c.id, "name": c.name} for c in linked_classes],
                "createdAt": game.createdAt.isoformat() if game.createdAt else None,
                "updatedAt": game.updatedAt.isoformat() if game.updatedAt else None
            }
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados: {str(e)}")
        return jsonify({"erro": "Erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao atualizar jogo: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao atualizar jogo", "detalhes": str(e)}), 500

@bp.route('/<string:game_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def delete_game(game_id):
    try:
        game = Game.query.get(game_id)
        
        if not game:
            return jsonify({"erro": "Jogo não encontrado"}), 404

        # Verificar permissões
        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não autenticado"}), 401

        user_role = current_user.get("role")
        
        # Apenas o criador do jogo ou admin/tecadm podem excluir
        if game.userId != current_user["id"] and user_role not in ["admin", "tecadm"]:
            return jsonify({"erro": "Sem permissão para excluir este jogo. Apenas o criador pode excluir seus próprios jogos."}), 403

        # Deletar jogo (cascade deletará automaticamente os registros em game_classes)
        db.session.delete(game)
        db.session.commit()

        logging.info(f"Jogo {game_id} deletado por usuário {current_user['id']}")
        return jsonify({"mensagem": "Jogo excluído com sucesso!"}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados: {str(e)}")
        return jsonify({"erro": "Erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao excluir jogo: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao excluir jogo", "detalhes": str(e)}), 500 