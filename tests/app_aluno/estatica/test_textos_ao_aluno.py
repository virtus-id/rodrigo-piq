"""Auditoria estática dos textos do registro lidos pelo aluno — `T-298`,
`RF-03`, `AC-36`.

O aluno é "você", nunca "o usuário" (termo técnico, 3ª pessoa). Barra entre
palavras sem espaço de um lado só: `">-"` dobrado em YAML vira
"inadimplência/ negativação" quando a quebra de linha cai depois da barra.
"""

from __future__ import annotations

import re

from collection.carga import carregar_registros


def _textos() -> list[tuple[str, str]]:
    textos = []
    for registro in carregar_registros().registros:
        textos.append((registro.ID, registro.enunciado))
        textos.extend((registro.ID, opcao.rotulo) for opcao in registro.opcoes)
    return textos


def test_t298_nenhum_texto_ao_aluno_fala_do_usuario() -> None:
    violacoes = [f"{i}: {t!r}" for i, t in _textos() if re.search(r"usu[aá]rio", t, re.I)]

    assert not violacoes, "\n".join(violacoes)


def test_t298_barra_sem_espaco_de_um_lado_so() -> None:
    violacoes = [f"{i}: {t!r}" for i, t in _textos() if re.search(r"\S/ | /\S", t)]

    assert not violacoes, "\n".join(violacoes)
