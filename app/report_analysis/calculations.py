# -*- coding: utf-8 -*-
"""
Funções de cálculo de relatórios.
Importa funções do report_routes.py original para manter compatibilidade.

==============================================================
RELATÓRIOS QUE USAM ESTE ARQUIVO:
  - Análise das Avaliações  (frontend: AnaliseAvaliacoes / analise-avaliacoes)
  - Relatório Escolar       (frontend: RelatorioEscolar)

RESPONSABILIDADE:
  Ponto de re-exportação das funções de cálculo que vivem em
  app/routes/report_routes.py para uso pelas tasks Celery.
  Evita importação circular entre routes e tasks.

ARQUIVOS RELACIONADOS AO SISTEMA DE RELATÓRIOS:
  app/report_analysis/routes.py       → rotas Flask
  app/report_analysis/tasks.py        → tasks Celery que importam deste arquivo
  app/report_analysis/services.py     → ReportAggregateService (cache no banco)
  app/report_analysis/calculations.py ← este arquivo (re-exportações)
  app/report_analysis/debounce.py     → debounce Redis (evita tasks duplicadas)
  app/report_analysis/celery_app.py   → configuração do Celery
  app/routes/report_routes.py         → origem real das funções de cálculo
  app/routes/evaluation_results_routes.py → dados tabulares (/avaliacoes e /opcoes-filtros)
==============================================================
"""

# Importar todas as funções de cálculo do report_routes original
# TODO: Mover essas funções para cá gradualmente para melhor organização
from app.routes.report_routes import (
    _calcular_totais_alunos_por_escopo,
    _calcular_totais_alunos_por_municipio,
    _calcular_totais_alunos,
    _calcular_niveis_aprendizagem_por_escopo,
    _calcular_niveis_aprendizagem_por_municipio,
    _calcular_niveis_aprendizagem,
    _calcular_proficiencia_por_escopo,
    _calcular_proficiencia_por_municipio,
    _calcular_proficiencia,
    _calcular_nota_geral_por_escopo,
    _calcular_nota_geral_por_municipio,
    _calcular_nota_geral,
    _calcular_acertos_habilidade_por_escopo,
    _calcular_acertos_habilidade_por_municipio,
    _calcular_acertos_habilidade,
    _obter_nome_curso,
    _obter_disciplinas_avaliacao,
    _obter_ordem_disciplinas_avaliacao,
    _determinar_escopo_relatorio,
    _buscar_turmas_por_escopo,
    _montar_resposta_relatorio,
    _montar_resposta_relatorio_por_turmas,
)

__all__ = [
    '_calcular_totais_alunos_por_escopo',
    '_calcular_totais_alunos_por_municipio',
    '_calcular_totais_alunos',
    '_calcular_niveis_aprendizagem_por_escopo',
    '_calcular_niveis_aprendizagem_por_municipio',
    '_calcular_niveis_aprendizagem',
    '_calcular_proficiencia_por_escopo',
    '_calcular_proficiencia_por_municipio',
    '_calcular_proficiencia',
    '_calcular_nota_geral_por_escopo',
    '_calcular_nota_geral_por_municipio',
    '_calcular_nota_geral',
    '_calcular_acertos_habilidade_por_escopo',
    '_calcular_acertos_habilidade_por_municipio',
    '_calcular_acertos_habilidade',
    '_obter_nome_curso',
    '_obter_disciplinas_avaliacao',
    '_obter_ordem_disciplinas_avaliacao',
    '_determinar_escopo_relatorio',
    '_buscar_turmas_por_escopo',
    '_montar_resposta_relatorio',
    '_montar_resposta_relatorio_por_turmas',
]

