"""Carregador dos estados financeiros dos gabaritos — T-11.

Lê `gab_a.json`, `gab_b.json` e `gab_c.json` (fixtures em `tests/fixtures/`) e
constrói `EstadoFinanceiro` de verdade (`engine/estado.py`), instanciando
`Divida`, `PerfilComportamental` e `SinaisComportamentais` conforme o schema
real do motor (T-08).

Todo valor monetário/taxa no JSON é STRING — nunca `number` — para virar
`Decimal` exato via `engine/precisao.dinheiro()` na carga (RF-12/G-01), e
nunca passar por `float`. É diferente do padrão de
`parameters/parametros-1.0.1.json` (que usa `parse_float=Decimal` sobre
literais numéricos): aqui a string é obrigatória mesmo para o `json.load`
padrão, porque `DinheiroTalvez`/`TaxaTalvez` também aceitam o literal
`"DESCONHECIDO"`, que só faz sentido como string.

Chaves de metadado que começam com `_` (ex.: `_nota_t11`,
`_perfil_comportamental_preenchimento_fixture`) são documentação sobre a
proveniência do dado — nunca carregadas em `EstadoFinanceiro`. Ver a
docstring de cada fixture para o que é normativo (transcrito da seção 10 da
canônica) e o que é preenchimento de engenharia necessário para completar o
objeto.

REGRAS: as fixtures reproduzem `GAB-A`, `GAB-B`, `GAB-C` — §10.2 de
`specs/piq-app-spec.md`.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from engine.estado import (
    CERTEZA_RECURSO_EXTRAORDINARIO,
    COBERTURA_MEIOS_PAGAMENTO,
    COBERTURA_PEQUENOS_GASTOS,
    CONHECIMENTO_GASTO,
    DEFASAGEM_REGISTRO,
    DISPOSICAO_USO_INVESTIMENTO,
    DISPOSICAO_USO_RESERVA,
    ESSENCIALIDADE,
    FREQUENCIA_REGISTRO,
    GASTOS_NAO_IDENTIFICADOS,
    JANELA_NOVA_DIVIDA,
    JANELA_RECURSO_EXTRAORDINARIO,
    LIQUIDEZ_INVESTIMENTOS,
    POSSIBILIDADE_VENDA,
    REGISTRO_GASTOS,
    RESERVA_EXISTE,
    REVISAO_SEMANAL,
    TIPO_ATIVO_FISICO,
    TIPO_DIVIDA,
    TIPO_RENDA,
    Divida,
    EstadoFinanceiro,
    ItemAtivo,
    ItemInvestimento,
    PerfilComportamental,
    RecursoExtraordinario,
    SinaisComportamentais,
)
from engine.precisao import dinheiro
from engine.tipos import (
    CONFIABILIDADE_DADOS,
    DESCONHECIDO,
    STATUS_DIVIDA,
    STATUS_VALIDADE_PROPOSTA,
    Desconhecido,
    DinheiroTalvez,
    SimNaoTalvez,
    TaxaTalvez,
)

DIRETORIO_FIXTURES = Path(__file__).parent


def _dinheiro_talvez(bruto: str) -> DinheiroTalvez:
    """Converte string do JSON em `Dinheiro` exato ou `DESCONHECIDO`.

    Nunca aceita `number` do JSON: o parser é sempre chamado sem
    `parse_float`, então qualquer valor não-string já teria vindo como
    `int`/`float` do `json.load` — e só `str` chega aqui por contrato do
    schema da fixture (ver docstring do módulo).
    """
    if bruto == "DESCONHECIDO":
        return DESCONHECIDO
    return dinheiro(bruto)


def _taxa_talvez(bruto: str) -> TaxaTalvez:
    if bruto == "DESCONHECIDO":
        return DESCONHECIDO
    return dinheiro(bruto)


def _dinheiro_talvez_ou_none(bruto: str | None) -> DinheiroTalvez | None:
    """RF-56, R4.6.1 — `RENDA_RECORRENTE_ATIVO: DinheiroTalvez | None` tem um
    TERCEIRO estado além de `Dinheiro`/`DESCONHECIDO`: `None` é o sentinela
    ESTRUTURAL de ausência (veículo, `OQ-38`), nunca confundido com
    `DESCONHECIDO`. Checa `None` primeiro, antes de delegar a
    `_dinheiro_talvez`."""
    if bruto is None:
        return None
    return _dinheiro_talvez(bruto)


def _int_talvez(bruto: object) -> int | Desconhecido:
    """Converte um inteiro 0–10 (JSON `number`) ou `DESCONHECIDO`.

    Compartilhado por `Divida.PESO_EMOCIONAL` (O-05/H-04) e
    `SinaisComportamentais.NECESSIDADE_VITORIA` (Definições §1, T-18) — mesmo
    domínio `int | Desconhecido` de escala 0–10, mesma regra de conversão.
    """
    if bruto == "DESCONHECIDO":
        return DESCONHECIDO
    assert isinstance(bruto, int)
    return bruto


def _carregar_divida(bruto: dict[str, Any]) -> Divida:
    return Divida(
        DIVIDA_ID=bruto["DIVIDA_ID"],
        TIPO_DIVIDA=TIPO_DIVIDA[bruto["TIPO_DIVIDA"]],
        STATUS_DIVIDA=STATUS_DIVIDA[bruto["STATUS_DIVIDA"]],
        SALDO_DEVEDOR_ATUAL=_dinheiro_talvez(bruto["SALDO_DEVEDOR_ATUAL"]),
        VALOR_QUITACAO_HOJE=_dinheiro_talvez(bruto["VALOR_QUITACAO_HOJE"]),
        QUITACAO_CONSULTADA=SimNaoTalvez[bruto["QUITACAO_CONSULTADA"]],
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA[bruto["STATUS_VALIDADE_PROPOSTA"]],
        TAXA_EFETIVA_MENSAL_NORMALIZADA=_taxa_talvez(bruto["TAXA_EFETIVA_MENSAL_NORMALIZADA"]),
        CET=_taxa_talvez(bruto["CET"]),
        PARCELA_CONTRATUAL=_dinheiro_talvez(bruto["PARCELA_CONTRATUAL"]),
        PAGAMENTO_MENSAL_EFETIVO=_dinheiro_talvez(bruto["PAGAMENTO_MENSAL_EFETIVO"]),
        SEGURO_INCLUIDO_PARCELA=bruto["SEGURO_INCLUIDO_PARCELA"],
        CUSTO_SEGURO=_dinheiro_talvez(bruto["CUSTO_SEGURO"]),
        PESO_EMOCIONAL=_int_talvez(bruto["PESO_EMOCIONAL"]),
        RENEGOCIACAO_PENDENTE=bruto["RENEGOCIACAO_PENDENTE"],
        TROCA_PENDENTE=bruto["TROCA_PENDENTE"],
        RISCO_MATERIAL_IMINENTE=bruto["RISCO_MATERIAL_IMINENTE"],
        OPORTUNIDADE_VIGENTE=None,  # nenhuma fixture de T-11 usa Gate 4 vigente
    )


def _carregar_perfil_comportamental(bruto: dict[str, Any]) -> PerfilComportamental:
    return PerfilComportamental(
        REGISTRO_GASTOS=REGISTRO_GASTOS[bruto["REGISTRO_GASTOS"]],
        FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO[bruto["FREQUENCIA_REGISTRO"]],
        DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO[bruto["DEFASAGEM_REGISTRO"]],
        COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS[bruto["COBERTURA_PEQUENOS_GASTOS"]],
        COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO[bruto["COBERTURA_MEIOS_PAGAMENTO"]],
        CONHECIMENTO_GASTO=CONHECIMENTO_GASTO[bruto["CONHECIMENTO_GASTO"]],
        GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS[bruto["GASTOS_NAO_IDENTIFICADOS"]],
        REVISAO_SEMANAL=REVISAO_SEMANAL[bruto["REVISAO_SEMANAL"]],
    )


def _mecanismo_deficit(bruto: object) -> frozenset[str] | Desconhecido:
    if bruto == "DESCONHECIDO":
        return DESCONHECIDO
    assert isinstance(bruto, list)
    return frozenset(bruto)


def _janela_nova_divida(bruto: object) -> JANELA_NOVA_DIVIDA | None:
    """B1.05 — `None` é ausência ESTRUTURAL (campo COND, só exibido quando
    `NOVA_DIVIDA_PREVISTA ∈ {SIM, TALVEZ}`), não `DESCONHECIDO` (T-34)."""
    if bruto is None:
        return None
    assert isinstance(bruto, str)
    return JANELA_NOVA_DIVIDA[bruto]


def _carregar_sinais_comportamentais(bruto: dict[str, Any]) -> SinaisComportamentais:
    return SinaisComportamentais(
        NOVA_DIVIDA_PREVISTA=SimNaoTalvez[bruto["NOVA_DIVIDA_PREVISTA"]],
        MECANISMO_DEFICIT=_mecanismo_deficit(bruto["MECANISMO_DEFICIT"]),
        HISTORICO_RECAIDA=SimNaoTalvez[bruto["HISTORICO_RECAIDA"]],
        NOVO_PARCELAMENTO_PREVISTO=SimNaoTalvez[bruto["NOVO_PARCELAMENTO_PREVISTO"]],
        PACTO=bruto["PACTO"],
        RISCO_IMPULSO=bruto["RISCO_IMPULSO"],
        LINHA_CONTINUA_SENDO_UTILIZADA=bruto["LINHA_CONTINUA_SENDO_UTILIZADA"],
        NECESSIDADE_VITORIA=_int_talvez(bruto["NECESSIDADE_VITORIA"]),
        HISTORICO_ABANDONO=SimNaoTalvez[bruto["HISTORICO_ABANDONO"]],
        JANELA_NOVA_DIVIDA=_janela_nova_divida(bruto["JANELA_NOVA_DIVIDA"]),
    )


def _carregar_item_investimento(bruto: dict[str, Any]) -> ItemInvestimento:
    """RF-38, RF-53, RF-59 · §13.2/§13.3/§14.3.1 — UM investimento por
    entrada da lista, nunca um total agregado (`AC-64`).
    `CLASSIFICACAO_MOBILIZACAO` NÃO chega mais pronta (`RF-59`, `T-125`): os
    campos BRUTOS abaixo é que vêm da fixture, e `classificar_investimento`
    deriva a classificação sob demanda (`EC-32` é o novo erro de contrato —
    item sem campo bruto)."""
    return ItemInvestimento(
        ITEM_ID=bruto["ITEM_ID"],
        VALOR_LIQUIDO_REALIZAVEL=dinheiro(bruto["VALOR_LIQUIDO_REALIZAVEL"]),
        POSSUI_LIQUIDEZ=bruto["POSSUI_LIQUIDEZ"],
        LIQUIDEZ_INVESTIMENTOS=LIQUIDEZ_INVESTIMENTOS[bruto["LIQUIDEZ_INVESTIMENTOS"]],
        DISPOSICAO_USO_INVESTIMENTO=DISPOSICAO_USO_INVESTIMENTO[
            bruto["DISPOSICAO_USO_INVESTIMENTO"]
        ],
        VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=dinheiro(
            bruto["VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL"]
        ),
        TEM_CUSTO_CONHECIDO=bruto["TEM_CUSTO_CONHECIDO"],
        SEM_CUSTO_PERDA_RELEVANTE=bruto["SEM_CUSTO_PERDA_RELEVANTE"],
    )


def _carregar_item_ativo(bruto: dict[str, Any]) -> ItemAtivo:
    """RF-38, RF-54, RF-56, RF-57, RF-59 · §13.3/§14.4-§14.9/§14.12 — UM
    ativo por entrada da lista. `CLASSIFICACAO_MOBILIZACAO` e
    `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` NÃO chegam mais prontos
    (`RF-59`, `T-125`): os campos BRUTOS abaixo vêm da fixture, e
    `classificar_ativo_fisico`/`derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO*`
    derivam sob demanda. `RENDA_RECORRENTE_ATIVO` usa `_dinheiro_talvez_ou_
    none` (não `_dinheiro_talvez`): o campo é `DinheiroTalvez | None`, e
    `None` é o sentinela ESTRUTURAL de veículo (`RF-56`, `OQ-38`)."""
    return ItemAtivo(
        ITEM_ID=bruto["ITEM_ID"],
        TIPO_ATIVO_FISICO=TIPO_ATIVO_FISICO[bruto["TIPO_ATIVO_FISICO"]],
        POSSIBILIDADE_VENDA=POSSIBILIDADE_VENDA[bruto["POSSIBILIDADE_VENDA"]],
        ESSENCIALIDADE=ESSENCIALIDADE[bruto["ESSENCIALIDADE"]],
        VALOR_ESTIMADO_ATIVO=_dinheiro_talvez(bruto["VALOR_ESTIMADO_ATIVO"]),
        POSSUI_PASSIVO_VINCULADO=bruto["POSSUI_PASSIVO_VINCULADO"],
        SALDO_PASSIVO_VINCULADO=_dinheiro_talvez(bruto["SALDO_PASSIVO_VINCULADO"]),
        POSSUI_CUSTO_DESMOBILIZACAO=bruto["POSSUI_CUSTO_DESMOBILIZACAO"],
        CUSTOS_ESTIMADOS_DESMOBILIZACAO=_dinheiro_talvez(
            bruto["CUSTOS_ESTIMADOS_DESMOBILIZACAO"]
        ),
        RENDA_RECORRENTE_ATIVO=_dinheiro_talvez_ou_none(bruto["RENDA_RECORRENTE_ATIVO"]),
        CUSTO_RECORRENTE_ATIVO=_dinheiro_talvez(bruto["CUSTO_RECORRENTE_ATIVO"]),
    )


def _carregar_recurso_extraordinario(bruto: dict[str, Any]) -> RecursoExtraordinario:
    """RF-39 · §13.2/§13.3 — UM recebimento previsto por entrada da lista."""
    return RecursoExtraordinario(
        ITEM_ID=bruto["ITEM_ID"],
        VALOR_RECURSO_EXTRAORDINARIO=dinheiro(bruto["VALOR_RECURSO_EXTRAORDINARIO"]),
        JANELA_RECURSO_EXTRAORDINARIO=JANELA_RECURSO_EXTRAORDINARIO[
            bruto["JANELA_RECURSO_EXTRAORDINARIO"]
        ],
        CERTEZA_RECURSO_EXTRAORDINARIO=CERTEZA_RECURSO_EXTRAORDINARIO[
            bruto["CERTEZA_RECURSO_EXTRAORDINARIO"]
        ],
    )


def carregar_estado_financeiro(caminho: Path) -> EstadoFinanceiro:
    """Lê um JSON de fixture e devolve `EstadoFinanceiro` completo.

    Chaves de nível superior que começam com `_` são metadado de
    proveniência (ver docstring do módulo) e são ignoradas na carga.
    """
    with caminho.open(encoding="utf-8") as arquivo:
        bruto: dict[str, Any] = json.load(arquivo)

    return EstadoFinanceiro(
        DATA_REFERENCIA=date.fromisoformat(bruto["DATA_REFERENCIA"]),
        RENDA_TOTAL_RECORRENTE=dinheiro(bruto["RENDA_TOTAL_RECORRENTE"]),
        TIPO_RENDA=TIPO_RENDA[bruto["TIPO_RENDA"]],
        DESPESAS_OPERACIONAIS_ATUAIS=dinheiro(bruto["DESPESAS_OPERACIONAIS_ATUAIS"]),
        DESPESAS_NAO_MENSAIS_NORMALIZADAS=dinheiro(bruto["DESPESAS_NAO_MENSAIS_NORMALIZADAS"]),
        CAPACIDADE_ATAQUE_DECLARADA=_dinheiro_talvez(bruto["CAPACIDADE_ATAQUE_DECLARADA"]),
        ECONOMIA_POTENCIAL_IMEDIATA=dinheiro(bruto["ECONOMIA_POTENCIAL_IMEDIATA"]),
        INVENTARIO_COMPLETO=bruto["INVENTARIO_COMPLETO"],
        dividas=tuple(_carregar_divida(d) for d in bruto["dividas"]),
        perfil_comportamental=_carregar_perfil_comportamental(bruto["perfil_comportamental"]),
        sinais_comportamentais=_carregar_sinais_comportamentais(bruto["sinais_comportamentais"]),
        CONFIABILIDADE_DADOS=CONFIABILIDADE_DADOS[bruto["CONFIABILIDADE_DADOS"]],
        AUTOPERCEPCAO_CONTROLE=_int_talvez(bruto["AUTOPERCEPCAO_CONTROLE"]),
        # --- Rodada 3 (T-96/T-97) — os nove campos novos, NEUTROS nas três
        # fixtures: a canônica não declara reserva, caixa nem patrimônio para
        # `GAB-A`/`GAB-B`/`GAB-C`, e `AC-87` exige que nada mude nelas. Ver a
        # nota `_reserva_caixa_patrimonio_preenchimento_fixture` de cada JSON.
        RESERVA_EXISTE=RESERVA_EXISTE[bruto["RESERVA_EXISTE"]],
        RESERVA_TOTAL=_dinheiro_talvez(bruto["RESERVA_TOTAL"]),
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA[bruto["DISPOSICAO_USO_RESERVA"]],
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=_dinheiro_talvez(
            bruto["VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO"]
        ),
        DINHEIRO_DISPONIVEL=dinheiro(bruto["DINHEIRO_DISPONIVEL"]),
        investimentos=tuple(_carregar_item_investimento(i) for i in bruto["investimentos"]),
        ativos=tuple(_carregar_item_ativo(a) for a in bruto["ativos"]),
        recursos_extraordinarios=tuple(
            _carregar_recurso_extraordinario(r) for r in bruto["recursos_extraordinarios"]
        ),
    )


def carregar_gab_a() -> EstadoFinanceiro:
    """`GAB-A` — Déficit / falso superávit observado (`piq-app-spec.md` §10.2)."""
    return carregar_estado_financeiro(DIRETORIO_FIXTURES / "gab_a.json")


def carregar_gab_b() -> EstadoFinanceiro:
    """`GAB-B` — Equilíbrio frágil / potencial não é capacidade (`piq-app-spec.md` §10.2)."""
    return carregar_estado_financeiro(DIRETORIO_FIXTURES / "gab_b.json")


def carregar_gab_c() -> EstadoFinanceiro:
    """`GAB-C` — Superávit / método Híbrido (`piq-app-spec.md` §10.1, §10.2)."""
    return carregar_estado_financeiro(DIRETORIO_FIXTURES / "gab_c.json")
