"""`Parametros` e o erro de carga — RF-13, RF-12, AC-17.

`Parametros` é o único jeito de o motor enxergar um valor `P_*`. Nenhum dos
valores ativos (§8 da canônica) pode ser escrito em `engine/` — eles chegam
em tempo de execução através de `FonteParametros.carregar()` (`engine/portas.py`)
e do adaptador concreto em `persistencia/arquivo/fonte_parametros.py`.

`numero(nome)` nunca devolve default: um default seria, na prática, um
parâmetro embutido no código, exatamente o que `AC-17` proíbe. Nome ausente é
`KeyError` ruidoso — silêncio aqui seria pior que exceção.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

REGRAS: Final[tuple[str, ...]] = ("RF-13", "RF-12", "AC-17")


class ErroParametros(Exception):
    """Levantado quando a carga de parâmetros não pode ser confiada.

    Cobre tanto violação de esquema (nomeando o `P_*` culpado) quanto
    `PARAMETROS_VERSION` divergente da versão pedida — RF-13/AC-17. Não há
    caminho de recuperação silenciosa: a carga aborta.
    """


@dataclass(frozen=True, slots=True)
class Parametros:
    """RF-13, AC-17 — os parâmetros ajustáveis, imutáveis após a carga.

    `_valores` é privado: só `numero()` (e, no futuro, acessores irmãos para
    `REGRA_*` e arrays) devem lê-lo. Prefixo simples, não duplo — evita name
    mangling desnecessário e permanece compatível com `frozen=True, slots=True`
    no Python 3.12.
    """

    PARAMETROS_VERSION: str
    ENGINE_VERSION: str
    DATA_VIGENCIA: date
    _valores: Mapping[str, Decimal | str | tuple[Decimal, ...]]

    def numero(self, nome: str) -> Decimal:
        """Devolve o valor escalar de um `P_*`. `KeyError` se não existir.

        AC-17: nunca um default. Se `nome` não está em `_valores`, o chamador
        pediu um parâmetro que a fonte externa não declara — isso é erro de
        programação ou de dado, não algo para mascarar com um valor
        embutido no motor.
        """
        valor = self._valores[nome]
        if not isinstance(valor, Decimal):
            raise KeyError(
                f"{nome!r} não é um parâmetro numérico escalar "
                f"(tipo carregado: {type(valor).__name__})"
            )
        return valor
