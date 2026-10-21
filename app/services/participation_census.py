# -*- coding: utf-8 -*-
"""Censo de participação da aplicação online, só em memória.

Não grava tabela e não altera endpoint. O chamador entrega turmas,
provas, vínculos ``class_test`` e resultados já autorizados.

Presença segue a modalidade do aluno. Regular conta só a prova regular.
ADAP 1, 2 ou 3 conta só a prova pareada. Modalidade errada, ou as duas
juntas, fica inconsistente: sem presença válida. A nota não escolhe a origem
e o ``test_id`` do resultado não é reescrito.

Completa significa presente em toda disciplina que a turma atual recebeu.
Pelo menos uma significa presente em uma ou mais dessas disciplinas.
Quem não tem turma atual vai para o histórico e fica fora da taxa.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.services.adap_resultado_pareado import classificar_resultado_modalidade
from app.services.alunos_resultado_filtro import aluno_entra_no_filtro, parse_alunos_filtro
from app.services.special_education import SpecialEducationStatus
from app.utils.decimal_helpers import round_to_two_decimals

_NIVEIS_ADAP = (1, 2, 3)


@dataclass(frozen=True)
class DisciplinaCenso:
    id: str
    nome: str


@dataclass(frozen=True)
class ProvaPareadaCenso:
    test_id: str
    nivel_da_prova: Optional[int] = None


@dataclass(frozen=True)
class ProvaCenso:
    """Prova regular da aplicação e as provas ADAP que apontam para ela."""

    test_id: str
    disciplinas: Tuple[DisciplinaCenso, ...]
    provas_adap: Tuple[ProvaPareadaCenso, ...] = ()


@dataclass(frozen=True)
class AlunoEntradaCenso:
    student_id: str
    escola_id: Optional[str] = None
    serie_id: Optional[str] = None
    turma_id: Optional[str] = None
    is_special: bool = False
    nivel_adap: Optional[int] = None


@dataclass(frozen=True)
class ResultadoEntradaCenso:
    student_id: str
    test_id: str
    calculated_at: Any = None
    class_id_snapshot: Optional[str] = None


@dataclass(frozen=True)
class ClassTestEntrada:
    class_id: str
    test_id: str


@dataclass(frozen=True)
class ParticipationCensusRequest:
    municipio_id: str
    provas: Sequence[ProvaCenso]
    universo: str
    alunos: Sequence[AlunoEntradaCenso]
    class_tests: Sequence[ClassTestEntrada]
    resultados: Sequence[ResultadoEntradaCenso]
    class_ids_permitidos: Optional[Iterable[str]] = None
    incluir_historico: bool = True
    excluir_faltantes: Optional[Iterable[str]] = None


@dataclass(frozen=True)
class OrigemCenso:
    tipo: str
    test_id: str
    nivel_da_prova: Optional[int] = None


@dataclass(frozen=True)
class DisciplinaAlunoCenso:
    disciplina_id: str
    nome: str
    prova_regular_id: str
    elegivel: bool
    situacao: str
    motivo_inconsistencia: Optional[str]
    origens: Tuple[OrigemCenso, ...]
    test_id_valido: Optional[str]


@dataclass(frozen=True)
class AlunoCenso:
    student_id: str
    escola_id: Optional[str]
    serie_id: Optional[str]
    turma_id: Optional[str]
    perfil: str
    nivel_adap: Optional[int]
    no_denominador: bool
    disciplinas: Tuple[DisciplinaAlunoCenso, ...]
    participacao_completa: bool
    participacao_pelo_menos_uma: bool
    historico: bool
    excluido_transferencia: bool


@dataclass(frozen=True)
class DisciplinaAgregada:
    disciplina_id: str
    nome: str
    prova_regular_id: str
    elegiveis: int
    presentes: int
    ausentes: int
    inconsistentes: int
    presentes_origem_regular: int
    presentes_origem_adap: int
    percentual_presentes: float


@dataclass(frozen=True)
class AgregadoCenso:
    nivel: str
    chave: str
    escola_id: Optional[str]
    serie_id: Optional[str]
    turma_id: Optional[str]
    matriculados: int
    presentes_completos: int
    presentes_pelo_menos_uma: int
    ausentes: int
    inconsistentes: int
    percentual_completa: float
    percentual_pelo_menos_uma: float
    por_disciplina: Tuple[DisciplinaAgregada, ...]


@dataclass(frozen=True)
class ParticipationCensus:
    alunos: Tuple[AlunoCenso, ...]
    geral: AgregadoCenso
    por_escola: Tuple[AgregadoCenso, ...]
    por_serie: Tuple[AgregadoCenso, ...]
    por_turma: Tuple[AgregadoCenso, ...]
    historico: int


@dataclass
class _SlotProva:
    prova_regular_id: str
    disciplina_id: str
    nome: str
    adap_por_id: Dict[str, Optional[int]] = field(default_factory=dict)


def campos_participacao(censo: ParticipationCensus, *, grupo: bool) -> Dict[str, Any]:
    """Campos de participação da resposta. Nota e proficiência ficam de fora."""
    geral = censo.geral
    participantes = geral.presentes_completos if grupo else geral.presentes_pelo_menos_uma
    percentual = geral.percentual_completa if grupo else geral.percentual_pelo_menos_uma
    fora = max(0, geral.matriculados - participantes)
    return {
        "total_alunos": geral.matriculados,
        "alunos_participantes": participantes,
        "alunos_completos": geral.presentes_completos,
        "alunos_parciais": max(0, geral.presentes_pelo_menos_uma - geral.presentes_completos),
        "alunos_ausentes": fora,
        "alunos_pendentes": fora,
        "percentual_comparecimento": percentual,
        "participacao_completa": {
            "presentes": geral.presentes_completos,
            "matriculados": geral.matriculados,
            "percentual": geral.percentual_completa,
        },
        "participacao_pelo_menos_uma": {
            "presentes": geral.presentes_pelo_menos_uma,
            "matriculados": geral.matriculados,
            "percentual": geral.percentual_pelo_menos_uma,
        },
        "por_disciplina_participacao": [
            {
                "id": item.disciplina_id,
                "nome": item.nome,
                "elegiveis": item.elegiveis,
                "presentes": item.presentes,
                "ausentes": item.ausentes,
                "inconsistentes": item.inconsistentes,
                "percentual": item.percentual_presentes,
            }
            for item in geral.por_disciplina
        ],
    }


def contagens_celula(
    censo: ParticipationCensus,
    escola_id: Any,
    serie_id: Any,
    disciplina: Optional[str] = None,
) -> Tuple[int, int]:
    """(matriculados, presentes) da célula. Sem disciplina, presentes = completa."""
    from app.services.special_education import fold_text

    escola = str(escola_id or "")
    serie = str(serie_id or "")
    alvo = fold_text(disciplina) if disciplina else ""
    matriculados = 0
    presentes = 0
    for aluno in censo.alunos:
        if not aluno.no_denominador:
            continue
        if str(aluno.escola_id or "") != escola or str(aluno.serie_id or "") != serie:
            continue
        matriculados += 1
        if not alvo:
            if aluno.participacao_completa:
                presentes += 1
            continue
        if any(
            item.elegivel and item.situacao == "presente" and fold_text(item.nome) == alvo
            for item in aluno.disciplinas
        ):
            presentes += 1
    return matriculados, presentes


def percentual_censo(numerador: int, denominador: int) -> float:
    """Razão do próprio conjunto, em duas casas. Denominador vazio vale 0."""
    if not denominador:
        return 0.0
    return round_to_two_decimals(100.0 * numerador / denominador)


def build_participation_census(pedido: ParticipationCensusRequest) -> ParticipationCensus:
    """Monta o censo. Não consulta banco e não projeta prova ADAP na regular."""
    universo = parse_alunos_filtro(pedido.universo)
    slots = _slots_da_aplicacao(pedido.provas)
    permitidas = _conjunto_opcional(pedido.class_ids_permitidos)
    excluir = _conjunto_opcional(pedido.excluir_faltantes) or set()
    provas_da_aplicacao = _ids_de_prova(slots)
    turmas_com_prova = _turmas_com_prova(pedido.class_tests, slots)
    resultados = _dedupe_resultados(pedido.resultados)
    por_aluno_prova = _resultados_por_aluno(resultados)

    alunos: List[AlunoCenso] = []
    historico_total = 0
    for entrada in pedido.alunos:
        aluno = _avaliar_aluno(
            entrada,
            universo=universo,
            slots=slots,
            turmas_com_prova=turmas_com_prova,
            por_aluno_prova=por_aluno_prova,
            permitidas=permitidas,
            excluir=excluir,
            provas_da_aplicacao=provas_da_aplicacao,
        )
        if aluno is None:
            continue
        if aluno.historico:
            historico_total += 1
            if not pedido.incluir_historico:
                continue
        alunos.append(aluno)

    alunos.sort(key=lambda item: item.student_id)
    no_denominador = [aluno for aluno in alunos if aluno.no_denominador]
    return ParticipationCensus(
        alunos=tuple(alunos),
        geral=_agregar("geral", pedido.municipio_id or "", None, None, None, no_denominador, slots),
        por_escola=tuple(_agregar_grupos(no_denominador, slots, "escola")),
        por_serie=tuple(_agregar_grupos(no_denominador, slots, "serie")),
        por_turma=tuple(_agregar_grupos(no_denominador, slots, "turma")),
        historico=historico_total,
    )


def _conjunto_opcional(valores: Optional[Iterable[str]]) -> Optional[set]:
    if valores is None:
        return None
    return {str(item) for item in valores if item}


def _slots_da_aplicacao(provas: Sequence[ProvaCenso]) -> List[_SlotProva]:
    slots: List[_SlotProva] = []
    for prova in provas or []:
        regular_id = str(getattr(prova, "test_id", "") or "")
        if not regular_id:
            continue
        adap_por_id = {
            str(par.test_id): par.nivel_da_prova
            for par in (prova.provas_adap or [])
            if getattr(par, "test_id", None)
        }
        disciplinas = list(prova.disciplinas or [])
        if not disciplinas:
            disciplinas = [DisciplinaCenso(id=regular_id, nome=regular_id)]
        for disciplina in disciplinas:
            disc_id = str(getattr(disciplina, "id", "") or "")
            if not disc_id:
                continue
            slots.append(
                _SlotProva(
                    prova_regular_id=regular_id,
                    disciplina_id=disc_id,
                    nome=str(getattr(disciplina, "nome", "") or ""),
                    adap_por_id=dict(adap_por_id),
                )
            )
    return slots


def _ids_de_prova(slots: Sequence[_SlotProva]) -> set:
    ids = set()
    for slot in slots:
        ids.add(slot.prova_regular_id)
        ids.update(slot.adap_por_id)
    return ids


def _turmas_com_prova(
    class_tests: Sequence[ClassTestEntrada],
    slots: Sequence[_SlotProva],
) -> Dict[str, set]:
    """Turma -> ids de prova regular que ela recebeu, inclusive via prova ADAP."""
    regular_por_qualquer = {}
    for slot in slots:
        regular_por_qualquer[slot.prova_regular_id] = slot.prova_regular_id
        for adap_id in slot.adap_por_id:
            regular_por_qualquer[adap_id] = slot.prova_regular_id
    por_turma: Dict[str, set] = {}
    for link in class_tests or []:
        class_id = str(getattr(link, "class_id", "") or "")
        test_id = str(getattr(link, "test_id", "") or "")
        regular_id = regular_por_qualquer.get(test_id)
        if not class_id or not regular_id:
            continue
        por_turma.setdefault(class_id, set()).add(regular_id)
    return por_turma


def _dedupe_resultados(
    resultados: Sequence[ResultadoEntradaCenso],
) -> List[ResultadoEntradaCenso]:
    por_chave: Dict[Tuple[str, str], ResultadoEntradaCenso] = {}
    ordem: List[Tuple[str, str]] = []
    for row in resultados or []:
        sid = str(getattr(row, "student_id", "") or "")
        tid = str(getattr(row, "test_id", "") or "")
        if not sid or not tid:
            continue
        chave = (sid, tid)
        prev = por_chave.get(chave)
        if prev is None:
            por_chave[chave] = row
            ordem.append(chave)
            continue
        if _mais_recente(row, prev):
            por_chave[chave] = row
    return [por_chave[chave] for chave in ordem]


def _mais_recente(atual: Any, anterior: Any) -> bool:
    atual_em = getattr(atual, "calculated_at", None)
    anterior_em = getattr(anterior, "calculated_at", None)
    if atual_em is None:
        return False
    if anterior_em is None:
        return True
    return atual_em > anterior_em


def _resultados_por_aluno(
    resultados: Sequence[ResultadoEntradaCenso],
) -> Dict[str, Dict[str, ResultadoEntradaCenso]]:
    por_aluno: Dict[str, Dict[str, ResultadoEntradaCenso]] = {}
    for row in resultados:
        sid = str(row.student_id)
        por_aluno.setdefault(sid, {})[str(row.test_id)] = row
    return por_aluno


def _avaliar_aluno(
    entrada: AlunoEntradaCenso,
    *,
    universo: str,
    slots: Sequence[_SlotProva],
    turmas_com_prova: Dict[str, set],
    por_aluno_prova: Dict[str, Dict[str, ResultadoEntradaCenso]],
    permitidas: Optional[set],
    excluir: set,
    provas_da_aplicacao: set,
) -> Optional[AlunoCenso]:
    sid = str(getattr(entrada, "student_id", "") or "")
    if not sid or not slots:
        return None
    status = SpecialEducationStatus(
        bool(entrada.is_special),
        entrada.nivel_adap if entrada.is_special else None,
        None,
    )
    if not aluno_entra_no_filtro(status, universo):
        return None

    turma_id = str(entrada.turma_id or "") or None
    linhas = por_aluno_prova.get(sid) or {}
    historico = _eh_historico(turma_id, linhas, provas_da_aplicacao)
    if turma_id and permitidas is not None and turma_id not in permitidas:
        return None
    if historico and permitidas is not None and not _snapshot_permitido(linhas, permitidas):
        return None

    provas_da_turma = turmas_com_prova.get(turma_id or "", set())
    excluido = sid in excluir and not historico
    disciplinas = tuple(
        _disciplina_do_aluno(slot, provas_da_turma, linhas, status, historico or excluido)
        for slot in slots
    )
    elegiveis = [item for item in disciplinas if item.elegivel]
    presente_alguma = any(item.situacao == "presente" for item in elegiveis)
    completa = bool(elegiveis) and all(item.situacao == "presente" for item in elegiveis)
    no_denominador = bool(elegiveis) and not historico and not excluido
    return AlunoCenso(
        student_id=sid,
        escola_id=entrada.escola_id,
        serie_id=entrada.serie_id,
        turma_id=turma_id,
        perfil=_perfil(status),
        nivel_adap=status.level if status.is_special else None,
        no_denominador=no_denominador,
        disciplinas=disciplinas,
        participacao_completa=completa and no_denominador,
        participacao_pelo_menos_uma=presente_alguma and no_denominador,
        historico=historico,
        excluido_transferencia=excluido,
    )


def _perfil(status: SpecialEducationStatus) -> str:
    if status.is_special and status.level in _NIVEIS_ADAP:
        return "adap"
    if status.is_special:
        return "especial_sem_nivel"
    return "regular"


def _eh_historico(
    turma_id: Optional[str],
    linhas: Dict[str, ResultadoEntradaCenso],
    provas_da_aplicacao: set,
) -> bool:
    if turma_id:
        return False
    return any(test_id in provas_da_aplicacao for test_id in linhas)


def _snapshot_permitido(
    linhas: Dict[str, ResultadoEntradaCenso],
    permitidas: set,
) -> bool:
    snapshots = {
        str(row.class_id_snapshot)
        for row in linhas.values()
        if getattr(row, "class_id_snapshot", None)
    }
    if not snapshots:
        return False
    return bool(snapshots & permitidas)


def _disciplina_do_aluno(
    slot: _SlotProva,
    provas_da_turma: set,
    linhas: Dict[str, ResultadoEntradaCenso],
    status: SpecialEducationStatus,
    fora_da_taxa: bool,
) -> DisciplinaAlunoCenso:
    elegivel = slot.prova_regular_id in provas_da_turma and not fora_da_taxa
    regular = linhas.get(slot.prova_regular_id)
    adap_rows = [linhas[tid] for tid in slot.adap_por_id if tid in linhas]
    origens = _origens(slot, regular, adap_rows)
    aluno_e_adap = bool(status.is_special and status.level in _NIVEIS_ADAP)
    if not status.is_special or aluno_e_adap:
        escolhido, situacao_modalidade = classificar_resultado_modalidade(
            regular,
            adap_rows,
            aluno_e_adap=aluno_e_adap,
        )
    else:
        escolhido, situacao_modalidade = (None, "inconsistente" if origens else "pendente")

    if situacao_modalidade == "participou" and escolhido is not None:
        situacao = "presente"
        motivo = None
        test_id_valido = str(getattr(escolhido, "test_id", "") or "") or None
        tipo_valido = "adap" if test_id_valido in slot.adap_por_id else "regular"
        origens_saida = tuple(origem for origem in origens if origem.tipo == tipo_valido)
    elif situacao_modalidade == "inconsistente":
        situacao = "inconsistente"
        motivo = _motivo(regular is not None, bool(adap_rows))
        test_id_valido = None
        origens_saida = origens
    else:
        situacao = "ausente"
        motivo = None
        test_id_valido = None
        origens_saida = ()

    if not elegivel:
        situacao_resposta = situacao if fora_da_taxa else "ausente"
        return DisciplinaAlunoCenso(
            disciplina_id=slot.disciplina_id,
            nome=slot.nome,
            prova_regular_id=slot.prova_regular_id,
            elegivel=False,
            situacao="ausente" if not fora_da_taxa else situacao_resposta,
            motivo_inconsistencia=motivo if fora_da_taxa and situacao == "inconsistente" else None,
            origens=origens_saida if fora_da_taxa else (),
            test_id_valido=test_id_valido if fora_da_taxa else None,
        )
    return DisciplinaAlunoCenso(
        disciplina_id=slot.disciplina_id,
        nome=slot.nome,
        prova_regular_id=slot.prova_regular_id,
        elegivel=True,
        situacao=situacao,
        motivo_inconsistencia=motivo,
        origens=origens_saida,
        test_id_valido=test_id_valido,
    )


def _origens(
    slot: _SlotProva,
    regular: Optional[ResultadoEntradaCenso],
    adap_rows: Sequence[ResultadoEntradaCenso],
) -> Tuple[OrigemCenso, ...]:
    origens: List[OrigemCenso] = []
    if regular is not None:
        origens.append(OrigemCenso("regular", slot.prova_regular_id, None))
    for row in adap_rows:
        tid = str(row.test_id)
        origens.append(OrigemCenso("adap", tid, slot.adap_por_id.get(tid)))
    return tuple(origens)


def _motivo(tem_regular: bool, tem_adap: bool) -> str:
    if tem_regular and tem_adap:
        return "ambas_modalidades"
    return "modalidade_incorreta"


def _agregar_grupos(
    alunos: Sequence[AlunoCenso],
    slots: Sequence[_SlotProva],
    nivel: str,
) -> List[AgregadoCenso]:
    grupos: Dict[Tuple[Optional[str], Optional[str], Optional[str]], List[AlunoCenso]] = {}
    for aluno in alunos:
        if nivel == "escola":
            chave = (aluno.escola_id, None, None)
        elif nivel == "serie":
            chave = (aluno.escola_id, aluno.serie_id, None)
        else:
            chave = (aluno.escola_id, aluno.serie_id, aluno.turma_id)
        grupos.setdefault(chave, []).append(aluno)
    agregados = [
        _agregar(
            nivel,
            "|".join(str(parte or "") for parte in chave),
            chave[0],
            chave[1],
            chave[2],
            grupo,
            slots,
        )
        for chave, grupo in grupos.items()
    ]
    agregados.sort(key=lambda item: item.chave)
    return agregados


def _agregar(
    nivel: str,
    chave: str,
    escola_id: Optional[str],
    serie_id: Optional[str],
    turma_id: Optional[str],
    alunos: Sequence[AlunoCenso],
    slots: Sequence[_SlotProva],
) -> AgregadoCenso:
    matriculados = len(alunos)
    completos = sum(1 for aluno in alunos if aluno.participacao_completa)
    alguma = sum(1 for aluno in alunos if aluno.participacao_pelo_menos_uma)
    inconsistentes = 0
    ausentes = 0
    for aluno in alunos:
        elegiveis = [item for item in aluno.disciplinas if item.elegivel]
        tem_inconsistente = any(item.situacao == "inconsistente" for item in elegiveis)
        tem_presente = any(item.situacao == "presente" for item in elegiveis)
        if tem_inconsistente:
            inconsistentes += 1
        if not tem_presente and not tem_inconsistente:
            ausentes += 1
    return AgregadoCenso(
        nivel=nivel,
        chave=chave,
        escola_id=escola_id,
        serie_id=serie_id,
        turma_id=turma_id,
        matriculados=matriculados,
        presentes_completos=completos,
        presentes_pelo_menos_uma=alguma,
        ausentes=ausentes,
        inconsistentes=inconsistentes,
        percentual_completa=percentual_censo(completos, matriculados),
        percentual_pelo_menos_uma=percentual_censo(alguma, matriculados),
        por_disciplina=tuple(_agregar_disciplinas(alunos, slots)),
    )


def _agregar_disciplinas(
    alunos: Sequence[AlunoCenso],
    slots: Sequence[_SlotProva],
) -> List[DisciplinaAgregada]:
    agregadas: List[DisciplinaAgregada] = []
    for slot in slots:
        elegiveis = presentes = ausentes = inconsistentes = 0
        origem_regular = origem_adap = 0
        for aluno in alunos:
            item = next(
                (
                    disc
                    for disc in aluno.disciplinas
                    if disc.prova_regular_id == slot.prova_regular_id
                    and disc.disciplina_id == slot.disciplina_id
                ),
                None,
            )
            if item is None or not item.elegivel:
                continue
            elegiveis += 1
            if item.situacao == "presente":
                presentes += 1
                if any(origem.tipo == "adap" for origem in item.origens):
                    origem_adap += 1
                else:
                    origem_regular += 1
            elif item.situacao == "inconsistente":
                inconsistentes += 1
            else:
                ausentes += 1
        agregadas.append(
            DisciplinaAgregada(
                disciplina_id=slot.disciplina_id,
                nome=slot.nome,
                prova_regular_id=slot.prova_regular_id,
                elegiveis=elegiveis,
                presentes=presentes,
                ausentes=ausentes,
                inconsistentes=inconsistentes,
                presentes_origem_regular=origem_regular,
                presentes_origem_adap=origem_adap,
                percentual_presentes=percentual_censo(presentes, elegiveis),
            )
        )
    return agregadas
