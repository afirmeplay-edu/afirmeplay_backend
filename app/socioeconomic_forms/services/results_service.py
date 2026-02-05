# -*- coding: utf-8 -*-
"""
Serviço para cálculo de resultados de formulários socioeconômicos.
Contém a lógica de negócio para gerar relatórios de índices e perfis.
"""

from app import db
from app.socioeconomic_forms.models import Form, FormResponse, FormQuestion
from app.models import User, Student, School, Grade, Class, City
from sqlalchemy.exc import SQLAlchemyError
from collections import defaultdict
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Constantes para education_stage_id
EDUCATION_STAGE_ANOS_INICIAIS = '614b7d10-b758-42ec-a04e-86f78dc7740a'  # 1º ao 5º ano
EDUCATION_STAGE_ANOS_FINAIS = 'c78fcd8e-00a1-485d-8c03-70bcf59e3025'  # 6º ao 9º ano


class ResultsService:
    """Serviço para cálculo de resultados de formulários socioeconômicos"""
    
    @staticmethod
    def calculate_general_indices(form_id, filters=None, page=1, limit=20):
        """
        Calcula os 4 índices gerais com porcentagens.
        
        Args:
            form_id: ID do formulário
            filters: Filtros hierárquicos {state, municipio, escola, serie, turma}
            page: Página para paginação dos alunos
            limit: Limite de alunos por página
            
        Returns:
            dict: Relatório com os 4 índices
        """
        try:
            form = Form.query.get(form_id)
            if not form:
                raise ValueError("Formulário não encontrado")
            
            # Buscar todas as respostas completas com JOINs
            query = ResultsService._build_base_query(form_id, filters)
            results = query.all()
            
            total_respostas = len(results)
            
            if total_respostas == 0:
                return ResultsService._empty_indices_response(form, filters)
            
            # Calcular cada índice
            indices = {
                'distorcaoIdadeSerie': ResultsService._calculate_distorcao_idade_serie(results, page, limit),
                'historicoReprovacao': ResultsService._calculate_historico_reprovacao(results, page, limit),
                'semAcessoInternet': ResultsService._calculate_sem_acesso_internet(results, page, limit),
                'baixoEngajamentoFamiliar': ResultsService._calculate_baixo_engajamento(results, page, limit)
            }
            
            # Preparar resposta
            return {
                'formId': form.id,
                'formTitle': form.title,
                'totalRespostas': total_respostas,
                'filtros': ResultsService._format_filters_info(filters, results),
                'indices': indices,
                'geradoEm': datetime.utcnow().isoformat()
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Erro ao calcular índices: {str(e)}")
            raise
    
    @staticmethod
    def calculate_profiles_report(form_id, filters=None):
        """
        Calcula os 4 perfis com contagens (não porcentagens).
        
        Args:
            form_id: ID do formulário
            filters: Filtros hierárquicos
            
        Returns:
            dict: Relatório com os 4 perfis
        """
        try:
            form = Form.query.get(form_id)
            if not form:
                raise ValueError("Formulário não encontrado")
            
            # Buscar todas as respostas completas
            query = ResultsService._build_base_query(form_id, filters)
            results = query.all()
            
            total_respostas = len(results)
            
            if total_respostas == 0:
                return ResultsService._empty_profiles_response(form, filters)
            
            # Detectar education_stage predominante para determinar questões do perfil 4
            education_stages = [r.Grade.education_stage_id for r in results if r.Grade]
            perfil_ambiente_questoes = ResultsService._determine_ambiente_escolar_questions(education_stages)
            
            # Definir mapeamento de perfis
            profile_mapping = {
                'perfilDemografico': {
                    'questoes': ['q1', 'q2', 'q3', 'q4', 'q5'],
                    'nome': 'Perfil Demográfico do Estudante'
                },
                'contextoFamiliar': {
                    'questoes': ['q6', 'q7', 'q8', 'q9', 'q10', 'q11', 'q12', 'q13'],
                    'nome': 'Contexto Familiar e Socioeconômico'
                },
                'trajetoriaEscolar': {
                    'questoes': ['q14', 'q15', 'q16', 'q17', 'q18', 'q19', 'q20', 'q21'],
                    'nome': 'Trajetória e Contexto Escolar'
                },
                'ambienteEscolar': {
                    'questoes': perfil_ambiente_questoes,
                    'nome': 'Percepções sobre o Ambiente Escolar'
                }
            }
            
            # Calcular perfis
            perfis = {}
            for perfil_key, perfil_config in profile_mapping.items():
                perfis[perfil_key] = ResultsService._calculate_profile(
                    form,
                    perfil_config,
                    results
                )
            
            return {
                'formId': form.id,
                'formTitle': form.title,
                'totalRespostas': total_respostas,
                'filtros': ResultsService._format_filters_info(filters, results),
                'perfis': perfis,
                'geradoEm': datetime.utcnow().isoformat()
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Erro ao calcular perfis: {str(e)}")
            raise
    
    @staticmethod
    def _build_base_query(form_id, filters=None):
        """
        Constrói query base com todos os JOINs necessários.
        
        Args:
            form_id: ID do formulário
            filters: Filtros a aplicar
            
        Returns:
            Query: Query configurada
        """
        query = db.session.query(
            FormResponse,
            User,
            Student,
            School,
            Grade,
            Class,
            City
        ).join(
            User, FormResponse.user_id == User.id
        ).join(
            Student, User.id == Student.user_id
        ).join(
            School, Student.school_id == School.id
        ).outerjoin(
            Grade, Student.grade_id == Grade.id
        ).outerjoin(
            Class, Student.class_id == Class.id
        ).join(
            City, School.city_id == City.id
        ).filter(
            FormResponse.form_id == form_id,
            FormResponse.status == 'completed'
        )
        
        # Aplicar filtros
        if filters:
            if filters.get('state'):
                query = query.filter(City.state == filters['state'])
            
            if filters.get('municipio'):
                query = query.filter(City.id == filters['municipio'])
            
            if filters.get('escola'):
                query = query.filter(School.id == filters['escola'])
            
            if filters.get('serie'):
                query = query.filter(Student.grade_id == filters['serie'])
            
            if filters.get('turma'):
                query = query.filter(Student.class_id == filters['turma'])
        
        return query
    
    @staticmethod
    def _calculate_distorcao_idade_serie(results, page, limit):
        """Calcula índice de distorção idade-série (Q20 != 'Nunca')"""
        alunos_distorcao = []
        
        for response, user, student, school, grade, class_, city in results:
            responses_data = response.responses or {}
            resposta_q20 = responses_data.get('q20')
            
            # Incluir se respondeu algo diferente de "Nunca"
            if resposta_q20 and resposta_q20 != 'Nunca':
                alunos_distorcao.append({
                    'response': response,
                    'user': user,
                    'student': student,
                    'school': school,
                    'grade': grade,
                    'class_': class_,
                    'resposta': resposta_q20
                })
        
        total = len(alunos_distorcao)
        porcentagem = (total / len(results) * 100) if len(results) > 0 else 0
        
        # Paginar alunos
        start = (page - 1) * limit
        end = start + limit
        alunos_paginated = alunos_distorcao[start:end]
        
        return {
            'total': total,
            'porcentagem': round(porcentagem, 2),
            'alunos': {
                'data': [ResultsService._format_aluno_info(a) for a in alunos_paginated],
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'totalPages': (total + limit - 1) // limit if limit > 0 else 0
                }
            }
        }
    
    @staticmethod
    def _calculate_historico_reprovacao(results, page, limit):
        """Calcula índice de reprovação (Q19 != 'Não')"""
        alunos_reprovacao = []
        
        for response, user, student, school, grade, class_, city in results:
            responses_data = response.responses or {}
            resposta_q19 = responses_data.get('q19')
            
            # Incluir se respondeu algo diferente de "Não"
            if resposta_q19 and resposta_q19.lower() != 'não':
                alunos_reprovacao.append({
                    'response': response,
                    'user': user,
                    'student': student,
                    'school': school,
                    'grade': grade,
                    'class_': class_,
                    'resposta': resposta_q19
                })
        
        total = len(alunos_reprovacao)
        porcentagem = (total / len(results) * 100) if len(results) > 0 else 0
        
        # Paginar alunos
        start = (page - 1) * limit
        end = start + limit
        alunos_paginated = alunos_reprovacao[start:end]
        
        return {
            'total': total,
            'porcentagem': round(porcentagem, 2),
            'alunos': {
                'data': [ResultsService._format_aluno_info(a) for a in alunos_paginated],
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'totalPages': (total + limit - 1) // limit if limit > 0 else 0
                }
            }
        }
    
    @staticmethod
    def _calculate_sem_acesso_internet(results, page, limit):
        """Calcula índice de sem acesso à internet (Q13b == 'não')"""
        alunos_sem_internet = []
        
        for response, user, student, school, grade, class_, city in results:
            responses_data = response.responses or {}
            resposta_q13b = responses_data.get('q13b')
            
            # Incluir se respondeu "não" para Wi-Fi
            if resposta_q13b and resposta_q13b.lower() == 'não':
                alunos_sem_internet.append({
                    'response': response,
                    'user': user,
                    'student': student,
                    'school': school,
                    'grade': grade,
                    'class_': class_,
                    'resposta': resposta_q13b
                })
        
        total = len(alunos_sem_internet)
        porcentagem = (total / len(results) * 100) if len(results) > 0 else 0
        
        # Paginar alunos
        start = (page - 1) * limit
        end = start + limit
        alunos_paginated = alunos_sem_internet[start:end]
        
        return {
            'total': total,
            'porcentagem': round(porcentagem, 2),
            'alunos': {
                'data': [ResultsService._format_aluno_info(a) for a in alunos_paginated],
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'totalPages': (total + limit - 1) // limit if limit > 0 else 0
                }
            }
        }
    
    @staticmethod
    def _calculate_baixo_engajamento(results, page, limit):
        """Calcula índice de baixo engajamento familiar (Q10 == 'Nunca')"""
        alunos_baixo_engajamento = []
        
        for response, user, student, school, grade, class_, city in results:
            responses_data = response.responses or {}
            resposta_q10 = responses_data.get('q10')
            
            # Incluir se respondeu "Nunca"
            if resposta_q10 == 'Nunca':
                alunos_baixo_engajamento.append({
                    'response': response,
                    'user': user,
                    'student': student,
                    'school': school,
                    'grade': grade,
                    'class_': class_,
                    'resposta': resposta_q10
                })
        
        total = len(alunos_baixo_engajamento)
        porcentagem = (total / len(results) * 100) if len(results) > 0 else 0
        
        # Paginar alunos
        start = (page - 1) * limit
        end = start + limit
        alunos_paginated = alunos_baixo_engajamento[start:end]
        
        return {
            'total': total,
            'porcentagem': round(porcentagem, 2),
            'alunos': {
                'data': [ResultsService._format_aluno_info(a) for a in alunos_paginated],
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'totalPages': (total + limit - 1) // limit if limit > 0 else 0
                }
            }
        }
    
    @staticmethod
    def _format_aluno_info(aluno_data):
        """Formata informações do aluno para resposta"""
        return {
            'alunoId': aluno_data['student'].id,
            'alunoNome': aluno_data['user'].name,
            'userId': aluno_data['user'].id,
            'dataNascimento': aluno_data['student'].birth_date.isoformat() if aluno_data['student'].birth_date else None,
            'escolaId': aluno_data['school'].id,
            'escolaNome': aluno_data['school'].name,
            'gradeId': str(aluno_data['grade'].id) if aluno_data['grade'] else None,
            'gradeName': aluno_data['grade'].name if aluno_data['grade'] else None,
            'classId': str(aluno_data['class_'].id) if aluno_data['class_'] else None,
            'className': aluno_data['class_'].name if aluno_data['class_'] else None,
            'resposta': aluno_data['resposta']
        }
    
    @staticmethod
    def _calculate_profile(form, perfil_config, results):
        """Calcula dados de um perfil específico"""
        perfil_data = {
            'nome': perfil_config['nome'],
            'questoes': perfil_config['questoes'],
            'dados': {}
        }
        
        # Para cada questão do perfil
        for question_id in perfil_config['questoes']:
            # Buscar a questão no formulário
            question = next((q for q in form.questions if q.question_id == question_id), None)
            if not question:
                continue
            
            question_data = {
                'textoPergunta': question.text,
                'tipo': question.type
            }
            
            # Se tem subperguntas
            if question.sub_questions:
                question_data['subperguntas'] = {}
                for sub_q in question.sub_questions:
                    sub_id = sub_q.get('id')
                    if not sub_id:
                        continue
                    
                    # Contar respostas para esta subpergunta
                    contador = defaultdict(int)
                    for response, user, student, school, grade, class_, city in results:
                        responses_data = response.responses or {}
                        answer = responses_data.get(sub_id)
                        if answer is not None and answer != '':
                            contador[str(answer)] += 1
                    
                    question_data['subperguntas'][sub_id] = {
                        'texto': sub_q.get('text', ''),
                        'contagem': dict(contador)
                    }
                
                question_data['totalRespostas'] = len(results)
            else:
                # Questão simples - contar respostas
                contador = defaultdict(int)
                for response, user, student, school, grade, class_, city in results:
                    responses_data = response.responses or {}
                    answer = responses_data.get(question_id)
                    if answer is not None and answer != '':
                        contador[str(answer)] += 1
                
                question_data['contagem'] = dict(contador)
                question_data['totalRespostas'] = len(results)
            
            perfil_data['dados'][question_id] = question_data
        
        return perfil_data
    
    @staticmethod
    def _determine_ambiente_escolar_questions(education_stages):
        """Determina questões do perfil Ambiente Escolar baseado nas séries"""
        if not education_stages:
            return ['q22', 'q23']
        
        # Contar ocorrências
        stage_counts = defaultdict(int)
        for stage in education_stages:
            stage_counts[str(stage)] += 1
        
        # Verificar qual predomina
        if stage_counts.get(EDUCATION_STAGE_ANOS_FINAIS, 0) > stage_counts.get(EDUCATION_STAGE_ANOS_INICIAIS, 0):
            # Anos Finais predomina - incluir q24
            return ['q22', 'q23', 'q24']
        else:
            # Anos Iniciais predomina ou empate - apenas q22 e q23
            return ['q22', 'q23']
    
    @staticmethod
    def _format_filters_info(filters, results):
        """Formata informações dos filtros aplicados"""
        if not filters or not results:
            return {}
        
        # Pegar primeiro resultado para obter nomes
        first_result = results[0]
        _, _, _, school, grade, class_, city = first_result
        
        filter_info = {}
        
        if filters.get('state'):
            filter_info['estado'] = filters['state']
        
        if filters.get('municipio'):
            filter_info['municipio'] = filters['municipio']
            filter_info['municipioNome'] = city.name if city else None
        
        if filters.get('escola'):
            filter_info['escola'] = filters['escola']
            filter_info['escolaNome'] = school.name if school else None
        
        if filters.get('serie'):
            filter_info['serie'] = filters['serie']
            filter_info['serieName'] = grade.name if grade else None
        
        if filters.get('turma'):
            filter_info['turma'] = filters['turma']
            filter_info['turmaName'] = class_.name if class_ else None
        
        return filter_info
    
    @staticmethod
    def _empty_indices_response(form, filters):
        """Resposta vazia para índices quando não há dados"""
        return {
            'formId': form.id,
            'formTitle': form.title,
            'totalRespostas': 0,
            'filtros': filters or {},
            'indices': {
                'distorcaoIdadeSerie': {'total': 0, 'porcentagem': 0, 'alunos': {'data': [], 'pagination': {'page': 1, 'limit': 20, 'total': 0, 'totalPages': 0}}},
                'historicoReprovacao': {'total': 0, 'porcentagem': 0, 'alunos': {'data': [], 'pagination': {'page': 1, 'limit': 20, 'total': 0, 'totalPages': 0}}},
                'semAcessoInternet': {'total': 0, 'porcentagem': 0, 'alunos': {'data': [], 'pagination': {'page': 1, 'limit': 20, 'total': 0, 'totalPages': 0}}},
                'baixoEngajamentoFamiliar': {'total': 0, 'porcentagem': 0, 'alunos': {'data': [], 'pagination': {'page': 1, 'limit': 20, 'total': 0, 'totalPages': 0}}}
            },
            'geradoEm': datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def _empty_profiles_response(form, filters):
        """Resposta vazia para perfis quando não há dados"""
        return {
            'formId': form.id,
            'formTitle': form.title,
            'totalRespostas': 0,
            'filtros': filters or {},
            'perfis': {},
            'geradoEm': datetime.utcnow().isoformat()
        }
