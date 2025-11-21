# -*- coding: utf-8 -*-
"""
Serviço para análise de relatórios usando OpenAI
"""

import logging
import re
from typing import Dict, Any, Optional
from app.openai_config.openai_config import (
    get_openai_client,
    get_gemini_client,
    USE_GEMINI,
    ANALYSIS_PROMPT_BASE, 
    CONTEXT_SETTINGS,
    PARTICIPATION_CLASSIFICATION_TABLE,
    PARTICIPATION_ANALYSIS_PROMPT_TEMPLATE,
    NIVEIS_APRENDIZAGEM_ANALYSIS_PROMPT_TEMPLATE,
    SAEB_PROFICIENCY_REFERENCE_TABLE,
    PROFICIENCY_ANALYSIS_PROMPT_TEMPLATE,
    NOTA_REFERENCE_TABLE,
    NOTA_ANALYSIS_PROMPT_TEMPLATE
)

class AIAnalysisService:
    """Serviço para análise de relatórios usando IA (OpenAI ou Gemini)"""
    
    def __init__(self):
        self.use_gemini = USE_GEMINI
        if self.use_gemini:
            try:
                self.gemini_model = get_gemini_client()
                self.client = None  # Não usar OpenAI quando usar Gemini
                self.logger = logging.getLogger(__name__)
                self.logger.info("Usando Google Gemini para análise de relatórios")
            except Exception as e:
                self.logger = logging.getLogger(__name__)
                self.logger.warning(f"Erro ao inicializar Gemini, usando OpenAI como fallback: {str(e)}")
                self.client = get_openai_client()
                self.gemini_model = None
                self.use_gemini = False
        else:
            self.client = get_openai_client()
            self.gemini_model = None
            self.logger = logging.getLogger(__name__)
            self.logger.info("Usando OpenAI para análise de relatórios")
    
    def analyze_report_data(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analisa dados do relatório e gera textos usando OpenAI em UMA ÚNICA chamada.
        OTIMIZAÇÃO: Consolida todas as análises (participação, proficiência, notas, níveis) 
        em uma única requisição à API para reduzir custos e latência.
        
        Args:
            report_data: Dados do relatório completo
            
        Returns:
            Dict com textos analíticos gerados pela IA:
            {
                'participacao': str,
                'proficiencia': Dict[str, str],  # {disciplina: análise}
                'notas': str,
                'niveis_aprendizagem': Dict[str, str]  # {disciplina: análise}
            }
        """
        try:
            # Preparar dados para análise
            analysis_data = self._prepare_analysis_data(report_data)
            avaliacao_titulo = report_data.get('avaliacao', {}).get('titulo', '') or report_data.get('avaliacao', {}).get('title', '')
            scope_type = report_data.get('scope_type', 'all')
            
            # Construir prompt unificado com todos os dados
            unified_prompt = self._build_unified_prompt(report_data, analysis_data, avaliacao_titulo, scope_type)
            
            # Fazer UMA ÚNICA chamada à IA
            unified_response = self._call_openai(unified_prompt)
            
            # Processar resposta e extrair as diferentes seções
            analysis_texts = self._parse_unified_response(unified_response, report_data)
            
            return analysis_texts
            
        except Exception as e:
            self.logger.error(f"Erro na análise da IA: {str(e)}", exc_info=True)
            return self._get_fallback_texts()
    
    def _prepare_analysis_data(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepara dados para análise da IA"""
        try:
            # Extrair dados relevantes
            total_alunos = report_data.get('total_alunos', {})
            niveis_aprendizagem = report_data.get('niveis_aprendizagem', {})
            proficiencia = report_data.get('proficiencia', {})
            nota_geral = report_data.get('nota_geral', {})
            acertos_habilidade = report_data.get('acertos_por_habilidade', {})
            
            # Dados de participação
            scope_type = report_data.get('scope_type', 'all')
            participacao_data = {
                'total_matriculados': total_alunos.get('total_geral', {}).get('matriculados', 0),
                'total_avaliados': total_alunos.get('total_geral', {}).get('avaliados', 0),
                'total_faltosos': total_alunos.get('total_geral', {}).get('faltosos', 0),
                'percentual_participacao': total_alunos.get('total_geral', {}).get('percentual', 0),
                'por_turma': total_alunos.get('por_turma', []),
                'por_escola': total_alunos.get('por_escola', [])
            }
            
            # Dados de proficiência
            proficiencia_data = {
                'por_disciplina': proficiencia.get('por_disciplina', {}),
                'media_municipal': proficiencia.get('media_municipal_por_disciplina', {})
            }
            
            # Dados de notas
            notas_data = {
                'por_disciplina': nota_geral.get('por_disciplina', {}),
                'media_municipal': nota_geral.get('media_municipal_por_disciplina', {})
            }
            
            # Dados de habilidades
            habilidades_data = {
                'por_disciplina': acertos_habilidade,
                'questoes_anuladas': report_data.get('avaliacao', {}).get('questoes_anuladas', [])
            }
            
            return {
                'participacao': participacao_data,
                'proficiencia': proficiencia_data,
                'notas': notas_data,
                'habilidades': habilidades_data,
                'avaliacao_info': report_data.get('avaliacao', {})
            }
            
        except Exception as e:
            self.logger.error(f"Erro ao preparar dados para análise: {str(e)}")
            return {}
    
    def _analyze_participation(self, analysis_data: Dict[str, Any], scope_type: str, avaliacao_titulo: str = "") -> str:
        """Analisa dados de participação (Página 4) usando o novo template"""
        try:
            participacao = analysis_data.get('participacao', {})
            total_matriculados = participacao.get('total_matriculados', 0)
            total_avaliados = participacao.get('total_avaliados', 0)
            total_faltosos = participacao.get('total_faltosos', 0)
            percentual_participacao = participacao.get('percentual_participacao', 0)
            
            # Dados por escola/turma
            dados_detalhados = participacao.get('por_turma', []) if scope_type != 'city' else participacao.get('por_escola', [])
            
            # Determinar contexto (Entidade)
            if scope_type == 'city':
                entidade = "Município"
                unidade_nome = "escola"
                unidade_label = "Escola"
            else:
                entidade = "Escola"
                unidade_nome = "turma"
                unidade_label = "Turma"
            
            # Identificar destaques (turmas/escolas com alta participação >= 95%)
            destaques = []
            for item in dados_detalhados:
                nome = item.get(unidade_nome, 'N/A')
                avaliados = item.get('avaliados', 0)
                matriculados = item.get('matriculados', 0)
                percentual_item = item.get('percentual', 0)
                
                if percentual_item >= 95:
                    if scope_type == 'city':
                        destaques.append(f"A {unidade_label.lower()} {nome} merece parabéns pelo desempenho exemplar de {percentual_item:.0f}% de participação ({avaliados}/{matriculados}).")
                    else:
                        destaques.append(f"A turma {nome} merece parabéns pelo desempenho exemplar de {percentual_item:.0f}% de participação ({avaliados}/{matriculados}).")
            
            # Identificar pontos de atenção (turmas/escolas com baixa participação < 80% ou muitos faltosos)
            pontos_atencao = []
            for item in dados_detalhados:
                nome = item.get(unidade_nome, 'N/A')
                avaliados = item.get('avaliados', 0)
                matriculados = item.get('matriculados', 0)
                faltosos = item.get('faltosos', 0)
                percentual_item = item.get('percentual', 0)
                
                if percentual_item < 80 or faltosos > 0:
                    if faltosos > 0:
                        pontos_atencao.append(f"{nome} - {percentual_item:.0f}% ({avaliados}/{matriculados}) com {faltosos} faltoso(s)")
                    else:
                        pontos_atencao.append(f"{nome} - {percentual_item:.0f}% ({avaliados}/{matriculados})")
            
            # Formatar destaques e pontos de atenção
            destaque_str = " ".join(destaques) if destaques else "Nenhum destaque específico"
            atencao_str = "; ".join(pontos_atencao) if pontos_atencao else "Nenhum ponto de atenção específico"
            
            # Preencher o template do prompt
            # Primeiro inserir a tabela no template
            prompt_base = PARTICIPATION_ANALYSIS_PROMPT_TEMPLATE.replace(
                "{PARTICIPATION_CLASSIFICATION_TABLE}", PARTICIPATION_CLASSIFICATION_TABLE
            )
            
            # Agora substituir os placeholders específicos (ordem importa para evitar substituições indevidas)
            prompt = prompt_base.replace(
                "[Entidade]",
                entidade
            ).replace(
                "[Avaliação]",
                avaliacao_titulo or "Avaliação Diagnóstica"
            ).replace(
                "- Entidade: [Entidade: Ex. Escola Municipal X / 5º Ano Geral]",
                f"- Entidade: {entidade}"
            ).replace(
                "- Avaliação: [Avaliação: Ex: Avaliação Diagnóstica 2025.1]",
                f"- Avaliação: {avaliacao_titulo or 'Avaliação Diagnóstica'}"
            ).replace(
                "- Total de Alunos Matriculados: [Nº]",
                f"- Total de Alunos Matriculados: {total_matriculados}"
            ).replace(
                "- Total de Alunos Avaliados: [Nº]",
                f"- Total de Alunos Avaliados: {total_avaliados}"
            ).replace(
                "- Total de Faltosos: [Nº]",
                f"- Total de Faltosos: {total_faltosos}"
            ).replace(
                "- Taxa de Participação Geral: [__]%",
                f"- Taxa de Participação Geral: {percentual_participacao}%"
            ).replace(
                "- Destaque(s) por Turma: [Ex: 5º A - M: 95% (21/22)]",
                f"- Destaque(s) por Turma: {destaque_str}"
            ).replace(
                "- Ponto(s) de Atenção por Turma: [Ex: 5º B - M: 91% (21/23) com 2 faltosos]",
                f"- Ponto(s) de Atenção por Turma: {atencao_str}"
            ).replace(
                "taxa de participação de [__]%",
                f"taxa de participação de {percentual_participacao}%"
            )
            
            response = self._call_openai(prompt)
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"Erro na análise de participação: {str(e)}")
            return f"Análise de participação não disponível. {total_avaliados} alunos avaliados de {total_matriculados} matriculados ({percentual_participacao}% de participação)."
    
    def _analyze_proficiency(self, analysis_data: Dict[str, Any], scope_type: str) -> str:
        """Analisa dados de proficiência (Página 6)"""
        try:
            proficiencia = analysis_data.get('proficiencia', {})
            
            if not proficiencia:
                return "Dados de proficiência não disponíveis para análise."
            
            # Determinar contexto
            if scope_type == 'city':
                contexto = "município"
                unidade = "escola"
                unidade_plural = "escolas"
            else:
                contexto = "escola"
                unidade = "turma"
                unidade_plural = "turmas"
            
            # Preparar dados de proficiência
            prof_data = self._prepare_proficiency_data(proficiencia, unidade)
            
            # Gerar prompt específico para proficiência
            prompt = f"""
            Analise os dados de PROFICIÊNCIA de uma avaliação educacional e gere uma análise resumida e construtiva.
            
            DADOS DE PROFICIÊNCIA:
            {prof_data}
            
            CONTEXTO: Relatório de {contexto}
            
            Gere uma análise RESUMIDA (máximo 5 linhas) que inclua:
            1. Visão geral da proficiência por disciplina
            2. Principais destaques entre as {unidade_plural}
            3. Pontos fortes e fracos na proficiência
            4. Recomendação principal para melhoria da proficiência
            
            Use um tom profissional e construtivo. Seja conciso e específico. NÃO use formatação markdown (sem ###, ####, etc).
            """
            
            response = self._call_openai(prompt)
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"Erro na análise de proficiência: {str(e)}")
            return "Análise de proficiência não disponível."
    
    def _analyze_grades(self, report_data: Dict[str, Any], avaliacao_titulo: str = "") -> str:
        """
        Analisa dados de notas usando o novo template
        
        Args:
            report_data: Dados completos do relatório
            avaliacao_titulo: Título da avaliação
            
        Returns:
            String com análise de notas
        """
        try:
            nota_geral = report_data.get('nota_geral', {})
            scope_type = report_data.get('scope_type', 'all')
            
            if not nota_geral:
                return "Dados de notas não disponíveis para análise."
            
            notas_disciplinas = nota_geral.get('por_disciplina', {})
            media_municipal_por_disc = nota_geral.get('media_municipal_por_disciplina', {})
            
            if not notas_disciplinas:
                return "Dados de notas por disciplina não disponíveis."
            
            # Obter ano/série
            ano_serie = self._obter_ano_serie(report_data)
            
            # Determinar entidade/nível
            if scope_type == 'city':
                entidade_nivel = f"Município - {ano_serie}"
            else:
                entidade_nivel = f"Escola - {ano_serie}"
            
            # Obter média geral (GERAL)
            dados_geral = notas_disciplinas.get('GERAL', {})
            media_geral_total = dados_geral.get('media_geral', 0)
            
            # Obter média municipal geral
            media_municipal_geral = media_municipal_por_disc.get('GERAL', 0)
            
            # Preparar dados por disciplina para o prompt
            dados_disciplinas_str = ""
            disciplinas_para_analise = []
            
            # Determinar tipo de unidade baseado no scope_type
            if scope_type == 'city':
                tipo_unidade = "escola"
                label_unidade = "Escola"
            else:
                tipo_unidade = "turma"
                label_unidade = "Turma"
            
            for disciplina, dados in notas_disciplinas.items():
                if disciplina == 'GERAL':
                    continue
                
                media_disciplina = dados.get('media_geral', 0)
                
                # Determinar o campo correto baseado no scope_type
                if scope_type == 'city':
                    dados_detalhados = dados.get('por_escola', [])
                else:
                    dados_detalhados = dados.get('por_turma', [])
                
                # Mapear disciplina para sigla SAEB
                sigla_disc = self._mapear_disciplina_para_sigla(disciplina)
                
                # Formatar dados detalhados
                detalhes_str = ""
                if dados_detalhados:
                    detalhes_list = []
                    for detalhe_data in dados_detalhados:
                        nome_unidade = detalhe_data.get(tipo_unidade, 'N/A')
                        if scope_type == 'city':
                            # Para escolas, usar 'media' ou 'nota'
                            nota_value = detalhe_data.get('media', detalhe_data.get('nota', 0))
                        else:
                            # Para turmas, usar 'nota'
                            nota_value = detalhe_data.get('nota', 0)
                        detalhes_list.append(f"  - {nome_unidade}: {nota_value:.2f}")
                    detalhes_str = "\n".join(detalhes_list)
                else:
                    detalhes_str = f"  Nenhum dado por {tipo_unidade} disponível"
                
                # Adicionar linha para esta disciplina
                media_municipal_disc = media_municipal_por_disc.get(disciplina, 0)
                dados_disciplinas_str += f"\n{disciplina} ({sigla_disc}):\n"
                dados_disciplinas_str += f"  - Média Geral: {media_disciplina:.2f}\n"
                if media_municipal_disc > 0:
                    dados_disciplinas_str += f"  - Média Municipal: {media_municipal_disc:.2f}\n"
                dados_disciplinas_str += f"  - Notas por {label_unidade}:\n{detalhes_str}\n"
                
                disciplinas_para_analise.append({
                    'nome': disciplina,
                    'sigla': sigla_disc,
                    'media': media_disciplina,
                    'media_municipal': media_municipal_disc,
                    'dados_detalhados': dados_detalhados
                })
            
            # Preencher o template do prompt
            prompt = NOTA_ANALYSIS_PROMPT_TEMPLATE.replace(
                "{NOTA_REFERENCE_TABLE}", NOTA_REFERENCE_TABLE
            ).replace(
                "[Ano/Série]",
                ano_serie
            ).replace(
                "[Avaliação]",
                avaliacao_titulo or "Avaliação Diagnóstica"
            ).replace(
                "- Entidade/Nível: [Entidade/Nível]",
                f"- Entidade/Nível: {entidade_nivel}"
            ).replace(
                "- Avaliação: [AVALIAÇÃO: ex: Avaliação Diagnóstica 2025.1]",
                f"- Avaliação: {avaliacao_titulo or 'Avaliação Diagnóstica'}"
            ).replace(
                "- Ano/Série: [Ano/Série]",
                f"- Ano/Série: {ano_serie}"
            ).replace(
                "{Dados por Disciplina}",
                dados_disciplinas_str
            ).replace(
                "- Média Geral (Todas as Disciplinas): [Média]",
                f"- Média Geral (Todas as Disciplinas): {media_geral_total:.2f}"
            ).replace(
                "- Benchmark (Média Municipal): [Média Municipal]",
                f"- Benchmark (Média Municipal): {media_municipal_geral:.2f}" if media_municipal_geral > 0 else "- Benchmark (Média Municipal): Não disponível"
            ).replace(
                "2. Análise por Disciplina e Turma",
                f"2. Análise por Disciplina e {label_unidade}"
            ).replace(
                "entre disciplinas (LP vs MT) e entre turmas",
                f"entre disciplinas (LP vs MT) e entre {label_unidade.lower()}s"
            ).replace(
                "onde o reforço é mais necessário",
                "onde o reforço é mais necessário"
            )
            
            response = self._call_openai(prompt)
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"Erro na análise de notas: {str(e)}")
            return "Análise de notas não disponível."
    
    def _obter_ano_serie(self, report_data: Dict[str, Any]) -> str:
        """Obtém o ano/série da avaliação (5º Ano ou 9º Ano)"""
        try:
            # Tentar obter do test.course se disponível
            avaliacao = report_data.get('avaliacao', {})
            course_name = avaliacao.get('course_name', '') or avaliacao.get('course', '')
            
            # Mapear nomes comuns de cursos para ano/série
            course_name_lower = str(course_name).lower()
            if '5' in course_name_lower or 'quinto' in course_name_lower or 'anos iniciais' in course_name_lower:
                return "5º Ano"
            elif '9' in course_name_lower or 'nono' in course_name_lower or 'anos finais' in course_name_lower:
                return "9º Ano"
            else:
                # Padrão: assumir 9º ano se não conseguir determinar
                return "9º Ano"
        except Exception as e:
            self.logger.warning(f"Erro ao obter ano/série: {str(e)}")
            return "9º Ano"  # Padrão
    
    def _mapear_disciplina_para_sigla(self, disciplina: str) -> str:
        """Mapeia nome da disciplina para sigla SAEB (LP ou MT)"""
        disciplina_lower = disciplina.lower()
        if 'portugu' in disciplina_lower or 'língua' in disciplina_lower:
            return "LP"
        elif 'matemática' in disciplina_lower or 'matematica' in disciplina_lower:
            return "MT"
        else:
            return "LP"  # Padrão
    
    def _analyze_proficiency_disciplinas(self, report_data: Dict[str, Any], avaliacao_titulo: str = "") -> Dict[str, str]:
        """
        Analisa proficiência por disciplina (exceto GERAL)
        
        Args:
            report_data: Dados completos do relatório
            avaliacao_titulo: Título da avaliação
            
        Returns:
            Dict com análise por disciplina: {disciplina: análise_texto}
        """
        try:
            proficiencia = report_data.get('proficiencia', {})
            
            if not proficiencia:
                return {}
            
            prof_disciplinas = proficiencia.get('por_disciplina', {})
            media_municipal_por_disc = proficiencia.get('media_municipal_por_disciplina', {})
            
            if not prof_disciplinas:
                return {}
            
            # Obter scope_type para determinar se é municipal (escolas) ou escola (turmas)
            scope_type = report_data.get('scope_type', 'all')
            
            # Obter ano/série
            ano_serie = self._obter_ano_serie(report_data)
            
            analises_por_disciplina = {}
            
            # Processar cada disciplina (exceto GERAL)
            for disciplina, dados in prof_disciplinas.items():
                if disciplina == 'GERAL':
                    continue
                
                # Obter média geral da disciplina
                media_geral = dados.get('media_geral', 0)
                
                if media_geral == 0:
                    continue
                
                # Obter média municipal (se disponível)
                media_municipal = media_municipal_por_disc.get(disciplina, 0)
                
                # Mapear disciplina para sigla SAEB
                sigla_disc = self._mapear_disciplina_para_sigla(disciplina)
                
                # Determinar o campo correto baseado no scope_type
                if scope_type == 'city':
                    # Relatório municipal: usar dados por escola
                    dados_detalhados = dados.get('por_escola', [])
                    tipo_unidade = "escola"
                    label_unidade = "Escola"
                else:
                    # Relatório de escola: usar dados por turma
                    dados_detalhados = dados.get('por_turma', [])
                    tipo_unidade = "turma"
                    label_unidade = "Turma"
                
                # Formatar dados detalhados para o prompt
                resultados_detalhados_str = ""
                if dados_detalhados:
                    detalhes_list = []
                    for detalhe_data in dados_detalhados:
                        nome_unidade = detalhe_data.get(tipo_unidade, 'N/A')
                        if scope_type == 'city':
                            # Para escolas, usar 'media' ao invés de 'proficiencia'
                            prof_value = detalhe_data.get('media', detalhe_data.get('proficiencia', 0))
                        else:
                            # Para turmas, usar 'proficiencia'
                            prof_value = detalhe_data.get('proficiencia', 0)
                        detalhes_list.append(f"  - {nome_unidade}: {prof_value:.2f}")
                    resultados_detalhados_str = "\n".join(detalhes_list)
                else:
                    resultados_detalhados_str = f"  Nenhum dado por {tipo_unidade} disponível"
                
                # Preencher o template do prompt
                prompt = PROFICIENCY_ANALYSIS_PROMPT_TEMPLATE.replace(
                    "{SAEB_PROFICIENCY_REFERENCE_TABLE}", SAEB_PROFICIENCY_REFERENCE_TABLE
                ).replace(
                    "[Disciplina]",
                    disciplina
                ).replace(
                    "[Ano/Série]",
                    ano_serie
                ).replace(
                    "[Avaliação]",
                    avaliacao_titulo or "Avaliação Diagnóstica"
                ).replace(
                    "- Ano/Série: [Ano/Série: 5º Ano ou 9º Ano]",
                    f"- Ano/Série: {ano_serie}"
                ).replace(
                    "- Disciplina: [Disciplina: LP ou MT]",
                    f"- Disciplina: {sigla_disc} (sigla SAEB para {disciplina})"
                ).replace(
                    "- Avaliação: [AVALIAÇÃO: ex: Avaliação 2025.1]",
                    f"- Avaliação: {avaliacao_titulo or 'Avaliação Diagnóstica'}"
                ).replace(
                    "- Média Geral da Rede/Escola: [Média]",
                    f"- Média Geral da Rede/Escola: {media_geral:.2f}"
                ).replace(
                    "- Média Municipal/Benchmark (se disponível): [Média Municipal]",
                    f"- Média Municipal/Benchmark (se disponível): {media_municipal:.2f}" if media_municipal > 0 else "- Média Municipal/Benchmark (se disponível): Não disponível"
                ).replace(
                    "{Resultados por Turma}",
                    resultados_detalhados_str
                ).replace(
                    "4. ANÁLISE POR TURMA",
                    f"4. ANÁLISE POR {label_unidade.upper()}"
                ).replace(
                    "classificar cada uma individualmente",
                    f"classificar cada {label_unidade.lower()} individualmente"
                ).replace(
                    "apontar disparidades entre elas",
                    f"apontar disparidades entre elas"
                )
                
                try:
                    response = self._call_openai(prompt)
                    analises_por_disciplina[disciplina] = response.strip()
                except Exception as e:
                    self.logger.error(f"Erro ao gerar análise de proficiência para {disciplina}: {str(e)}")
                    analises_por_disciplina[disciplina] = f"Análise não disponível para {disciplina}."
            
            return analises_por_disciplina
            
        except Exception as e:
            self.logger.error(f"Erro na análise de proficiência: {str(e)}")
            return {}
    
    def _analyze_niveis_aprendizagem_disciplinas(self, report_data: Dict[str, Any], avaliacao_titulo: str = "") -> Dict[str, str]:
        """
        Analisa níveis de aprendizagem por disciplina (exceto GERAL)
        
        Args:
            report_data: Dados completos do relatório
            avaliacao_titulo: Título da avaliação
            
        Returns:
            Dict com análise por disciplina: {disciplina: análise_texto}
        """
        try:
            niveis_aprendizagem = report_data.get('niveis_aprendizagem', {})
            
            if not niveis_aprendizagem:
                return {}
            
            analises_por_disciplina = {}
            
            # Processar cada disciplina (exceto GERAL)
            for disciplina, dados in niveis_aprendizagem.items():
                if disciplina == 'GERAL':
                    continue
                
                # Obter dados gerais da disciplina (total)
                disc_data = dados.get('geral') or dados.get('total_geral', {})
                
                if not disc_data:
                    continue
                
                total_alunos = disc_data.get('total', 0)
                
                if total_alunos == 0:
                    continue
                
                abaixo_basico = disc_data.get('abaixo_do_basico', 0)
                basico = disc_data.get('basico', 0)
                adequado = disc_data.get('adequado', 0)
                avancado = disc_data.get('avancado', 0)
                
                # Calcular percentuais
                perc_abaixo = (abaixo_basico / total_alunos * 100) if total_alunos > 0 else 0
                perc_basico = (basico / total_alunos * 100) if total_alunos > 0 else 0
                perc_adequado = (adequado / total_alunos * 100) if total_alunos > 0 else 0
                perc_avancado = (avancado / total_alunos * 100) if total_alunos > 0 else 0
                
                # Preencher o template do prompt (ordem importa)
                prompt = NIVEIS_APRENDIZAGEM_ANALYSIS_PROMPT_TEMPLATE.replace(
                    "[DISCIPLINA]",
                    disciplina
                ).replace(
                    "[Avaliação]",
                    avaliacao_titulo or "Avaliação Diagnóstica"
                ).replace(
                    "[Disciplina]",
                    disciplina
                ).replace(
                    "[Série/Ano]",
                    "9º ano"  # Pode ser ajustado dinamicamente no futuro
                ).replace(
                    "- Disciplina: [PREENCHER DISCIPLINA: ex: Matemática / Língua Portuguesa]",
                    f"- Disciplina: {disciplina}"
                ).replace(
                    "- Avaliação: [AVALIAÇÃO: ex: Avaliação Diagnóstica 2025.1]",
                    f"- Avaliação: {avaliacao_titulo or 'Avaliação Diagnóstica'}"
                ).replace(
                    "- Total de alunos avaliados: [Nº]",
                    f"- Total de alunos avaliados: {total_alunos}"
                ).replace(
                    "- Abaixo do Básico: [Nº] alunos ([__]%)",
                    f"- Abaixo do Básico: {abaixo_basico} alunos ({perc_abaixo:.1f}%)"
                ).replace(
                    "- Básico: [Nº] alunos ([__]%)",
                    f"- Básico: {basico} alunos ({perc_basico:.1f}%)"
                ).replace(
                    "- Adequado: [Nº] alunos ([__]%)",
                    f"- Adequado: {adequado} alunos ({perc_adequado:.1f}%)"
                ).replace(
                    "- Avançado: [Nº] alunos ([__]%)",
                    f"- Avançado: {avancado} alunos ({perc_avancado:.1f}%)"
                )
                
                try:
                    response = self._call_openai(prompt)
                    analises_por_disciplina[disciplina] = response.strip()
                except Exception as e:
                    self.logger.error(f"Erro ao gerar análise de níveis para {disciplina}: {str(e)}")
                    analises_por_disciplina[disciplina] = f"Análise não disponível para {disciplina}."
            
            return analises_por_disciplina
            
        except Exception as e:
            self.logger.error(f"Erro na análise de níveis de aprendizagem: {str(e)}")
            return {}
    
    def _format_detailed_participation_data(self, dados_detalhados: list, unidade: str) -> str:
        """Formata dados detalhados de participação para o prompt"""
        if not dados_detalhados:
            return "Nenhum dado detalhado disponível."
        
        formatted_data = []
        for item in dados_detalhados:
            nome = item.get(unidade, 'N/A')
            matriculados = item.get('matriculados', 0)
            avaliados = item.get('avaliados', 0)
            percentual = item.get('percentual', 0)
            faltosos = item.get('faltosos', 0)
            
            formatted_data.append(f"- {nome}: {avaliados} de {matriculados} ({percentual}%) - {faltosos} faltosos")
        
        return "\n".join(formatted_data)
    
    def _prepare_proficiency_data(self, proficiencia: dict, unidade: str) -> str:
        """Prepara dados de proficiência para análise"""
        try:
            prof_disciplinas = proficiencia.get('por_disciplina', {})
            
            if not prof_disciplinas:
                return "Nenhum dado de proficiência disponível."
            
            data_lines = []
            
            for disciplina, dados in prof_disciplinas.items():
                if disciplina == 'GERAL':
                    continue
                    
                data_lines.append(f"\n{disciplina.upper()}:")
                
                # Dados por unidade
                dados_unidade = dados.get(f'por_{unidade}', [])
                if dados_unidade:
                    for item in dados_unidade:
                        nome = item.get(unidade, 'N/A')
                        media = item.get('media', 0)
                        total_alunos = item.get('total_alunos', 0)
                        data_lines.append(f"  - {nome}: {media} (média) - {total_alunos} alunos")
                
                # Média geral
                media_geral = dados.get('media_geral', 0)
                if media_geral > 0:
                    data_lines.append(f"  - Média geral: {media_geral}")
            
            return "\n".join(data_lines) if data_lines else "Nenhum dado de proficiência disponível."
            
        except Exception as e:
            self.logger.error(f"Erro ao preparar dados de proficiência: {str(e)}")
            return "Erro ao processar dados de proficiência."
    
    def _prepare_grades_data(self, notas: dict, unidade: str) -> str:
        """Prepara dados de notas para análise"""
        try:
            notas_disciplinas = notas.get('por_disciplina', {})
            
            if not notas_disciplinas:
                return "Nenhum dado de notas disponível."
            
            data_lines = []
            
            for disciplina, dados in notas_disciplinas.items():
                if disciplina == 'GERAL':
                    continue
                    
                data_lines.append(f"\n{disciplina.upper()}:")
                
                # Dados por unidade
                dados_unidade = dados.get(f'por_{unidade}', [])
                if dados_unidade:
                    for item in dados_unidade:
                        nome = item.get(unidade, 'N/A')
                        media = item.get('media', 0)
                        total_alunos = item.get('total_alunos', 0)
                        data_lines.append(f"  - {nome}: {media} (média) - {total_alunos} alunos")
                
                # Média geral
                media_geral = dados.get('media_geral', 0)
                if media_geral > 0:
                    data_lines.append(f"  - Média geral: {media_geral}")
            
            return "\n".join(data_lines) if data_lines else "Nenhum dado de notas disponível."
            
        except Exception as e:
            self.logger.error(f"Erro ao preparar dados de notas: {str(e)}")
            return "Erro ao processar dados de notas."
    
    def _generate_specific_prompt(self, analysis_data: Dict[str, Any]) -> str:
        """Gera prompt específico para esta análise"""
        
        # Dados de participação
        participacao = analysis_data.get('participacao', {})
        total_mat = participacao.get('total_matriculados', 0)
        total_av = participacao.get('total_avaliados', 0)
        total_falt = participacao.get('total_faltosos', 0)
        percentual = participacao.get('percentual_participacao', 0)
        
        # Dados de proficiência
        proficiencia = analysis_data.get('proficiencia', {})
        prof_disciplinas = proficiencia.get('por_disciplina', {})
        prof_municipal = proficiencia.get('media_municipal', {})
        
        # Dados de notas
        notas = analysis_data.get('notas', {})
        notas_disciplinas = notas.get('por_disciplina', {})
        notas_municipal = notas.get('media_municipal', {})
        
        # Dados de habilidades
        habilidades = analysis_data.get('habilidades', {})
        habilidades_disciplinas = habilidades.get('por_disciplina', {})
        questoes_anuladas = habilidades.get('questoes_anuladas', [])
        
        specific_prompt = f"""
{ANALYSIS_PROMPT_BASE}

ANALISE OS SEGUINTES DADOS ESPECÍFICOS:

PARTICIPAÇÃO:
- Total matriculados: {total_mat}
- Total avaliados: {total_av}
- Total faltosos: {total_falt}
- Percentual de participação: {percentual}%

PROFICIÊNCIA:
{self._format_proficiencia_data(prof_disciplinas, prof_municipal)}

NOTAS:
{self._format_notas_data(notas_disciplinas, notas_municipal)}

HABILIDADES:
{self._format_habilidades_data(habilidades_disciplinas)}

QUESTÕES ANULADAS: {questoes_anuladas}

Gere análises específicas baseadas nestes dados reais, com foco nos pontos críticos 
e recomendações práticas para a escola.
"""
        
        return specific_prompt
    
    def _format_proficiencia_data(self, prof_disciplinas: Dict, prof_municipal: Dict) -> str:
        """Formata dados de proficiência para o prompt"""
        if not prof_disciplinas:
            return "Dados de proficiência não disponíveis"
        
        formatted = "Dados de proficiência por disciplina:\n"
        for disciplina, dados in prof_disciplinas.items():
            if disciplina != 'GERAL':
                media_geral = dados.get('media_geral', 0)
                media_municipal = prof_municipal.get(disciplina, 0)
                formatted += f"- {disciplina}: Média escola {media_geral}, Média municipal {media_municipal}\n"
        
        return formatted
    
    def _format_notas_data(self, notas_disciplinas: Dict, notas_municipal: Dict) -> str:
        """Formata dados de notas para o prompt"""
        if not notas_disciplinas:
            return "Dados de notas não disponíveis"
        
        formatted = "Dados de notas por disciplina:\n"
        for disciplina, dados in notas_disciplinas.items():
            if disciplina != 'GERAL':
                media_geral = dados.get('media_geral', 0)
                media_municipal = notas_municipal.get(disciplina, 0)
                formatted += f"- {disciplina}: Média escola {media_geral}, Média municipal {media_municipal}\n"
        
        return formatted
    
    def _format_habilidades_data(self, habilidades_disciplinas: Dict) -> str:
        """Formata dados de habilidades para o prompt"""
        if not habilidades_disciplinas:
            return "Dados de habilidades não disponíveis"
        
        formatted = "Dados de habilidades por disciplina:\n"
        for disciplina, dados in habilidades_disciplinas.items():
            if disciplina != 'GERAL' and 'habilidades' in dados:
                habilidades = dados['habilidades']
                formatted += f"- {disciplina}:\n"
                for hab in habilidades[:5]:  # Primeiras 5 habilidades
                    codigo = hab.get('codigo', 'N/A')
                    percentual = hab.get('percentual', 0)
                    formatted += f"  * {codigo}: {percentual}% de acertos\n"
        
        return formatted
    
    def _call_openai(self, prompt: str) -> str:
        """Chama API de IA (OpenAI ou Gemini)"""
        try:
            system_prompt = "Você é um especialista em educação e análise de dados educacionais. Sempre gere texto humanizado e profissional, SEM usar formatação markdown (sem #, ##, *, **, etc). Use apenas parágrafos normais e títulos em maiúsculas seguidos de dois pontos."
            
            if self.use_gemini and self.gemini_model:
                # Usar Gemini
                try:
                    # Combinar system prompt com user prompt para Gemini
                    full_prompt = f"{system_prompt}\n\n{prompt}"
                    
                    response = self.gemini_model.generate_content(
                        full_prompt,
                        generation_config={
                            "temperature": CONTEXT_SETTINGS['temperature'],
                            "max_output_tokens": CONTEXT_SETTINGS['max_tokens'],
                        }
                    )
                    
                    # Extrair texto da resposta
                    if hasattr(response, 'text'):
                        return response.text
                    elif hasattr(response, 'candidates') and len(response.candidates) > 0:
                        return response.candidates[0].content.parts[0].text
                    else:
                        raise Exception("Resposta do Gemini em formato inesperado")
                        
                except Exception as e:
                    self.logger.error(f"Erro ao chamar Gemini: {str(e)}")
                    # Tentar fallback para OpenAI se disponível
                    if self.client:
                        self.logger.info("Tentando fallback para OpenAI...")
                        self.use_gemini = False
                        return self._call_openai_openai(prompt)
                    raise
            else:
                # Usar OpenAI (código original)
                return self._call_openai_openai(prompt)
                
        except Exception as e:
            self.logger.error(f"Erro ao chamar API de IA: {str(e)}")
            raise
    
    def _call_openai_openai(self, prompt: str) -> str:
        """Chama OpenAI API (método auxiliar)"""
        if not self.client:
            raise Exception("Cliente OpenAI não está disponível")
            
        response = self.client.chat.completions.create(
            model=CONTEXT_SETTINGS['model'],
            messages=[
                {
                    "role": "system", 
                    "content": "Você é um especialista em educação e análise de dados educacionais. Sempre gere texto humanizado e profissional, SEM usar formatação markdown (sem #, ##, *, **, etc). Use apenas parágrafos normais e títulos em maiúsculas seguidos de dois pontos."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=CONTEXT_SETTINGS['max_tokens'],
            temperature=CONTEXT_SETTINGS['temperature']
        )
        
        return response.choices[0].message.content
    
    def _process_ai_response(self, ai_response: str) -> Dict[str, str]:
        """Processa resposta da IA e organiza em seções"""
        try:
            # Dividir resposta em seções baseado em marcadores
            sections = {
                'participacao_analise': '',
                'proficiencia_analise': '',
                'notas_analise': '',
                'habilidades_analise': '',
                'recomendacoes_gerais': ''
            }
            
            # Processar resposta da IA (implementação básica)
            # Em uma versão mais avançada, poderíamos usar parsing mais sofisticado
            if ai_response:
                # Dividir por parágrafos e atribuir às seções
                paragraphs = ai_response.split('\n\n')
                
                if len(paragraphs) >= 1:
                    sections['participacao_analise'] = paragraphs[0]
                if len(paragraphs) >= 2:
                    sections['proficiencia_analise'] = paragraphs[1]
                if len(paragraphs) >= 3:
                    sections['notas_analise'] = paragraphs[2]
                if len(paragraphs) >= 4:
                    sections['habilidades_analise'] = paragraphs[3]
                if len(paragraphs) >= 5:
                    sections['recomendacoes_gerais'] = '\n\n'.join(paragraphs[4:])
            
            return sections
            
        except Exception as e:
            self.logger.error(f"Erro ao processar resposta da IA: {str(e)}")
            return self._get_fallback_texts()
    
    def _build_unified_prompt(self, report_data: Dict[str, Any], analysis_data: Dict[str, Any], 
                             avaliacao_titulo: str, scope_type: str) -> str:
        """
        Constrói um prompt unificado que solicita todas as análises de uma vez.
        
        Args:
            report_data: Dados completos do relatório
            analysis_data: Dados preparados para análise
            avaliacao_titulo: Título da avaliação
            scope_type: Tipo de escopo (overall, city, school, teacher)
            
        Returns:
            String com o prompt completo
        """
        participacao = analysis_data.get('participacao', {})
        proficiencia = report_data.get('proficiencia', {})
        nota_geral = report_data.get('nota_geral', {})
        niveis_aprendizagem = report_data.get('niveis_aprendizagem', {})
        
        # Dados de participação
        total_matriculados = participacao.get('total_matriculados', 0)
        total_avaliados = participacao.get('total_avaliados', 0)
        total_faltosos = participacao.get('total_faltosos', 0)
        percentual_participacao = participacao.get('percentual_participacao', 0)
        dados_detalhados_participacao = participacao.get('por_turma', []) if scope_type != 'city' else participacao.get('por_escola', [])
        
        # Determinar contexto
        if scope_type == 'city':
            entidade = "Município"
            unidade_nome = "escola"
            unidade_label = "Escola"
        else:
            entidade = "Escola"
            unidade_nome = "turma"
            unidade_label = "Turma"
        
        # Identificar destaques e pontos de atenção para participação
        destaques = []
        pontos_atencao = []
        for item in dados_detalhados_participacao:
            nome = item.get(unidade_nome, 'N/A')
            avaliados = item.get('avaliados', 0)
            matriculados = item.get('matriculados', 0)
            faltosos = item.get('faltosos', 0)
            percentual_item = item.get('percentual', 0)
            
            if percentual_item >= 95:
                destaques.append(f"{nome}: {percentual_item:.0f}% ({avaliados}/{matriculados})")
            if percentual_item < 80 or faltosos > 0:
                if faltosos > 0:
                    pontos_atencao.append(f"{nome}: {percentual_item:.0f}% ({avaliados}/{matriculados}) com {faltosos} faltoso(s)")
                else:
                    pontos_atencao.append(f"{nome}: {percentual_item:.0f}% ({avaliados}/{matriculados})")
        
        destaque_str = " ".join(destaques) if destaques else "Nenhum destaque específico"
        atencao_str = "; ".join(pontos_atencao) if pontos_atencao else "Nenhum ponto de atenção específico"
        
        # Dados de proficiência por disciplina
        prof_disciplinas = proficiencia.get('por_disciplina', {})
        media_municipal_prof = proficiencia.get('media_municipal_por_disciplina', {})
        prof_data_str = ""
        for disciplina, dados in prof_disciplinas.items():
            if disciplina == 'GERAL':
                continue
            media_geral = dados.get('media_geral', 0)
            media_municipal = media_municipal_prof.get(disciplina, 0)
            dados_detalhados = dados.get('por_turma', []) if scope_type != 'city' else dados.get('por_escola', [])
            detalhes_list = []
            for detalhe in dados_detalhados:
                nome_unidade = detalhe.get(unidade_nome, 'N/A')
                prof_value = detalhe.get('proficiencia', detalhe.get('media', 0))
                detalhes_list.append(f"  - {nome_unidade}: {prof_value:.2f}")
            detalhes_str = "\n".join(detalhes_list) if detalhes_list else f"  Nenhum dado por {unidade_nome} disponível"
            prof_data_str += f"\n{disciplina}:\n  - Média Geral: {media_geral:.2f}\n"
            if media_municipal > 0:
                prof_data_str += f"  - Média Municipal: {media_municipal:.2f}\n"
            prof_data_str += f"  - Resultados por {unidade_label}:\n{detalhes_str}\n"
        
        # Dados de notas
        notas_disciplinas = nota_geral.get('por_disciplina', {})
        media_municipal_notas = nota_geral.get('media_municipal_por_disciplina', {})
        notas_data_str = ""
        media_geral_total = notas_disciplinas.get('GERAL', {}).get('media_geral', 0)
        media_municipal_geral = media_municipal_notas.get('GERAL', 0)
        for disciplina, dados in notas_disciplinas.items():
            if disciplina == 'GERAL':
                continue
            media_disciplina = dados.get('media_geral', 0)
            media_municipal_disc = media_municipal_notas.get(disciplina, 0)
            dados_detalhados = dados.get('por_turma', []) if scope_type != 'city' else dados.get('por_escola', [])
            detalhes_list = []
            for detalhe in dados_detalhados:
                nome_unidade = detalhe.get(unidade_nome, 'N/A')
                nota_value = detalhe.get('nota', detalhe.get('media', 0))
                detalhes_list.append(f"  - {nome_unidade}: {nota_value:.2f}")
            detalhes_str = "\n".join(detalhes_list) if detalhes_list else f"  Nenhum dado por {unidade_nome} disponível"
            notas_data_str += f"\n{disciplina}:\n  - Média Geral: {media_disciplina:.2f}\n"
            if media_municipal_disc > 0:
                notas_data_str += f"  - Média Municipal: {media_municipal_disc:.2f}\n"
            notas_data_str += f"  - Notas por {unidade_label}:\n{detalhes_str}\n"
        
        # Dados de níveis de aprendizagem por disciplina
        niveis_data_str = ""
        for disciplina, dados in niveis_aprendizagem.items():
            if disciplina == 'GERAL':
                continue
            disc_data = dados.get('geral') or dados.get('total_geral', {})
            if not disc_data:
                continue
            total_alunos = disc_data.get('total', 0)
            if total_alunos == 0:
                continue
            abaixo_basico = disc_data.get('abaixo_do_basico', 0)
            basico = disc_data.get('basico', 0)
            adequado = disc_data.get('adequado', 0)
            avancado = disc_data.get('avancado', 0)
            perc_abaixo = (abaixo_basico / total_alunos * 100) if total_alunos > 0 else 0
            perc_basico = (basico / total_alunos * 100) if total_alunos > 0 else 0
            perc_adequado = (adequado / total_alunos * 100) if total_alunos > 0 else 0
            perc_avancado = (avancado / total_alunos * 100) if total_alunos > 0 else 0
            niveis_data_str += f"\n{disciplina}:\n"
            niveis_data_str += f"  - Total de alunos: {total_alunos}\n"
            niveis_data_str += f"  - Abaixo do Básico: {abaixo_basico} alunos ({perc_abaixo:.1f}%)\n"
            niveis_data_str += f"  - Básico: {basico} alunos ({perc_basico:.1f}%)\n"
            niveis_data_str += f"  - Adequado: {adequado} alunos ({perc_adequado:.1f}%)\n"
            niveis_data_str += f"  - Avançado: {avancado} alunos ({perc_avancado:.1f}%)\n"
        
        # Obter ano/série
        ano_serie = self._obter_ano_serie(report_data)
        
        # Formatar média municipal geral (evitar erro de formatação)
        media_municipal_geral_str = f"{media_municipal_geral:.2f}" if media_municipal_geral > 0 else "Não disponível"
        
        # Construir prompt unificado
        prompt = f"""IMPORTANTE: Você deve gerar TODAS as análises solicitadas abaixo em uma única resposta, separadas por marcadores claros.

Gere APENAS texto puro, SEM formatação markdown (sem #, ##, *, **, etc). Use apenas parágrafos normais e títulos em maiúsculas seguidos de dois pontos.

Use QUEBRAS DE LINHA DUPLAS (\\n\\n) para separar parágrafos diferentes.
Use QUEBRAS DE LINHA SIMPLES (\\n) antes de títulos ou seções importantes.

===========================================
DADOS DO RELATÓRIO
===========================================
- Entidade: {entidade}
- Avaliação: {avaliacao_titulo or 'Avaliação Diagnóstica'}
- Ano/Série: {ano_serie}
- Escopo: {scope_type}

===========================================
1. ANÁLISE DE PARTICIPAÇÃO
===========================================

DADOS DE PARTICIPAÇÃO:
- Total de Alunos Matriculados: {total_matriculados}
- Total de Alunos Avaliados: {total_avaliados}
- Total de Faltosos: {total_faltosos}
- Taxa de Participação Geral: {percentual_participacao}%
- Destaque(s) por {unidade_label}: {destaque_str}
- Ponto(s) de Atenção por {unidade_label}: {atencao_str}

TABELA DE CLASSIFICAÇÃO DE PARTICIPAÇÃO:
{PARTICIPATION_CLASSIFICATION_TABLE}

INSTRUÇÕES PARA ANÁLISE DE PARTICIPAÇÃO:
Gere um PARECER TÉCNICO DE PARTICIPAÇÃO seguindo este formato:

PARECER TÉCNICO DE PARTICIPAÇÃO: {entidade} ({avaliacao_titulo or 'Avaliação Diagnóstica'})
[Primeiro parágrafo mencionando a participação geral e os dados básicos. Use os números específicos fornecidos.]

Classificação: [Nome da Classificação]
[Segundo parágrafo explicando o que essa classificação significa em termos de engajamento e confiabilidade dos dados. Explique se podemos confiar nas médias de proficiência.]

Destaques e Recomendações:
[Mencione os destaques formatados como frases completas. Se não houver destaques, não mencione destaques.]
[Mencione as recomendações práticas focadas nos pontos de atenção, especialmente alunos faltosos. Use formato de parágrafo ou lista com bullets simples (•).]

Use a tabela acima para classificar a taxa de participação de {percentual_participacao}% e mencione a classificação encontrada no texto.

===========================================
2. ANÁLISE DE PROFICIÊNCIA POR DISCIPLINA
===========================================

TABELA DE REFERÊNCIA SAEB:
{SAEB_PROFICIENCY_REFERENCE_TABLE}

DADOS DE PROFICIÊNCIA:
{prof_data_str}

INSTRUÇÕES PARA ANÁLISE DE PROFICIÊNCIA:
Para CADA disciplina listada acima, gere um PARECER TÉCNICO DE PROFICIÊNCIA seguindo este formato:

PARECER TÉCNICO: PROFICIÊNCIA EM [Disciplina] ({ano_serie} - {avaliacao_titulo or 'Avaliação Diagnóstica'})
[Primeiro parágrafo explicando o que é proficiência na escala TRI e mencionando que a meta é o nível "Adequado"]

1. Classificação da Média Geral
[Aqui classifique a média geral de acordo com a tabela de referência e mencione o valor e a classificação encontrada]

2. Análise de Posição
[Aqui descreva onde a média se encontra em relação aos pontos de corte. Se houver benchmark municipal, mencione a distância até ele.]

3. Diagnóstico Pedagógico (INEP)
[Aqui use as definições oficiais do INEP para descrever o que essa classificação significa em termos de aprendizagem, mencionando "desempenho aquém do esperado", "significativo comprometimento", "intervenções emergenciais", etc.]

4. Análise por {unidade_label}
[Se houver dados por {unidade_nome}, classifique cada uma individualmente e aponte as disparidades. Use formato de lista com bullets simples (•).]

Use a tabela de referência acima para classificar a média geral de acordo com o ano/série e disciplina.

===========================================
3. ANÁLISE DE NOTAS
===========================================

TABELA DE REFERÊNCIA PEDAGÓGICA:
{NOTA_REFERENCE_TABLE}

DADOS DE NOTAS:
{notas_data_str}
- Média Geral (Todas as Disciplinas): {media_geral_total:.2f}
- Benchmark (Média Municipal): {media_municipal_geral_str}

INSTRUÇÕES PARA ANÁLISE DE NOTAS:
Gere um PARECER TÉCNICO DE NOTA seguindo este formato:

PARECER TÉCNICO: NOTA (0-10) - {ano_serie} ({avaliacao_titulo or 'Avaliação Diagnóstica'})
[Primeiro parágrafo explicando brevemente o que é a Nota (escala 0-10 derivada da proficiência, usada no IDEB)]

1. Classificação e Comparação (Média Geral)
[Aqui classifique a média geral usando a tabela de referência. Compare com a média municipal, com a meta e com o IDEB oficial se disponível.]

2. Análise por Disciplina e {unidade_label}
[Aqui compare o desempenho entre disciplinas (LP vs MT) e entre {unidade_label.lower()}s. Aponte disparidades e onde o reforço é mais necessário. Use formato de lista com bullets simples (•) se necessário.]

3. Conclusão e Recomendação
[Baseado apenas na análise das notas, sumarize o diagnóstico e recomende ações gerais (aulas de recuperação, avaliações formativas, metodologias ativas) para elevar o rendimento.]

Use a tabela de referência acima para classificar a média geral.

===========================================
4. ANÁLISE DE NÍVEIS DE APRENDIZAGEM POR DISCIPLINA
===========================================

DEFINIÇÕES DOS NÍVEIS (INEP - "Descritores de Padrões de Desempenho - 2025"):
1. Abaixo do Básico: Indica um desempenho "aquém do esperado", com "significativo comprometimento" das habilidades. Esses alunos têm a "trajetória académica seriamente comprometida" e necessitam de "intervenções emergenciais".
2. Básico: Indica um domínio parcial e insuficiente das habilidades. O aluno não consolidou as competências essenciais para a série e precisa de apoio para recompor a aprendizagem.
3. Adequado (A Meta): Indica o "desempenho esperado". O aluno demonstra ter "desenvolvido as habilidades previstas" e possui "condições adequadas à continuidade" de sua trajetória.
4. Avançado: Indica um "desempenho superior àquele esperado". O aluno domina "habilidades mais complexas" e necessita de "atividades mais desafiadoras".

DADOS DE NÍVEIS DE APRENDIZAGEM:
{niveis_data_str}

INSTRUÇÕES PARA ANÁLISE DE NÍVEIS:
Para CADA disciplina listada acima, gere um PARECER TÉCNICO DE NÍVEIS DE APRENDIZAGEM seguindo este formato:

PARECER TÉCNICO: NÍVEIS DE APRENDIZAGEM EM [Disciplina] ({avaliacao_titulo or 'Avaliação Diagnóstica'})
[Aqui comece o primeiro parágrafo explicando o que são os Níveis de Aprendizagem e sua importância como diagnóstico pedagógico. Em seguida, explique os 4 níveis usando as definições do INEP, deixando claro que "Adequado" é a meta esperada.]

Diagnóstico e Meta ([Disciplina] - {ano_serie})
[Segundo parágrafo apresentando os dados da avaliação e a análise do gargalo: percentual que não atingiu a meta vs percentual que atingiu a meta, com detalhamento por nível]

Conclusão: [Conclusão diagnosticando onde está o maior desafio (gargalo) para esta disciplina]

Calcule e apresente claramente:
- O percentual total de alunos que NÃO ATINGIRAM A META (soma de Abaixo do Básico + Básico)
- O percentual total de alunos que ATINGIRAM A META (soma de Adequado + Avançado)
- Detalhe cada nível com números específicos (ex: "42% (19 alunos) estão no nível Abaixo do Básico")

===========================================
FORMATO DA RESPOSTA
===========================================

Sua resposta deve seguir EXATAMENTE este formato, usando os marcadores abaixo para separar as seções:

[MARCADOR: PARTICIPACAO]
[Análise completa de participação aqui]

[MARCADOR: PROFICIENCIA]
[Para cada disciplina, use o formato:]
[DISCIPLINA: Nome da Disciplina]
[Análise de proficiência para esta disciplina]

[DISCIPLINA: Próxima Disciplina]
[Análise de proficiência para esta disciplina]

[MARCADOR: NOTAS]
[Análise completa de notas aqui]

[MARCADOR: NIVEIS]
[Para cada disciplina, use o formato:]
[DISCIPLINA: Nome da Disciplina]
[Análise de níveis de aprendizagem para esta disciplina]

[DISCIPLINA: Próxima Disciplina]
[Análise de níveis de aprendizagem para esta disciplina]

IMPORTANTE: Use os marcadores exatos [MARCADOR: PARTICIPACAO], [MARCADOR: PROFICIENCIA], [MARCADOR: NOTAS], [MARCADOR: NIVEIS] e [DISCIPLINA: ...] para que possamos processar sua resposta corretamente.
"""
        return prompt
    
    def _parse_unified_response(self, unified_response: str, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa a resposta unificada da IA e extrai as diferentes seções.
        
        Args:
            unified_response: Resposta completa da IA
            report_data: Dados do relatório (para identificar disciplinas)
            
        Returns:
            Dict com as análises separadas:
            {
                'participacao': str,
                'proficiencia': Dict[str, str],
                'notas': str,
                'niveis_aprendizagem': Dict[str, str]
            }
        """
        result = {
            'participacao': '',
            'proficiencia': {},
            'notas': '',
            'niveis_aprendizagem': {}
        }
        
        try:
            # Extrair seção de participação
            if '[MARCADOR: PARTICIPACAO]' in unified_response:
                parts = unified_response.split('[MARCADOR: PARTICIPACAO]', 1)
                if len(parts) > 1:
                    participacao_section = parts[1].split('[MARCADOR: PROFICIENCIA]', 1)[0]
                    result['participacao'] = participacao_section.strip()
            
            # Extrair seção de proficiência
            if '[MARCADOR: PROFICIENCIA]' in unified_response:
                parts = unified_response.split('[MARCADOR: PROFICIENCIA]', 1)
                if len(parts) > 1:
                    prof_section = parts[1].split('[MARCADOR: NOTAS]', 1)[0]
                    # Extrair todas as disciplinas usando regex
                    disciplina_pattern = r'\[DISCIPLINA:\s*([^\]]+)\]'
                    matches = re.finditer(disciplina_pattern, prof_section)
                    for match in matches:
                        disciplina_nome = match.group(1).strip()
                        start_pos = match.end()
                        # Encontrar próxima disciplina ou fim da seção
                        next_match = re.search(disciplina_pattern, prof_section[start_pos:])
                        if next_match:
                            end_pos = start_pos + next_match.start()
                        else:
                            end_pos = len(prof_section)
                        disc_analysis = prof_section[start_pos:end_pos].strip()
                        result['proficiencia'][disciplina_nome] = disc_analysis
            
            # Extrair seção de notas
            if '[MARCADOR: NOTAS]' in unified_response:
                parts = unified_response.split('[MARCADOR: NOTAS]', 1)
                if len(parts) > 1:
                    notas_section = parts[1].split('[MARCADOR: NIVEIS]', 1)[0]
                    result['notas'] = notas_section.strip()
            
            # Extrair seção de níveis
            if '[MARCADOR: NIVEIS]' in unified_response:
                parts = unified_response.split('[MARCADOR: NIVEIS]', 1)
                if len(parts) > 1:
                    niveis_section = parts[1]
                    # Extrair todas as disciplinas usando regex
                    disciplina_pattern = r'\[DISCIPLINA:\s*([^\]]+)\]'
                    matches = re.finditer(disciplina_pattern, niveis_section)
                    for match in matches:
                        disciplina_nome = match.group(1).strip()
                        start_pos = match.end()
                        # Encontrar próxima disciplina ou fim da seção
                        next_match = re.search(disciplina_pattern, niveis_section[start_pos:])
                        if next_match:
                            end_pos = start_pos + next_match.start()
                        else:
                            end_pos = len(niveis_section)
                        disc_analysis = niveis_section[start_pos:end_pos].strip()
                        result['niveis_aprendizagem'][disciplina_nome] = disc_analysis
            
            # Fallback: se não encontrou marcadores, tentar parsing mais flexível
            if not result['participacao'] and not result['proficiencia']:
                self.logger.warning("Marcadores não encontrados na resposta da IA, tentando parsing alternativo")
                # Dividir por seções comuns
                sections = unified_response.split('\n\n\n')
                if len(sections) >= 1:
                    result['participacao'] = sections[0][:500] if sections[0] else ''
                if len(sections) >= 2:
                    result['notas'] = sections[1][:500] if sections[1] else ''
            
        except Exception as e:
            self.logger.error(f"Erro ao processar resposta unificada: {str(e)}", exc_info=True)
            # Retornar fallback
            return self._get_fallback_texts()
        
        # Garantir que pelo menos temos fallback para campos vazios
        if not result['participacao']:
            result['participacao'] = 'Análise de participação não disponível no momento.'
        if not result['notas']:
            result['notas'] = 'Análise de notas não disponível no momento.'
        if not result['proficiencia']:
            # Tentar obter disciplinas do report_data
            prof_disciplinas = report_data.get('proficiencia', {}).get('por_disciplina', {})
            for disciplina in prof_disciplinas.keys():
                if disciplina != 'GERAL':
                    result['proficiencia'][disciplina] = f'Análise de proficiência não disponível para {disciplina}.'
        if not result['niveis_aprendizagem']:
            # Tentar obter disciplinas do report_data
            niveis_disciplinas = report_data.get('niveis_aprendizagem', {})
            for disciplina in niveis_disciplinas.keys():
                if disciplina != 'GERAL':
                    result['niveis_aprendizagem'][disciplina] = f'Análise de níveis não disponível para {disciplina}.'
        
        return result
    
    def _get_fallback_texts(self) -> Dict[str, Any]:
        """Retorna textos padrão em caso de erro"""
        return {
            'participacao': 'Análise de participação não disponível no momento.',
            'proficiencia': {},
            'notas': 'Análise de notas não disponível no momento.',
            'niveis_aprendizagem': {}
        }
