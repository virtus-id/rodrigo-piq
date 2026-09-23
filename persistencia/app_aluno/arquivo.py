"""Adaptador de arquivo das tabelas desta feature — `RF-10`, `RF-01`.

Implementa os quatro `Protocol`s de `persistencia/app_aluno/` (`RepositorioRespostas`
em `respostas.py`, T-22; `RepositorioCasos` em `casos.py` e `RepositorioItens`
em `itens.py`, T-23; `RepositorioEventosCaso` em `eventos.py`, T-87) sobre
JSON/JSONL local — o MESMO precedente de `persistencia/arquivo/` no slug
`motor-calculo` (`repositorio_snapshots.py`, `fonte_parametros.py`),
reaproveitado aqui, não reinventado:

- Uma linha JSON por evento, sempre em modo *append* (`open(..., "a")`) —
  nunca reescreve nem trunca o arquivo. A leitura reduz o histórico ao estado
  corrente por chave (a última linha escrita para aquela chave vence),
  reproduzindo em memória a mesma semântica de `ON CONFLICT ... DO UPDATE`
  (respostas) e `UPDATE` (casos, itens) que o adaptador Postgres expressa em
  SQL — sem reescrever o arquivo em nenhuma operação de gravação.
- `Decimal` sempre vira `string` na serialização e volta via `Decimal(str)`
  na leitura — nunca `float` em nenhum ponto do caminho de ida ou volta
  (mesma regra de `persistencia/arquivo/repositorio_snapshots.py::_decimal`
  e de `persistencia/app_aluno/respostas.py::_serializar_valor`/
  `_desserializar_valor`, reaproveitada aqui, não duplicada com lógica
  divergente).
- `date`/`datetime` viram `isoformat()` na escrita e voltam por
  `date.fromisoformat`/`datetime.fromisoformat` na leitura — mesmo padrão do
  motor.
- `Enum` vira `.value` na escrita e volta pelo construtor do enum
  (`ESTADO_CASO(valor)`, `EscopoRepeticao(valor)`) na leitura.

Este módulo existe para que a suíte principal desta feature rode sem
`DATABASE_URL` (`pytest -m "not requer_banco"`) — os testes que hoje exigem
Postgres real por falta deste adaptador podem passar a rodar contra arquivo
em `tests/app_aluno/integracao/test_persistencia_app_aluno.py` (T-25).

Direção de dependência: este módulo importa de `collection/` (os tipos
`Resposta`/`ValorResposta`/`NaoSei`) e de `persistencia/app_aluno/` (os três
`Protocol`s e os dataclasses `Caso`/`ItemRepetido`) e de stdlib — nunca de
`engine/` nem de `persistencia/arquivo/` (a pasta do motor, intocada por esta
tarefa, `AC-44`).

**Guarda "sem consentimento, nenhuma resposta é gravada" (`RF-30`, `AC-39`,
T-36) NÃO está neste adaptador.** A guarda foi implementada em
`RepositorioRespostasSupabase.gravar` (`persistencia/app_aluno/respostas.py`)
— o único caminho de gravação de resposta que qualquer rota HTTP real usa
hoje. Este adaptador de arquivo existe exclusivamente para a suíte de testes
rodar sem `DATABASE_URL` (ver o parágrafo acima) — nenhuma rota de produção
grava resposta por este adaptador.

**`T-91` (`RF-31`, `EC-14`) — `RepositorioRespostasArquivo.gravar` agora
TAMBÉM atualiza `ultima_interacao_em`.** Extensão ADITIVA e mínima do
construtor: um parâmetro opcional `repositorio_casos: RepositorioCasosArquivo
| None = None` (default `None`, para não quebrar nenhum teste existente que
já instancia este adaptador sem ele). Quando fornecido, `gravar` chama
`repositorio_casos.registrar_interacao(resposta.CASO_ID, resposta.
respondida_em)` logo após anexar a linha da resposta — o mesmo comportamento
que `RepositorioRespostasSupabase.gravar` (Postgres) agora tem embutido no
próprio `UPDATE` da transação. Quando `None` (uso pré-existente, ex.:
`tests/app_aluno/test_arquivo.py`), o comportamento é EXATAMENTE o de antes
desta tarefa — nenhuma chamada extra, nenhuma exceção nova.

REGRAS: `RF-10`, `RF-01`, `RF-31`, `EC-14`
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

from collection.registro import EscopoRepeticao
from collection.repeticao import PREFIXO_POR_ESCOPO, erro_escopo_sem_item
from collection.respostas import NAO_SEI, NaoSei, Resposta, ValorResposta
from persistencia.app_aluno.casos import (
    ESTADO_CASO,
    Caso,
    ErroCasoInexistente,
    RepositorioCasos,
)
from persistencia.app_aluno.eventos import EventoCaso, RepositorioEventosCaso
from persistencia.app_aluno.itens import ItemRepetido, RepositorioItens
from persistencia.app_aluno.respostas import RepositorioRespostas

REGRAS: Final[tuple[str, ...]] = ("RF-10", "RF-01", "RF-31", "EC-14")

_NOME_ARQUIVO_RESPOSTAS: Final[str] = "respostas.jsonl"
_NOME_ARQUIVO_CASOS: Final[str] = "casos.jsonl"
_NOME_ARQUIVO_ITENS: Final[str] = "itens_repetidos.jsonl"
_NOME_ARQUIVO_EVENTOS: Final[str] = "eventos_caso.jsonl"

# Mesmos prefixos de serialização textual de `persistencia/app_aluno/
# respostas.py` — reaproveitados por igualdade de valor (não por import, para
# não acoplar os dois adaptadores um ao outro): cada prefixo distingue, na
# leitura, uma `str` literal de uma `date`/`frozenset[str]`/`int` serializados
# como texto.
_PREFIXO_DATA: Final[str] = "DATA:"
_PREFIXO_FROZENSET: Final[str] = "CONJUNTO:"
_PREFIXO_INT: Final[str] = "INTEIRO:"
_SEPARADOR_FROZENSET: Final[str] = "\x1f"


class ErroGravacaoResposta(Exception):
    """Mesma disciplina de `persistencia.app_aluno.respostas.
    ErroGravacaoResposta` (`EC-05`): levantada quando a gravação falha antes
    de a linha ser efetivamente escrita — nunca engolida."""


class ErroGravacaoCaso(Exception):
    """Mesma disciplina de `persistencia.app_aluno.casos.ErroGravacaoCaso`."""


class ErroGravacaoItem(Exception):
    """Mesma disciplina de `persistencia.app_aluno.itens.ErroGravacaoItem`."""


class ErroGravacaoEventoCaso(Exception):
    """Mesma disciplina de `persistencia.app_aluno.eventos.
    ErroGravacaoEventoCaso` (T-87)."""


def _serializar_valor(valor: ValorResposta) -> dict[str, Any]:
    """Espelha `persistencia.app_aluno.respostas._serializar_valor`, mas em
    formato JSON (um único campo `valor` com prefixo), já que o arquivo não
    tem colunas separadas para texto/numérico/não-sei."""
    if isinstance(valor, NaoSei):
        return {"tipo": "NAO_SEI"}
    if isinstance(valor, Decimal):
        # RF-13: Decimal sempre como string — nunca via float.
        return {"tipo": "DECIMAL", "valor": str(valor)}
    if isinstance(valor, bool):
        # bool é subtipo de int — checado ANTES de int (mesma ordem do
        # adaptador Postgres).
        return {"tipo": "TEXTO", "valor": f"{_PREFIXO_INT}{int(valor)}"}
    if isinstance(valor, int):
        return {"tipo": "TEXTO", "valor": f"{_PREFIXO_INT}{valor}"}
    if isinstance(valor, date):
        return {"tipo": "TEXTO", "valor": f"{_PREFIXO_DATA}{valor.isoformat()}"}
    if isinstance(valor, frozenset):
        return {
            "tipo": "TEXTO",
            "valor": f"{_PREFIXO_FROZENSET}{_SEPARADOR_FROZENSET.join(sorted(valor))}",
        }
    return {"tipo": "TEXTO", "valor": valor}


def desserializar_valor(bruto: dict[str, Any]) -> ValorResposta:
    """Inverso de `_serializar_valor`.

    Nome SEM underscore inicial, começando literalmente com
    `desserializar_` — critério objetivo de
    `tests/app_aluno/estatica/test_fronteira_decimal_unica.py` (`RF-13`,
    T-27) para reconhecer esta função como a exceção declarada de
    desserialização do adaptador de persistência (o `Decimal(...)` abaixo
    reconstrói um valor que já veio validado da linha gravada — nunca
    entrada de usuário nova, que é o que a fronteira única de
    `app/montagem/conversao.py` existe para proteger)."""
    tipo = bruto["tipo"]
    if tipo == "NAO_SEI":
        return NAO_SEI
    if tipo == "DECIMAL":
        # str -> Decimal exato, nunca via float (RF-13).
        return Decimal(bruto["valor"])
    texto: str = bruto["valor"]
    if texto.startswith(_PREFIXO_DATA):
        return date.fromisoformat(texto[len(_PREFIXO_DATA) :])
    if texto.startswith(_PREFIXO_FROZENSET):
        resto = texto[len(_PREFIXO_FROZENSET) :]
        return frozenset(resto.split(_SEPARADOR_FROZENSET)) if resto else frozenset()
    if texto.startswith(_PREFIXO_INT):
        return int(texto[len(_PREFIXO_INT) :])
    return texto


def _ler_linhas(caminho: Path) -> list[dict[str, Any]]:
    """Mesmo padrão de `persistencia/arquivo/repositorio_snapshots.py::
    _ler_linhas`: arquivo ausente é histórico vazio, nunca erro."""
    if not caminho.is_file():
        return []
    linhas: list[dict[str, Any]] = []
    with caminho.open(encoding="utf-8") as arquivo:
        for linha_bruta in arquivo:
            linha_bruta = linha_bruta.strip()
            if not linha_bruta:
                continue
            linhas.append(json.loads(linha_bruta))
    return linhas


def _anexar_linha(caminho: Path, registro: dict[str, Any]) -> None:
    linha = json.dumps(registro, ensure_ascii=True, sort_keys=True)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("a", encoding="utf-8") as arquivo:
        arquivo.write(linha)
        arquivo.write("\n")


def _como_utc(instante: datetime) -> datetime:
    return instante if instante.tzinfo is not None else instante.replace(tzinfo=UTC)


# ---------------------------------------------------------------------------
# RepositorioRespostas (persistencia/app_aluno/respostas.py, T-22)
# ---------------------------------------------------------------------------


class RepositorioRespostasArquivo(RepositorioRespostas):
    """Implementa `persistencia.app_aluno.respostas.RepositorioRespostas`
    sobre `respostas.jsonl` — uma linha por gravação, `ON CONFLICT DO UPDATE`
    reproduzido na LEITURA: `listar_do_caso` devolve só a última linha
    escrita por `(ID_PERGUNTA, item_id)` (`EC-10`, sem merge)."""

    def __init__(
        self,
        caminho_arquivo: Path | None = None,
        repositorio_casos: RepositorioCasosArquivo | None = None,
    ) -> None:
        self._caminho_arquivo = caminho_arquivo or Path(_NOME_ARQUIVO_RESPOSTAS)
        # T-91 (RF-31/EC-14): opcional, default None — ver a nota extensa do
        # módulo sobre por que esta extensão é aditiva e não quebra nenhum
        # uso pré-existente que instancia este adaptador sem ele.
        self._repositorio_casos = repositorio_casos

    def gravar(self, resposta: Resposta) -> None:
        """`EC-10`: a linha nova é sempre ANEXADA (nunca reescreve as
        anteriores) — a leitura em `listar_do_caso` é quem garante que
        apenas a última confirmada por chave é observável, sem merge
        parcial. `EC-05`: se a escrita falhar (erro de I/O), a exceção
        original propaga envolvida em `ErroGravacaoResposta`, nunca
        reportando sucesso.

        `T-91` (`RF-31`, `EC-14`): quando o construtor recebeu um
        `repositorio_casos`, `ultima_interacao_em` do caso é atualizada para
        `resposta.respondida_em` logo após a linha ser anexada — mesmo
        comportamento (por fora da transação única do Postgres, que este
        adaptador não tem) de `RepositorioRespostasSupabase.gravar`."""
        registro = {
            "CASO_ID": resposta.CASO_ID,
            "ID_PERGUNTA": resposta.ID_PERGUNTA,
            "item_id": resposta.item_id or "",
            "valor": _serializar_valor(resposta.valor),
            "QUESTIONARIO_VERSION": resposta.QUESTIONARIO_VERSION,
            "respondida_em": resposta.respondida_em.isoformat(),
        }
        try:
            _anexar_linha(self._caminho_arquivo, registro)
        except OSError as erro:
            raise ErroGravacaoResposta(
                f"falha ao gravar resposta CASO_ID={resposta.CASO_ID!r} "
                f"ID_PERGUNTA={resposta.ID_PERGUNTA!r} item_id={resposta.item_id!r}: {erro}"
            ) from erro

        if self._repositorio_casos is not None:
            self._repositorio_casos.registrar_interacao(
                resposta.CASO_ID, resposta.respondida_em
            )

    def listar_do_caso(self, caso_id: str) -> tuple[Resposta, ...]:
        """Reduz o histórico de linhas à ÚLTIMA por `(ID_PERGUNTA, item_id)`
        — mesma garantia de unicidade por chave que a PK do Postgres dá
        nativamente (`EC-10`)."""
        ultima_por_chave: dict[tuple[str, str], dict[str, Any]] = {}
        for linha in _ler_linhas(self._caminho_arquivo):
            if linha["CASO_ID"] != caso_id:
                continue
            chave = (linha["ID_PERGUNTA"], linha["item_id"])
            ultima_por_chave[chave] = linha

        return tuple(_linha_para_resposta(linha) for linha in ultima_por_chave.values())

    def listar_de_varios_casos(
        self, caso_ids: tuple[str, ...]
    ) -> dict[str, tuple[Resposta, ...]]:
        """`T-187` — espelha `RepositorioRespostasSupabase.
        listar_de_varios_casos`, aditivo. Loop sobre `listar_do_caso`."""
        resultado: dict[str, tuple[Resposta, ...]] = {}
        for caso_id in caso_ids:
            respostas = self.listar_do_caso(caso_id)
            if respostas:
                resultado[caso_id] = respostas
        return resultado


def _linha_para_resposta(linha: dict[str, Any]) -> Resposta:
    item_id: str = linha["item_id"]
    return Resposta(
        CASO_ID=linha["CASO_ID"],
        ID_PERGUNTA=linha["ID_PERGUNTA"],
        item_id=item_id or None,
        valor=desserializar_valor(linha["valor"]),
        QUESTIONARIO_VERSION=linha["QUESTIONARIO_VERSION"],
        respondida_em=_como_utc(datetime.fromisoformat(linha["respondida_em"])),
    )


# ---------------------------------------------------------------------------
# RepositorioCasos (persistencia/app_aluno/casos.py, T-23)
# ---------------------------------------------------------------------------


class RepositorioCasosArquivo(RepositorioCasos):
    """Implementa `persistencia.app_aluno.casos.RepositorioCasos` sobre
    `casos.jsonl` — uma linha por gravação (criação ou atualização de
    estado/interação/snapshot), lida como o ÚLTIMO registro por `CASO_ID`.

    `FOR UPDATE` (Postgres) não existe em arquivo: um `threading.Lock` por
    instância serializa `transicionar_estado` do mesmo processo — suficiente
    para o único cenário coberto por esta tarefa (a suíte principal sem
    banco, single-process); não reproduz isolamento entre processos
    diferentes, que é exclusividade do Postgres real (T-23, já validado
    contra banco real com duas conexões de fato concorrentes)."""

    def __init__(self, caminho_arquivo: Path | None = None) -> None:
        self._caminho_arquivo = caminho_arquivo or Path(_NOME_ARQUIVO_CASOS)
        self._lock = threading.Lock()

    def criar(self, caso: Caso) -> None:
        registro = _caso_para_registro(caso)
        try:
            _anexar_linha(self._caminho_arquivo, registro)
        except OSError as erro:
            raise ErroGravacaoCaso(
                f"falha ao criar caso CASO_ID={caso.CASO_ID!r}: {erro}"
            ) from erro

    def buscar(self, caso_id: str) -> Caso | None:
        registro = self._ultimo_registro(caso_id)
        return _registro_para_caso(registro) if registro is not None else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        """Espelha `RepositorioCasosSupabase.pertence_a_conta` (T-31):
        `False` tanto para `caso_id` inexistente quanto para `caso_id` de
        outra conta, pela mesma comparação — nenhum ramo que distinga as
        duas situações."""
        registro = self._ultimo_registro(caso_id)
        return registro is not None and registro["conta_id"] == conta_id

    def transicionar_estado(
        self, caso_id: str, novo_estado: ESTADO_CASO, agora: datetime | None = None
    ) -> Caso:
        """Serializado por `threading.Lock` — ver a nota da classe sobre o
        limite dessa garantia em relação ao `SELECT ... FOR UPDATE` real."""
        instante = agora if agora is not None else datetime.now(UTC)
        with self._lock:
            atual = self._ultimo_registro(caso_id)
            if atual is None:
                raise ErroCasoInexistente(
                    f"transição de estado recusada: CASO_ID={caso_id!r} não existe"
                )
            novo_registro = dict(atual)
            novo_registro["estado"] = novo_estado.value
            novo_registro["ultima_interacao_em"] = instante.isoformat()
            try:
                _anexar_linha(self._caminho_arquivo, novo_registro)
            except OSError as erro:
                raise ErroGravacaoCaso(
                    f"falha ao transicionar CASO_ID={caso_id!r} para {novo_estado!r}: {erro}"
                ) from erro
            return _registro_para_caso(novo_registro)

    def transicionar_estado_se(
        self,
        caso_id: str,
        estado_esperado: ESTADO_CASO,
        novo_estado: ESTADO_CASO,
        agora: datetime | None = None,
    ) -> Caso | None:
        """`T-56` — mesmo `threading.Lock` de `transicionar_estado`, mas a
        gravação só ocorre se `atual["estado"] == estado_esperado.value`
        (checagem DENTRO da seção crítica do lock, mesma disciplina de
        `RepositorioCasosSupabase.transicionar_estado_se`). Devolve `None`
        sem gravar quando a condição não vale."""
        instante = agora if agora is not None else datetime.now(UTC)
        with self._lock:
            atual = self._ultimo_registro(caso_id)
            if atual is None:
                raise ErroCasoInexistente(
                    f"transição condicional recusada: CASO_ID={caso_id!r} não existe"
                )
            if atual["estado"] != estado_esperado.value:
                return None
            novo_registro = dict(atual)
            novo_registro["estado"] = novo_estado.value
            novo_registro["ultima_interacao_em"] = instante.isoformat()
            try:
                _anexar_linha(self._caminho_arquivo, novo_registro)
            except OSError as erro:
                raise ErroGravacaoCaso(
                    f"falha ao transicionar condicionalmente CASO_ID={caso_id!r} "
                    f"para {novo_estado!r}: {erro}"
                ) from erro
            return _registro_para_caso(novo_registro)

    def registrar_interacao(self, caso_id: str, agora: datetime | None = None) -> None:
        instante = agora if agora is not None else datetime.now(UTC)
        with self._lock:
            atual = self._ultimo_registro(caso_id)
            if atual is None:
                raise ErroCasoInexistente(
                    f"registro de interação recusado: CASO_ID={caso_id!r} não existe"
                )
            novo_registro = dict(atual)
            novo_registro["ultima_interacao_em"] = instante.isoformat()
            try:
                _anexar_linha(self._caminho_arquivo, novo_registro)
            except OSError as erro:
                raise ErroGravacaoCaso(
                    f"falha ao registrar interação de CASO_ID={caso_id!r}: {erro}"
                ) from erro

    def registrar_snapshot_raiz(self, caso_id: str, snapshot_raiz_id: str) -> None:
        with self._lock:
            atual = self._ultimo_registro(caso_id)
            if atual is None:
                raise ErroCasoInexistente(
                    f"registro de snapshot raiz recusado: CASO_ID={caso_id!r} não existe"
                )
            novo_registro = dict(atual)
            novo_registro["snapshot_raiz_id"] = snapshot_raiz_id
            try:
                _anexar_linha(self._caminho_arquivo, novo_registro)
            except OSError as erro:
                raise ErroGravacaoCaso(
                    f"falha ao registrar snapshot_raiz_id de CASO_ID={caso_id!r}: {erro}"
                ) from erro

    def registrar_snapshot_liberado(self, caso_id: str, snapshot_liberado_id: str) -> None:
        with self._lock:
            atual = self._ultimo_registro(caso_id)
            if atual is None:
                raise ErroCasoInexistente(
                    f"registro de snapshot liberado recusado: CASO_ID={caso_id!r} não existe"
                )
            novo_registro = dict(atual)
            novo_registro["snapshot_liberado_id"] = snapshot_liberado_id
            try:
                _anexar_linha(self._caminho_arquivo, novo_registro)
            except OSError as erro:
                raise ErroGravacaoCaso(
                    f"falha ao registrar snapshot_liberado_id de CASO_ID={caso_id!r}: {erro}"
                ) from erro

    def listar_por_estado(self, estado: ESTADO_CASO) -> tuple[str, ...]:
        """Espelha `RepositorioCasosSupabase.listar_por_estado` (T-69):
        reduz o histórico ao último registro por `CASO_ID` (mesma leitura de
        `buscar`/`pertence_a_conta`) e filtra por `estado`."""
        ultimo_por_caso: dict[str, dict[str, Any]] = {}
        for linha in _ler_linhas(self._caminho_arquivo):
            ultimo_por_caso[linha["CASO_ID"]] = linha

        return tuple(
            caso_id
            for caso_id, registro in ultimo_por_caso.items()
            if registro["estado"] == estado.value
        )

    def listar_todos(self) -> tuple[str, ...]:
        """Espelha `RepositorioCasosSupabase.listar_todos` (`RF-35`, T-102):
        reduz o histórico ao último registro por `CASO_ID`, sem filtro de
        `estado`."""
        ultimo_por_caso: dict[str, dict[str, Any]] = {}
        for linha in _ler_linhas(self._caminho_arquivo):
            ultimo_por_caso[linha["CASO_ID"]] = linha

        return tuple(ultimo_por_caso.keys())

    def buscar_varios(self, caso_ids: tuple[str, ...]) -> dict[str, Caso]:
        """`T-187` — espelha `RepositorioCasosSupabase.buscar_varios`,
        aditivo. Loop sobre `buscar`: arquivo não tem a pressão de rede
        que motivou a versão em lote do Postgres, só a fidelidade ao
        contrato importa aqui."""
        resultado: dict[str, Caso] = {}
        for caso_id in caso_ids:
            caso = self.buscar(caso_id)
            if caso is not None:
                resultado[caso_id] = caso
        return resultado

    def _ultimo_registro(self, caso_id: str) -> dict[str, Any] | None:
        ultimo: dict[str, Any] | None = None
        for linha in _ler_linhas(self._caminho_arquivo):
            if linha["CASO_ID"] == caso_id:
                ultimo = linha
        return ultimo


def _caso_para_registro(caso: Caso) -> dict[str, Any]:
    return {
        "CASO_ID": caso.CASO_ID,
        "conta_id": caso.conta_id,
        "estado": caso.estado.value,
        "DATA_REFERENCIA": caso.DATA_REFERENCIA.isoformat(),
        "QUESTIONARIO_VERSION": caso.QUESTIONARIO_VERSION,
        "snapshot_raiz_id": caso.snapshot_raiz_id,
        "snapshot_liberado_id": caso.snapshot_liberado_id,
        "ultima_interacao_em": caso.ultima_interacao_em.isoformat(),
        "criado_em": caso.criado_em.isoformat(),
    }


def _registro_para_caso(registro: dict[str, Any]) -> Caso:
    return Caso(
        CASO_ID=registro["CASO_ID"],
        conta_id=registro["conta_id"],
        estado=ESTADO_CASO(registro["estado"]),
        DATA_REFERENCIA=date.fromisoformat(registro["DATA_REFERENCIA"]),
        QUESTIONARIO_VERSION=registro["QUESTIONARIO_VERSION"],
        snapshot_raiz_id=registro["snapshot_raiz_id"],
        snapshot_liberado_id=registro["snapshot_liberado_id"],
        ultima_interacao_em=_como_utc(datetime.fromisoformat(registro["ultima_interacao_em"])),
        criado_em=_como_utc(datetime.fromisoformat(registro["criado_em"])),
    )


# ---------------------------------------------------------------------------
# RepositorioItens (persistencia/app_aluno/itens.py, T-23)
# ---------------------------------------------------------------------------


class RepositorioItensArquivo(RepositorioItens):
    """Implementa `persistencia.app_aluno.itens.RepositorioItens` sobre
    `itens_repetidos.jsonl`. Mesmo mecanismo de não-reaproveitamento do
    adaptador Postgres (`persistencia/app_aluno/itens.py`, comentário do
    módulo): o próximo número é `total de linhas já geradas para o par
    (CASO_ID, escopo) + 1`, contando TAMBÉM os itens já removidos — a
    remoção nunca apaga uma linha, só marca `removido_em` numa linha nova
    anexada, então a contagem nunca "esquece" um número já usado.

    `threading.Lock` por instância serializa `proximo_identificador` do
    mesmo processo — mesmo limite documentado em `RepositorioCasosArquivo`
    quanto a não reproduzir isolamento entre processos."""

    def __init__(self, caminho_arquivo: Path | None = None) -> None:
        self._caminho_arquivo = caminho_arquivo or Path(_NOME_ARQUIVO_ITENS)
        self._lock = threading.Lock()

    def proximo_identificador(self, CASO_ID: str, escopo: EscopoRepeticao) -> str:
        prefixo = PREFIXO_POR_ESCOPO.get(escopo)
        if prefixo is None:
            raise erro_escopo_sem_item(escopo)

        with self._lock:
            linhas_do_par = [
                linha
                for linha in _ler_linhas(self._caminho_arquivo)
                if linha["CASO_ID"] == CASO_ID and linha["escopo"] == escopo.value
            ]
            # Cada `item_id` gerado tem exatamente UMA linha de criação (a
            # remoção é uma linha adicional que reaproveita o mesmo
            # `item_id` para marcar `removido_em` — nunca uma linha nova de
            # criação). Contar `item_id`s DISTINTOS de criação é o
            # equivalente exato do `COUNT(*)` do adaptador Postgres sobre
            # a tabela (onde cada `item_id` também é PK única).
            identificadores_ja_gerados = {linha["item_id"] for linha in linhas_do_par}
            proximo_numero = len(identificadores_ja_gerados) + 1
            identificador_legivel = f"{prefixo}{proximo_numero:03d}"

            agora = datetime.now(UTC)
            registro = {
                "item_id": identificador_legivel,
                "CASO_ID": CASO_ID,
                "escopo": escopo.value,
                "removido_em": None,
                "criado_em": agora.isoformat(),
            }
            try:
                _anexar_linha(self._caminho_arquivo, registro)
            except OSError as erro:
                raise ErroGravacaoItem(
                    f"falha ao gerar próximo item_id para CASO_ID={CASO_ID!r} "
                    f"escopo={escopo!r}: {erro}"
                ) from erro

        return identificador_legivel

    def remover(self, caso_id: str, item_id: str, agora: datetime | None = None) -> None:
        """Anexa uma linha nova marcando `removido_em` — NUNCA apaga a linha
        de criação (mesma disciplina do adaptador Postgres: apagar
        destruiria a memória de que o número já foi usado)."""
        instante = agora if agora is not None else datetime.now(UTC)
        with self._lock:
            linhas_do_item = [
                linha
                for linha in _ler_linhas(self._caminho_arquivo)
                if linha["CASO_ID"] == caso_id and linha["item_id"] == item_id
            ]
            if not linhas_do_item:
                # Mesmo comportamento do adaptador Postgres: `rowcount == 0`
                # não levanta lá (é um UPDATE que afeta zero linhas,
                # silencioso) — aqui, sem linha de criação, não há o que
                # marcar; não é erro, só não produz efeito observável.
                return
            escopo = linhas_do_item[-1]["escopo"]
            registro = {
                "item_id": item_id,
                "CASO_ID": caso_id,
                "escopo": escopo,
                "removido_em": instante.isoformat(),
                "criado_em": linhas_do_item[0]["criado_em"],
            }
            try:
                _anexar_linha(self._caminho_arquivo, registro)
            except OSError as erro:
                raise ErroGravacaoItem(f"falha ao remover item_id={item_id!r}: {erro}") from erro

    def listar_do_caso(
        self, caso_id: str, *, incluir_removidos: bool = True
    ) -> tuple[ItemRepetido, ...]:
        """Reduz o histórico ao ÚLTIMO registro por `item_id` (criação,
        depois eventual remoção) — mesma leitura "estado corrente" que
        `RepositorioRespostasArquivo.listar_do_caso` aplica."""
        ultimo_por_item: dict[str, dict[str, Any]] = {}
        for linha in _ler_linhas(self._caminho_arquivo):
            if linha["CASO_ID"] != caso_id:
                continue
            ultimo_por_item[linha["item_id"]] = linha

        itens = [_linha_para_item(linha) for linha in ultimo_por_item.values()]
        if not incluir_removidos:
            itens = [item for item in itens if item.removido_em is None]
        itens.sort(key=lambda item: item.criado_em)
        return tuple(itens)

    def listar_de_varios_casos(
        self, caso_ids: tuple[str, ...], *, incluir_removidos: bool = True
    ) -> dict[str, tuple[ItemRepetido, ...]]:
        """`T-187` — espelha `RepositorioItensSupabase.
        listar_de_varios_casos`, aditivo. Loop sobre `listar_do_caso`."""
        resultado: dict[str, tuple[ItemRepetido, ...]] = {}
        for caso_id in caso_ids:
            itens = self.listar_do_caso(caso_id, incluir_removidos=incluir_removidos)
            if itens:
                resultado[caso_id] = itens
        return resultado


def _linha_para_item(linha: dict[str, Any]) -> ItemRepetido:
    removido_em = linha["removido_em"]
    return ItemRepetido(
        item_id=linha["item_id"],
        CASO_ID=linha["CASO_ID"],
        escopo=EscopoRepeticao(linha["escopo"]),
        removido_em=_como_utc(datetime.fromisoformat(removido_em))
        if removido_em is not None
        else None,
        criado_em=_como_utc(datetime.fromisoformat(linha["criado_em"])),
    )


# ---------------------------------------------------------------------------
# RepositorioEventosCaso (persistencia/app_aluno/eventos.py, T-87)
# ---------------------------------------------------------------------------


class RepositorioEventosCasoArquivo(RepositorioEventosCaso):
    """Implementa `persistencia.app_aluno.eventos.RepositorioEventosCaso`
    sobre `eventos_caso.jsonl` — uma linha por evento registrado, sempre em
    modo *append* (mesma disciplina dos demais repositórios deste módulo).
    Trilha, não estado: nenhum método aqui toca `casos.jsonl`."""

    def __init__(self, caminho_arquivo: Path | None = None) -> None:
        self._caminho_arquivo = caminho_arquivo or Path(_NOME_ARQUIVO_EVENTOS)

    def registrar(self, evento: EventoCaso) -> None:
        registro = {
            "evento_id": evento.evento_id,
            "CASO_ID": evento.CASO_ID,
            "tipo_evento": evento.tipo_evento,
            "estado_de": evento.estado_de,
            "estado_para": evento.estado_para,
            "detalhe": evento.detalhe,
            "ocorrido_em": evento.ocorrido_em.isoformat(),
        }
        try:
            _anexar_linha(self._caminho_arquivo, registro)
        except OSError as erro:
            raise ErroGravacaoEventoCaso(
                f"falha ao registrar evento_id={evento.evento_id!r} "
                f"CASO_ID={evento.CASO_ID!r}: {erro}"
            ) from erro

    def listar_do_caso(self, caso_id: str) -> tuple[EventoCaso, ...]:
        return tuple(
            _linha_para_evento(linha)
            for linha in _ler_linhas(self._caminho_arquivo)
            if linha["CASO_ID"] == caso_id
        )


def _linha_para_evento(linha: dict[str, Any]) -> EventoCaso:
    return EventoCaso(
        evento_id=linha["evento_id"],
        CASO_ID=linha["CASO_ID"],
        tipo_evento=linha["tipo_evento"],
        estado_de=linha["estado_de"],
        estado_para=linha["estado_para"],
        detalhe=linha["detalhe"],
        ocorrido_em=_como_utc(datetime.fromisoformat(linha["ocorrido_em"])),
    )
