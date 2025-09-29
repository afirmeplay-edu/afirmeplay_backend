# -*- coding: utf-8 -*-
"""
Serviço para análise de relatórios usando OpenAI
"""

import logging
from typing import Dict, Any, Optional
from app.openai_config.openai_config import get_openai_client, ANALYSIS_PROMPT_BASE, CONTEXT_SETTINGS

class AIAnalysisService:
    """Serviço para análise de relatórios usando IA"""
    
    def __init__(self):
        self.client = get_openai_client()
        self.logger = logging.getLogger(__name__)
    
    def analyze_report_data(self, report_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Analisa dados do relatório e gera textos usando OpenAI
        
        Args:
            report_data: Dados do relatório completo
            
        Returns:
            Dict com textos analíticos gerados pela IA
        """
        try:
            # Preparar dados para análise
            analysis_data = self._prepare_analysis_data(report_data)
            
            # Gerar análises específicas para cada página
            analysis_texts = {}
            
            # Análise da página 4 - Participação
            analysis_texts['participacao'] = self._analyze_participation(analysis_data, report_data.get('scope_type', 'all'))
            
            # Análise da página 6 - Proficiência
            analysis_texts['proficiencia'] = self._analyze_proficiency(analysis_data, report_data.get('scope_type', 'all'))
            
            # Análise da página 6 - Notas
            analysis_texts['notas'] = self._analyze_grades(analysis_data, report_data.get('scope_type', 'all'))
            
            return analysis_texts
            
        except Exception as e:
            self.logger.error(f"Erro na análise da IA: {str(e)}")
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
    
    def _analyze_participation(self, analysis_data: Dict[str, Any], scope_type: str) -> str:
        """Analisa dados de participação (Página 4)"""
        try:
            participacao = analysis_data.get('participacao', {})
            total_matriculados = participacao.get('total_matriculados', 0)
            total_avaliados = participacao.get('total_avaliados', 0)
            total_faltosos = participacao.get('total_faltosos', 0)
            percentual_participacao = participacao.get('percentual_participacao', 0)
            
            # Dados por escola/turma
            dados_detalhados = participacao.get('por_turma', []) if scope_type != 'city' else participacao.get('por_escola', [])
            
            # Determinar contexto
            if scope_type == 'city':
                contexto = "município"
                unidade = "escola"
                unidade_plural = "escolas"
            else:
                contexto = "escola"
                unidade = "turma"
                unidade_plural = "turmas"
            
            # Gerar prompt específico para participação
            prompt = f"""
            Analise os dados de participação de uma avaliação educacional e gere uma análise resumida e construtiva.
            
            DADOS:
            - Total de alunos matriculados: {total_matriculados}
            - Total de alunos avaliados: {total_avaliados}
            - Total de alunos faltosos: {total_faltosos}
            - Percentual de participação: {percentual_participacao}%
            - Dados por {unidade}:
            {self._format_detailed_participation_data(dados_detalhados, unidade)}
            
            CONTEXTO: Relatório de {contexto}
            
            Gere uma análise RESUMIDA (máximo 5 linhas) que inclua:
            1. Contexto geral da participação
            2. Avaliação qualitativa da taxa de participação
            3. Principais destaques por {unidade}
            4. Recomendação principal para melhoria
            
            Use um tom profissional e construtivo. Seja conciso e específico. NÃO use formatação markdown (sem ###, ####, etc).
            """
            
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
    
    def _analyze_grades(self, analysis_data: Dict[str, Any], scope_type: str) -> str:
        """Analisa dados de notas (Página 6)"""
        try:
            notas = analysis_data.get('notas', {})
            
            if not notas:
                return "Dados de notas não disponíveis para análise."
            
            # Determinar contexto
            if scope_type == 'city':
                contexto = "município"
                unidade = "escola"
                unidade_plural = "escolas"
            else:
                contexto = "escola"
                unidade = "turma"
                unidade_plural = "turmas"
            
            # Preparar dados de notas
            notas_data = self._prepare_grades_data(notas, unidade)
            
            # Gerar prompt específico para notas
            prompt = f"""
            Analise os dados de NOTAS de uma avaliação educacional e gere uma análise resumida e construtiva.
            
            DADOS DE NOTAS:
            {notas_data}
            
            CONTEXTO: Relatório de {contexto}
            
            Gere uma análise RESUMIDA (máximo 5 linhas) que inclua:
            1. Visão geral das notas por disciplina
            2. Principais destaques entre as {unidade_plural}
            3. Pontos fortes e fracos nas notas
            4. Recomendação principal para melhoria das notas
            
            Use um tom profissional e construtivo. Seja conciso e específico. NÃO use formatação markdown (sem ###, ####, etc).
            """
            
            response = self._call_openai(prompt)
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"Erro na análise de notas: {str(e)}")
            return "Análise de notas não disponível."
    
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
        """Chama OpenAI API"""
        try:
            response = self.client.chat.completions.create(
                model=CONTEXT_SETTINGS['model'],
                messages=[
                    {"role": "system", "content": "Você é um especialista em educação e análise de dados educacionais."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=CONTEXT_SETTINGS['max_tokens'],
                temperature=CONTEXT_SETTINGS['temperature']
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"Erro ao chamar OpenAI: {str(e)}")
            raise
    
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
    
    def _get_fallback_texts(self) -> Dict[str, str]:
        """Retorna textos padrão em caso de erro"""
        return {
            'participacao_analise': 'Análise de participação não disponível no momento.',
            'proficiencia_analise': 'Análise de proficiência não disponível no momento.',
            'notas_analise': 'Análise de notas não disponível no momento.',
            'habilidades_analise': 'Análise de habilidades não disponível no momento.',
            'recomendacoes_gerais': 'Recomendações não disponíveis no momento.'
        }
