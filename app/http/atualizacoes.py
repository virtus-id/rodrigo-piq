"""As respostas mudaram desde o plano? — `RF-120`, `AC-185`, `AC-188` (T-343).

O aluno com plano liberado edita uma resposta e, sem este aviso, não tem como
saber que o plano que vê já não reflete o que ele respondeu. A comparação é
entre o estado financeiro MONTADO das respostas de agora (a mesma montagem do
cálculo) e o `estado_inputs` do plano liberado — não entre datas: regravar o
mesmo valor não é mudança, e mudar algo que o plano não lê também não.

**Nunca derruba o Início.** Qualquer falha na montagem (uma resposta que o
cálculo recusaria, por exemplo) vira `None` — "não sei dizer" — e fica no log.
O Início só deixa de AFIRMAR a mudança; a ação de pedir o plano novo continua
lá (`AC-188`).

REGRAS: `RF-120`, `AC-185`, `AC-188`
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Final

from app.casos.maquina import Caso
from app.http.edicao import ESTADOS_COM_PLANO_LIBERADO
from app.http.rotas_calculo import (
    ParametrosExternosDoBloco6,
    _montar_estado_financeiro_do_caso,
    _respostas_do_calculo,
)
from collection.carga import ColecaoDeRegistros
from collection.registro import EscopoRepeticao
from collection.respostas import RespostasCaso
from engine.snapshot import SnapshotOrdem

_LOGGER: Final = logging.getLogger(__name__)


def _canonico(valor: Any) -> Any:
    """Forma comparável de um estado de entrada: o mesmo critério que o motor usa
    para o `hash_inputs` do snapshot (`Decimal` como texto, `Enum` pelo valor,
    contêineres pela ordem, `frozenset` ordenado), mas aqui na aplicação — o
    motor é arquivo congelado (`AC-44`) e não se importa dele além da fronteira
    (`AC-41`). Um snapshot relido do banco pode trazer a mesma carteira em outro
    contêiner; isso não é mudança de resposta."""
    if valor is None or isinstance(valor, str | int | bool):
        return valor
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Mapping):
        return {str(_canonico(k)): _canonico(v) for k, v in valor.items()}
    if isinstance(valor, frozenset | set):
        return sorted(_canonico(item) for item in valor)
    if isinstance(valor, tuple | list):
        return [_canonico(item) for item in valor]
    if hasattr(valor, "__dataclass_fields__"):
        campos = sorted(valor.__dataclass_fields__)
        return {nome: _canonico(getattr(valor, nome)) for nome in campos}
    return str(valor)  # tipo novo: compara pelo texto, nunca por identidade


def respostas_mudaram_desde_o_plano(
    *,
    caso: Caso,
    snapshot: SnapshotOrdem | None,
    respostas: RespostasCaso,
    itens_por_escopo: dict[EscopoRepeticao, tuple[str, ...]],
    colecao: ColecaoDeRegistros,
    parametros_externos: ParametrosExternosDoBloco6,
) -> bool | None:
    """`True`/`False` com plano liberado; `None` fora dele ou sem como comparar."""
    if snapshot is None or caso.estado not in ESTADOS_COM_PLANO_LIBERADO:
        return None
    try:
        do_calculo = _respostas_do_calculo(colecao.registros, respostas)
        externos = parametros_externos.obter(caso, do_calculo)
        atual = _montar_estado_financeiro_do_caso(caso, do_calculo, itens_por_escopo, externos)
    except Exception:  # defensivo de propósito: a decoração do Início nunca a derruba
        _LOGGER.warning("comparação impossível", exc_info=True)
        return None
    mudou: bool = _canonico(atual) != _canonico(snapshot.estado_inputs)
    return mudou
