# -*- coding: utf-8 -*-
"""
Gerador Hierárquico de Cartões Resposta
Suporta geração por Escolas → Séries → Turmas
com separação de tasks por "pai"
"""

import logging
from typing import Dict, List, Optional, Tuple
from app import db
from app.models.studentClass import Class
from app.models.school import School
from app.models.grades import Grade
from app.models.city import City
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

logger = logging.getLogger(__name__)


class HierarchicalAnswerSheetGenerator:
    """
    Gerencia geração hierárquica de cartões resposta
    Separa tarefas por "pai" para evitar overload
    """

    def __init__(self):
        self.logger = logger

    def determine_generation_scope(
        self,
        state: str,
        city: str,
        school_id: Optional[str] = None,
        grade_id: Optional[str] = None,
        class_id: Optional[str] = None,
        user: Optional[Dict] = None
    ) -> Dict:
        """
        Determina o escopo de geração baseado nos filtros
        ⚠️ USADA APENAS PARA VALIDAR GERAÇÃO (não para filtros em cascata)
        
        Args:
            state: Estado (obrigatório)
            city: Cidade (obrigatório)
            school_id: ID da escola (opcional)
            grade_id: ID da série (opcional)
            class_id: ID da turma (opcional)
            user: Usuário logado (para validar permissões)
        
        Returns:
            Dict com:
            {
                "scope_type": "class|grade|school|city",
                "parent_grouping": "none|serie|school",
                "city_id": "uuid",
                "city_data": City object,
                "schools": [School objects],
                "classes": [Class objects],
                "validation_errors": [erros se houver]
            }
        """
        errors = []

        try:
            # 1. Validar filtros obrigatórios
            if not state or state.lower() == 'all':
                errors.append("Estado é obrigatório e não pode ser 'all'")
                return {"validation_errors": errors}

            if not city or city.lower() == 'all':
                errors.append("Cidade é obrigatória e não pode ser 'all'")
                return {"validation_errors": errors}

            # 2. Buscar cidade
            city_obj = City.query.get(city)
            if not city_obj:
                city_obj = City.query.filter(City.name.ilike(f"%{city}%")).first()

            if not city_obj:
                errors.append(f"Cidade '{city}' não encontrada")
                return {"validation_errors": errors}

            city_id = city_obj.id

            # 3. Validar estado
            if not city_obj.state.lower().startswith(state.lower()):
                errors.append(f"Cidade '{city}' não pertence ao estado '{state}'")
                return {"validation_errors": errors}

            # 4. Determinar scope_type e parent_grouping
            scope_type = "class"  # default
            parent_grouping = "none"  # default
            schools_list = []
            classes_list = []

            if class_id and class_id.lower() != 'all':
                # Caso 1: Turma específica
                scope_type = "class"
                parent_grouping = "none"
                
                class_obj = Class.query.get(class_id)
                if not class_obj:
                    class_obj = Class.query.filter(Class.name.ilike(f"%{class_id}%")).first()

                if not class_obj:
                    errors.append(f"Turma '{class_id}' não encontrada")
                    return {"validation_errors": errors}

                classes_list = [class_obj]
                schools_list = [class_obj.school] if class_obj.school else []

            elif grade_id and grade_id.lower() != 'all':
                # Caso 2: Série específica
                scope_type = "grade"
                parent_grouping = "school"  # Agrupa por escola
                
                grade_obj = Grade.query.get(grade_id)
                if not grade_obj:
                    grade_obj = Grade.query.filter(Grade.name.ilike(f"%{grade_id}%")).first()

                if not grade_obj:
                    errors.append(f"Série '{grade_id}' não encontrada")
                    return {"validation_errors": errors}

                # Buscar todas as turmas dessa série na cidade
                classes_list = Class.query.filter(
                    Class.grade_id == grade_obj.id,
                    Class.school_id.in_(
                        db.session.query(School.id).filter(School.city_id == city_id)
                    )
                ).all()

                # Extrair escolas únicas
                schools_set = set()
                for cls in classes_list:
                    if cls.school:
                        schools_set.add(cls.school)
                schools_list = list(schools_set)

            elif school_id and school_id.lower() != 'all':
                # Caso 3: Escola específica
                scope_type = "school"
                parent_grouping = "serie"  # Agrupa por série
                
                school_obj = School.query.filter(School.id == school_id).first()
                if not school_obj:
                    school_obj = School.query.filter(School.name.ilike(f"%{school_id}%")).first()

                if not school_obj:
                    errors.append(f"Escola '{school_id}' não encontrada")
                    return {"validation_errors": errors}

                if school_obj.city_id != city_id:
                    errors.append(f"Escola '{school_id}' não pertence a '{city}'")
                    return {"validation_errors": errors}

                schools_list = [school_obj]

                # Buscar todas as turmas da escola
                classes_list = Class.query.filter(
                    Class.school_id == school_obj.id
                ).all()

            else:
                # Caso 4: Apenas cidade
                scope_type = "city"
                parent_grouping = "school"  # Agrupa por escola

                # Buscar todas as escolas da cidade
                schools_list = School.query.filter(School.city_id == city_id).all()

                # Buscar todas as turmas da cidade
                classes_list = Class.query.filter(
                    Class.school_id.in_(db.session.query(School.id).filter(School.city_id == city_id))
                ).all()

            # 5. Aplicar permissões do usuário
            if user:
                from app.permissions.utils import get_user_scope
                scope_info_perms = get_user_scope(user)

                # Filtrar por permissões
                if scope_info_perms.get('scope') == 'municipio':
                    # Tecadm: apenas seu município
                    if scope_info_perms.get('city_id') != city_id:
                        errors.append("Acesso negado a este município")
                        return {"validation_errors": errors}

                elif scope_info_perms.get('scope') == 'escola':
                    # Diretor/Coordenador ou Professor: apenas sua escola
                    school_id_perm = scope_info_perms.get('school_id')
                    school_ids_perm = scope_info_perms.get('school_ids', [])
                    
                    if school_id_perm:
                        # Diretor/Coordenador: apenas sua escola
                        schools_list = [s for s in schools_list if s.id == school_id_perm]
                        classes_list = [c for c in classes_list if c.school_id == school_id_perm]
                    elif school_ids_perm:
                        # Professor: suas escolas
                        schools_list = [s for s in schools_list if s.id in school_ids_perm]
                        classes_list = [c for c in classes_list if c.school_id in school_ids_perm]
                    else:
                        errors.append("Você não tem escola vinculada")
                        return {"validation_errors": errors}

            if not classes_list:
                errors.append("Nenhuma turma encontrada com os filtros especificados")
                return {"validation_errors": errors}

            logger.info(
                f"Escopo determinado: type={scope_type}, "
                f"turmas={len(classes_list)}, escolas={len(schools_list)}"
            )

            return {
                "validation_errors": [],
                "scope_type": scope_type,
                "city_id": city_id,
                "city_data": city_obj,
                "schools": schools_list,
                "classes": classes_list,
                "total_classes": len(classes_list),
                "total_schools": len(schools_list),
                "state": state,
                "city": city,
                "school_id": school_id,
                "grade_id": grade_id,
                "class_id": class_id
            }

        except Exception as e:
            logger.error(f"Erro ao determinar escopo: {str(e)}", exc_info=True)
            errors.append(f"Erro ao determinar escopo: {str(e)}")
            return {"validation_errors": errors}

    def distribute_tasks_by_parent(self, scope_info: Dict) -> List[Dict]:
        """
        Distribui classes em tasks separadas por "pai"
        
        Args:
            scope_info: Resultado de determine_generation_scope()
        
        Returns:
            Lista de distribuições:
            [
              {
                'parent_id': 'uuid-serie-6',
                'parent_type': 'serie',
                'parent_name': '6º Ano',
                'classes_ids': ['uuid-c1', 'uuid-c2', ...],
                'total_classes': 10,
                'total_students': 250
              },
              ...
            ]
        """
        try:
            classes_list = scope_info.get('classes', [])
            parent_grouping = scope_info.get('parent_grouping', 'none')
            scope_type = scope_info.get('scope_type', 'class')

            distribution = []

            if scope_type == 'class':
                # 1 task por turma
                for cls in classes_list:
                    student_count = len(cls.students) if cls.students else 0
                    distribution.append({
                        'parent_id': str(cls.id),
                        'parent_type': 'class',
                        'parent_name': cls.name,
                        'classes_ids': [str(cls.id)],
                        'total_classes': 1,
                        'total_students': student_count
                    })

            elif parent_grouping == 'serie':
                # Agrupar por série
                classes_by_grade = {}
                for cls in classes_list:
                    grade_id = str(cls.grade_id) if cls.grade_id else 'sem_serie'
                    if grade_id not in classes_by_grade:
                        classes_by_grade[grade_id] = {
                            'grade_name': cls.grade.name if cls.grade else 'Sem série',
                            'classes': []
                        }
                    classes_by_grade[grade_id]['classes'].append(cls)

                for grade_id, grade_data in classes_by_grade.items():
                    class_ids = [str(c.id) for c in grade_data['classes']]
                    total_students = sum(len(c.students) if c.students else 0 for c in grade_data['classes'])
                    
                    distribution.append({
                        'parent_id': grade_id,
                        'parent_type': 'serie',
                        'parent_name': grade_data['grade_name'],
                        'classes_ids': class_ids,
                        'total_classes': len(grade_data['classes']),
                        'total_students': total_students
                    })

            elif parent_grouping == 'school':
                # Agrupar por escola
                classes_by_school = {}
                for cls in classes_list:
                    school_id = str(cls.school_id) if cls.school_id else 'sem_escola'
                    if school_id not in classes_by_school:
                        classes_by_school[school_id] = {
                            'school_name': cls.school.name if cls.school else 'Sem escola',
                            'classes': []
                        }
                    classes_by_school[school_id]['classes'].append(cls)

                for school_id, school_data in classes_by_school.items():
                    class_ids = [str(c.id) for c in school_data['classes']]
                    total_students = sum(len(c.students) if c.students else 0 for c in school_data['classes'])
                    
                    distribution.append({
                        'parent_id': school_id,
                        'parent_type': 'school',
                        'parent_name': school_data['school_name'],
                        'classes_ids': class_ids,
                        'total_classes': len(school_data['classes']),
                        'total_students': total_students
                    })

            logger.info(f"Distribuição de tasks: {len(distribution)} tarefas geradas")
            return distribution

        except Exception as e:
            logger.error(f"Erro ao distribuir tasks: {str(e)}", exc_info=True)
            return []
