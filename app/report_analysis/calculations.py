# -*- coding: utf-8 -*-
"""
Funções de cálculo de relatórios.
Importa funções do report_routes.py original para manter compatibilidade.
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

