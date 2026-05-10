# -*- coding: utf-8 -*-
"""
Serviço de indicadores PNEERQ calculados a partir das respostas dos formulários socioeconômicos.

Este serviço NÃO executa SAEB externo; ele usa as respostas já coletadas nos templates
`aluno-jovem` e `aluno-velho` do próprio sistema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.socioeconomic_forms.services.results_service import ResultsService


RACE_PRETA = "Preta"
RACE_PARDA = "Parda"
RACE_BRANCA = "Branca"


def _normalize_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _race_group(value: Optional[str]) -> str:
    """
    Grupos raciais para dashboard:
    - Branca
    - PretaParda (Preta + Parda)
    - Outras (Amarela, Indígena, etc.)
    - NaoDeclarada
    """
    v = (_normalize_str(value) or "").lower()
    if v == "branca":
        return "Branca"
    if v in ("preta", "parda"):
        return "PretaParda"
    if v in ("não quero declarar", "nao quero declarar", "não declarar", "nao declarar"):
        return "NaoDeclarada"
    if v:
        return "Outras"
    return "NaoInformada"


def _parse_age(value: Optional[str]) -> Optional[int]:
    """
    Converte opções textuais do questionário em idade aproximada (inteiro).
    Regras:
    - Pega o primeiro número encontrado
    - "Menos de 3 anos" => 2
    - "13 anos ou menos" => 13
    - "13 anos ou mais" => 13
    - "18 anos ou mais" => 18
    """
    s = (_normalize_str(value) or "").lower()
    if not s:
        return None
    if "menos de 3" in s:
        return 2

    import re

    m = re.search(r"(\d+)", s)
    if not m:
        return None
    return int(m.group(1))


def _parse_grade_from_text(value: Optional[str]) -> Optional[int]:
    """
    Extrai o ano escolar (1..9) de textos como '5º Ano', '7 ano', etc.
    Retorna None se não conseguir.
    """
    s = (_normalize_str(value) or "").lower()
    if not s:
        return None
    import re

    m = re.search(r"(\d+)", s)
    if not m:
        return None
    n = int(m.group(1))
    if 1 <= n <= 9:
        return n
    return None


def _distorcao_threshold_from_template(q1_value: Optional[str]) -> Optional[int]:
    """
    Retorna a idade a partir da qual o aluno é considerado em distorção idade-série,
    seguindo a tabela documentada em `app/socioeconomic_forms/templates/README.md`.

    Regra baseada na resposta de série/curso (q1).

    aluno-jovem:
      - Creche: 5
      - Pré I: 6
      - Pré II: 7
      - 1º Ano: 8
      - 2º Ano: 9
      - 3º Ano: 10
      - 4º Ano: 11
      - 5º Ano: 12

    aluno-velho:
      - 4º Ano: 11
      - 5º Ano: 12
      - 6º Ano: 13
      - 7º Ano: 14
      - 8º Ano: 15
      - 9º Ano: 16
      - EJA: não definido (retorna None)
    """
    s = (_normalize_str(q1_value) or "").lower()
    if not s:
        return None

    # Educação Infantil
    if "creche" in s:
        return 5
    if "pré i" in s or "pre i" in s:
        return 6
    if "pré ii" in s or "pre ii" in s:
        return 7

    # EJA não tem regra de distorção definida na tabela
    if "eja" in s:
        return None

    # Anos do EF (1º a 9º)
    grade_num = _parse_grade_from_text(q1_value)
    if grade_num is None:
        return None

    thresholds = {
        1: 8,
        2: 9,
        3: 10,
        4: 11,
        5: 12,
        6: 13,
        7: 14,
        8: 15,
        9: 16,
    }
    return thresholds.get(grade_num)


@dataclass(frozen=True)
class Metric:
    numerator: int
    denominator: int

    @property
    def value(self) -> float:
        if self.denominator <= 0:
            return 0.0
        return round(self.numerator / self.denominator * 100.0, 2)


class PneerqService:
    """
    Gera relatório PNEERQ com indicadores de equidade racial.
    """

    @staticmethod
    def calculate_pneerq_report(
        form_id: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        filters = filters or {}

        # Reutiliza a mesma base de joins e filtros do ResultsService
        query = ResultsService._build_base_query(form_id, filters)  # pylint: disable=protected-access
        results = query.all()

        # "results" é uma lista de tuplas: (FormResponse, User, Student, School, Grade, Class, City)
        total_respostas = len(results)

        # Contadores por raça (grupo para equidade)
        denom_by_race: Dict[str, int] = {}

        def inc_denom(race_key: str) -> None:
            denom_by_race[race_key] = denom_by_race.get(race_key, 0) + 1

        # Indicadores: numeradores por raça
        num_age_distortion_by_race: Dict[str, int] = {}
        num_dropout_by_race: Dict[str, int] = {}
        num_curricular_silencing_by_race: Dict[str, int] = {}
        num_bullying_low_by_race: Dict[str, int] = {}
        num_safety_low_by_race: Dict[str, int] = {}
        num_expectation_low_h_by_race: Dict[str, int] = {}
        num_expectation_low_i_by_race: Dict[str, int] = {}
        num_non_portuguese_by_race: Dict[str, int] = {}

        # Distribuições para dashboard (overall)
        race_distribution_group: Dict[str, int] = {}
        curricular_distribution: Dict[str, int] = {}
        expectativa_distribution: Dict[str, int] = {}

        # Para agregação por escola/município (usado principalmente no agregado)
        by_school: Dict[str, Dict[str, Any]] = {}
        by_municipio: Dict[str, Dict[str, Any]] = {}

        def _inc(d: Dict[str, int], k: str) -> None:
            d[k] = d.get(k, 0) + 1

        def _get_scope_keys(school, city) -> Tuple[Optional[str], Optional[str]]:
            school_id = getattr(school, "id", None)
            municipio_id = getattr(city, "id", None)
            return (str(school_id) if school_id else None, str(municipio_id) if municipio_id else None)

        # Regras de respostas
        curricular_silencing_bad = {"Poucos deles", "Nenhum deles"}
        bullying_low_bad = {"Poucos deles", "Nenhum deles"}
        agree_disagree_negative = {"Discordo", "Discordo totalmente"}

        curricular_labels = ["Todos eles", "A maior parte deles", "Poucos deles", "Nenhum deles"]
        expectativa_labels = ["Concordo totalmente", "Concordo", "Discordo", "Discordo totalmente"]

        for response, _user, _student, school, grade, _class, city in results:
            responses_data = response.responses or {}

            race_raw = _normalize_str(responses_data.get("q5"))
            race_key = _race_group(race_raw)
            inc_denom(race_key)
            race_distribution_group[race_key] = race_distribution_group.get(race_key, 0) + 1

            # === Eixo 2: distorção idade-série (conforme tabela do template: q1 + q2) ===
            age = _parse_age(_normalize_str(responses_data.get("q2")))
            q1 = _normalize_str(responses_data.get("q1"))
            if age is not None:
                threshold = _distorcao_threshold_from_template(q1)
                if threshold is not None and age >= threshold:
                    _inc(num_age_distortion_by_race, race_key)

            # === Eixo 2: abandono (q21) ===
            q21 = _normalize_str(responses_data.get("q21"))
            if q21 and q21 != "Nunca":
                _inc(num_dropout_by_race, race_key)

            # === Eixo 3/4: silenciamento curricular (q23d) ===
            q23d = _normalize_str(responses_data.get("q23d"))
            if q23d:
                curricular_distribution[q23d] = curricular_distribution.get(q23d, 0) + 1
            if q23d in curricular_silencing_bad:
                _inc(num_curricular_silencing_by_race, race_key)

            # === Eixo 5: bullying/violência (q23f) ===
            q23f = _normalize_str(responses_data.get("q23f"))
            if q23f in bullying_low_bad:
                _inc(num_bullying_low_by_race, race_key)

            # === Eixo 5: percepção de segurança (q24d) ===
            q24d = _normalize_str(responses_data.get("q24d"))
            if q24d in agree_disagree_negative:
                _inc(num_safety_low_by_race, race_key)

            # === Eixo 6: expectativa docente (q24h/q24i) ===
            q24h = _normalize_str(responses_data.get("q24h"))
            if q24h:
                expectativa_distribution[q24h] = expectativa_distribution.get(q24h, 0) + 1
            if q24h in agree_disagree_negative:
                _inc(num_expectation_low_h_by_race, race_key)
            q24i = _normalize_str(responses_data.get("q24i"))
            if q24i in agree_disagree_negative:
                _inc(num_expectation_low_i_by_race, race_key)

            # === Eixo 7: diversidade linguística (q4) ===
            q4 = _normalize_str(responses_data.get("q4"))
            if q4 and q4 != "Português":
                _inc(num_non_portuguese_by_race, race_key)

            school_id, municipio_id = _get_scope_keys(school, city)
            if school_id:
                by_school.setdefault(
                    school_id,
                    {
                        "school": {"id": school_id, "nome": getattr(school, "name", None), "name": getattr(school, "name", None)},
                        "denominador": 0,
                        "porGrupoRacial": {},
                    },
                )
                by_school[school_id]["denominador"] += 1
            if municipio_id:
                by_municipio.setdefault(
                    municipio_id,
                    {
                        "municipio": {"id": municipio_id, "nome": getattr(city, "name", None), "name": getattr(city, "name", None), "estado": getattr(city, "state", None)},
                        "denominador": 0,
                        "porGrupoRacial": {},
                    },
                )
                by_municipio[municipio_id]["denominador"] += 1

        def metric_for(numerators: Dict[str, int], race_key: str) -> Metric:
            return Metric(numerator=numerators.get(race_key, 0), denominator=denom_by_race.get(race_key, 0))

        def metric_total(numerators: Dict[str, int]) -> Metric:
            return Metric(numerator=sum(numerators.values()), denominator=sum(denom_by_race.values()))

        grupos = sorted(denom_by_race.keys())

        def indicator(
            *,
            indicator_id: str,
            nome: str,
            descricao: str,
            numerators: Dict[str, int],
            unit: str = "percent",
        ) -> Dict[str, Any]:
            total_m = metric_total(numerators)
            por_grupo = {
                g: {
                    "numerador": metric_for(numerators, g).numerator,
                    "denominador": metric_for(numerators, g).denominator,
                    "valor": metric_for(numerators, g).value,
                }
                for g in grupos
            }
            return {
                "id": indicator_id,
                "nome": nome,
                "descricao": descricao,
                "unidade": unit,
                "metricas": {
                    "numerador": total_m.numerator,
                    "denominador": total_m.denominator,
                    "valor": total_m.value,
                },
                "porGrupoRacial": por_grupo,
            }

        # Helpers para dashboard (sem expor detalhes técnicos)
        def pct(num: int, den: int) -> float:
            if den <= 0:
                return 0.0
            return round(num / den * 100.0, 2)

        total_students = sum(denom_by_race.values())
        branca_neg = metric_for(num_expectation_low_i_by_race, "Branca").value
        preta_parda_neg = metric_for(num_expectation_low_i_by_race, "PretaParda").value
        gap_motivacao_pp = round(preta_parda_neg - branca_neg, 2)

        silenciamento_num = curricular_distribution.get("Poucos deles", 0) + curricular_distribution.get("Nenhum deles", 0)
        silenciamento_pct = pct(silenciamento_num, total_respostas)
        preta_parda_share = pct(denom_by_race.get("PretaParda", 0), total_students)

        risk_components = [
            metric_total(num_curricular_silencing_by_race).value,
            metric_total(num_safety_low_by_race).value,
            metric_total(num_expectation_low_i_by_race).value,
            metric_total(num_age_distortion_by_race).value,
        ]
        risk_score = round(sum(risk_components) / len(risk_components), 2) if risk_components else 0.0
        if risk_score >= 60:
            alvo = "ALTO"
        elif risk_score >= 35:
            alvo = "MÉDIO"
        else:
            alvo = "BAIXO"

        def status_from_health(health: float) -> str:
            if health >= 70:
                return "CONCLUÍDO"
            if health >= 40:
                return "ALERTA"
            return "CRÍTICO"

        eixos = {
            "eixo2_diagnostico_monitoramento": {
                "nome": "Eixo 2 — Diagnóstico e Monitoramento",
                "indicadores": [
                    indicator(
                        indicator_id="age_grade_distortion",
                        nome="Distorção idade-série",
                        descricao="Percentual de alunos em distorção idade-série.",
                        numerators=num_age_distortion_by_race,
                    ),
                    indicator(
                        indicator_id="dropout_history",
                        nome="Histórico de abandono escolar",
                        descricao="Percentual de alunos com histórico de abandono escolar.",
                        numerators=num_dropout_by_race,
                    ),
                ],
            },
            "eixo3_4_formacao_curriculo": {
                "nome": "Eixo 3/4 — Formação e Currículo",
                "indicadores": [
                    indicator(
                        indicator_id="curricular_silencing_index",
                        nome="Silenciamento curricular",
                        descricao="Percentual de estudantes que relatam baixa abordagem do tema em sala.",
                        numerators=num_curricular_silencing_by_race,
                    )
                ],
            },
            "eixo5_protocolos_racismo": {
                "nome": "Eixo 5 — Protocolos contra o Racismo (Clima/Segurança)",
                "indicadores": [
                    indicator(
                        indicator_id="violence_bullying_low_approach",
                        nome="Abordagem de bullying/violência (baixa)",
                        descricao="Percentual de estudantes que relatam baixa abordagem do tema em sala.",
                        numerators=num_bullying_low_by_race,
                    ),
                    indicator(
                        indicator_id="safety_perception_low",
                        nome="Percepção de segurança (baixa)",
                        descricao="Percentual de estudantes com percepção de segurança baixa na escola.",
                        numerators=num_safety_low_by_race,
                    ),
                ],
            },
            "eixo6_afirmacao_trajetorias": {
                "nome": "Eixo 6 — Afirmação de Trajetórias (Expectativas)",
                "indicadores": [
                    indicator(
                        indicator_id="teacher_expectation_low_capable",
                        nome="Expectativa docente (baixa)",
                        descricao="Percentual de estudantes com baixa percepção de expectativa docente.",
                        numerators=num_expectation_low_h_by_race,
                    ),
                    indicator(
                        indicator_id="teacher_expectation_low_motivation",
                        nome="Motivação docente (baixa)",
                        descricao="Percentual de estudantes com baixa percepção de motivação docente.",
                        numerators=num_expectation_low_i_by_race,
                    ),
                ],
            },
            "eixo7_difusao_saberes": {
                "nome": "Eixo 7 — Difusão de Saberes (Diversidade)",
                "indicadores": [
                    indicator(
                        indicator_id="home_language_non_portuguese",
                        nome="Língua em casa não-Português",
                        descricao="Percentual de estudantes que indicam outra língua em casa.",
                        numerators=num_non_portuguese_by_race,
                    )
                ],
            },
        }

        curriculo_values = [curricular_distribution.get(lbl, 0) for lbl in curricular_labels]
        curriculo_pct_values = [pct(v, total_respostas) for v in curriculo_values]

        expectativa_values = [expectativa_distribution.get(lbl, 0) for lbl in expectativa_labels]
        expectativa_pct_values = [pct(v, total_respostas) for v in expectativa_values]

        health_monitoramento = round(100.0 - metric_total(num_age_distortion_by_race).value, 2)
        health_formacao = round(100.0 - metric_total(num_curricular_silencing_by_race).value, 2)
        health_protocolos = round(
            100.0 - max(metric_total(num_safety_low_by_race).value, metric_total(num_bullying_low_by_race).value),
            2,
        )

        return {
            "formId": form_id,
            "totalRespostas": total_respostas,
            "filtros": ResultsService._format_filters_info(filters, results),  # pylint: disable=protected-access
            "gruposRaciais": {
                "disponiveis": grupos,
                "definicao": {
                    "Branca": ["Branca"],
                    "PretaParda": ["Preta", "Parda"],
                    "Outras": ["Amarela", "Indígena", "Outras"],
                    "NaoDeclarada": ["Não quero declarar"],
                    "NaoInformada": ["(vazio)"],
                },
            },
            "metadados": {
                "ageDistortionRule": "template_thresholds",
                "ageDistortionThresholds": {
                    "Creche": 5,
                    "Pré I": 6,
                    "Pré II": 7,
                    "1º Ano": 8,
                    "2º Ano": 9,
                    "3º Ano": 10,
                    "4º Ano": 11,
                    "5º Ano": 12,
                    "6º Ano": 13,
                    "7º Ano": 14,
                    "8º Ano": 15,
                    "9º Ano": 16
                },
                "fonte": "forms",
            },
            "eixos": eixos,
            "dashboard": {
                "kpis": [
                    {
                        "id": "perfil_etnico_racial_preta_parda",
                        "titulo": "Perfil étnico-racial",
                        "valor": preta_parda_share,
                        "unidade": "percent",
                        "subtitulo": "Pretos e pardos",
                    },
                    {
                        "id": "silenciamento_curricular",
                        "titulo": "Silenciamento curricular",
                        "valor": silenciamento_pct,
                        "unidade": "percent",
                        "subtitulo": "Baixa abordagem do tema",
                    },
                    {
                        "id": "gap_motivacao",
                        "titulo": "Gap de motivação",
                        "valor": gap_motivacao_pp,
                        "unidade": "pp",
                        "subtitulo": "Pretos/pardos vs brancos",
                    },
                    {
                        "id": "alvo_pneerq",
                        "titulo": "Alvo PNEERQ",
                        "valor": alvo,
                        "unidade": "label",
                        "subtitulo": "Prioridade de intervenção",
                    },
                ],
                "charts": {
                    "curriculo": {
                        "titulo": "Abordagem do tema em sala",
                        "labels": curricular_labels,
                        "valuesPercent": curriculo_pct_values,
                        "valuesCount": curriculo_values,
                    },
                    "expectativa": {
                        "titulo": "Expectativa docente",
                        "labels": expectativa_labels,
                        "valuesPercent": expectativa_pct_values,
                        "valuesCount": expectativa_values,
                    },
                },
                "matrix": [
                    {
                        "eixo": "Diagnóstico e monitoramento",
                        "referencia": "Raça e fluxo escolar",
                        "saude": health_monitoramento,
                        "status": status_from_health(health_monitoramento),
                    },
                    {
                        "eixo": "Formação e currículo",
                        "referencia": "Abordagem do tema em sala",
                        "saude": health_formacao,
                        "status": status_from_health(health_formacao),
                    },
                    {
                        "eixo": "Clima e segurança",
                        "referencia": "Bullying/violência e segurança",
                        "saude": health_protocolos,
                        "status": status_from_health(health_protocolos),
                    },
                ],
                "score": {
                    "risco": risk_score,
                    "alvo": alvo,
                },
                "quality": {
                    "semInformacaoRacaPercent": pct(denom_by_race.get("NaoInformada", 0), total_students),
                },
            },
            # Mantido para possível evolução do frontend (não usado pelas rotas atuais)
            "breakdowns": {
                "bySchool": by_school,
                "byMunicipio": by_municipio,
            },
        }

