# -*- coding: utf-8 -*-
"""
Serviço para agregação de resultados de múltiplos formulários socioeconômicos.
Consolida dados de TODOS os formulários aplicados em um escopo específico.
"""

from app.socioeconomic_forms.models import Form
from app.socioeconomic_forms.services.results_service import ResultsService
from app.socioeconomic_forms.services.results_cache_service import ResultsCacheService
from app.models import School, Grade, Class, City
from sqlalchemy.exc import SQLAlchemyError
from collections import defaultdict
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AggregatedResultsService:
    """Serviço para agregação de resultados de múltiplos formulários"""
    
    @staticmethod
    def get_aggregated_indices(filters, page=1, limit=20):
        """
        Obtém índices agregados de TODOS os formulários aplicados no escopo.
        
        Args:
            filters: Filtros hierárquicos {state, municipio, escola, serie, turma}
            page: Página para paginação
            limit: Limite de registros
            
        Returns:
            dict: Resultados agregados de todos os formulários
        """
        try:
            # 1. Buscar formulários que se aplicam ao escopo
            forms = AggregatedResultsService._find_forms_for_scope(filters)
            
            if not forms:
                return AggregatedResultsService._empty_aggregated_response(filters, 'indices')
            
            logger.info("[AGGREGATED] Encontrados %d formulários para o escopo: %s", len(forms), filters)
            
            # 2. Buscar/calcular resultados de cada formulário
            all_results = []
            forms_summary = []
            
            for form in forms:
                # Tentar buscar do cache primeiro
                cached_result = ResultsCacheService.get_result(form.id, 'indices', filters)
                
                if cached_result:
                    result = cached_result
                    logger.info("[AGGREGATED] Usando cache para form_id=%s", form.id)
                else:
                    # Calcular se não estiver em cache
                    logger.info("[AGGREGATED] Calculando resultado para form_id=%s", form.id)
                    result = ResultsService.calculate_general_indices(form.id, filters, page, limit)
                
                all_results.append({
                    'form_id': form.id,
                    'form_title': form.title,
                    'form_type': form.form_type,
                    'result': result
                })
                
                forms_summary.append({
                    'formId': form.id,
                    'formTitle': form.title,
                    'formType': form.form_type,
                    'totalRespostas': result.get('totalRespostas', 0),
                    'createdAt': form.created_at.isoformat() if form.created_at else None
                })
            
            # 3. Consolidar resultados
            consolidated = AggregatedResultsService._consolidate_indices(all_results, page, limit)
            
            # 4. Preparar resposta
            return {
                'escopo': AggregatedResultsService._format_scope_info(filters),
                'formularios': forms_summary,
                'totalFormularios': len(forms),
                'totalRespostas': sum(f['totalRespostas'] for f in forms_summary),
                'indicesConsolidados': consolidated,
                'geradoEm': datetime.utcnow().isoformat()
            }
            
        except SQLAlchemyError as e:
            logger.error("Erro ao obter índices agregados: %s", str(e))
            raise
    
    @staticmethod
    def get_aggregated_profiles(filters):
        """
        Obtém perfis agregados de TODOS os formulários aplicados no escopo.
        
        Args:
            filters: Filtros hierárquicos
            
        Returns:
            dict: Perfis agregados de todos os formulários
        """
        try:
            # 1. Buscar formulários que se aplicam ao escopo
            forms = AggregatedResultsService._find_forms_for_scope(filters)
            
            if not forms:
                return AggregatedResultsService._empty_aggregated_response(filters, 'profiles')
            
            logger.info("[AGGREGATED] Encontrados %d formulários para o escopo: %s", len(forms), filters)
            
            # 2. Buscar/calcular resultados de cada formulário
            all_results = []
            forms_summary = []
            
            for form in forms:
                # Tentar buscar do cache primeiro
                cached_result = ResultsCacheService.get_result(form.id, 'profiles', filters)
                
                if cached_result:
                    result = cached_result
                else:
                    # Calcular se não estiver em cache
                    result = ResultsService.calculate_profiles_report(form.id, filters)
                
                all_results.append({
                    'form_id': form.id,
                    'form_title': form.title,
                    'form_type': form.form_type,
                    'result': result
                })
                
                forms_summary.append({
                    'formId': form.id,
                    'formTitle': form.title,
                    'formType': form.form_type,
                    'totalRespostas': result.get('totalRespostas', 0),
                    'createdAt': form.created_at.isoformat() if form.created_at else None
                })
            
            # 3. Consolidar resultados
            consolidated = AggregatedResultsService._consolidate_profiles(all_results)
            
            # 4. Preparar resposta
            return {
                'escopo': AggregatedResultsService._format_scope_info(filters),
                'formularios': forms_summary,
                'totalFormularios': len(forms),
                'totalRespostas': sum(f['totalRespostas'] for f in forms_summary),
                'perfisConsolidados': consolidated,
                'geradoEm': datetime.utcnow().isoformat()
            }
            
        except SQLAlchemyError as e:
            logger.error("Erro ao obter perfis agregados: %s", str(e))
            raise
    
    @staticmethod
    def _find_forms_for_scope(filters):
        """
        Encontra todos os formulários que foram aplicados no escopo especificado.
        
        Args:
            filters: Filtros hierárquicos {state, municipio, escola, serie, turma}
            
        Returns:
            list: Lista de objetos Form
        """
        # Buscar formulários ativos de alunos
        query = Form.query.filter(
            Form.is_active == True,
            Form.form_type.in_(['aluno-jovem', 'aluno-velho'])
        )
        
        # Agora precisamos filtrar formulários que foram aplicados no escopo
        # Um formulário se aplica ao escopo se:
        # 1. Form.filters inclui o escopo OU
        # 2. Form.selected_* inclui o escopo
        
        matching_forms = []
        
        for form in query.all():
            if AggregatedResultsService._form_matches_scope(form, filters):
                matching_forms.append(form)
        
        return matching_forms
    
    @staticmethod
    def _form_matches_scope(form, filters):
        """
        Verifica se um formulário foi aplicado no escopo especificado.
        
        Args:
            form: Objeto Form
            filters: Filtros do escopo
            
        Returns:
            bool: True se o formulário se aplica ao escopo
        """
        # Se filtros não especificados, incluir todos
        if not filters:
            return True
        
        # ESTRATÉGIA:
        # 1. Se form tem 'filters', verificar compatibilidade com escopo solicitado
        # 2. Se form não tem 'filters', usar 'selected_*' e verificar via relacionamentos
        
        # ============================================================
        # CASO 1: Formulário tem campo 'filters'
        # ============================================================
        if form.filters:
            form_filters = form.filters
            
            # Estado
            if filters.get('state'):
                if form_filters.get('estado'):
                    if form_filters['estado'] != filters['state']:
                        return False
            
            # Município
            if filters.get('municipio'):
                if form_filters.get('municipio'):
                    if form_filters['municipio'] != filters['municipio']:
                        return False
            
            # Escola (pode estar em 'filters.escola' ou em 'selected_schools')
            if filters.get('escola'):
                escola_match = False
                
                # Verificar em form.filters.escola
                if form_filters.get('escola'):
                    if form_filters['escola'] == filters['escola']:
                        escola_match = True
                
                # Se não tem em filters.escola, verificar em selected_schools
                if not escola_match and form.selected_schools:
                    if filters['escola'] in form.selected_schools:
                        escola_match = True
                
                if not escola_match:
                    return False
            
            # Série (pode estar em 'filters.serie' ou em 'selected_grades')
            if filters.get('serie'):
                serie_match = False
                
                if form_filters.get('serie'):
                    if form_filters['serie'] == filters['serie']:
                        serie_match = True
                
                if not serie_match and form.selected_grades:
                    if filters['serie'] in form.selected_grades:
                        serie_match = True
                
                if not serie_match:
                    return False
            
            # Turma (pode estar em 'filters.turma' ou em 'selected_classes')
            if filters.get('turma'):
                turma_match = False
                
                if form_filters.get('turma'):
                    if form_filters['turma'] == filters['turma']:
                        turma_match = True
                
                if not turma_match and form.selected_classes:
                    if filters['turma'] in form.selected_classes:
                        turma_match = True
                
                if not turma_match:
                    return False
            
            return True
        
        # ============================================================
        # CASO 2: Formulário NÃO tem campo 'filters' (usa selected_*)
        # ============================================================
        else:
            # Escola
            if filters.get('escola'):
                if not form.selected_schools:
                    return False
                if filters['escola'] not in form.selected_schools:
                    return False
            
            # Série
            if filters.get('serie'):
                if not form.selected_grades:
                    return False
                if filters['serie'] not in form.selected_grades:
                    return False
            
            # Turma
            if filters.get('turma'):
                if not form.selected_classes:
                    return False
                if filters['turma'] not in form.selected_classes:
                    return False
            
            # Município e/ou Estado: verificar via escolas selecionadas
            if filters.get('municipio') or filters.get('state'):
                if not form.selected_schools or len(form.selected_schools) == 0:
                    return False
                
                # Verificar se QUALQUER escola do formulário pertence ao município/estado
                any_school_matches = False
                
                for school_id in form.selected_schools:
                    school = School.query.get(school_id)
                    if not school or not school.city_id:
                        continue
                    
                    city = City.query.get(school.city_id)
                    if not city:
                        continue
                    
                    # Verificar município
                    if filters.get('municipio'):
                        if city.id != filters['municipio']:
                            continue
                    
                    # Verificar estado
                    if filters.get('state'):
                        if city.state != filters['state']:
                            continue
                    
                    # Se chegou aqui, esta escola corresponde aos filtros
                    any_school_matches = True
                    break
                
                if not any_school_matches:
                    return False
            
            return True
    
    @staticmethod
    def _consolidate_indices(all_results, page, limit):
        """
        Consolida índices de múltiplos formulários.
        
        Args:
            all_results: Lista de resultados de cada formulário
            page: Página atual
            limit: Limite de registros
            
        Returns:
            dict: Índices consolidados
        """
        # Estrutura para consolidação
        consolidated = {
            'distorcaoIdadeSerie': {'total': 0, 'porcentagem': 0, 'alunos': [], 'porFormulario': {}},
            'historicoReprovacao': {'total': 0, 'porcentagem': 0, 'alunos': [], 'porFormulario': {}},
            'semAcessoInternet': {'total': 0, 'porcentagem': 0, 'alunos': [], 'porFormulario': {}},
            'baixoEngajamentoFamiliar': {'total': 0, 'porcentagem': 0, 'alunos': [], 'porFormulario': {}}
        }
        
        total_respostas_geral = 0
        alunos_por_indice = defaultdict(list)
        
        # Agregar dados de cada formulário
        for item in all_results:
            form_id = item['form_id']
            form_title = item['form_title']
            result = item['result']
            
            indices = result.get('indices', {})
            total_respostas = result.get('totalRespostas', 0)
            total_respostas_geral += total_respostas
            
            # Processar cada índice
            for indice_key in consolidated.keys():
                if indice_key in indices:
                    indice_data = indices[indice_key]
                    
                    # Somar totais
                    consolidated[indice_key]['total'] += indice_data.get('total', 0)
                    
                    # Agregar alunos (remover duplicatas por alunoId)
                    if 'alunos' in indice_data and 'data' in indice_data['alunos']:
                        for aluno in indice_data['alunos']['data']:
                            # Adicionar referência ao formulário
                            aluno_with_form = aluno.copy()
                            aluno_with_form['formId'] = form_id
                            aluno_with_form['formTitle'] = form_title
                            alunos_por_indice[indice_key].append(aluno_with_form)
                    
                    # Guardar estatísticas por formulário
                    consolidated[indice_key]['porFormulario'][form_id] = {
                        'formTitle': form_title,
                        'total': indice_data.get('total', 0),
                        'porcentagem': indice_data.get('porcentagem', 0),
                        'totalRespostas': total_respostas
                    }
        
        # Calcular porcentagens consolidadas e paginar alunos
        for indice_key in consolidated.keys():
            total = consolidated[indice_key]['total']
            porcentagem = (total / total_respostas_geral * 100) if total_respostas_geral > 0 else 0
            consolidated[indice_key]['porcentagem'] = round(porcentagem, 2)
            
            # Remover duplicatas de alunos (mesmo aluno pode ter respondido múltiplos formulários)
            unique_alunos = {}
            for aluno in alunos_por_indice[indice_key]:
                aluno_id = aluno['alunoId']
                # Manter o primeiro registro de cada aluno (ou combinar?)
                if aluno_id not in unique_alunos:
                    unique_alunos[aluno_id] = aluno
            
            all_alunos = list(unique_alunos.values())
            
            # Paginar
            start = (page - 1) * limit
            end = start + limit
            alunos_paginated = all_alunos[start:end]
            
            consolidated[indice_key]['alunos'] = {
                'data': alunos_paginated,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': len(all_alunos),
                    'totalPages': (len(all_alunos) + limit - 1) // limit if limit > 0 else 0
                }
            }
        
        return consolidated
    
    @staticmethod
    def _consolidate_profiles(all_results):
        """
        Consolida perfis de múltiplos formulários.
        
        Args:
            all_results: Lista de resultados de cada formulário
            
        Returns:
            dict: Perfis consolidados
        """
        # Estrutura para consolidação
        consolidated = {
            'perfilDemografico': {'nome': 'Perfil Demográfico do Estudante', 'questoes': ['q1', 'q2', 'q3', 'q4', 'q5'], 'dados': {}},
            'contextoFamiliar': {'nome': 'Contexto Familiar e Socioeconômico', 'questoes': ['q6', 'q7', 'q8', 'q9', 'q10', 'q11', 'q12', 'q13'], 'dados': {}},
            'trajetoriaEscolar': {'nome': 'Trajetória e Contexto Escolar', 'questoes': ['q14', 'q15', 'q16', 'q17', 'q18', 'q19', 'q20', 'q21'], 'dados': {}},
            'ambienteEscolar': {'nome': 'Percepções sobre o Ambiente Escolar', 'questoes': ['q22', 'q23', 'q24'], 'dados': {}}
        }
        
        # Agregar dados de cada formulário
        for item in all_results:
            form_id = item['form_id']
            form_title = item['form_title']
            result = item['result']
            
            perfis = result.get('perfis', {})
            
            # Processar cada perfil
            for perfil_key in consolidated.keys():
                if perfil_key in perfis:
                    perfil_data = perfis[perfil_key]
                    dados = perfil_data.get('dados', {})
                    
                    # Processar cada questão
                    for question_id, question_data in dados.items():
                        if question_id not in consolidated[perfil_key]['dados']:
                            # Primeira vez vendo esta questão
                            consolidated[perfil_key]['dados'][question_id] = {
                                'textoPergunta': question_data.get('textoPergunta', ''),
                                'tipo': question_data.get('tipo', ''),
                                'contagem': defaultdict(int),
                                'totalRespostas': 0,
                                'porFormulario': {}
                            }
                            
                            # Se tem subperguntas, inicializar
                            if 'subperguntas' in question_data:
                                consolidated[perfil_key]['dados'][question_id]['subperguntas'] = {}
                        
                        # Agregar contagens
                        if 'subperguntas' in question_data:
                            # Questão com subperguntas
                            for sub_id, sub_data in question_data['subperguntas'].items():
                                if sub_id not in consolidated[perfil_key]['dados'][question_id]['subperguntas']:
                                    consolidated[perfil_key]['dados'][question_id]['subperguntas'][sub_id] = {
                                        'texto': sub_data.get('texto', ''),
                                        'contagem': defaultdict(int)
                                    }
                                
                                # Somar contagens
                                for opcao, count in sub_data.get('contagem', {}).items():
                                    consolidated[perfil_key]['dados'][question_id]['subperguntas'][sub_id]['contagem'][opcao] += count
                        else:
                            # Questão simples - somar contagens
                            for opcao, count in question_data.get('contagem', {}).items():
                                consolidated[perfil_key]['dados'][question_id]['contagem'][opcao] += count
                        
                        # Somar total de respostas
                        consolidated[perfil_key]['dados'][question_id]['totalRespostas'] += question_data.get('totalRespostas', 0)
                        
                        # Guardar estatísticas por formulário
                        consolidated[perfil_key]['dados'][question_id]['porFormulario'][form_id] = {
                            'formTitle': form_title,
                            'contagem': question_data.get('contagem', {}),
                            'totalRespostas': question_data.get('totalRespostas', 0)
                        }
        
        # Converter defaultdict para dict
        for perfil_key in consolidated.keys():
            for question_id in consolidated[perfil_key]['dados'].keys():
                if 'contagem' in consolidated[perfil_key]['dados'][question_id]:
                    consolidated[perfil_key]['dados'][question_id]['contagem'] = dict(
                        consolidated[perfil_key]['dados'][question_id]['contagem']
                    )
                
                if 'subperguntas' in consolidated[perfil_key]['dados'][question_id]:
                    for sub_id in consolidated[perfil_key]['dados'][question_id]['subperguntas'].keys():
                        consolidated[perfil_key]['dados'][question_id]['subperguntas'][sub_id]['contagem'] = dict(
                            consolidated[perfil_key]['dados'][question_id]['subperguntas'][sub_id]['contagem']
                        )
        
        return consolidated
    
    @staticmethod
    def _format_scope_info(filters):
        """
        Formata informações do escopo com nomes legíveis.
        
        Args:
            filters: Filtros aplicados
            
        Returns:
            dict: Informações formatadas do escopo
        """
        scope_info = {}
        
        if filters.get('state'):
            scope_info['estado'] = filters['state']
        
        if filters.get('municipio'):
            city = City.query.get(filters['municipio'])
            scope_info['municipio'] = filters['municipio']
            scope_info['municipioNome'] = city.name if city else None
        
        if filters.get('escola'):
            school = School.query.get(filters['escola'])
            scope_info['escola'] = filters['escola']
            scope_info['escolaNome'] = school.name if school else None
        
        if filters.get('serie'):
            grade = Grade.query.get(filters['serie'])
            scope_info['serie'] = filters['serie']
            scope_info['serieName'] = grade.name if grade else None
        
        if filters.get('turma'):
            turma = Class.query.get(filters['turma'])
            scope_info['turma'] = filters['turma']
            scope_info['turmaName'] = turma.name if turma else None
        
        return scope_info
    
    @staticmethod
    def _empty_aggregated_response(filters, report_type):
        """Resposta vazia quando não há formulários no escopo"""
        return {
            'escopo': AggregatedResultsService._format_scope_info(filters),
            'formularios': [],
            'totalFormularios': 0,
            'totalRespostas': 0,
            'indicesConsolidados': {} if report_type == 'indices' else None,
            'perfisConsolidados': {} if report_type == 'profiles' else None,
            'geradoEm': datetime.utcnow().isoformat(),
            'message': 'Nenhum formulário encontrado para o escopo especificado'
        }
