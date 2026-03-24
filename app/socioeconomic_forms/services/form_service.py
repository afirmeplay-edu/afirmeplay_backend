# -*- coding: utf-8 -*-
"""
Serviço para gerenciamento de formulários socioeconômicos
"""

from app import db
from app.socioeconomic_forms.models import Form, FormQuestion
from app.models.city import City
from app.models.school import School
from app.models.grades import Grade
from app.models.educationStage import EducationStage
from app.models.studentClass import Class
from app.utils.uuid_helpers import ensure_uuid, ensure_uuid_list
from app.socioeconomic_forms.services.template_service import TemplateService
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import JSONB
import logging
from datetime import datetime


class FormService:
    """Serviço para operações CRUD de formulários"""
    
    # Mapeamento de education_stage_id para formType
    EDUCATION_STAGE_TO_FORM_TYPE = {
        # aluno-jovem
        'd1142d12-ed98-46f4-ae78-62c963371464': 'aluno-jovem',  # Educação Infantil
        '614b7d10-b758-42ec-a04e-86f78dc7740a': 'aluno-jovem',  # Anos Iniciais
        '63cb6876-3221-4fa2-89e8-a82ad1733032': 'aluno-jovem',  # EJA períodos 1-5 (frontend envia IDs corretos)
        # aluno-velho
        'c78fcd8e-00a1-485d-8c03-70bcf59e3025': 'aluno-velho',  # Anos Finais
        # EJA períodos 6-9 também usa '63cb6876-3221-4fa2-89e8-a82ad1733032' mas frontend envia IDs corretos
    }
    
    # Mapeamento reverso: formType -> education_stage_ids (para inferir séries do formulário)
    FORM_TYPE_TO_EDUCATION_STAGE_IDS = {
        'aluno-jovem': [
            'd1142d12-ed98-46f4-ae78-62c963371464',  # Educação Infantil
            '614b7d10-b758-42ec-a04e-86f78dc7740a',  # Anos Iniciais
            '63cb6876-3221-4fa2-89e8-a82ad1733032',  # EJA 1-5
        ],
        'aluno-velho': [
            'c78fcd8e-00a1-485d-8c03-70bcf59e3025',  # Anos Finais
            '63cb6876-3221-4fa2-89e8-a82ad1733032',  # EJA
        ],
    }
    
    @staticmethod
    def _get_grade_ids_for_form_type(form_type):
        """
        Retorna todos os IDs de séries (Grade) compatíveis com o tipo de formulário.
        
        Args:
            form_type: aluno-jovem ou aluno-velho
            
        Returns:
            list: Lista de IDs (string) de séries
        """
        stage_ids = FormService.FORM_TYPE_TO_EDUCATION_STAGE_IDS.get(form_type, [])
        if not stage_ids:
            return []
        stage_uuids = [ensure_uuid(s) for s in stage_ids]
        grades = Grade.query.filter(Grade.education_stage_id.in_(stage_uuids)).all()
        return [str(g.id) for g in grades]

    
    @staticmethod
    def _grade_is_compatible_with_form_type(grade, form_type):
        """Verifica se a série é compatível com o tipo de formulário."""
        if not grade or not form_type:
            return False
        stage_id = str(grade.education_stage_id)
        return FormService.EDUCATION_STAGE_TO_FORM_TYPE.get(stage_id) == form_type
    
    @staticmethod
    def _validate_filters(filters):
        """
        Valida filtros hierárquicos.
        Escola é opcional quando o frontend usa selectedSchools.
        
        Args:
            filters: Dicionário com filtros {estado, municipio, escola?, serie, turma}
            
        Raises:
            ValueError: Se validação falhar
        """
        if not filters:
            return
        
        # Validar estado e município se fornecidos
        if filters.get('estado') and filters.get('municipio'):
            municipio = City.query.get(filters['municipio'])
            if not municipio:
                raise ValueError("Município não encontrado")
            if municipio.state != filters['estado']:
                raise ValueError("Município não pertence ao estado informado")
        
        # Validar escola(s) se fornecida(s) - aceita um ID ou lista de IDs
        if filters.get('escola'):
            escola_ids = filters['escola']
            if not isinstance(escola_ids, list):
                escola_ids = [escola_ids]
            for escola_id in escola_ids:
                escola = School.query.get(escola_id)
                if not escola:
                    raise ValueError(f"Escola não encontrada: {escola_id}")
                if filters.get('municipio') and escola.city_id != filters['municipio']:
                    raise ValueError(f"Escola não pertence ao município informado: {escola_id}")
        
        # Validar série se fornecida
        if filters.get('serie'):
            # Converter string para UUID se necessário
            import uuid as uuid_lib
            serie_id = filters['serie']
            try:
                if isinstance(serie_id, str):
                    serie_uuid = uuid_lib.UUID(serie_id)
                else:
                    serie_uuid = serie_id
            except (ValueError, AttributeError):
                serie_uuid = serie_id
            
            grade = Grade.query.get(serie_uuid)
            if not grade:
                raise ValueError("Série não encontrada")
            # Verificar se a série tem turmas na escola (class.school_id é VARCHAR → comparar com string)
            school_id_uuid = ensure_uuid(filters['escola'])
            classes = Class.query.filter_by(
                grade_id=serie_uuid,
                school_id=str(school_id_uuid)
            ).first()
            if not classes:
                raise ValueError("Série não possui turmas na escola informada")
        
        # Validar turma se fornecida
        if filters.get('turma'):
            # Converter turma_id para UUID (Class.id é UUID)
            turma_id_uuid = ensure_uuid(filters['turma'])
            turma = Class.query.get(turma_id_uuid)
            if not turma:
                raise ValueError("Turma não encontrada")
            # turma.school_id (hybrid) retorna string; comparar com string
            escola_id_uuid = ensure_uuid(filters['escola'])
            if turma.school_id != str(escola_id_uuid):
                raise ValueError("Turma não pertence à escola informada")
            if filters.get('serie'):
                # Converter para comparar corretamente
                import uuid as uuid_lib
                serie_id = filters['serie']
                try:
                    if isinstance(serie_id, str):
                        serie_uuid = uuid_lib.UUID(serie_id)
                    else:
                        serie_uuid = serie_id
                except (ValueError, AttributeError):
                    serie_uuid = serie_id
                
                if turma.grade_id != serie_uuid:
                    raise ValueError("Turma não pertence à série informada")
    
    @staticmethod
    def _validate_form_type_vs_grades(form_type, grade_ids):
        """
        Valida se o tipo de formulário corresponde ao education_stage_id das séries
        
        Args:
            form_type: Tipo do formulário (aluno-jovem, aluno-velho, etc.)
            grade_ids: Lista de IDs de séries
            
        Raises:
            ValueError: Se validação falhar
        """
        if not grade_ids or form_type not in ['aluno-jovem', 'aluno-velho']:
            return
        
        # Converter strings para UUID se necessário
        import uuid as uuid_lib
        grade_uuids = []
        for g in grade_ids:
            if isinstance(g, str):
                try:
                    uuid_obj = uuid_lib.UUID(g)
                    grade_uuids.append(uuid_obj)
                except (ValueError, AttributeError):
                    grade_uuids.append(g)
            else:
                grade_uuids.append(g)
        
        grades = Grade.query.filter(Grade.id.in_(grade_uuids)).all()
        if len(grades) != len(grade_ids):
            raise ValueError("Uma ou mais séries não foram encontradas")
        
        for grade in grades:
            education_stage_id = str(grade.education_stage_id)
            expected_form_type = FormService.EDUCATION_STAGE_TO_FORM_TYPE.get(education_stage_id)
            
            # Para EJA, o mesmo education_stage_id pode ser usado para ambos os tipos
            # O frontend envia os IDs corretos das séries, então validamos apenas se o tipo corresponde
            if education_stage_id == '63cb6876-3221-4fa2-89e8-a82ad1733032':
                # EJA - aceitar ambos os tipos pois o frontend já enviou os IDs corretos
                if form_type not in ['aluno-jovem', 'aluno-velho']:
                    raise ValueError(f"A série {grade.name} (EJA) não corresponde ao tipo de formulário {form_type}")
            elif expected_form_type and expected_form_type != form_type:
                raise ValueError(
                    f"A série {grade.name} (education_stage_id: {education_stage_id}) "
                    f"corresponde ao tipo '{expected_form_type}', não '{form_type}'"
                )
    
    @staticmethod
    def _resolve_scope_and_warnings(data):
        """
        Resolve escopo (escolas/séries/turmas) para formulários de aluno:
        - Só selectedSchools: infere séries compatíveis com formType; avisa escolas sem turmas.
        - Só selectedGrades: valida compatibilidade; infere escolas a partir das turmas; avisa séries incompatíveis.
        - Só selectedClasses: valida compatibilidade de cada turma; deriva escolas e séries; avisa turmas incompatíveis.
        
        Modifica data com selectedSchools/selectedGrades/selectedClasses preenchidos e retorna avisos.
        
        Returns:
            tuple: (data, warnings: list of str)
        """
        warnings = []
        selected_schools = data.get('selectedSchools', []) or []
        selected_grades = data.get('selectedGrades', []) or []
        selected_classes = data.get('selectedClasses', []) or []
        form_type = data.get('formType')
        
        # Apenas para aluno-jovem e aluno-velho
        if form_type not in ('aluno-jovem', 'aluno-velho'):
            return data, warnings
        
        has_schools = bool(selected_schools)
        has_grades = bool(selected_grades)
        has_classes = bool(selected_classes)
        
        # Caso 1: só escolas → inferir todas as séries do formType e avisar escolas sem turmas
        if has_schools and not has_grades and not has_classes:
            if not form_type:
                raise ValueError("formType é obrigatório quando apenas selectedSchools é enviado")
            grade_ids = FormService._get_grade_ids_for_form_type(form_type)
            if not grade_ids:
                raise ValueError(f"Nenhuma série cadastrada para o tipo de formulário '{form_type}'")
            data['selectedGrades'] = grade_ids
            selected_grades = grade_ids
            school_ids_uuids = ensure_uuid_list(selected_schools)
            grade_uuids = ensure_uuid_list(grade_ids)
            for school_id in selected_schools:
                sid = ensure_uuid(school_id)
                # class.school_id é VARCHAR; comparar como string para evitar operator does not exist: character varying = uuid
                count = Class.query.filter(
                    Class.school_id == str(sid),
                    Class.grade_id.in_(grade_uuids)
                ).count()
                if count == 0:
                    school = School.query.get(str(sid))
                    name = school.name if school else str(school_id)
                    warnings.append(f"Escola '{name}' não possui turmas compatíveis com o formulário.")
            # Exigir pelo menos uma escola com turmas (class.school_id é VARCHAR → comparar com strings)
            total = Class.query.filter(
                Class.school_id.in_([str(s) for s in school_ids_uuids]),
                Class.grade_id.in_(grade_uuids)
            ).count()
            if total == 0:
                raise ValueError("Nenhuma das escolas selecionadas possui turmas compatíveis com este formulário.")
            return data, warnings
        
        # Caso 2: só séries → validar compatibilidade; inferir escolas a partir das turmas
        if has_grades and not has_schools and not has_classes:
            if not form_type:
                raise ValueError("formType é obrigatório quando apenas selectedGrades é enviado")
            grade_uuids = ensure_uuid_list(selected_grades)
            grades = Grade.query.filter(Grade.id.in_(grade_uuids)).all()
            compatible_ids = []
            for g in grades:
                if FormService._grade_is_compatible_with_form_type(g, form_type):
                    compatible_ids.append(str(g.id))
                else:
                    warnings.append(f"Série '{g.name}' não é compatível com o tipo de formulário '{form_type}' e foi ignorada.")
            if not compatible_ids:
                raise ValueError("Nenhuma série selecionada é compatível com o tipo de formulário.")
            data['selectedGrades'] = compatible_ids
            selected_grades = compatible_ids
            grade_uuids = ensure_uuid_list(compatible_ids)
            classes = Class.query.filter(Class.grade_id.in_(grade_uuids)).all()
            school_ids = list({str(c.school_id) for c in classes})
            if not school_ids:
                raise ValueError("Nenhuma turma encontrada para as séries compatíveis.")
            data['selectedSchools'] = school_ids
            selected_schools = school_ids
            return data, warnings
        
        # Caso 3: só turmas → validar compatibilidade; derivar escolas e séries
        if has_classes and not has_schools and not has_grades:
            class_ids_uuids = ensure_uuid_list(selected_classes)
            classes = Class.query.filter(Class.id.in_(class_ids_uuids)).all()
            if len(classes) != len(selected_classes):
                found = {str(c.id) for c in classes}
                missing = [c for c in selected_classes if str(c) not in found]
                raise ValueError(f"Turma(s) não encontrada(s): {missing}")
            # Se formType não foi enviado, inferir do primeiro tipo encontrado
            scope_form_type = form_type
            valid_classes = []
            for c in classes:
                grade = Grade.query.get(c.grade_id)
                if not grade:
                    warnings.append(f"Turma {c.id} possui série inválida e foi ignorada.")
                    continue
                type_for_grade = FormService.EDUCATION_STAGE_TO_FORM_TYPE.get(str(grade.education_stage_id))
                if not type_for_grade or type_for_grade not in ('aluno-jovem', 'aluno-velho'):
                    warnings.append(f"Turma (série: {grade.name}) não é compatível com formulário de aluno e foi ignorada.")
                    continue
                if not scope_form_type:
                    scope_form_type = type_for_grade
                if type_for_grade != scope_form_type:
                    warnings.append(f"Turma (série: {grade.name}) não é compatível com o tipo de formulário '{scope_form_type}' e foi ignorada.")
                    continue
                valid_classes.append(c)
            if not valid_classes:
                raise ValueError("Nenhuma turma selecionada é compatível com o tipo de formulário.")
            if not data.get('formType') and scope_form_type:
                data['formType'] = scope_form_type
            school_ids = list({str(c.school_id) for c in valid_classes})
            grade_ids = list({str(c.grade_id) for c in valid_classes})
            data['selectedSchools'] = school_ids
            data['selectedGrades'] = grade_ids
            data['selectedClasses'] = [str(c.id) for c in valid_classes]
            return data, warnings
        
        # Caso 4: combinação (schools+grades, schools+classes, etc.) → validar compatibilidade e avisar
        if has_grades:
            grade_uuids = ensure_uuid_list(selected_grades)
            grades = Grade.query.filter(Grade.id.in_(grade_uuids)).all()
            for g in grades:
                if form_type and not FormService._grade_is_compatible_with_form_type(g, form_type):
                    warnings.append(f"Série '{g.name}' não é compatível com o tipo de formulário '{form_type}'.")
        if has_classes:
            class_ids_uuids = ensure_uuid_list(selected_classes)
            classes = Class.query.filter(Class.id.in_(class_ids_uuids)).all()
            for c in classes:
                grade = Grade.query.get(c.grade_id) if c else None
                if grade and form_type and not FormService._grade_is_compatible_with_form_type(grade, form_type):
                    warnings.append(f"Turma (série: {grade.name}) não é compatível com o tipo de formulário.")
        return data, warnings
    
    @staticmethod
    def _validate_selections(selected_schools, selected_grades, selected_classes):
        """
        Valida seleções de escolas, séries e turmas (após resolução de escopo).
        
        Args:
            selected_schools: Lista de IDs de escolas
            selected_grades: Lista de IDs de séries
            selected_classes: Lista de IDs de turmas
            
        Raises:
            ValueError: Se validação falhar
        """
        if selected_schools:
            # school.id é VARCHAR → comparar com strings para evitar operator does not exist: character varying = uuid
            school_ids_uuids = ensure_uuid_list(selected_schools)
            school_ids_str = [str(s) for s in school_ids_uuids]
            schools = School.query.filter(School.id.in_(school_ids_str)).all()
            if len(schools) != len(selected_schools):
                raise ValueError("Uma ou mais escolas não foram encontradas")
        
        if selected_grades:
            if selected_schools and not selected_classes:
                # Quando temos escolas e séries (sem turmas específicas), verificar se há turmas
                grade_uuids = ensure_uuid_list(selected_grades)
                school_ids_uuids = ensure_uuid_list(selected_schools)
                # class.school_id é VARCHAR → comparar com strings
                classes = Class.query.filter(
                    Class.grade_id.in_(grade_uuids),
                    Class.school_id.in_([str(s) for s in school_ids_uuids])
                ).distinct().all()
                if not classes:
                    raise ValueError("Nenhuma turma encontrada para as séries e escolas selecionadas")
            else:
                grade_uuids = ensure_uuid_list(selected_grades)
                grades = Grade.query.filter(Grade.id.in_(grade_uuids)).all()
                if len(grades) != len(selected_grades):
                    raise ValueError("Uma ou mais séries não foram encontradas")
        
        if selected_classes:
            class_ids_uuids = ensure_uuid_list(selected_classes)
            classes = Class.query.filter(Class.id.in_(class_ids_uuids)).all()
            if len(classes) != len(selected_classes):
                raise ValueError("Uma ou mais turmas não foram encontradas")
            if selected_grades:
                grade_set = {str(g) for g in selected_grades}
                for class_obj in classes:
                    if str(class_obj.grade_id) not in grade_set:
                        raise ValueError(f"Turma {class_obj.id} não pertence às séries selecionadas")
    
    @staticmethod
    def _validate_grades_exist(grade_ids):
        """
        Valida que todas as séries fornecidas existem no banco de dados
        
        Args:
            grade_ids: Lista de IDs de séries
            
        Returns:
            list: Lista de objetos Grade encontrados
            
        Raises:
            ValueError: Se alguma série não for encontrada
        """
        if not grade_ids:
            return []
        
        # Converter para UUID se necessário
        import uuid as uuid_lib
        grade_uuids = []
        for g in grade_ids:
            if isinstance(g, str):
                try:
                    uuid_obj = uuid_lib.UUID(g)
                    grade_uuids.append(uuid_obj)
                except (ValueError, AttributeError):
                    grade_uuids.append(g)
            else:
                grade_uuids.append(g)
        
        # Buscar todas as séries
        grades = Grade.query.filter(Grade.id.in_(grade_uuids)).all()
        
        # Verificar se todas foram encontradas
        if len(grades) != len(grade_ids):
            found_ids = {str(g.id) for g in grades}
            provided_ids = {str(g) for g in grade_ids}
            missing_ids = provided_ids - found_ids
            raise ValueError(f"Série(s) não encontrada(s) no sistema: {', '.join(missing_ids)}")
        
        return grades
    
    @staticmethod
    def _group_grades_by_form_type(grades):
        """
        Agrupa séries por tipo de formulário baseado no education_stage_id
        
        Args:
            grades: Lista de objetos Grade
            
        Returns:
            dict: {form_type: [grade_ids]}
        """
        groups = {}
        
        for grade in grades:
            education_stage_id = str(grade.education_stage_id)
            form_type = FormService.EDUCATION_STAGE_TO_FORM_TYPE.get(education_stage_id)
            
            if not form_type:
                # Se não encontrar mapeamento, tentar inferir
                logging.warning(f"Education stage {education_stage_id} não mapeado para form_type")
                continue
            
            if form_type not in groups:
                groups[form_type] = []
            
            groups[form_type].append(str(grade.id))
        
        return groups
    
    @staticmethod
    def _count_previous_applications(form_type, school_id):
        """
        Conta quantas aplicações anteriores deste tipo de formulário na escola
        
        Args:
            form_type: Tipo do formulário (aluno-jovem, aluno-velho, etc.)
            school_id: ID da escola
            
        Returns:
            int: Número de aplicações anteriores + 1 (próximo número)
        """
        if not school_id:
            # Se não tiver escola, retornar 1
            return 1
        
        # Contar formulários do mesmo tipo nesta escola
        # forms.selected_schools é JSON; usar cast para JSONB e @> para evitar operator does not exist: json ~~ text
        count = Form.query.filter(
            Form.form_type == form_type,
            Form.selected_schools.isnot(None)
        ).filter(
            cast(Form.selected_schools, JSONB).op('@>')([str(school_id)])
        ).count()
        
        return count + 1
    
    @staticmethod
    def _get_education_stage_name(grades):
        """
        Obtém o nome do education stage das séries
        Retorna o nome do primeiro education stage encontrado
        
        Args:
            grades: Lista de objetos Grade
            
        Returns:
            str: Nome do education stage
        """
        if not grades:
            return "Questionário"
        
        first_grade = grades[0]
        education_stage = EducationStage.query.get(first_grade.education_stage_id)
        
        if education_stage:
            return education_stage.name
        
        return "Questionário"
    
    @staticmethod
    def _generate_title(form_type, school_id, grade_ids, application_number):
        """
        Gera título automático para o formulário
        
        Formato: "{N}° Questionário Socioeconômico - {Education Stage} - {Escola}"
        Exemplo: "3° Questionário Socioeconômico - Educação Infantil - Escola XYZ"
        
        Args:
            form_type: Tipo do formulário
            school_id: ID da escola
            grade_ids: Lista de IDs de séries
            application_number: Número da aplicação (1, 2, 3...)
            
        Returns:
            str: Título gerado
        """
        ordinal = f"{application_number}°"
        base_title = f"{ordinal} Questionário Socioeconômico"
        
        # Buscar nome da escola
        school_name = "Escola"
        if school_id:
            school = School.query.get(school_id)
            if school:
                school_name = school.name
        
        # Buscar nome do education stage
        stage_name = None
        if grade_ids and len(grade_ids) > 0:
            # Pegar primeira série para determinar o education stage
            import uuid as uuid_lib
            try:
                grade_id = uuid_lib.UUID(grade_ids[0]) if isinstance(grade_ids[0], str) else grade_ids[0]
                grade = Grade.query.get(grade_id)
                if grade:
                    education_stage = EducationStage.query.get(grade.education_stage_id)
                    if education_stage:
                        stage_name = education_stage.name
            except (ValueError, AttributeError):
                pass
        
        # Montar título
        if stage_name:
            return f"{base_title} - {stage_name} - {school_name}"
        else:
            return f"{base_title} - {school_name}"
    
    @staticmethod
    def create_form(data, created_by):
        """
        Cria formulário(s) automaticamente baseado nas séries selecionadas
        
        Se as séries pertencem a diferentes education_stages (aluno-jovem vs aluno-velho),
        cria múltiplos formulários automaticamente, um para cada tipo.
        
        Títulos são gerados automaticamente no formato:
        "{N}° Questionário Socioeconômico - {Education Stage} - {Escola}"
        
        Args:
            data: Dicionário com dados do formulário
                - selectedGrades: Lista de IDs de séries (obrigatório para aluno)
                - selectedSchools: Lista de IDs de escolas
                - selectedClasses: Lista de IDs de turmas
                - formType: Tipo (opcional, será ignorado se houver múltiplas stages)
                - deadline: Data limite
                - isActive: Status ativo
                - questions: Perguntas (opcional, carrega do template se não fornecido)
            created_by: ID do usuário criador
            
        Returns:
            list ou Form: Lista de formulários criados (se múltiplos) ou Form único
        """
        try:
            # Validar filtros se fornecidos
            filters = data.get('filters')
            if filters:
                FormService._validate_filters(filters)
            
            # Resolver escopo para aluno (inferir grades/schools, validar compatibilidade, coletar avisos)
            data, scope_warnings = FormService._resolve_scope_and_warnings(data)
            
            selected_schools = data.get('selectedSchools', []) or []
            selected_grades = data.get('selectedGrades', []) or []
            selected_classes = data.get('selectedClasses', []) or []
            form_type = data.get('formType')
            
            # Para formulários de aluno, é obrigatório ter ao menos uma seleção (escolas, séries ou turmas)
            if form_type in ['aluno-jovem', 'aluno-velho']:
                if not filters and not selected_schools and not selected_grades and not selected_classes:
                    raise ValueError("Informe selectedSchools, selectedGrades ou selectedClasses para formulários de alunos")
            
            # Validar seleções básicas (após resolução de escopo)
            if selected_schools or selected_grades or selected_classes:
                FormService._validate_selections(selected_schools, selected_grades, selected_classes)
            
            # 1. Validar que todas as séries existem no banco
            grades = FormService._validate_grades_exist(selected_grades) if selected_grades else []
            
            # 2. Agrupar séries por tipo de formulário
            if grades:
                groups = FormService._group_grades_by_form_type(grades)
                
                # Se não há grupos, significa que nenhuma série foi mapeada
                if not groups:
                    raise ValueError("Nenhuma série válida foi encontrada para criar formulário")
                
                # Se há múltiplos grupos, criar múltiplos formulários
                if len(groups) > 1:
                    logging.info(f"Criando {len(groups)} formulários para diferentes education stages")
                    created_forms = []
                    
                    for form_type_detected, grade_ids_for_type in groups.items():
                        # Criar formulário para cada grupo
                        form_data_copy = data.copy()
                        form_data_copy['formType'] = form_type_detected
                        form_data_copy['selectedGrades'] = grade_ids_for_type
                        
                        form = FormService._create_single_form(form_data_copy, created_by)
                        created_forms.append(form)
                    
                    db.session.commit()
                    return created_forms, scope_warnings
                
                # Se há apenas um grupo, usar o tipo detectado
                form_type = list(groups.keys())[0]
                data['formType'] = form_type
            
            # 3. Criar formulário único
            form = FormService._create_single_form(data, created_by)
            db.session.commit()
            return form, scope_warnings
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao criar formulário: {str(e)}")
            raise
    
    @staticmethod
    def _create_single_form(data, created_by):
        """
        Cria um único formulário (método interno)
        
        Args:
            data: Dicionário com dados do formulário
            created_by: ID do usuário criador
            
        Returns:
            Form: Formulário criado (ainda não commitado)
        """
        form_type = data['formType']
        selected_schools = data.get('selectedSchools', [])
        selected_grades = data.get('selectedGrades', [])
        selected_classes = data.get('selectedClasses', [])
        
        # Gerar título automático
        school_id = selected_schools[0] if selected_schools else None
        application_number = FormService._count_previous_applications(form_type, school_id)
        title = FormService._generate_title(form_type, school_id, selected_grades, application_number)
        
        # Carregar perguntas do template se não fornecidas
        questions = data.get('questions')
        if not questions:
            template = TemplateService.load_template(form_type)
            if template:
                questions = template['questions']
            else:
                raise ValueError(f"Template para '{form_type}' não encontrado e perguntas não fornecidas")
        
        # Validar perguntas
        if questions:
            for q in questions:
                if not q.get('id') or not q.get('text') or not q.get('type'):
                    raise ValueError("Perguntas devem ter id, text e type")
        
        # Criar formulário
        form = Form(
            title=title,
            description=data.get('description'),
            form_type=form_type,
            target_groups=data.get('targetGroups', []),
            selected_schools=selected_schools if selected_schools else None,
            selected_grades=selected_grades if selected_grades else None,
            selected_classes=selected_classes if selected_classes else None,
            selected_tecadmin_users=data.get('selectedTecAdminUsers'),
            filters=data.get('filters') if data.get('filters') else None,
            is_active=data.get('isActive', True),
            deadline=datetime.fromisoformat(data['deadline'].replace('Z', '+00:00')) if data.get('deadline') else None,
            instructions=data.get('instructions'),
            created_by=created_by
        )
        
        db.session.add(form)
        db.session.flush()  # Para obter o ID do formulário
        
        # Criar questões
        if questions:
            for q_data in questions:
                question = FormQuestion(
                    form_id=form.id,
                    question_id=q_data['id'],
                    text=q_data['text'],
                    type=q_data['type'],
                    options=q_data.get('options'),
                    sub_questions=q_data.get('subQuestions'),
                    min_value=q_data.get('min'),
                    max_value=q_data.get('max'),
                    option_id=q_data.get('optionId'),
                    option_text=q_data.get('optionText'),
                    required=q_data.get('required', False),
                    question_order=q_data.get('order', 0),
                    depends_on=q_data.get('dependsOn')
                )
                db.session.add(question)
        
        return form
    
    @staticmethod
    def get_form(form_id, include_questions=False, include_statistics=False):
        """
        Obtém um formulário por ID
        
        Args:
            form_id: ID do formulário
            include_questions: Se deve incluir questões
            include_statistics: Se deve incluir estatísticas
            
        Returns:
            Form ou None
        """
        try:
            form = Form.query.get(form_id)
            return form
        except SQLAlchemyError as e:
            logging.error(f"Erro ao buscar formulário: {str(e)}")
            raise
    
    @staticmethod
    def list_forms(form_type=None, is_active=None, selected_schools=None, 
                    selected_grades=None, selected_classes=None, page=1, limit=20, created_by=None):
        """
        Lista formulários com paginação e filtros de escopo.
        Se created_by for informado, retorna apenas formulários criados por esse usuário.
        
        Args:
            form_type: Filtrar por tipo (opcional)
            is_active: Filtrar por status ativo (opcional)
            selected_schools: Lista de IDs de escolas para filtrar (opcional)
            selected_grades: Lista de IDs de séries para filtrar (opcional)
            selected_classes: Lista de IDs de turmas para filtrar (opcional)
            page: Número da página
            limit: Itens por página
            created_by: ID do usuário criador (opcional) — se informado, só retorna formulários dele
            
        Returns:
            dict: Dicionário com 'data' e 'pagination'
        """
        try:
            query = Form.query
            
            # Filtro por criador (formulários que o usuário criou)
            if created_by:
                query = query.filter(Form.created_by == created_by)
            
            # Filtro por tipo
            if form_type:
                query = query.filter(Form.form_type == form_type)
            
            # Filtro por status ativo
            if is_active is not None:
                query = query.filter(Form.is_active == is_active)
            
            # Filtro por escolas aplicadas (colunas JSON: cast para JSONB e @> para evitar json ~~ text)
            if selected_schools and len(selected_schools) > 0:
                filters = []
                for school_id in selected_schools:
                    filters.append(cast(Form.selected_schools, JSONB).op('@>')([str(school_id)]))
                if filters:
                    from sqlalchemy import or_
                    query = query.filter(or_(*filters))
            
            # Filtro por séries aplicadas
            if selected_grades and len(selected_grades) > 0:
                filters = []
                for grade_id in selected_grades:
                    filters.append(cast(Form.selected_grades, JSONB).op('@>')([str(grade_id)]))
                if filters:
                    from sqlalchemy import or_
                    query = query.filter(or_(*filters))
            
            # Filtro por turmas aplicadas
            if selected_classes and len(selected_classes) > 0:
                filters = []
                for class_id in selected_classes:
                    filters.append(cast(Form.selected_classes, JSONB).op('@>')([str(class_id)]))
                
                if filters:
                    from sqlalchemy import or_
                    query = query.filter(or_(*filters))
            
            # Ordenar por data de criação (mais recentes primeiro)
            query = query.order_by(Form.created_at.desc())
            
            # Paginação
            pagination = query.paginate(page=page, per_page=limit, error_out=False)
            
            # Calcular estatísticas básicas para cada formulário
            forms_data = []
            for form in pagination.items:
                form_dict = form.to_dict(include_questions=False, include_statistics=True)
                forms_data.append(form_dict)
            
            return {
                'data': forms_data,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': pagination.total,
                    'totalPages': pagination.pages
                }
            }
            
        except SQLAlchemyError as e:
            logging.error(f"Erro ao listar formulários: {str(e)}")
            raise
    
    @staticmethod
    def update_form(form_id, data):
        """
        Atualiza um formulário
        
        Args:
            form_id: ID do formulário
            data: Dicionário com dados para atualizar
            
        Returns:
            Form: Objeto do formulário atualizado
        """
        try:
            form = Form.query.get(form_id)
            if not form:
                return None
            
            # Atualizar campos básicos
            if 'title' in data:
                form.title = data['title']
            if 'description' in data:
                form.description = data.get('description')
            if 'formType' in data:
                form.form_type = data['formType']
            if 'targetGroups' in data:
                form.target_groups = data['targetGroups']
            if 'selectedSchools' in data:
                form.selected_schools = data['selectedSchools']
            if 'selectedTecAdminUsers' in data:
                form.selected_tecadmin_users = data['selectedTecAdminUsers']
            if 'isActive' in data:
                form.is_active = data['isActive']
            if 'deadline' in data:
                form.deadline = datetime.fromisoformat(data['deadline'].replace('Z', '+00:00')) if data.get('deadline') else None
            if 'instructions' in data:
                form.instructions = data.get('instructions')
            
            # Atualizar questões se fornecidas
            if 'questions' in data:
                # Deletar questões antigas
                FormQuestion.query.filter_by(form_id=form_id).delete()
                
                # Criar novas questões
                for q_data in data['questions']:
                    question = FormQuestion(
                        form_id=form.id,
                        question_id=q_data['id'],
                        text=q_data['text'],
                        type=q_data['type'],
                        options=q_data.get('options'),
                        sub_questions=q_data.get('subQuestions'),
                        min_value=q_data.get('min'),
                        max_value=q_data.get('max'),
                        option_id=q_data.get('optionId'),
                        option_text=q_data.get('optionText'),
                        required=q_data.get('required', False),
                        question_order=q_data.get('order', 0),
                        depends_on=q_data.get('dependsOn')
                    )
                    db.session.add(question)
            
            db.session.commit()
            return form
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao atualizar formulário: {str(e)}")
            raise
    
    @staticmethod
    def delete_form(form_id):
        """
        Deleta um formulário
        
        Args:
            form_id: ID do formulário
            
        Returns:
            bool: True se deletado com sucesso
        """
        try:
            form = Form.query.get(form_id)
            if not form:
                return False
            
            db.session.delete(form)
            db.session.commit()
            return True
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao deletar formulário: {str(e)}")
            raise
    
    @staticmethod
    def duplicate_form(form_id, new_title=None, is_active=False):
        """
        Duplica um formulário
        
        Args:
            form_id: ID do formulário a duplicar
            new_title: Título para o novo formulário (opcional)
            is_active: Se o novo formulário deve estar ativo
            
        Returns:
            Form: Objeto do formulário duplicado
        """
        try:
            original_form = Form.query.get(form_id)
            if not original_form:
                return None
            
            # Criar novo formulário
            new_form = Form(
                title=new_title or f"Cópia de {original_form.title}",
                description=original_form.description,
                form_type=original_form.form_type,
                target_groups=original_form.target_groups,
                selected_schools=original_form.selected_schools,
                selected_grades=original_form.selected_grades,
                selected_tecadmin_users=original_form.selected_tecadmin_users,
                is_active=is_active,
                deadline=original_form.deadline,
                instructions=original_form.instructions,
                created_by=original_form.created_by
            )
            
            db.session.add(new_form)
            db.session.flush()
            
            # Duplicar questões
            for original_question in original_form.questions:
                new_question = FormQuestion(
                    form_id=new_form.id,
                    question_id=original_question.question_id,
                    text=original_question.text,
                    type=original_question.type,
                    options=original_question.options,
                    sub_questions=original_question.sub_questions,
                    min_value=original_question.min_value,
                    max_value=original_question.max_value,
                    option_id=original_question.option_id,
                    option_text=original_question.option_text,
                    required=original_question.required,
                    question_order=original_question.question_order,
                    depends_on=original_question.depends_on
                )
                db.session.add(new_question)
            
            db.session.commit()
            return new_form
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao duplicar formulário: {str(e)}")
            raise

