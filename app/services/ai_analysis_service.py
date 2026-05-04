# -*- coding: utf-8 -*-
"""
Serviço para análise de relatórios usando Google AI Studio (Gemini).
"""

import logging
import os
import json
import re
import unicodedata
from typing import Dict, Any, Optional, Mapping
import google.generativeai as genai
from app.openai_config.openai_config import (
    OPENROUTER_MAX_TOKENS,
    OPENROUTER_TEMPERATURE,
    ANALYSIS_PROMPT_BASE,
    PARTICIPATION_CLASSIFICATION_TABLE,
    PARTICIPATION_ANALYSIS_PROMPT_TEMPLATE,
    NIVEIS_APRENDIZAGEM_ANALYSIS_PROMPT_TEMPLATE,
    SAEB_PROFICIENCY_REFERENCE_TABLE,
    PROFICIENCY_ANALYSIS_PROMPT_TEMPLATE,
    NOTA_REFERENCE_TABLE,
    NOTA_ANALYSIS_PROMPT_TEMPLATE
)

class AIAnalysisService:
    """Serviço para análise de relatórios (Google AI Studio / Gemini)."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)

        google_key_set = bool(os.getenv("GOOGLE_AI_STUDIO_API_KEY"))
        google_model = os.getenv("GOOGLE_AI_STUDIO_MODEL", "gemini-1.5-pro")
        print(
            f"[AIAnalysisService] init | GOOGLE_AI_STUDIO_API_KEY set? {google_key_set} | "
            f"GOOGLE_AI_STUDIO_MODEL={google_model}"
        )
        print("[AIAnalysisService] init | Provedor esperado para análise: Google AI Studio (Gemini)")
    
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
                'niveis_aprendizagem': Dict[str, str],  # {disciplina: análise}
                'habilidades': Dict[str, str]  # {disciplina: análise}
            }
        """
        try:
            # Validar que temos dados mínimos necessários
            if not report_data:
                self.logger.error("report_data está vazio")
                return self._get_fallback_texts(report_data)
            
            # Validar presença de dados principais
            has_participacao = bool(report_data.get('total_alunos', {}).get('total_geral', {}).get('avaliados', 0) > 0)
            has_proficiencia = bool(report_data.get('proficiencia', {}).get('por_disciplina', {}))
            has_notas = bool(report_data.get('nota_geral', {}).get('por_disciplina', {}))
            has_niveis = bool(report_data.get('niveis_aprendizagem', {}))
            has_habilidades = bool(report_data.get('acertos_por_habilidade', {}))
            
            self.logger.info(f"Validação de dados: participacao={has_participacao}, proficiencia={has_proficiencia}, notas={has_notas}, niveis={has_niveis}, habilidades={has_habilidades}")
            
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
            
            # Validação final: garantir que todas as seções esperadas foram geradas
            self._validate_analysis_completeness(analysis_texts, report_data)
            
            return analysis_texts
            
        except Exception as e:
            self.logger.error(f"Erro na análise da IA: {str(e)}", exc_info=True)
            return self._get_fallback_texts(report_data)
    
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
            
            label_destaque = "Escola" if scope_type == "city" else "Turma"
            # Agora substituir os placeholders específicos (ordem importa para evitar substituições indevidas)
            prompt = prompt_base.replace(
                "[Entidade]",
                entidade
            ).replace(
                "[Avaliação]",
                avaliacao_titulo or "Avaliação Diagnóstica"
            ).replace(
                "Entidade: [Entidade: Ex. Escola Municipal X / 5º Ano Geral]",
                f"Entidade: {entidade}"
            ).replace(
                "Avaliação: [Avaliação: Ex: Avaliação Diagnóstica 2025.1]",
                f"Avaliação: {avaliacao_titulo or 'Avaliação Diagnóstica'}"
            ).replace(
                "Total de Alunos Matriculados: [Nº]",
                f"Total de Alunos Matriculados: {total_matriculados}"
            ).replace(
                "Total de Alunos Avaliados: [Nº]",
                f"Total de Alunos Avaliados: {total_avaliados}"
            ).replace(
                "Total de Faltosos: [Nº]",
                f"Total de Faltosos: {total_faltosos}"
            ).replace(
                "Taxa de Participação Geral: [__]%",
                f"Taxa de Participação Geral: {percentual_participacao}%"
            ).replace(
                "Destaque(s) por Turma: [Ex: 5º A - M: 95% (21/22)]",
                f"Destaque(s) por {label_destaque}: {destaque_str}"
            ).replace(
                "Ponto(s) de Atenção por Turma: [Ex: 5º B - M: 91% (21/23) com 2 faltosos]",
                f"Ponto(s) de Atenção por {label_destaque}: {atencao_str}"
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
                "Entidade/Nível: [Entidade/Nível]",
                f"Entidade/Nível: {entidade_nivel}"
            ).replace(
                "Avaliação: [AVALIAÇÃO: ex: Avaliação Diagnóstica 2025.1]",
                f"Avaliação: {avaliacao_titulo or 'Avaliação Diagnóstica'}"
            ).replace(
                "Ano/Série: [Ano/Série]",
                f"Ano/Série: {ano_serie}"
            ).replace(
                "{Dados por Disciplina}",
                dados_disciplinas_str
            ).replace(
                "Média Geral (Abrangendo todos os Componentes): [Média]",
                f"Média Geral (Abrangendo todos os Componentes): {media_geral_total:.2f}"
            ).replace(
                "Benchmark (Média da Rede Municipal): [Média Municipal]",
                f"Benchmark (Média da Rede Municipal): {media_municipal_geral:.2f}" if media_municipal_geral > 0 else "Benchmark (Média da Rede Municipal): Não disponível"
            )
            if scope_type == "city":
                prompt = prompt.replace(
                    "comportamento interturmas.",
                    "comportamento entre as unidades escolares.",
                )
            
            response = self._call_openai(prompt)
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"Erro na análise de notas: {str(e)}")
            return "Análise de notas não disponível."
    
    def _obter_ano_serie(self, report_data: Dict[str, Any]) -> str:
        """
        Resolve o rótulo de série/etapa avaliada para o parecer.
        Prioriza listas explícitas do relatório (series_label / series), depois o nome do curso.
        """
        try:
            avaliacao = report_data.get("avaliacao") or {}
            if isinstance(avaliacao, dict):
                rotulo = self._rotulo_serie_de_bloco(avaliacao)
                if rotulo:
                    return rotulo
                curso = (avaliacao.get("course_name") or avaliacao.get("course") or "").strip()
                if curso:
                    inferido = self._resolver_etapa_por_texto_curso(curso)
                    if inferido:
                        return inferido
            metadados = report_data.get("metadados") or {}
            if isinstance(metadados, dict):
                rotulo = self._rotulo_serie_de_bloco(metadados)
                if rotulo:
                    return rotulo
        except Exception as e:
            self.logger.warning("Erro ao obter ano/série: %s", e)
        return "Série não informada"

    def _rotulo_serie_de_bloco(self, bloco: Mapping[str, Any]) -> Optional[str]:
        """Extrai série a partir de chaves padronizadas do payload de relatório."""
        sl = bloco.get("series_label")
        if isinstance(sl, str) and sl.strip():
            return sl.strip()
        series = bloco.get("series")
        if isinstance(series, (list, tuple)) and series:
            partes = [str(s).strip() for s in series if s is not None and str(s).strip()]
            if partes:
                return ", ".join(dict.fromkeys(partes))
        for chave in ("grade_name", "serie", "série", "ano_serie", "grade_label"):
            v = bloco.get(chave)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    def _resolver_etapa_por_texto_curso(self, course: str) -> Optional[str]:
        """
        Infere rótulo pedagógico a partir do nome do curso/instituição quando não há series_label.
        Cobre anos numéricos, EJA, Educação Infantil, Especial e segmentos.
        """
        if not course or not str(course).strip():
            return None
        texto = str(course).strip()
        low = unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("ASCII").lower()

        # Anos escolares explícitos: "3º Ano", "3o ano", "12 º Ano"
        achados = re.findall(r"(\d{1,2})\s*[º°o]?\s*ano\b", low, flags=re.IGNORECASE)
        rotulos_ano: list = []
        for a in achados:
            try:
                n = int(a)
            except ValueError:
                continue
            if 1 <= n <= 13:
                rotulos_ano.append(f"{n}º Ano")
        if rotulos_ano:
            return ", ".join(dict.fromkeys(rotulos_ano))

        # EJA: períodos
        if "eja" in low:
            mp = re.search(r"(\d{1,2})\s*[º°o]?\s*periodo", low)
            if mp:
                try:
                    p = int(mp.group(1))
                    if 1 <= p <= 9:
                        return f"{p}º período (EJA)"
                except ValueError:
                    pass
            if any(
                x in low
                for x in (
                    "1 segmento",
                    "primeiro segmento",
                    "1o segmento",
                    "primeiro seg",
                )
            ):
                return "EJA – 1º Segmento"
            if any(
                x in low
                for x in (
                    "2 segmento",
                    "segundo segmento",
                    "2o segmento",
                    "segundo seg",
                )
            ):
                return "EJA – 2º Segmento"
            return "EJA"

        # Educação Infantil
        if any(
            x in low
            for x in (
                "infantil",
                "creche",
                "maternal",
                "bercario",
                "educacao infantil",
                "ei ",
                " ei",
            )
        ) or re.search(r"\bgrupo\s*[123]\b", low) or re.search(r"\bg\s*[123]\b", low):
            return "Educação Infantil"

        # Educação Especial / AEE
        if re.search(r"suporte\s*[123]", low) or "aee" in low:
            msup = re.search(r"suporte\s*([123])", low)
            if msup:
                return f"Educação Especial (Suporte {msup.group(1)})"
            return "Educação Especial"
        if "especial" in low and "ensino medio" not in low:
            return "Educação Especial"

        # Segmentos amplos (nome de etapa no banco)
        if "anos iniciais" in low:
            return "Anos Iniciais"
        if "anos finais" in low:
            return "Anos Finais"
        if "ensino medio" in low or "ensino médio" in texto.lower():
            return "Ensino Médio"

        # Ordinais por extenso (fundamental)
        extenso_para_ano = {
            "primeiro": 1,
            "segundo": 2,
            "terceiro": 3,
            "quarto": 4,
            "quinto": 5,
            "sexto": 6,
            "setimo": 7,
            "oitavo": 8,
            "nono": 9,
        }
        for palavra, num in extenso_para_ano.items():
            if re.search(rf"\b{palavra}\s+ano\b", low):
                return f"{num}º Ano"

        # Fallback: devolver o próprio nome do curso se for descritivo (evita perder "Magistério", etc.)
        if len(texto) <= 120:
            return texto
        return texto[:117] + "..."

    def _mapear_disciplina_para_sigla(self, disciplina: str) -> str:
        """Mapeia nome da disciplina para sigla SAEB (LP ou MT)"""
        disciplina_lower = disciplina.lower()
        if 'portugu' in disciplina_lower or 'língua' in disciplina_lower:
            return "LP"
        elif 'matemática' in disciplina_lower or 'matematica' in disciplina_lower:
            return "MT"
        else:
            return "LP"  # Padrão
    
    def _normalize_discipline_name(self, disciplina_nome: str, report_data: Dict[str, Any] = None) -> str:
        """
        Normaliza nome de disciplina extraído da IA para o nome padrão do banco de dados.
        
        Mapeia variações como "Língua Portuguesa" para "Português" (nome do banco).
        
        Args:
            disciplina_nome: Nome da disciplina extraído do marcador [DISCIPLINA: ...]
            report_data: Dados do relatório (opcional, para buscar disciplinas do payload)
            
        Returns:
            Nome normalizado da disciplina (nome do banco de dados)
        """
        if not disciplina_nome or disciplina_nome.strip() == '':
            return disciplina_nome
        
        # Se for GERAL, manter como está (aceita variações como "GERAL (Todas as Disciplinas)")
        disciplina_upper = disciplina_nome.upper().strip()
        if disciplina_upper == 'GERAL' or disciplina_upper.startswith('GERAL'):
            return 'GERAL'
        
        # Normalizar para comparação (remover acentos, lowercase)
        import unicodedata
        def normalize_for_comparison(name: str) -> str:
            if not name:
                return ""
            name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
            return name.lower().strip()
        
        # Normalizar para comparação (remover acentos, lowercase)
        disciplina_normalized = normalize_for_comparison(disciplina_nome)
        
        # 1. Mapeamento direto de variações conhecidas para nomes do banco
        # Baseado no resultado do script: banco tem "Português", não "Língua Portuguesa"
        # Mapeamento de variações de Português
        if 'lingua' in disciplina_normalized and 'portug' in disciplina_normalized:
            # "Língua Portuguesa", "Lingua Portuguesa", etc. → "Português"
            return "Português"
        elif disciplina_normalized == 'portugues' or disciplina_normalized == 'português':
            return "Português"
        
        # Mapeamento de variações de Matemática
        if disciplina_normalized == 'matematica' or disciplina_normalized == 'matemática':
            return "Matemática"
        
        # 2. Se temos report_data, tentar encontrar a disciplina correspondente no payload
        # Isso garante que usamos o nome exato que está no payload (que vem do banco)
        if report_data:
            # Buscar disciplinas no payload de proficiência
            prof_disciplinas = report_data.get('proficiencia', {}).get('por_disciplina', {})
            for disc_payload in prof_disciplinas.keys():
                if disc_payload == 'GERAL':
                    continue
                # Comparar normalizado para encontrar correspondência mesmo com variações
                if normalize_for_comparison(disc_payload) == disciplina_normalized:
                    return disc_payload
            
            # Buscar disciplinas no payload de níveis de aprendizagem
            niveis_disciplinas = report_data.get('niveis_aprendizagem', {})
            for disc_payload in niveis_disciplinas.keys():
                if disc_payload == 'GERAL':
                    continue
                # Comparar normalizado para encontrar correspondência mesmo com variações
                if normalize_for_comparison(disc_payload) == disciplina_normalized:
                    return disc_payload
        
        # 3. Se não encontrou correspondência, buscar no banco de dados
        try:
            from app.models.subject import Subject
            from app import db
            
            # Buscar todas as disciplinas do banco
            all_subjects = Subject.query.all()
            for subject in all_subjects:
                if subject.name and normalize_for_comparison(subject.name) == disciplina_normalized:
                    return subject.name
        except Exception as e:
            self.logger.warning(f"Erro ao buscar disciplinas no banco para normalização: {str(e)}")
        
        # 4. Se não encontrou correspondência, retornar o nome original (pode ser uma disciplina nova)
        self.logger.warning(f"Disciplina '{disciplina_nome}' não foi normalizada - usando nome original")
        return disciplina_nome
    
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
                    "Ano/Série: [Ano/Série ex: 1º Ano, 7º Ano, etc.]",
                    f"Ano/Série: {ano_serie}"
                ).replace(
                    "Disciplina: [Disciplina: LP ou MT]",
                    f"Disciplina: {sigla_disc} (sigla SAEB para {disciplina})"
                ).replace(
                    "Avaliação: [AVALIAÇÃO: ex: Avaliação 2025.1]",
                    f"Avaliação: {avaliacao_titulo or 'Avaliação Diagnóstica'}"
                ).replace(
                    "Média Geral da Rede/Escola: [Média]",
                    f"Média Geral da Rede/Escola: {media_geral:.2f}"
                ).replace(
                    "Média Municipal/Benchmark (se disponível): [Média Municipal]",
                    f"Média Municipal/Benchmark (se disponível): {media_municipal:.2f}" if media_municipal > 0 else "Média Municipal/Benchmark (se disponível): Não disponível"
                ).replace(
                    "{Resultados por Turma}",
                    resultados_detalhados_str
                ).replace(
                    "Análise por Turma/Escola",
                    f"Análise por {label_unidade}"
                ).replace(
                    "Existindo segmentação de dados por turmas, emita breves laudos individuais",
                    f"Existindo segmentação de dados por {label_unidade.lower()}s, emita breves laudos individuais",
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
        Analisa níveis de aprendizagem por disciplina (incluindo GERAL)
        
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
            
            # Processar cada disciplina (incluindo GERAL)
            for disciplina, dados in niveis_aprendizagem.items():
                
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
                
                # Ajustar nome da disciplina para GERAL
                disciplina_nome = "GERAL" if disciplina == 'GERAL' else disciplina
                disciplina_label = "GERAL (Todas as Disciplinas)" if disciplina == 'GERAL' else disciplina
                
                # Preencher o template do prompt (ordem importa)
                ano_serie_niveis = self._obter_ano_serie(report_data)
                prompt = NIVEIS_APRENDIZAGEM_ANALYSIS_PROMPT_TEMPLATE.replace(
                    "[DISCIPLINA]",
                    disciplina_label
                ).replace(
                    "[Avaliação]",
                    avaliacao_titulo or "Avaliação Diagnóstica"
                ).replace(
                    "[Disciplina]",
                    disciplina_label
                ).replace(
                    "[Série/Ano]",
                    ano_serie_niveis
                ).replace(
                    "Disciplina: [PREENCHER DISCIPLINA: ex: Matemática / Língua Portuguesa]",
                    f"Disciplina: {disciplina_label}"
                ).replace(
                    "Avaliação: [AVALIAÇÃO: ex: Avaliação Diagnóstica 2025.1]",
                    f"Avaliação: {avaliacao_titulo or 'Avaliação Diagnóstica'}"
                ).replace(
                    "Total de alunos avaliados: [Nº]",
                    f"Total de alunos avaliados: {total_alunos}"
                ).replace(
                    "Abaixo do Básico: [Nº] alunos ([__]%)",
                    f"Abaixo do Básico: {abaixo_basico} alunos ({perc_abaixo:.1f}%)"
                ).replace(
                    "Básico: [Nº] alunos ([__]%)",
                    f"Básico: {basico} alunos ({perc_basico:.1f}%)"
                ).replace(
                    "Adequado: [Nº] alunos ([__]%)",
                    f"Adequado: {adequado} alunos ({perc_adequado:.1f}%)"
                ).replace(
                    "Avançado: [Nº] alunos ([__]%)",
                    f"Avançado: {avancado} alunos ({perc_avancado:.1f}%)"
                )
                
                try:
                    response = self._call_openai(prompt)
                    # Usar a chave original da disciplina (incluindo 'GERAL')
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
        """
        Chama a API do Google AI Studio (Gemini) para gerar análise.
        Mantém a mesma assinatura usada anteriormente com OpenRouter.
        """
        try:
            # Chave da API do Google AI Studio deve vir de variável de ambiente
            api_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
            if not api_key:
                self.logger.error("GOOGLE_AI_STUDIO_API_KEY não configurada no ambiente")
                raise RuntimeError("Chave da API do Google AI Studio não configurada")

            # Configurar cliente global do Gemini
            genai.configure(api_key=api_key)

            # Modelo: sempre usar GOOGLE_AI_STUDIO_MODEL do ambiente (ex: gemini-3-pro-preview)
            model_name = (os.getenv("GOOGLE_AI_STUDIO_MODEL") or "gemini-1.5-pro").strip()
            if not model_name:
                model_name = "gemini-1.5-pro"
            print(f"[AIAnalysisService] call | Google AI Studio (Gemini) | model={model_name}")

            system_prompt = (
                "Você atua como um Doutor em Análise de Dados Educacionais e Especialista em "
                "Avaliação Educacional. Gere texto humanizado e profissional, SEM formatação markdown "
                "(sem #, ##, *, **). Use parágrafos e títulos em maiúsculas seguidos de dois pontos. "
                "Respeite rigorosamente as regras de série, segmento e nomenclatura do prompt do usuário."
            )

            # Gemini 3 usa "thinking" interno: com prompt longo pode consumir todos os tokens
            # e devolver finish_reason=MAX_TOKENS sem Part. Reservar mais tokens para a saída.
            max_tokens = OPENROUTER_MAX_TOKENS
            if "gemini-3" in (model_name or "").lower():
                max_tokens = int(os.getenv("GOOGLE_AI_STUDIO_MAX_OUTPUT_TOKENS", "32768"))
                self.logger.info("Gemini 3 detectado: max_output_tokens=%s (evita resposta vazia com prompts longos)", max_tokens)
            generation_config = {
                "temperature": OPENROUTER_TEMPERATURE,
                "max_output_tokens": max_tokens,
            }

            model = genai.GenerativeModel(
                model_name,
                system_instruction=system_prompt,
                generation_config=generation_config,
            )

            response = model.generate_content(prompt)

            # Extrair texto dos candidates/parts (evita ValueError quando response.text
            # não existe por finish_reason=MAX_TOKENS/SAFETY/etc. ou Part vazia)
            candidates = getattr(response, "candidates", None) or []
            for cand in candidates:
                content = getattr(cand, "content", None)
                if not content:
                    continue
                parts = getattr(content, "parts", None) or []
                texts = [getattr(p, "text", "") for p in parts if getattr(p, "text", "")]
                joined = "\n".join(texts).strip()
                if joined:
                    return joined

            # Sem texto: logar finish_reason para diagnóstico (2=MAX_TOKENS, 3=SAFETY, etc.)
            finish_reasons = [getattr(c, "finish_reason", None) for c in candidates]
            self.logger.error(
                "Resposta do Google AI sem Part válida. finish_reason(s)=%s. "
                "Se 2 (MAX_TOKENS), aumente OPENROUTER_MAX_TOKENS ou use modelo com mais saída.",
                finish_reasons,
            )
            raise RuntimeError(
                "Resposta do Google AI sem conteúdo (finish_reason pode ser MAX_TOKENS ou SAFETY). "
                "Tente aumentar max_output_tokens ou outro modelo."
            )

        except Exception as e:
            self.logger.error(f"Erro ao chamar Google AI Studio: {str(e)}", exc_info=True)
            raise

    def _call_openai_json(self, prompt: str) -> str:
        """
        Chama a API do Google AI Studio (Gemini) exigindo retorno em JSON válido.
        Mantém o método separado para não alterar o comportamento do fluxo existente de relatórios.
        """
        try:
            api_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
            if not api_key:
                self.logger.error("GOOGLE_AI_STUDIO_API_KEY não configurada no ambiente")
                raise RuntimeError("Chave da API do Google AI Studio não configurada")

            genai.configure(api_key=api_key)

            model_name = (os.getenv("GOOGLE_AI_STUDIO_MODEL") or "gemini-1.5-pro").strip() or "gemini-1.5-pro"
            print(f"[AIAnalysisService] call | Google AI Studio (Gemini) | model={model_name} | json_only=1")

            system_prompt = (
                "Responda APENAS com um JSON válido (objeto). "
                "Não use Markdown, não use blocos de código, não use texto antes ou depois do JSON. "
                "Use apenas aspas duplas em chaves e strings. "
                "Se algum dado estiver ausente, use null ou string vazia, mas mantenha o JSON válido."
            )

            max_tokens = OPENROUTER_MAX_TOKENS
            if "gemini-3" in (model_name or "").lower():
                max_tokens = int(os.getenv("GOOGLE_AI_STUDIO_MAX_OUTPUT_TOKENS", "32768"))
                self.logger.info(
                    "Gemini 3 detectado (json): max_output_tokens=%s", max_tokens
                )

            generation_config = {
                "temperature": OPENROUTER_TEMPERATURE,
                "max_output_tokens": max_tokens,
            }

            model = genai.GenerativeModel(
                model_name,
                system_instruction=system_prompt,
                generation_config=generation_config,
            )

            response = model.generate_content(prompt)

            candidates = getattr(response, "candidates", None) or []
            for cand in candidates:
                content = getattr(cand, "content", None)
                if not content:
                    continue
                parts = getattr(content, "parts", None) or []
                texts = [getattr(p, "text", "") for p in parts if getattr(p, "text", "")]
                joined = "\n".join(texts).strip()
                if joined:
                    return joined

            finish_reasons = [getattr(c, "finish_reason", None) for c in candidates]
            self.logger.error(
                "Resposta do Google AI sem Part válida (json). finish_reason(s)=%s",
                finish_reasons,
            )
            raise RuntimeError("Resposta do Google AI sem conteúdo (json).")
        except Exception as e:
            self.logger.error(f"Erro ao chamar Google AI Studio (json): {str(e)}", exc_info=True)
            raise

    @staticmethod
    def _extract_json_object(text: str) -> str:
        """
        Tenta extrair o primeiro objeto JSON do texto.
        Suporta casos em que o modelo devolve texto extra ou envolve em ```json.
        """
        if not text:
            return ""

        s = text.strip()

        # Remover fences comuns
        if s.startswith("```"):
            s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
            s = re.sub(r"\s*```$", "", s)
            s = s.strip()

        # Se já é um objeto
        if s.startswith("{") and s.endswith("}"):
            return s

        # Extrair primeiro objeto por heurística simples de chaves balanceadas
        start = s.find("{")
        if start < 0:
            return ""
        depth = 0
        for i in range(start, len(s)):
            ch = s[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return s[start : i + 1].strip()
        return ""

    def analyze_intervention_plan_json(self, prompt: str) -> Dict[str, Any]:
        """
        Gera um plano de intervenção seguindo o prompt do usuário e devolve JSON (dict).
        """
        try:
            raw = self._call_openai_json(prompt)
            json_str = self._extract_json_object(raw)
            if not json_str:
                return {
                    "error": "IA não retornou um objeto JSON válido",
                    "raw": raw,
                }
            return json.loads(json_str)
        except Exception as e:
            return {
                "error": "Falha ao gerar análise em JSON",
                "details": str(e),
            }
    
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
        
        # Dados de níveis de aprendizagem por disciplina (incluindo GERAL)
        niveis_data_str = ""
        for disciplina, dados in niveis_aprendizagem.items():
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
            # Ajustar nome da disciplina para GERAL
            disciplina_label = "GERAL (Todas as Disciplinas)" if disciplina == 'GERAL' else disciplina
            niveis_data_str += f"\n{disciplina_label}:\n"
            niveis_data_str += f"  - Total de alunos: {total_alunos}\n"
            niveis_data_str += f"  - Abaixo do Básico: {abaixo_basico} alunos ({perc_abaixo:.1f}%)\n"
            niveis_data_str += f"  - Básico: {basico} alunos ({perc_basico:.1f}%)\n"
            niveis_data_str += f"  - Adequado: {adequado} alunos ({perc_adequado:.1f}%)\n"
            niveis_data_str += f"  - Avançado: {avancado} alunos ({perc_avancado:.1f}%)\n"
        
        # Dados de acertos por habilidade
        acertos_habilidade = report_data.get('acertos_por_habilidade', {})
        habilidades_data_str = ""
        
        for disciplina, dados in acertos_habilidade.items():
            questoes = dados.get('questoes', [])
            if not questoes:
                continue
            
            # Ajustar nome da disciplina para GERAL
            disciplina_label = "GERAL (Todas as Disciplinas)" if disciplina == 'GERAL' else disciplina
            
            habilidades_data_str += f"\n{disciplina_label}:\n"
            for questao in questoes:
                codigo = questao.get('codigo', 'N/A')
                descricao = questao.get('descricao', 'N/A')
                acertos = questao.get('acertos', 0)
                total = questao.get('total', 0)
                percentual = questao.get('percentual', 0.0)
                
                # Classificar habilidade
                if percentual >= 70:
                    status = "CONCLUÍDO"
                elif percentual >= 50:
                    status = "REVISAR"
                else:
                    status = "REAVALIAR"
                
                habilidades_data_str += f"  - Questão {questao.get('numero_questao', 'N/A')}: {codigo} - {descricao}\n"
                habilidades_data_str += f"    Acertos: {acertos}/{total} ({percentual:.1f}%) | Status: {status}\n"
        
        # Obter ano/série e rótulos (fidelidade à série; series_label/series têm prioridade em _obter_ano_serie)
        ano_serie = self._obter_ano_serie(report_data)
        avaliacao_meta = report_data.get("avaliacao", {}) or {}
        nome_curso_cadastro = (avaliacao_meta.get("course_name") or avaliacao_meta.get("course") or "").strip()
        serie_ref = ano_serie

        # Formatar média municipal geral (evitar erro de formatação)
        media_municipal_geral_str = f"{media_municipal_geral:.2f}" if media_municipal_geral > 0 else "Não disponível"

        # Construir prompt unificado
        prompt = f"""{ANALYSIS_PROMPT_BASE}

IMPORTANTE: Você deve gerar TODAS as análises solicitadas abaixo em uma única resposta, separadas por marcadores claros.

Gere APENAS texto puro, SEM formatação markdown (sem #, ##, *, **, etc). Use apenas parágrafos normais e títulos em maiúsculas seguidos de dois pontos.

Use QUEBRAS DE LINHA DUPLAS (\\n\\n) para separar parágrafos diferentes.
Use QUEBRAS DE LINHA SIMPLES (\\n) antes de títulos ou seções importantes.

FORMATAÇÃO DE NÚMEROS (OBRIGATÓRIO):
- Sempre use 1 (uma) casa decimal após a vírgula para:
  * Notas (ex: 7,5 ao invés de 7,50 ou 7)
  * Percentuais (ex: 85,3% ao invés de 85,30% ou 85%)
  * Médias de proficiência (ex: 245,7 ao invés de 245,70 ou 245)
  * Qualquer valor numérico decimal mencionado no texto
- Use vírgula (,) como separador decimal, não ponto (.)
- Exemplos corretos: 7,5 pontos | 85,3% | 245,7 de proficiência
- Exemplos incorretos: 7,50 | 85,30% | 245,70 | 7.5 | 85.3%

===========================================
DADOS DO RELATÓRIO
===========================================
- Entidade: {entidade}
- Avaliação: {avaliacao_titulo or 'Avaliação Diagnóstica'}
- Série / etapa (turmas avaliadas): {serie_ref}
- Curso no cadastro da prova: {nome_curso_cadastro or 'não informado'}
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
Gere um PARECER TÉCNICO DE PARTICIPAÇÃO alinhado ao template de participação: panorama com números exatos, classificação segundo a tabela, confiabilidade dos dados para uso das médias de proficiência, destaques (se houver) e recomendações estratégicas para absenteísmo. Mencione a série/etapa apenas conforme a avaliação (use "{serie_ref}" quando fizer sentido). Honre as regras de série e segmento do prompt base.

===========================================
2. ANÁLISE DE PROFICIÊNCIA POR DISCIPLINA
===========================================

TABELA DE REFERÊNCIA SAEB:
{SAEB_PROFICIENCY_REFERENCE_TABLE}

DADOS DE PROFICIÊNCIA:
{prof_data_str}

INSTRUÇÕES PARA ANÁLISE DE PROFICIÊNCIA:
Para CADA disciplina listada acima, gere um PARECER TÉCNICO DE PROFICIÊNCIA com: abertura sobre TRI e meta "Adequado"; Classificação da Média Geral; Análise de Posição (pontos de corte e municipal); Diagnóstico Pedagógico (INEP); Análise por {unidade_label} com bullets (•) quando houver dados. Use a régua do 5º ou do 9º ano conforme o segmento, sem violar as regras de nomenclatura do prompt base.

PARECER TÉCNICO: PROFICIÊNCIA EM [Disciplina] ({serie_ref} - {avaliacao_titulo or 'Avaliação Diagnóstica'})

===========================================
3. ANÁLISE DE RENDIMENTO ESCOLAR (NOTAS)
===========================================

TABELA DE REFERÊNCIA PEDAGÓGICA:
{NOTA_REFERENCE_TABLE}

DADOS DE NOTAS:
{notas_data_str}
- Média Geral (Abrangendo todos os Componentes): {media_geral_total:.2f}
- Benchmark (Média da Rede Municipal): {media_municipal_geral_str}

INSTRUÇÕES PARA ANÁLISE DE NOTAS:
Gere um PARECER TÉCNICO: RENDIMENTO ESCOLAR (0-10) - {serie_ref} ({avaliacao_titulo or 'Avaliação Diagnóstica'}) com: Classificação e Estudo Comparativo da Média Geral; Radiografia por Disciplina e Unidade de Ensino (LP x MT e {unidade_label.lower()}s); Parecer Conclusivo e Recomendações Pedagógicas. Aplique o PRINCÍPIO INEGOCIÁVEL DA SÉRIE E RÉGUA do template de notas.

===========================================
4. ANÁLISE DE NÍVEIS DE APRENDIZAGEM POR DISCIPLINA
===========================================

DEFINIÇÕES DOS NÍVEIS (INEP - "Descritores de Padrões de Desempenho - 2025"):
Abaixo do Básico: Reflete um desempenho "aquém do esperado", apontando "significativo comprometimento" no domínio das habilidades focais. Tais estudantes encontram-se com a "trajetória acadêmica seriamente comprometida", demandando "intervenções emergenciais" e suporte intensivo.
Básico: Denota um desenvolvimento apenas elementar e fragmentado das habilidades aferidas. O aluno não sedimentou as competências balizares para a sua etapa, exigindo estratégias direcionadas para a recomposição das aprendizagens não consolidadas.
Adequado (A Meta): Expressa o "desempenho esperado". Trata-se do cenário ideal, no qual o estudante atesta ter "desenvolvido as habilidades previstas", assegurando "condições adequadas à continuidade" autônoma do seu ciclo de estudos.
Avançado: Corresponde a um "desempenho superior àquele esperado". O aluno demonstra fluência em "habilidades mais complexas", sinalizando a necessidade de enriquecimento curricular e "atividades mais desafiadoras".

DADOS DE NÍVEIS DE APRENDIZAGEM:
{niveis_data_str}

INSTRUÇÕES PARA ANÁLISE DE NÍVEIS:
Para CADA disciplina listada acima (incluindo "GERAL (Todas as Disciplinas)" se presente), gere um PARECER TÉCNICO: NÍVEIS DE APRENDIZAGEM EM [Disciplina] ({avaliacao_titulo or 'Avaliação Diagnóstica'}) com introdução, Diagnóstico e Meta ([Disciplina] - {serie_ref}), e Conclusão sobre o gargalo. Calcule % fora da meta (Abaixo+Básico) e % na meta (Adequado+Avançado), com detalhes por nível.

IMPORTANTE: Se "GERAL (Todas as Disciplinas)" estiver listado acima, você DEVE incluir uma análise para ele também. Use o nome "GERAL" ou "GERAL (Todas as Disciplinas)" no marcador [DISCIPLINA: ...].

===========================================
5. ANÁLISE DE ACERTOS POR HABILIDADE
===========================================

METODOLOGIA DE CLASSIFICAÇÃO (MAPA DE CALOR):
Classifique cada habilidade/objetivo com base nos acertos:
CONCLUÍDO: Acertos ≥ 70%.
REVISAR: Acertos entre 50% e 69%.
REAVALIAR: Acertos < 50%.

DADOS DE ACERTOS POR HABILIDADE:
{habilidades_data_str}

INSTRUÇÕES PARA ANÁLISE DE HABILIDADES:
Para CADA disciplina listada acima (incluindo GERAL se presente), gere um PARECER PEDAGÓGICO: ACERTOS POR HABILIDADE EM [Disciplina] ({avaliacao_titulo or 'Avaliação Diagnóstica'}) com Mapa de Calor (texto), Diagnóstico Cognitivo, Proposta de Intervenção para REVISAR/REAVALIAR e Síntese. Considere questões anuladas se presentes nos dados globais da avaliação.

IMPORTANTE: Se "GERAL (Todas as Disciplinas)" estiver listado acima, você DEVE incluir uma análise para ele também. Use o nome "GERAL" ou "GERAL (Todas as Disciplinas)" no marcador [DISCIPLINA: ...].

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
[Para cada disciplina listada nos dados acima (incluindo GERAL se presente), use o formato:]
[DISCIPLINA: Nome da Disciplina]
[Análise de níveis de aprendizagem para esta disciplina]

[DISCIPLINA: Próxima Disciplina]
[Análise de níveis de aprendizagem para esta disciplina]

[DISCIPLINA: GERAL]
[Se "GERAL (Todas as Disciplinas)" estiver nos dados acima, você DEVE incluir uma análise de níveis de aprendizagem para GERAL aqui. Use exatamente o marcador [DISCIPLINA: GERAL] ou [DISCIPLINA: GERAL (Todas as Disciplinas)].]

[MARCADOR: HABILIDADES]
[Para cada disciplina listada nos dados de acertos por habilidade acima (incluindo GERAL se presente), use o formato:]
[DISCIPLINA: Nome da Disciplina]
[Análise completa de acertos por habilidade para esta disciplina (incluindo Mapa de Calor, Diagnóstico Cognitivo, Proposta de Intervenção e Síntese)]

[DISCIPLINA: Próxima Disciplina]
[Análise completa de acertos por habilidade para esta disciplina]

[DISCIPLINA: GERAL]
[Se "GERAL (Todas as Disciplinas)" estiver nos dados de acertos por habilidade acima, você DEVE incluir uma análise para GERAL aqui. Use exatamente o marcador [DISCIPLINA: GERAL] ou [DISCIPLINA: GERAL (Todas as Disciplinas)].]

IMPORTANTE: Use os marcadores exatos [MARCADOR: PARTICIPACAO], [MARCADOR: PROFICIENCIA], [MARCADOR: NOTAS], [MARCADOR: NIVEIS], [MARCADOR: HABILIDADES] e [DISCIPLINA: ...] para que possamos processar sua resposta corretamente.

ATENÇÃO ESPECIAL: Se você viu "GERAL (Todas as Disciplinas)" nos dados de níveis de aprendizagem acima, você DEVE gerar uma análise para ele usando o marcador [DISCIPLINA: GERAL] ou [DISCIPLINA: GERAL (Todas as Disciplinas)]. Não pule esta análise!
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
                'niveis_aprendizagem': Dict[str, str],
                'habilidades': Dict[str, str]
            }
        """
        result = {
            'participacao': '',
            'proficiencia': {},
            'notas': '',
            'niveis_aprendizagem': {},
            'habilidades': {}
        }
        
        
        try:
            
            # Extrair seção de participação
            if '[MARCADOR: PARTICIPACAO]' in unified_response:
                parts = unified_response.split('[MARCADOR: PARTICIPACAO]', 1)
                if len(parts) > 1:
                    if '[MARCADOR: PROFICIENCIA]' in parts[1]:
                        participacao_section = parts[1].split('[MARCADOR: PROFICIENCIA]', 1)[0]
                        result['participacao'] = participacao_section.strip()
                    else:
                        result['participacao'] = parts[1].strip()
            
            # Extrair seção de proficiência
            if '[MARCADOR: PROFICIENCIA]' in unified_response:
                parts = unified_response.split('[MARCADOR: PROFICIENCIA]', 1)
                if len(parts) > 1:
                    if '[MARCADOR: NOTAS]' in parts[1]:
                        prof_section = parts[1].split('[MARCADOR: NOTAS]', 1)[0]
                    else:
                        prof_section = parts[1]
                    # Extrair todas as disciplinas usando regex
                    disciplina_pattern = r'\[DISCIPLINA:\s*([^\]]+)\]'
                    matches = list(re.finditer(disciplina_pattern, prof_section))
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
                        # Normalizar nome da disciplina para o nome padrão do banco
                        disciplina_key = self._normalize_discipline_name(disciplina_nome, report_data)
                        result['proficiencia'][disciplina_key] = disc_analysis
            
            # Extrair seção de notas
            if '[MARCADOR: NOTAS]' in unified_response:
                parts = unified_response.split('[MARCADOR: NOTAS]', 1)
                if len(parts) > 1:
                    if '[MARCADOR: NIVEIS]' in parts[1]:
                        notas_section = parts[1].split('[MARCADOR: NIVEIS]', 1)[0]
                        result['notas'] = notas_section.strip()
                    elif '[MARCADOR: HABILIDADES]' in parts[1]:
                        notas_section = parts[1].split('[MARCADOR: HABILIDADES]', 1)[0]
                        result['notas'] = notas_section.strip()
                    else:
                        result['notas'] = parts[1].strip()
            
            # Extrair seção de níveis
            if '[MARCADOR: NIVEIS]' in unified_response:
                parts = unified_response.split('[MARCADOR: NIVEIS]', 1)
                if len(parts) > 1:
                    # Verificar se há marcador de HABILIDADES após NIVEIS
                    if '[MARCADOR: HABILIDADES]' in parts[1]:
                        niveis_section = parts[1].split('[MARCADOR: HABILIDADES]', 1)[0]
                    else:
                        niveis_section = parts[1]
                    
                    # Extrair todas as disciplinas usando regex
                    disciplina_pattern = r'\[DISCIPLINA:\s*([^\]]+)\]'
                    matches = list(re.finditer(disciplina_pattern, niveis_section))
                    
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
                        
                        # Normalizar nome da disciplina para o nome padrão do banco
                        disciplina_key = self._normalize_discipline_name(disciplina_nome, report_data)
                        
                        result['niveis_aprendizagem'][disciplina_key] = disc_analysis
                    
                    # Tentar buscar GERAL na seção de níveis mesmo sem marcador explícito
                    if 'GERAL' not in result['niveis_aprendizagem'] and 'GERAL' in niveis_section.upper():
                        # Procurar por padrões que indiquem análise de GERAL
                        geral_patterns = [
                            r'PARECER TÉCNICO[^\n]*NÍVEIS[^\n]*GERAL[^\n]*\n(.*?)(?=\[DISCIPLINA:|PARECER TÉCNICO|$)',
                            r'GERAL[^\n]*TODAS AS DISCIPLINAS[^\n]*\n(.*?)(?=\[DISCIPLINA:|PARECER TÉCNICO|$)',
                            r'NÍVEIS DE APRENDIZAGEM[^\n]*GERAL[^\n]*\n(.*?)(?=\[DISCIPLINA:|PARECER TÉCNICO|$)',
                        ]
                        for pattern in geral_patterns:
                            match = re.search(pattern, niveis_section, re.IGNORECASE | re.DOTALL)
                            if match:
                                geral_analysis = match.group(1).strip()
                                if len(geral_analysis) > 100:  # Garantir que é uma análise válida
                                    result['niveis_aprendizagem']['GERAL'] = geral_analysis
                                    break
            
            # Extrair seção de habilidades
            if '[MARCADOR: HABILIDADES]' in unified_response:
                parts = unified_response.split('[MARCADOR: HABILIDADES]', 1)
                if len(parts) > 1:
                    habilidades_section = parts[1]
                    
                    # Extrair todas as disciplinas usando regex
                    disciplina_pattern = r'\[DISCIPLINA:\s*([^\]]+)\]'
                    matches = list(re.finditer(disciplina_pattern, habilidades_section))
                    
                    for match in matches:
                        disciplina_nome = match.group(1).strip()
                        start_pos = match.end()
                        # Encontrar próxima disciplina ou fim da seção
                        next_match = re.search(disciplina_pattern, habilidades_section[start_pos:])
                        if next_match:
                            end_pos = start_pos + next_match.start()
                        else:
                            end_pos = len(habilidades_section)
                        disc_analysis = habilidades_section[start_pos:end_pos].strip()
                        
                        # Normalizar nome da disciplina para o nome padrão do banco
                        disciplina_key = self._normalize_discipline_name(disciplina_nome, report_data)
                        
                        result['habilidades'][disciplina_key] = disc_analysis
            
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
            # Retornar fallback com dados do report_data
            return self._get_fallback_texts(report_data)
        
        # Garantir que pelo menos temos fallback para campos vazios
        
        # Garantir que todas as seções tenham conteúdo, mesmo que vazio
        # Seção de participação
        if not result['participacao']:
            result['participacao'] = 'Análise de participação não disponível no momento.'
        
        # Seção de notas
        if not result['notas']:
            result['notas'] = 'Análise de notas não disponível no momento.'
        
        # Seção de proficiência - garantir que todas as disciplinas tenham análise
        prof_disciplinas = report_data.get('proficiencia', {}).get('por_disciplina', {})
        if prof_disciplinas:
            for disciplina in prof_disciplinas.keys():
                if disciplina != 'GERAL':
                    # Se não foi extraída, criar fallback
                    if disciplina not in result['proficiencia']:
                        result['proficiencia'][disciplina] = f'Análise de proficiência não disponível para {disciplina}.'
                        self.logger.warning(f"Análise de proficiência não encontrada para disciplina: {disciplina}")
        elif not result['proficiencia']:
            # Se não há dados de proficiência, manter dict vazio
            result['proficiencia'] = {}
        
        # Seção de níveis de aprendizagem - garantir que todas as disciplinas tenham análise
        niveis_disciplinas = report_data.get('niveis_aprendizagem', {})
        if niveis_disciplinas:
            for disciplina in niveis_disciplinas.keys():
                # Se não foi extraída, criar fallback (incluindo GERAL)
                if disciplina not in result['niveis_aprendizagem']:
                    result['niveis_aprendizagem'][disciplina] = f'Análise de níveis não disponível para {disciplina}.'
                    self.logger.warning(f"Análise de níveis não encontrada para disciplina: {disciplina}")
        elif not result['niveis_aprendizagem']:
            # Se não há dados de níveis, manter dict vazio
            result['niveis_aprendizagem'] = {}
        
        # Seção de habilidades - garantir que todas as disciplinas tenham análise
        habilidades_disciplinas = report_data.get('acertos_por_habilidade', {})
        if habilidades_disciplinas:
            for disciplina in habilidades_disciplinas.keys():
                # Se não foi extraída, criar fallback (incluindo GERAL)
                if disciplina not in result['habilidades']:
                    result['habilidades'][disciplina] = f'Análise de habilidades não disponível para {disciplina}.'
                    self.logger.warning(f"Análise de habilidades não encontrada para disciplina: {disciplina}")
        elif not result['habilidades']:
            # Se não há dados de habilidades, manter dict vazio
            result['habilidades'] = {}
        
        # Formatar todas as análises em HTML
        result['participacao'] = self._format_ai_text(result['participacao'])
        result['notas'] = self._format_ai_text(result['notas'])
        
        # Formatar análises por disciplina
        for disciplina in result['proficiencia']:
            result['proficiencia'][disciplina] = self._format_ai_text(result['proficiencia'][disciplina])
        
        for disciplina in result['niveis_aprendizagem']:
            result['niveis_aprendizagem'][disciplina] = self._format_ai_text(result['niveis_aprendizagem'][disciplina])

        for disciplina in result['habilidades']:
            result['habilidades'][disciplina] = self._format_ai_text(result['habilidades'][disciplina])
        
        
        return result
    
    def _format_ai_text(self, text: str) -> str:
        """
        Formata texto da IA convertendo markdown simples em HTML.
        
        Converte:
        - Títulos (linhas que começam com #, PARECER TÉCNICO, ou são seguidas de dois pontos)
        - Listas (linhas que começam com -, *, •, ou números)
        - Negrito (texto entre **)
        - Parágrafos (quebras de linha duplas)
        
        Args:
            text: Texto simples da IA
            
        Returns:
            Texto formatado em HTML
        """
        if not text or not isinstance(text, str):
            return text or ''
        
        
        # Normalizar espaços múltiplos mas preservar estrutura
        text = re.sub(r'[ \t]+', ' ', text)  # Múltiplos espaços/tabs viram um espaço
        text = re.sub(r'\n\s*\n+', '\n\n', text)  # Múltiplas quebras viram duas
        
        # Dividir por quebras de linha existentes
        lines = text.split('\n')
        non_empty_lines = [l.strip() for l in lines if l.strip()]
        
        # Se não há quebras de linha adequadas ou texto está muito longo, tentar dividir por padrões
        if len(non_empty_lines) <= 1 or (len(non_empty_lines) == 1 and len(non_empty_lines[0]) > 200):
            original_text = text
            # IMPORTANTE: Dividir por padrões específicos ANTES de outras divisões
            
            # 1. Dividir por títulos em maiúsculas seguidos de dois pontos (ex: "PARECER TÉCNICO DE PARTICIPAÇÃO:")
            text = re.sub(r'([A-ZÁÉÍÓÚÇ][A-ZÁÉÍÓÚÇ\s]{10,}):\s*', r'\n\n\1: ', text)
            
            # 2. Dividir por títulos menores seguidos de dois pontos (ex: "Classificação:", "Destaques e Recomendações:")
            text = re.sub(r'([A-ZÁÉÍÓÚÇ][a-záéíóúç\s]{3,30}):\s*', r'\n\n\1: ', text)
            
            # 3. Dividir por listas com bullet (•) - adicionar quebra antes do bullet
            text = re.sub(r'\s+•\s+', r'\n• ', text)
            
            # 4. Dividir por padrões como " - " (lista) - preservar o espaço após o hífen
            text = re.sub(r'\s+-\s+([A-ZÁÉÍÓÚÇ])', r'\n- \1', text)
            text = re.sub(r'\s+-\s+', r'\n- ', text)
            
            # 5. Dividir por pontos finais seguidos de espaço e maiúscula (novos parágrafos)
            text = re.sub(r'\.\s+([A-ZÁÉÍÓÚÇ][a-záéíóúç])', r'.\n\n\1', text)
            
            lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        formatted_lines = []
        in_list = False
        
        for line in lines:
            line = line.strip()
            
            if not line:
                if in_list:
                    formatted_lines.append('</ul>')
                    in_list = False
                continue
            
            # Títulos: linhas que começam com # ou são seguidas de dois pontos
            if line.startswith('#'):
                if in_list:
                    formatted_lines.append('</ul>')
                    in_list = False
                title_text = line.lstrip('#').strip()
                if title_text:
                    formatted_lines.append(f'<p style="margin-top: 12px; margin-bottom: 8px;"><strong style="font-size: 1.15em; font-weight: bold; color: #1e293b;">{self._process_inline_formatting(title_text)}</strong></p>')
            # Títulos em maiúsculas (como "PARECER TÉCNICO DE PARTICIPAÇÃO:" ou "DIAGNÓSTICO E META")
            elif (re.match(r'^[A-ZÁÉÍÓÚÇ][A-ZÁÉÍÓÚÇ\s]{8,}:', line) or 
                  (line.isupper() and len(line) > 15 and ':' in line) or
                  (re.match(r'^[A-ZÁÉÍÓÚÇ][A-ZÁÉÍÓÚÇ\s]{5,}DE\s+[A-ZÁÉÍÓÚÇ]', line) and ':' in line)):
                if in_list:
                    formatted_lines.append('</ul>')
                    in_list = False
                if ':' in line:
                    title_part = line.split(':', 1)[0].strip()
                    content_part = line.split(':', 1)[1].strip()
                    if content_part:
                        formatted_lines.append(f'<p style="margin-top: 12px; margin-bottom: 8px;"><strong style="font-size: 1.1em; font-weight: bold; color: #1e293b;">{self._process_inline_formatting(title_part)}:</strong> {self._process_inline_formatting(content_part)}</p>')
                    else:
                        formatted_lines.append(f'<p style="margin-top: 12px; margin-bottom: 8px;"><strong style="font-size: 1.1em; font-weight: bold; color: #1e293b;">{self._process_inline_formatting(title_part)}:</strong></p>')
                else:
                    formatted_lines.append(f'<p style="margin-top: 12px; margin-bottom: 8px;"><strong style="font-size: 1.1em; font-weight: bold; color: #1e293b;">{self._process_inline_formatting(line)}</strong></p>')
            # Títulos menores (texto curto seguido de dois pontos, não lista)
            elif ':' in line and len(line.split(':')[0]) < 60 and not line.startswith('-') and not line.startswith('*') and not (len(line) > 0 and line[0].isdigit()):
                if in_list:
                    formatted_lines.append('</ul>')
                    in_list = False
                title_part = line.split(':', 1)[0].strip()
                content_part = line.split(':', 1)[1].strip() if ':' in line else ''
                if title_part:
                    formatted_lines.append(f'<p style="margin-top: 8px; margin-bottom: 4px;"><strong style="font-weight: bold; color: #1e293b;">{self._process_inline_formatting(title_part)}:</strong> {self._process_inline_formatting(content_part) if content_part else ""}</p>')
                else:
                    formatted_lines.append(f'<p style="margin-top: 8px; margin-bottom: 4px; text-align: left;">{self._process_inline_formatting(line)}</p>')
            # Listas: linhas que começam com -, *, •, ou números
            elif (line.startswith('-') or line.startswith('*') or line.startswith('•') or 
                  (len(line) > 0 and line[0].isdigit() and len(line) > 1 and (line[1] in '. )'))):
                if not in_list:
                    formatted_lines.append('<ul style="margin-left: 20px; padding-left: 20px; list-style-type: disc; text-align: left;">')
                    in_list = True
                # Remover marcador de lista
                if line.startswith('•'):
                    list_item = line[1:].strip()
                elif line.startswith('-') or line.startswith('*'):
                    list_item = line[1:].strip()
                else:
                    # Para listas numeradas, remover número e marcador
                    list_item = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
                if list_item:
                    formatted_lines.append(f'<li style="margin-bottom: 6px; text-align: left; line-height: 1.6;">{self._process_inline_formatting(list_item)}</li>')
            else:
                if in_list:
                    formatted_lines.append('</ul>')
                    in_list = False
                # Parágrafo normal
                formatted_lines.append(f'<p style="margin-top: 8px; margin-bottom: 8px; text-align: justify; line-height: 1.8;">{self._process_inline_formatting(line)}</p>')
        
        # Fechar lista se ainda estiver aberta
        if in_list:
            formatted_lines.append('</ul>')
        
        return '\n'.join(formatted_lines)
    
    def _process_inline_formatting(self, text: str) -> str:
        """
        Processa formatação inline (negrito, itálico) no texto.
        
        Args:
            text: Texto com formatação markdown
            
        Returns:
            Texto com HTML inline
        """
        if not text:
            return ''
        
        # Escapar HTML para segurança
        import html
        text = html.escape(text)
        
        # Negrito: **texto** ou __texto__
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
        
        # Itálico: *texto* ou _texto_
        text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
        text = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'<em>\1</em>', text)
        
        return text
    
    def _get_fallback_texts(self, report_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Retorna textos padrão em caso de erro.
        Se report_data for fornecido, cria fallbacks para todas as disciplinas encontradas.
        
        Args:
            report_data: Dados do relatório (opcional) para criar fallbacks por disciplina
            
        Returns:
            Dict com textos padrão, incluindo entradas para todas as disciplinas se report_data fornecido
        """
        result = {
            'participacao': 'Análise de participação não disponível no momento.',
            'proficiencia': {},
            'notas': 'Análise de notas não disponível no momento.',
            'niveis_aprendizagem': {},
            'habilidades': {}
        }
        
        # Se report_data fornecido, criar fallbacks para todas as disciplinas
        if report_data:
            # Proficiência - criar fallback para cada disciplina (exceto GERAL)
            prof_disciplinas = report_data.get('proficiencia', {}).get('por_disciplina', {})
            if prof_disciplinas:
                for disciplina in prof_disciplinas.keys():
                    if disciplina != 'GERAL':
                        result['proficiencia'][disciplina] = f'Análise de proficiência não disponível para {disciplina}.'
                        self.logger.warning(f"Fallback criado para proficiência: {disciplina}")
            
            # Níveis de aprendizagem - criar fallback para cada disciplina (incluindo GERAL)
            niveis_disciplinas = report_data.get('niveis_aprendizagem', {})
            if niveis_disciplinas:
                for disciplina in niveis_disciplinas.keys():
                    result['niveis_aprendizagem'][disciplina] = f'Análise de níveis não disponível para {disciplina}.'
                    self.logger.warning(f"Fallback criado para níveis: {disciplina}")
            
            # Habilidades - criar fallback para cada disciplina (incluindo GERAL)
            habilidades_disciplinas = report_data.get('acertos_por_habilidade', {})
            if habilidades_disciplinas:
                for disciplina in habilidades_disciplinas.keys():
                    result['habilidades'][disciplina] = f'Análise de habilidades não disponível para {disciplina}.'
                    self.logger.warning(f"Fallback criado para habilidades: {disciplina}")
        
        return result
    
    def _validate_analysis_completeness(self, analysis_texts: Dict[str, Any], report_data: Dict[str, Any]) -> None:
        """
        Valida se todas as seções esperadas foram geradas corretamente.
        Se alguma estiver faltando, cria fallbacks apropriados.
        
        Args:
            analysis_texts: Resultado da análise gerada
            report_data: Dados originais do relatório
        """
        # Validar participação
        if not analysis_texts.get('participacao'):
            self.logger.warning("Análise de participação está vazia, criando fallback")
            analysis_texts['participacao'] = 'Análise de participação não disponível no momento.'
        
        # Validar notas
        if not analysis_texts.get('notas'):
            self.logger.warning("Análise de notas está vazia, criando fallback")
            analysis_texts['notas'] = 'Análise de notas não disponível no momento.'
        
        # Validar proficiência - verificar se todas as disciplinas têm análise
        prof_disciplinas = report_data.get('proficiencia', {}).get('por_disciplina', {})
        if prof_disciplinas:
            for disciplina in prof_disciplinas.keys():
                if disciplina != 'GERAL' and disciplina not in analysis_texts.get('proficiencia', {}):
                    self.logger.warning(f"Análise de proficiência faltando para disciplina: {disciplina}")
                    if 'proficiencia' not in analysis_texts:
                        analysis_texts['proficiencia'] = {}
                    analysis_texts['proficiencia'][disciplina] = f'Análise de proficiência não disponível para {disciplina}.'
        
        # Validar níveis de aprendizagem - verificar se todas as disciplinas têm análise
        niveis_disciplinas = report_data.get('niveis_aprendizagem', {})
        if niveis_disciplinas:
            for disciplina in niveis_disciplinas.keys():
                if disciplina not in analysis_texts.get('niveis_aprendizagem', {}):
                    self.logger.warning(f"Análise de níveis faltando para disciplina: {disciplina}")
                    if 'niveis_aprendizagem' not in analysis_texts:
                        analysis_texts['niveis_aprendizagem'] = {}
                    analysis_texts['niveis_aprendizagem'][disciplina] = f'Análise de níveis não disponível para {disciplina}.'
        
        # Validar habilidades - verificar se todas as disciplinas têm análise
        habilidades_disciplinas = report_data.get('acertos_por_habilidade', {})
        if habilidades_disciplinas:
            for disciplina in habilidades_disciplinas.keys():
                if disciplina not in analysis_texts.get('habilidades', {}):
                    self.logger.warning(f"Análise de habilidades faltando para disciplina: {disciplina}")
                    if 'habilidades' not in analysis_texts:
                        analysis_texts['habilidades'] = {}
                    analysis_texts['habilidades'][disciplina] = f'Análise de habilidades não disponível para {disciplina}.'
        
        # Log final de validação
        self.logger.info(f"Validação completa: participacao={bool(analysis_texts.get('participacao'))}, "
                        f"notas={bool(analysis_texts.get('notas'))}, "
                        f"proficiencia={len(analysis_texts.get('proficiencia', {}))} disciplinas, "
                        f"niveis={len(analysis_texts.get('niveis_aprendizagem', {}))} disciplinas, "
                        f"habilidades={len(analysis_texts.get('habilidades', {}))} disciplinas")