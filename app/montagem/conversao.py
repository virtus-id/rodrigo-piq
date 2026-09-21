"""Fronteira `Decimal` única — `RF-13` (`AC-09`, `AC-10`, `EC-01`).

Este é o **único** módulo desta feature autorizado a construir
`Dinheiro`/`Taxa` a partir de entrada de usuário — verificado por
`tests/app_aluno/estatica/test_fronteira_decimal_unica.py` (`T-27`), que
falha se `Decimal(...)`/`dinheiro(...)` aparecer em qualquer outro arquivo de
`app/`, `collection/`, `report/` ou `persistencia/app_aluno/` (exceto a
desserialização do adaptador de persistência, prefixo `desserializar_`).

`plans/app-aluno.plan.md` §5.1: `"1234,56" → normaliza separadores →
Decimal("1234.56") via engine.precisao.dinheiro() — str direto para Decimal,
jamais float`. `engine.precisao.dinheiro()` é o único construtor autorizado
pelo motor (`G-01`); este módulo nunca chama `Decimal(...)` diretamente —
normaliza a string e delega a `dinheiro()`.

**Regra de normalização de separador (decisão desta tarefa, determinística):**

1. Espaços nas bordas são descartados; string vazia (ou só espaços) é
   recusada (`EC-01`).
2. Presença de `,` **e** `.` na mesma string: `.` é sempre separador de
   milhar (removido) e `,` é sempre separador decimal (vira `.`) — formato
   brasileiro completo. `"1.234,56"` → `"1234.56"`.
3. Presença de `,` sem `.`: `,` é sempre separador decimal. `"1234,56"` →
   `"1234.56"` (`AC-10`).
4. Presença de `.` sem `,` — caso ambíguo, resolvido por contagem de dígitos
   após o **último** `.`:
   - Exatamente um `.` no texto e 1 ou 2 dígitos depois dele: `.` é separador
     DECIMAL (convenção não brasileira, mas inequívoca — `"1234.56"` →
     `"1234.56"`, `"12.5"` → `"12.5"`).
   - Qualquer outro caso (mais de um `.`, ou o único `.` seguido de 3
     dígitos): `.` é sempre separador de MILHAR e é removido —
     `"1.234"` → `"1234"` (mil e duzentos... não, mil duzentos e trinta e
     quatro), `"1.234.567"` → `"1234567"`. Esta é a leitura brasileira
     padrão: ponto de milhar agrupa em blocos de três dígitos.
5. Sem `,` nem `.`: dígitos passam direto.
6. Sinal e qualquer caractere que não seja dígito, `,` ou `.` (letras,
   múltiplos sinais, mais de uma vírgula) fazem a entrada ser recusada —
   nunca há tentativa de "salvar" um texto como `"mil reais"`.

Nenhuma coerção a `0` em nenhum caminho: entrada recusada levanta
`ErroConversaoInvalida`, e a chamadora (`app/http/` — fora do escopo desta
tarefa) não grava nada (`EC-01`).

REGRAS: `RF-13`, `AC-09`, `AC-10`, `EC-01`
"""

from __future__ import annotations

import re
from decimal import localcontext
from typing import Final

from engine.precisao import CONTEXTO_MOTOR, dinheiro
from engine.tipos import Dinheiro, Taxa

REGRAS: Final[tuple[str, ...]] = ("RF-13", "AC-09", "AC-10", "EC-01")

# Só dígitos, vírgula e ponto (e opcionalmente um único sinal de menos na
# frente) sobrevivem à validação de caracteres — qualquer outra coisa
# ("mil reais", espaço interno, letra) é recusada antes de qualquer tentativa
# de normalização.
_CARACTERES_ACEITOS: Final[re.Pattern[str]] = re.compile(r"^-?[0-9.,]+$")

# Padrão do resultado normalizado, antes de virar Decimal: um sinal opcional,
# dígitos, e opcionalmente um ponto decimal com dígitos. Se o texto recusado
# chegou até aqui e ainda não bate neste padrão (ex.: "1.2.3" que não é nem
# "duas vírgulas" nem "um ponto de milhar válido"), a entrada é ambígua e é
# recusada — nunca adivinhada.
_PADRAO_NUMERICO_NORMALIZADO: Final[re.Pattern[str]] = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")

_CEM: Final = 100


class ErroConversaoInvalida(Exception):
    """Erro tipado da fronteira — `EC-01`. Carrega o valor exatamente como
    recebido (`valor_recusado`) e o motivo, nunca uma mensagem genérica.
    Levantar esta exceção é a única reação a entrada inválida: a chamadora
    não grava nada e não coage o valor a `0`."""

    def __init__(self, valor_recusado: str, motivo: str) -> None:
        self.valor_recusado = valor_recusado
        self.motivo = motivo
        super().__init__(
            f"entrada monetária/taxa recusada: {valor_recusado!r} — {motivo}"
        )


def _milhar_valido(texto_com_pontos: str) -> bool:
    """`True` quando `texto_com_pontos` (só dígitos, ponto e sinal opcional)
    é um agrupamento de milhar válido: o primeiro grupo tem de 1 a 3 dígitos
    e todo grupo seguinte tem exatamente 3 — a leitura brasileira padrão
    (`"1.234"`, `"12.345.678"`). `"1.2.3"` falha aqui (segundo e terceiro
    grupos não têm 3 dígitos) e é recusado, nunca interpretado como milhar."""
    texto_sem_sinal = texto_com_pontos[1:] if texto_com_pontos.startswith("-") else texto_com_pontos
    grupos = texto_sem_sinal.split(".")
    if len(grupos) < 2:
        return False
    primeiro, *restantes = grupos
    if not (1 <= len(primeiro) <= 3):
        return False
    return all(len(grupo) == 3 for grupo in restantes)


def _normalizar_separadores(texto: str) -> str:
    """Aplica a regra de normalização documentada no módulo e devolve uma
    string apenas com dígitos, sinal opcional e no máximo um `.` decimal —
    pronta para `dinheiro()`. Levanta `ErroConversaoInvalida` para qualquer
    entrada que não se encaixe deterministicamente na regra."""
    texto_stripado = texto.strip()
    if not texto_stripado:
        raise ErroConversaoInvalida(texto, "entrada vazia")

    if not _CARACTERES_ACEITOS.match(texto_stripado):
        raise ErroConversaoInvalida(texto, "caractere não numérico")

    tem_virgula = "," in texto_stripado
    tem_ponto = "." in texto_stripado

    if tem_virgula and tem_ponto:
        # Formato brasileiro completo: "." é milhar (removido), "," é
        # decimal (vira ".") — regra 2. Só é aceito se a parte antes da
        # vírgula for um agrupamento de milhar VÁLIDO (todo grupo entre
        # pontos, exceto o primeiro, com exatamente 3 dígitos) — "1.2,3"
        # não é "mil e duzentos vírgula três", é ambíguo e é recusado.
        if texto_stripado.count(",") != 1:
            raise ErroConversaoInvalida(texto, "mais de uma vírgula")
        parte_inteira, parte_decimal = texto_stripado.split(",")
        if not _milhar_valido(parte_inteira):
            raise ErroConversaoInvalida(texto, "milhar inválido")
        normalizado = parte_inteira.replace(".", "") + "." + parte_decimal
    elif tem_virgula:
        # Só vírgula: sempre decimal — regra 3 (AC-10).
        if texto_stripado.count(",") != 1:
            raise ErroConversaoInvalida(texto, "mais de uma vírgula")
        normalizado = texto_stripado.replace(",", ".")
    elif tem_ponto:
        # Só ponto: ambíguo, resolvido por contagem de dígitos finais — regra 4.
        pontos = texto_stripado.count(".")
        digitos_apos_ultimo_ponto = len(texto_stripado.rsplit(".", 1)[1])
        if pontos == 1 and digitos_apos_ultimo_ponto in (1, 2):
            normalizado = texto_stripado  # ponto decimal, mantido como está
        elif _milhar_valido(texto_stripado):
            normalizado = texto_stripado.replace(".", "")  # ponto(s) de milhar
        else:
            raise ErroConversaoInvalida(texto, "ponto ambíguo")
    else:
        normalizado = texto_stripado  # regra 5: só dígitos (e sinal)

    if not _PADRAO_NUMERICO_NORMALIZADO.match(normalizado):
        raise ErroConversaoInvalida(texto, "formato numérico inválido")

    return normalizado


def converter_para_dinheiro(texto: str) -> Dinheiro:
    """Converte a string de um campo `MOEDA` do formulário em `Dinheiro`.

    `str` direto para `Decimal` via `engine.precisao.dinheiro()` — jamais
    `float` (`RF-13`). `"1234,56"` produz exatamente `Decimal("1234.56")`
    (`AC-10`). Entrada inválida levanta `ErroConversaoInvalida`; nada é
    coagido a `0`.
    """
    normalizado = _normalizar_separadores(texto)
    return dinheiro(normalizado)


def converter_para_taxa(texto: str) -> Taxa:
    """Converte a string de um campo `TAXA` do formulário (percentual, ex.
    `"4,5"` para "4,5% a.m.") em `Taxa` — fração decimal (`Decimal("0.045")`),
    a mesma convenção de `engine/tipos.py::Taxa` (`"4% a.m." ==
    Decimal("0.04")`).

    Separada de `converter_para_dinheiro`: a normalização de separador é
    idêntica, mas aqui o valor normalizado ainda precisa ser dividido por 100
    antes de virar `Taxa` — moeda nunca passa por essa divisão. Ambas passam
    pelo mesmo construtor de `engine.precisao` (`dinheiro`), nunca por
    `Decimal(...)` direto. A divisão ocorre sob o mesmo `CONTEXTO_MOTOR`
    (prec=34) usado por `dinheiro()`, para que a fração herde a mesma
    precisão decimal integral do motor (`G-01`) em vez do contexto padrão do
    módulo `decimal`.
    """
    normalizado = _normalizar_separadores(texto)
    percentual = dinheiro(normalizado)
    with localcontext(CONTEXTO_MOTOR):
        fracao = percentual / _CEM
    return dinheiro(fracao)
