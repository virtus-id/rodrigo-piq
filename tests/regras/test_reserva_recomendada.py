"""Testes da §13.4, §13.5 e §13.6 — `T-105`, `T-106` e `T-107`.

RF-46, RF-47, RF-48, RF-50 · §13.4 (necessidade residual e reserva como
ÚLTIMO componente, ordem 5 da §13.7) · §13.5 (o elegível como TETO) · §13.6
(hierarquia canônica, na parte verificável sem a fatia 3C).

Cobre os critérios comportamentais das três tarefas, agrupados por tarefa nas
seções abaixo. O que cada uma arrisca:

- `T-105` — `EC-29` (não protetivos que já cobrem a necessidade dão residual
  `0`, nunca negativo); a **TRAVA MODO_ESTABILIZAÇÃO** de `AC-74` (déficit
  mensal zera a reserva por mais alto que seja o mobilizável); `EC-26`
  (mobilizável desconhecido dá `0` "até decisão válida", com a pendência
  registrada em `Diagnostico`, não convertida aqui); e a ORDEM de avaliação
  do `deriveReservaRecomendada` da §13.9, que só é observável nos casos em
  que dois ramos poderiam responder.
- `T-106` — `EC-28` (elegível `= 0` dá `0` mesmo com recursos positivos: a
  §13.5 proíbe recomendar recurso sem destinação elegível) e `AC-76`/
  `GAB-AI-07` (elegível como teto, não como parcela).
- `T-107` — `AC-82`: comparação EXATA, sem tolerância; `ErroInvariante` que
  nomeia os dois valores; nunca correção silenciosa.

Tolerância ZERO em toda asserção monetária (spec §5): `assertar_exato`, nunca
`assertar_monetario` — `NECESSIDADE_RESIDUAL` e `ATAQUE_IMEDIATO_RECOMENDADO`
estão em `SIMBOLOS_TOLERANCIA_ZERO` desde `T-109`.

Os gabaritos `GAB-AI` formais (`@pytest.mark.gabarito_ataque_imediato`, em
`tests/gabaritos_ataque_imediato/`) são `T-110`/`T-111` e **não** estão aqui;
`tests/regras/test_ataque_imediato.py` é de `T-112`.
"""

import pytest

from engine.ataque_imediato import (
    calcular_ATAQUE_IMEDIATO_RECOMENDADO,
    calcular_NECESSIDADE_RESIDUAL,
    derivar_RESERVA_RECOMENDADA,
    verificar_hierarquia_ataque_imediato,
)
from engine.ciclo_mensal import ErroInvariante
from engine.precisao import dinheiro
from engine.tipos import DESCONHECIDO, Dinheiro, DinheiroTalvez
from tests.conftest import assertar_exato

# Resultado mensal SUPERAVITÁRIO de referência: qualquer valor `>= 0` deixa a
# trava da §13.4 desarmada. Zero está incluído de propósito nas varreduras
# abaixo — a norma diz `< 0`, e zero não é déficit.
SUPERAVIT: Dinheiro = dinheiro(1500)


# ===========================================================================
# T-105 — `calcular_NECESSIDADE_RESIDUAL` (§13.4, primeira metade)
# ===========================================================================
@pytest.mark.regra
def test_necessidade_residual_subtrai_os_quatro_nao_protetivos() -> None:
    """`RF-46` · §13.4: `MAX(0, elegível − caixa − investimentos −
    extraordinários − ativos)`. Os quatro subtraendos são potências de dois
    distintas (1.000/2.000/4.000/8.000) para que, se um deles for esquecido
    ou somado no lugar de subtraído, o total denuncie **qual**: 20.000 − 15.000
    = 5.000."""
    obtido = calcular_NECESSIDADE_RESIDUAL(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(20000),
        CAIXA_RECOMENDADO=dinheiro(1000),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(2000),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(4000),
        ATIVOS_RECOMENDADOS=dinheiro(8000),
    )

    assertar_exato(obtido, dinheiro(5000))


@pytest.mark.regra
def test_necessidade_residual_da_zero_quando_os_nao_protetivos_ja_cobrem() -> None:
    """`EC-29` · §13.4: quando os recursos não protetivos já cobrem a
    necessidade elegível, o residual é `0` — e nunca negativo. A subtração
    crua daria −5.000; o `MAX(0, ...)` da §13.4 é regra, não defesa: um
    residual negativo vazando para `derivar_RESERVA_RECOMENDADA` faria o `MIN`
    devolver número negativo e quebraria a hierarquia da §13.6."""
    obtido = calcular_NECESSIDADE_RESIDUAL(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(10000),
        CAIXA_RECOMENDADO=dinheiro(9000),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(6000),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(0),
        ATIVOS_RECOMENDADOS=dinheiro(0),
    )

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
def test_necessidade_residual_cobertura_exata_da_zero_sem_folga() -> None:
    """A fronteira de `EC-29`: cobertura EXATA (soma dos quatro igual ao
    elegível) dá `0`, não centavo residual. Os centavos são de propósito —
    um `quantize` ou arredondamento escondido apareceria aqui."""
    obtido = calcular_NECESSIDADE_RESIDUAL(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro("7333.33"),
        CAIXA_RECOMENDADO=dinheiro("3333.33"),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(4000),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(0),
        ATIVOS_RECOMENDADOS=dinheiro(0),
    )

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
def test_necessidade_residual_preserva_centavos() -> None:
    """Precisão integral (`G-01`, `sdd.config.md` §4): o residual sai com os
    centavos que a subtração produziu, sem arredondar para real — o
    arredondamento existe apenas na camada de exibição."""
    obtido = calcular_NECESSIDADE_RESIDUAL(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro("1000.07"),
        CAIXA_RECOMENDADO=dinheiro("0.01"),
        INVESTIMENTOS_RECOMENDADOS=dinheiro("0.02"),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro("0.03"),
        ATIVOS_RECOMENDADOS=dinheiro("0.04"),
    )

    assertar_exato(obtido, dinheiro("999.97"))


@pytest.mark.regra
def test_necessidade_residual_com_tudo_zerado() -> None:
    """`EC-27`/`EC-29` na borda inferior: sem necessidade e sem recursos, o
    residual é `dinheiro(0)` — nenhum erro, nenhum desconhecido fabricado."""
    obtido = calcular_NECESSIDADE_RESIDUAL(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(0),
        CAIXA_RECOMENDADO=dinheiro(0),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(0),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(0),
        ATIVOS_RECOMENDADOS=dinheiro(0),
    )

    assertar_exato(obtido, dinheiro(0))


# ===========================================================================
# T-105 — `derivar_RESERVA_RECOMENDADA` (§13.4, TRAVA MODO_ESTABILIZACAO)
# ===========================================================================
@pytest.mark.regra
def test_trava_modo_estabilizacao_zera_a_reserva_com_mobilizavel_alto() -> None:
    """`AC-74` · `GAB-AI-05` · TRAVA da §13.4: `RESULTADO_MENSAL_ATUAL =
    −1.000` com `RESERVA_MOBILIZAVEL = 20.000` dá `RESERVA_RECOMENDADA = 0`.
    A norma é literal — "a reserva não pode ser usada para mascarar déficit
    estrutural". Sem a trava, o `MIN(20.000, 20.000)` devolveria 20.000."""
    obtido = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=dinheiro(20000),
        NECESSIDADE_RESIDUAL=dinheiro(20000),
        RESULTADO_MENSAL_ATUAL=dinheiro(-1000),
    )

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
@pytest.mark.parametrize(
    "deficit",
    [dinheiro("-0.01"), dinheiro(-1), dinheiro(-1000), dinheiro(-999999)],
)
def test_trava_dispara_para_qualquer_deficit_inclusive_de_um_centavo(
    deficit: Dinheiro,
) -> None:
    """A condição da §13.4 é `< 0`, sem limiar e sem parâmetro calibrável:
    um centavo de déficit já zera a reserva. Não existe `P_*` de tolerância
    aqui, e inventar um seria decidir metodologia no código."""
    obtido = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=dinheiro(50000),
        NECESSIDADE_RESIDUAL=dinheiro(50000),
        RESULTADO_MENSAL_ATUAL=deficit,
    )

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
def test_resultado_mensal_zero_nao_e_deficit_e_nao_aciona_a_trava() -> None:
    """A fronteira exata da trava: a §13.4 diz `< 0`, não `<= 0`. Resultado
    mensal exatamente zero é aperto, não déficit — a reserva segue para o
    `MIN` normal e devolve 3.000."""
    obtido = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=dinheiro(3000),
        NECESSIDADE_RESIDUAL=dinheiro(8000),
        RESULTADO_MENSAL_ATUAL=dinheiro(0),
    )

    assertar_exato(obtido, dinheiro(3000))


# ===========================================================================
# T-105 — `derivar_RESERVA_RECOMENDADA` (desconhecido, MIN e ORDEM da §13.9)
# ===========================================================================
@pytest.mark.regra
def test_mobilizavel_desconhecido_da_zero_ate_decisao_valida() -> None:
    """`EC-26` · §13.9: `RESERVA_MOBILIZAVEL` desconhecida devolve `0` "até
    decisão válida", com residual alto disponível. Não é conversão do
    desconhecido em informação: a §13.1 manda que "nenhum valor da reserva
    entre numericamente no recomendado ou aprovado até existir decisão
    válida" (`AC-73`), e a PENDÊNCIA continua registrada em
    `Diagnostico.RESERVA_MOBILIZAVEL: DinheiroTalvez` (`RF-41`), que é
    `DinheiroTalvez` justamente para carregá-la — esta função devolve
    `Dinheiro` porque a §13.9 devolve `0`, não `DESCONHECIDA`."""
    obtido = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=DESCONHECIDO,
        NECESSIDADE_RESIDUAL=dinheiro(30000),
        RESULTADO_MENSAL_ATUAL=SUPERAVIT,
    )

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
def test_mobilizavel_zero_conhecido_e_decisao_valida_nao_desconhecido() -> None:
    """A guarda é `is DESCONHECIDO`, nunca "é falsy". `dinheiro(0)` conhecido
    é decisão válida do usuário (ele decidiu não mobilizar) e passa pelo
    `MIN` normalmente. Numericamente coincide com o caso desconhecido, e é
    por isso que os dois têm teste separado: um `if not RESERVA_MOBILIZAVEL`
    passaria nos dois e estaria errado."""
    obtido = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=dinheiro(0),
        NECESSIDADE_RESIDUAL=dinheiro(30000),
        RESULTADO_MENSAL_ATUAL=SUPERAVIT,
    )

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
def test_reserva_recomendada_limitada_pela_necessidade_residual() -> None:
    """§13.4 · `GAB-AI-06`: `MIN(10.000, 8.000) = 8.000`. A reserva é o
    ÚLTIMO componente (§13.7, ordem 5) e entra "apenas [pela] necessidade
    residual" — o excedente da reserva não é mobilizado só por existir
    (REGRA CANÔNICA da §13.4)."""
    obtido = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=dinheiro(10000),
        NECESSIDADE_RESIDUAL=dinheiro(8000),
        RESULTADO_MENSAL_ATUAL=SUPERAVIT,
    )

    assertar_exato(obtido, dinheiro(8000))


@pytest.mark.regra
def test_reserva_recomendada_limitada_pelo_mobilizavel() -> None:
    """O outro lado do `MIN` (§13.4): quando o residual é maior que o
    mobilizável, vence o mobilizável — a reserva nunca ultrapassa o máximo
    que o usuário aceitou submeter à análise (§13.1, `AC-71`)."""
    obtido = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=dinheiro(2500),
        NECESSIDADE_RESIDUAL=dinheiro(9000),
        RESULTADO_MENSAL_ATUAL=SUPERAVIT,
    )

    assertar_exato(obtido, dinheiro(2500))


@pytest.mark.regra
def test_residual_zero_zera_a_reserva_mesmo_com_mobilizavel_alto() -> None:
    """`EC-29` encadeado na §13.4: se os não protetivos já cobriram tudo, o
    residual é `0` e `MIN(40.000, 0) = 0`. É a formalização de "a reserva é o
    último componente": recurso protetivo só entra pelo que sobrou."""
    obtido = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=dinheiro(40000),
        NECESSIDADE_RESIDUAL=dinheiro(0),
        RESULTADO_MENSAL_ATUAL=SUPERAVIT,
    )

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
def test_ordem_da_secao_13_9_a_trava_vence_o_desconhecido() -> None:
    """ORDEM de `deriveReservaRecomendada` (§13.9), primeiro caso observável:
    com déficit **e** mobilizável `DESCONHECIDO`, a trava do déficit responde
    primeiro. Os dois ramos devolvem `0`, então o número não distingue — o
    que distingue é que a função não pode levantar nem devolver
    `DESCONHECIDO`: inverter as guardas para propagar a pendência quebraria
    `AC-74`, que exige `0` sob déficit sem condição nenhuma. Que o retorno
    nunca é `DESCONHECIDO` está provado de forma mais forte que por assert:
    a assinatura devolve `Dinheiro`, e `mypy --strict` recusa o contrário
    (o assert de runtime seria "non-overlapping identity check")."""
    obtido = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=DESCONHECIDO,
        NECESSIDADE_RESIDUAL=dinheiro(12000),
        RESULTADO_MENSAL_ATUAL=dinheiro(-500),
    )

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
def test_ordem_da_secao_13_9_a_trava_vence_o_min() -> None:
    """ORDEM da §13.9, segundo caso observável — e o único em que a ordem
    muda o NÚMERO: com déficit, o `MIN(7.000, 7.000)` **não** é avaliado.
    Se a trava fosse aplicada depois do `MIN`, ou como mais um argumento
    dele, o resultado seria 7.000. É a diferença entre transcrever a §13.4 e
    reinterpretá-la."""
    obtido = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=dinheiro(7000),
        NECESSIDADE_RESIDUAL=dinheiro(7000),
        RESULTADO_MENSAL_ATUAL=dinheiro(-1),
    )

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
def test_gab_ai_06_residual_e_reserva_encadeados() -> None:
    """`GAB-AI-06` na parte que estas duas funções cobrem (o ponta a ponta é
    `T-110`): elegível 20.000, caixa 5.000, investimentos 7.000, extras 0,
    ativos 0 → residual 8.000; mobilizável 10.000 → reserva 8.000. As duas
    funções encadeadas exatamente como a §13.4 as encadeia."""
    residual = calcular_NECESSIDADE_RESIDUAL(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(20000),
        CAIXA_RECOMENDADO=dinheiro(5000),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(7000),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(0),
        ATIVOS_RECOMENDADOS=dinheiro(0),
    )
    assertar_exato(residual, dinheiro(8000))

    reserva = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=dinheiro(10000),
        NECESSIDADE_RESIDUAL=residual,
        RESULTADO_MENSAL_ATUAL=SUPERAVIT,
    )

    assertar_exato(reserva, dinheiro(8000))


@pytest.mark.regra
def test_as_duas_funcoes_da_secao_13_4_recusam_chamada_posicional() -> None:
    """NFR "Pureza (Rodada 3)" (spec §5) e `RF-48`: as duas assinaturas
    começam com `*`. Com cinco `Dinheiro` de mesmo tipo em
    `calcular_NECESSIDADE_RESIDUAL`, a passagem posicional tornaria uma troca
    de ordem erro silencioso que nenhum tipo pega."""
    with pytest.raises(TypeError):
        calcular_NECESSIDADE_RESIDUAL(  # type: ignore[call-arg]
            dinheiro(1), dinheiro(0), dinheiro(0), dinheiro(0), dinheiro(0)
        )
    with pytest.raises(TypeError):
        derivar_RESERVA_RECOMENDADA(  # type: ignore[call-arg]
            dinheiro(1), dinheiro(1), dinheiro(1)
        )


# ===========================================================================
# T-106 — `calcular_ATAQUE_IMEDIATO_RECOMENDADO` (§13.3, §13.5, §13.9)
# ===========================================================================
@pytest.mark.regra
def test_recomendado_soma_os_cinco_componentes_quando_o_elegivel_nao_limita() -> None:
    """`RF-47` · §13.9 `deriveAtaqueImediatoRecomendado`: com elegível folgado,
    o resultado é a soma dos CINCO componentes recomendados. As cinco parcelas
    são potências de dois (1.000/2.000/4.000/8.000/16.000): se alguma faltar
    na soma, o total 31.000 denuncia **qual**."""
    obtido = calcular_ATAQUE_IMEDIATO_RECOMENDADO(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(999999),
        CAIXA_RECOMENDADO=dinheiro(1000),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(2000),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(4000),
        ATIVOS_RECOMENDADOS=dinheiro(8000),
        RESERVA_RECOMENDADA=dinheiro(16000),
    )

    assertar_exato(obtido, dinheiro(31000))


@pytest.mark.regra
def test_elegivel_zero_da_zero_mesmo_com_recursos_altos() -> None:
    """`EC-28` · §13.5: "nunca recomendar recurso sem destinação financeira
    elegível". Com elegível `= 0` e 100.000 de recursos recomendáveis, o
    resultado é `dinheiro(0)` — ter dinheiro mobilizável não é razão para
    mobilizá-lo. Uma implementação que somasse antes de limitar, ou que
    tratasse o elegível `0` como "sem limite", devolveria 100.000."""
    obtido = calcular_ATAQUE_IMEDIATO_RECOMENDADO(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(0),
        CAIXA_RECOMENDADO=dinheiro(20000),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(20000),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(20000),
        ATIVOS_RECOMENDADOS=dinheiro(20000),
        RESERVA_RECOMENDADA=dinheiro(20000),
    )

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
def test_elegivel_e_teto_nao_parcela() -> None:
    """`AC-76` · `GAB-AI-07`: elegível 10.000 contra 25.000 de recursos
    recomendáveis dá **10.000**, não 25.000 e nem 35.000 — o elegível LIMITA
    a soma, jamais entra nela (§13.5)."""
    obtido = calcular_ATAQUE_IMEDIATO_RECOMENDADO(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(10000),
        CAIXA_RECOMENDADO=dinheiro(5000),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(5000),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(5000),
        ATIVOS_RECOMENDADOS=dinheiro(5000),
        RESERVA_RECOMENDADA=dinheiro(5000),
    )

    assertar_exato(obtido, dinheiro(10000))


@pytest.mark.regra
def test_gab_ai_06_recomendado_igual_ao_elegivel_na_cobertura_exata() -> None:
    """`GAB-AI-06`, terceira linha: caixa 5.000 + investimentos 7.000 +
    reserva 8.000 = 20.000, exatamente o elegível → `ATAQUE_IMEDIATO_RECOMENDADO
    = 20.000`. A fronteira do `MIN` com os dois lados iguais."""
    obtido = calcular_ATAQUE_IMEDIATO_RECOMENDADO(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(20000),
        CAIXA_RECOMENDADO=dinheiro(5000),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(7000),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(0),
        ATIVOS_RECOMENDADOS=dinheiro(0),
        RESERVA_RECOMENDADA=dinheiro(8000),
    )

    assertar_exato(obtido, dinheiro(20000))


@pytest.mark.regra
def test_reserva_desconhecida_nao_entra_no_recomendado() -> None:
    """`AC-73` encadeado: com a decisão de reserva adiada,
    `derivar_RESERVA_RECOMENDADA` devolve `0` e o recomendado fica com os
    12.000 dos não protetivos — "nenhum valor da reserva entra numericamente
    no recomendado ou aprovado até existir decisão válida" (§13.1). O
    recomendado continua NUMÉRICO, nunca desconhecido (plano R3.4.6)."""
    reserva = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=DESCONHECIDO,
        NECESSIDADE_RESIDUAL=dinheiro(50000),
        RESULTADO_MENSAL_ATUAL=SUPERAVIT,
    )

    obtido = calcular_ATAQUE_IMEDIATO_RECOMENDADO(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(60000),
        CAIXA_RECOMENDADO=dinheiro(4000),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(3000),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(2000),
        ATIVOS_RECOMENDADOS=dinheiro(3000),
        RESERVA_RECOMENDADA=reserva,
    )

    assertar_exato(obtido, dinheiro(12000))


@pytest.mark.regra
def test_recomendado_preserva_centavos() -> None:
    """Precisão integral (`G-01`): a soma dos cinco sai com os centavos
    exatos, sem arredondar para real. `NECESSIDADE_RESIDUAL` e
    `ATAQUE_IMEDIATO_RECOMENDADO` são símbolos de tolerância ZERO
    (`T-109`)."""
    obtido = calcular_ATAQUE_IMEDIATO_RECOMENDADO(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(99999),
        CAIXA_RECOMENDADO=dinheiro("0.01"),
        INVESTIMENTOS_RECOMENDADOS=dinheiro("0.02"),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro("0.03"),
        ATIVOS_RECOMENDADOS=dinheiro("0.04"),
        RESERVA_RECOMENDADA=dinheiro("0.05"),
    )

    assertar_exato(obtido, dinheiro("0.15"))


@pytest.mark.regra
def test_recomendado_recusa_chamada_posicional() -> None:
    """`AC-80` e plano R3.4.5: com SEIS parâmetros `Dinheiro` de mesmo tipo,
    trocar `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` por `CAIXA_RECOMENDADO`
    em chamada posicional seria erro silencioso que nenhum tipo pega. O `*`
    torna a chamada posicional impossível — `TypeError` em execução, erro em
    `mypy --strict`."""
    with pytest.raises(TypeError):
        calcular_ATAQUE_IMEDIATO_RECOMENDADO(  # type: ignore[call-arg]
            dinheiro(1), dinheiro(1), dinheiro(1), dinheiro(1), dinheiro(1), dinheiro(1)
        )


# ===========================================================================
# T-107 — `verificar_hierarquia_ataque_imediato` (§13.6)
# ===========================================================================
@pytest.mark.regra
@pytest.mark.parametrize(
    ("potencial", "recomendado"),
    [
        (dinheiro(0), dinheiro(0)),
        (dinheiro(31000), dinheiro(31000)),
        (dinheiro(50000), dinheiro(10000)),
        (dinheiro("0.02"), dinheiro("0.01")),
    ],
)
def test_hierarquia_valida_passa_em_silencio(
    potencial: Dinheiro, recomendado: Dinheiro
) -> None:
    """`RF-50` · §13.6: `POTENCIAL >= RECOMENDADO >= 0` — inclusive nos casos
    de igualdade, que são o normal quando tudo o que é potencial também é
    recomendável. A função não devolve valor: ou passa em silêncio, ou
    levanta. Que ela não devolve nada é garantido por `-> None` em
    `mypy --strict` (asserção de runtime sobre o retorno seria recusada como
    `func-returns-value`), então o que este teste prova é a ausência de
    exceção."""
    verificar_hierarquia_ataque_imediato(
        ATAQUE_IMEDIATO_POTENCIAL=potencial,
        ATAQUE_IMEDIATO_RECOMENDADO=recomendado,
    )


@pytest.mark.regra
def test_potencial_menor_que_recomendado_levanta_erro_invariante() -> None:
    """`AC-82` · `A-04`: recomendado acima do potencial é bug do motor (item
    que entrou no filtro da §13.3 sem estar no da §13.2), nunca dado do
    usuário. `ErroInvariante`, no mesmo padrão de `engine/ciclo_mensal.py` —
    e a mensagem NOMEIA os dois valores, para que o diagnóstico não exija
    reproduzir o caso."""
    with pytest.raises(ErroInvariante) as capturado:
        verificar_hierarquia_ataque_imediato(
            ATAQUE_IMEDIATO_POTENCIAL=dinheiro(9000),
            ATAQUE_IMEDIATO_RECOMENDADO=dinheiro(9500),
        )

    mensagem = str(capturado.value)
    assert "ATAQUE_IMEDIATO_POTENCIAL" in mensagem
    assert "ATAQUE_IMEDIATO_RECOMENDADO" in mensagem
    assert "9000" in mensagem
    assert "9500" in mensagem


@pytest.mark.regra
def test_recomendado_negativo_levanta_erro_invariante() -> None:
    """§13.6, o outro ramo verificável: `RECOMENDADO >= 0`. Um recomendado
    negativo passaria pela primeira guarda (o potencial é maior), então
    precisa da sua — e a mensagem nomeia os dois valores também aqui."""
    with pytest.raises(ErroInvariante) as capturado:
        verificar_hierarquia_ataque_imediato(
            ATAQUE_IMEDIATO_POTENCIAL=dinheiro(5000),
            ATAQUE_IMEDIATO_RECOMENDADO=dinheiro(-1),
        )

    mensagem = str(capturado.value)
    assert "ATAQUE_IMEDIATO_RECOMENDADO" in mensagem
    assert "ATAQUE_IMEDIATO_POTENCIAL" in mensagem
    assert "-1" in mensagem


@pytest.mark.regra
def test_hierarquia_tem_tolerancia_zero_um_centavo_ja_viola() -> None:
    """`AC-82`: tolerância ZERO. Um centavo de excesso do recomendado sobre o
    potencial já levanta — a tolerância de `± R$ 0,05` da spec §5 vale para
    valores acumulados ao longo de meses, e os dois lados aqui saem da MESMA
    rodada de cálculo, sobre os mesmos itens. Um centavo de folga esconderia
    exatamente o erro de filtro que esta função existe para pegar."""
    with pytest.raises(ErroInvariante):
        verificar_hierarquia_ataque_imediato(
            ATAQUE_IMEDIATO_POTENCIAL=dinheiro("1000.00"),
            ATAQUE_IMEDIATO_RECOMENDADO=dinheiro("1000.01"),
        )


@pytest.mark.regra
def test_hierarquia_nunca_corrige_o_valor_recebido() -> None:
    """`A-04` · plano R3.4.5: a função "nunca corrige, nunca degrada
    silenciosamente". Não devolve valor (`-> None` verificado por
    `mypy --strict`), então não há canal por onde um número rebaixado saia
    dela; e os `Decimal` recebidos permanecem intactos após a chamada válida
    — `Decimal` é imutável, e a função não reatribui nada no chamador."""
    potencial = dinheiro(8000)
    recomendado = dinheiro(3000)

    verificar_hierarquia_ataque_imediato(
        ATAQUE_IMEDIATO_POTENCIAL=potencial,
        ATAQUE_IMEDIATO_RECOMENDADO=recomendado,
    )

    assertar_exato(potencial, dinheiro(8000))
    assertar_exato(recomendado, dinheiro(3000))


@pytest.mark.regra
def test_hierarquia_recusa_chamada_posicional() -> None:
    """Assinatura com `*` (plano R3.4.5): com dois `Dinheiro` de mesmo tipo,
    inverter potencial e recomendado em chamada posicional transformaria a
    verificação no seu contrário — e passaria em silêncio."""
    with pytest.raises(TypeError):
        verificar_hierarquia_ataque_imediato(  # type: ignore[call-arg]
            dinheiro(10), dinheiro(5)
        )


# ===========================================================================
# T-105/T-106/T-107 — pureza: nenhuma das quatro busca dado em estado
# ===========================================================================
@pytest.mark.regra
def test_as_quatro_funcoes_nao_consultam_estado_nem_diagnostico() -> None:
    """`RF-48`/`AC-80` e a NFR de Pureza (spec §5), verificado por AST sobre o
    módulo: `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` e
    `RESULTADO_MENSAL_ATUAL` chegam por parâmetro, e nenhum nome de
    `EstadoFinanceiro`, `Diagnostico` ou `MODO_ESTABILIZACAO` existe em código
    executável — só em prosa. `MODO_ESTABILIZACAO` deriva da MESMA condição
    de déficit em `engine/diagnostico.py`, e é justamente por isso que
    consultá-lo seria tentador e quebraria a pureza."""
    import ast
    import inspect

    import engine.ataque_imediato as modulo

    arvore = ast.parse(inspect.getsource(modulo))
    nomes_executaveis = {
        no.id for no in ast.walk(arvore) if isinstance(no, ast.Name)
    } | {no.attr for no in ast.walk(arvore) if isinstance(no, ast.Attribute)}

    for proibido in ("EstadoFinanceiro", "Diagnostico", "MODO_ESTABILIZACAO"):
        assert proibido not in nomes_executaveis, (
            f"{proibido} apareceu em código executável de engine/ataque_imediato.py"
        )

    assert not [no for no in ast.walk(arvore) if isinstance(no, (ast.Global, ast.Nonlocal))]


@pytest.mark.regra
@pytest.mark.parametrize(
    "mobilizavel",
    [DESCONHECIDO, dinheiro(0), dinheiro(1234), dinheiro("0.01")],
)
def test_reserva_recomendada_nunca_devolve_negativo(mobilizavel: DinheiroTalvez) -> None:
    """Contrato de saída que sustenta a hierarquia da §13.6: sob qualquer
    combinação de entrada — inclusive residual `0` e mobilizável desconhecido
    — `RESERVA_RECOMENDADA >= 0`. Se ela pudesse ser negativa,
    `ATAQUE_IMEDIATO_RECOMENDADO` também poderia, e
    `verificar_hierarquia_ataque_imediato` levantaria em operação normal."""
    for residual in (dinheiro(0), dinheiro(5), dinheiro(90000)):
        for resultado_mensal in (dinheiro(-10), dinheiro(0), dinheiro(10)):
            obtido = derivar_RESERVA_RECOMENDADA(
                RESERVA_MOBILIZAVEL=mobilizavel,
                NECESSIDADE_RESIDUAL=residual,
                RESULTADO_MENSAL_ATUAL=resultado_mensal,
            )
            assert obtido >= dinheiro(0)
