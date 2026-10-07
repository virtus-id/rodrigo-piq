// @vitest-environment happy-dom
/**
 * `TelaEquipeCaso` — pendências de homologação e fontes (`T-266`, `RF-93`,
 * `AC-142`, `AC-155`).
 *
 * A lista e os rótulos vêm do servidor (`GET .../decisao`); a tela só os
 * mostra e desabilita "Liberar" — a recusa de verdade é o `409`.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import TelaEquipeCaso from "../../../src/telas/TelaEquipeCaso";
import * as api from "../../../src/services/api";
import type {
  CasoParaRevisao,
  OpcoesDeDecisao,
} from "../../../src/services/api";

afterEach(() => {
  vi.restoreAllMocks();
});

const CASO = {
  CASO_ID: "CASO-1",
  plano: {
    titulo: "Sua ordem projetada de quitação",
    corpo: "",
    ordem: [],
    PRAZO_TOTAL: "",
    CUSTO_FUTURO_TOTAL: "",
    ENGINE_VERSION: "e",
    PARAMETROS_VERSION: "p",
    cenario: "",
    acoes: [],
    pendencias: null,
    MODO_ESTABILIZACAO: false,
    RESULTADO_CAIXA_OBSERVADO: "",
    reserva_mobilizavel: { pendente_de_decisao: false, valor: null },
  },
  estado_inputs: {
    campos: [],
    perfil_comportamental: [],
    sinais_comportamentais: [],
    dividas: [],
  },
  fila: {
    CASO_ID: "CASO-1",
    SNAPSHOT_ID: "S1",
    versao: 1,
    DATA_REFERENCIA: "2026-09-30",
    MOTIVO_RECALCULO: null,
    EVENTO_RECALCULO: null,
    METODO_RECOMENDADO_PIQ: "AVALANCHE",
    STATUS_METODO: "DEFINITIVO_NA_DATA",
    metodo: "Avalanche",
    status_metodo: "Definitivo na data",
    criterio_metodo:
      "Cada dívida entra quando é a que mais economiza juros por real pago, entre as que restam.",
    motivo: "Primeiro cálculo, sem evento de recálculo",
    entra_por_politica: true,
    e_metodologico: false,
    ENGINE_VERSION: "e",
    PARAMETROS_VERSION: "p",
  },
} as unknown as CasoParaRevisao;

function montar(opcoes: OpcoesDeDecisao, caso: CasoParaRevisao = CASO) {
  vi.spyOn(api, "obterCasoParaRevisao").mockResolvedValue(caso);
  vi.spyOn(api, "obterOpcoesDeDecisao").mockResolvedValue(opcoes);
  render(<TelaEquipeCaso casoId="CASO-1" voltar={vi.fn()} />);
}

describe("TelaEquipeCaso — pendências de homologação (T-266)", () => {
  it("lista cada pendência nomeando dívida e dado, e desabilita Liberar", async () => {
    montar({
      classificacoes_erro: [],
      fontes: [
        {
          item_id: "D001",
          nome: "Consignado — CAIXA · 2",
          dado: "Fonte das informações",
          origem: "B5.I02",
          nivel: "PENDENTE_DE_CONFIRMACAO",
          rotulo: "Pendente de confirmação",
        },
      ],
      seguros_nao_informados: [
        { item_id: "D001", nome: "Consignado — CAIXA · 2" },
      ],
      rotulo_nao_informado: "Não informado",
      pendencias_homologacao: [
        {
          item_id: "D001",
          nome: "Consignado — CAIXA · 2",
          ID_PERGUNTA: "B5.B03",
          enunciado: "Qual é o saldo devedor atual desta dívida?",
          motivo: "PENDENTE_DE_CONFIRMACAO",
        },
      ],
    });

    const alerta = await screen.findByRole("alert");
    // `T-328` (`RF-111`): a dívida e o dado por nome, nunca `D001`/`B5.I02`.
    expect(alerta).toHaveTextContent(
      "Consignado — CAIXA · 2 · Qual é o saldo devedor atual desta dívida?",
    );
    expect(
      screen.getByRole("button", { name: "Liberar para o aluno" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Pedir correção" }),
    ).toBeEnabled();
    expect(
      screen.getByText(
        "Consignado — CAIXA · 2 · Fonte das informações: Pendente de confirmação",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Consignado — CAIXA · 2 · seguro: Não informado"),
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(
      /\bD0\d\d\b|\bB\d+\.[A-Z0-9]+\b/,
    );
  });

  it("sem pendência, Liberar fica disponível", async () => {
    montar({ classificacoes_erro: [], pendencias_homologacao: [] });

    expect(
      await screen.findByRole("button", { name: "Liberar para o aluno" }),
    ).toBeEnabled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("TelaEquipeCaso — registro de homologação (T-304, RF-96)", () => {
  it('mostra os cinco itens de DE-08, com "não disponível" e o motivo', async () => {
    montar({
      classificacoes_erro: [],
      pendencias_homologacao: [],
      homologacao: {
        homologavel: true,
        itens: {
          // `T-328`: o servidor já manda os nomes.
          ordem_final_de_ataque: {
            valor: ["1º Cheque — CAIXA", "2º Consignado — BB"],
            origem: ["o"],
            motivo: null,
          },
          mes_de_quitacao_por_divida: {
            valor: { "Cheque — CAIXA": 4, "Consignado — BB": 9 },
            origem: ["o"],
            motivo: null,
          },
          valor_mensal_destinado: {
            valor: "R$ 500,00",
            origem: ["o"],
            motivo: null,
          },
          custo_total_de_juros: {
            valor: "R$ 321,00",
            origem: ["o"],
            motivo: null,
          },
          uso_da_reserva: {
            valor: "não disponível",
            origem: [],
            motivo: "a reserva recomendada ainda não é registrada pelo cálculo",
          },
        },
      },
    });

    const secao = await screen.findByRole("region", {
      name: "Registro de homologação",
    });
    expect(secao).toHaveTextContent(
      "Ordem final de ataque1º Cheque — CAIXA2º Consignado — BB",
    );
    expect(secao).toHaveTextContent(
      "Cheque — CAIXA: mês 4Consignado — BB: mês 9",
    );
    expect(secao).toHaveTextContent("Valor mensal destinadoR$ 500,00");
    expect(secao).toHaveTextContent("Custo total de jurosR$ 321,00");
    expect(secao).toHaveTextContent(
      "não disponívela reserva recomendada ainda não é registrada pelo cálculo",
    );
    expect(secao).toHaveTextContent("Pode ser homologadosim");
  });
});

describe("TelaEquipeCaso — linguagem humana (T-326, RF-111, AC-174)", () => {
  const JUSTIFICATIVA =
    "Posição 1: D011 — método HIBRIDO, critério: D_ESTRELA prioritária (H-05, H-06, H-07).";

  function casoComDados(): CasoParaRevisao {
    return {
      ...CASO,
      plano: {
        ...CASO.plano,
        ordem: [
          {
            posicao: 1,
            indice: 1,
            total: 1,
            DIVIDA_ID: "D011",
            nome: "Cheque especial — CAIXA ECONOMICA FEDERAL",
            JUSTIFICATIVA_POSICAO: JUSTIFICATIVA,
            explicacao: "É a dívida que mais destrava o seu orçamento agora.",
            valores_de_apoio: [],
          },
        ],
      },
      estado_inputs: {
        campos: [
          {
            nome: "Renda total recorrente",
            valor: "R$ 10.350,92",
            codigo: "RENDA_TOTAL_RECORRENTE",
          },
        ],
        perfil_comportamental: [
          {
            nome: "Registro dos gastos",
            valor: "A maior parte, mas alguns ficam de fora.",
            codigo: "REGISTRO_GASTOS",
          },
        ],
        sinais_comportamentais: [],
        dividas: [
          {
            DIVIDA_ID: "D011",
            nome: "Cheque especial — CAIXA ECONOMICA FEDERAL",
            campos: [
              {
                nome: "Custo efetivo total (CET)",
                valor: "Não informado",
                codigo: "CET",
              },
            ],
          },
        ],
      },
    };
  }

  it('posição por "tipo — credor" e explicação, sem a justificativa do motor (T-330)', async () => {
    montar(
      { classificacoes_erro: [], pendencias_homologacao: [] },
      casoComDados(),
    );

    expect(
      await screen.findAllByText("Cheque especial — CAIXA ECONOMICA FEDERAL", {
        exact: false,
      }),
    ).not.toHaveLength(0);
    expect(
      screen.getByText("É a dívida que mais destrava o seu orçamento agora."),
    ).toBeInTheDocument();
    expect(screen.queryByText(JUSTIFICATIVA)).not.toBeInTheDocument();
    expect(screen.queryByText("Detalhe técnico")).not.toBeInTheDocument();
  });

  it("dados com rótulo e valor do servidor, sem o nome da variável", async () => {
    montar(
      { classificacoes_erro: [], pendencias_homologacao: [] },
      casoComDados(),
    );

    // `T-348`: o dado da dívida também aparece no cartão dela ("Para o revisor") —
    // o rótulo existe nos dois lugares; qualquer um prova o rótulo legível.
    const cet = (
      await screen.findAllByText("Custo efetivo total (CET)", { exact: false })
    )[0].closest("dt");
    expect(cet).toHaveTextContent(/^Custo efetivo total \(CET\)$/);
    expect(
      screen.queryByText("RENDA_TOTAL_RECORRENTE"),
    ).not.toBeInTheDocument();
    expect(cet?.nextElementSibling).toHaveTextContent("Não informado");
    expect(screen.getByText("R$ 10.350,92")).toBeInTheDocument();
    expect(
      screen.getByText("A maior parte, mas alguns ficam de fora."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", {
        name: "Cheque especial — CAIXA ECONOMICA FEDERAL",
      }),
    ).not.toHaveTextContent("D011");
  });

  it("método do caso em destaque, uma vez, com o critério (T-330)", async () => {
    montar({ classificacoes_erro: [], pendencias_homologacao: [] });

    const destaque = await screen.findByRole("region", { name: /Avalanche/ });
    expect(destaque).toHaveTextContent("Método selecionado para este aluno");
    expect(destaque).toHaveTextContent("Definitivo na data");
    expect(destaque).toHaveTextContent("mais economiza juros por real pago");
    expect(screen.getAllByText(/Avalanche/)).toHaveLength(1);
    expect(document.body.textContent).not.toContain("DEFINITIVO_NA_DATA");
  });
});

describe("TelaEquipeCaso — o caso pelo e-mail do aluno (T-327, RF-111)", () => {
  it("título pelo e-mail; o CASO_ID só no localizador", async () => {
    montar(
      { classificacoes_erro: [], pendencias_homologacao: [] },
      { ...CASO, fila: { ...CASO.fila, email_do_aluno: "fulano@exemplo.com" } },
    );

    expect(
      await screen.findByRole("heading", {
        name: "Conferir o plano de fulano@exemplo.com",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("CASO-1 · plano v1")).toBeInTheDocument();
  });

  it("sem e-mail, o título cai no CASO_ID", async () => {
    montar({ classificacoes_erro: [], pendencias_homologacao: [] });

    expect(
      await screen.findByRole("heading", {
        name: "Conferir o plano de CASO-1",
      }),
    ).toBeInTheDocument();
  });
});

describe("TelaEquipeCaso — mensagem para o aluno (T-333, RF-113)", () => {
  it("pedir correção sem mensagem é recusado na tela, sem chamar o servidor", async () => {
    const decidir = vi.spyOn(api, "decidirRevisao").mockResolvedValue({});
    montar({ classificacoes_erro: [], pendencias_homologacao: [] });

    await userEvent.click(
      await screen.findByRole("button", { name: "Pedir correção" }),
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Escreva a mensagem para o aluno.",
    );
    expect(decidir).not.toHaveBeenCalled();
  });

  it("envia a mensagem separada da observação interna", async () => {
    const decidir = vi.spyOn(api, "decidirRevisao").mockResolvedValue({});
    montar({ classificacoes_erro: [], pendencias_homologacao: [] });

    await userEvent.type(
      await screen.findByLabelText("Mensagem para o aluno"),
      "Informe a taxa do cheque especial",
    );
    await userEvent.type(screen.getByLabelText("Observação"), "taxa zerada");
    await userEvent.click(
      screen.getByRole("button", { name: "Pedir correção" }),
    );

    expect(decidir).toHaveBeenCalledWith("CASO-1", {
      decisao: "REPROVAR",
      classificacaoErro: undefined,
      observacao: "taxa zerada",
      mensagemAluno: "Informe a taxa do cheque especial",
    });
  });
});

describe("TelaEquipeCaso — o plano como o aluno vai ver (T-347, RF-121, AC-190)", () => {
  const comPlano: CasoParaRevisao = {
    ...CASO,
    plano: {
      ...CASO.plano,
      secoes: { dividas: "Suas dívidas, uma a uma" },
      pendencias_acionaveis: [
        {
          DIVIDA_ID: "D001",
          nome_divida: "Cheque especial — CAIXA",
          rotulo: "a taxa de juros",
          onde_achar: "No app do banco",
          ID_PERGUNTA: "B5.D01",
        },
      ],
      ordem: [
        {
          posicao: 1,
          indice: 1,
          total: 1,
          DIVIDA_ID: "D001",
          nome: "Cheque especial — CAIXA",
          explicacao: "É a dívida que mais destrava o seu orçamento agora.",
          valores_de_apoio: [],
          fatos: [{ rotulo: "Quanto você deve hoje", valor: "R$ 662,28" }],
          mes_de_quitacao: 4,
        },
      ],
    },
    estado_inputs: {
      campos: [],
      perfil_comportamental: [],
      sinais_comportamentais: [],
      dividas: [
        {
          DIVIDA_ID: "D001",
          nome: "Cheque especial — CAIXA",
          campos: [
            {
              nome: "Taxa de juros ao mês",
              valor: "8%",
              codigo: "TAXA_EFETIVA_MENSAL_NORMALIZADA",
            },
          ],
        },
      ],
    },
  } as unknown as CasoParaRevisao;

  it("mostra o plano do aluno: a seção das dívidas, os números e a explicação", async () => {
    montar({ classificacoes_erro: [], pendencias_homologacao: [] }, comPlano);

    const plano = await screen.findByRole("region", {
      name: "Como o aluno vai ver",
    });
    expect(plano).toHaveTextContent("Suas dívidas, uma a uma");
    expect(plano).toHaveTextContent("Quanto você deve hoje");
    expect(plano).toHaveTextContent("R$ 662,28");
    expect(plano).toHaveTextContent(
      "É a dívida que mais destrava o seu orçamento agora.",
    );
  });

  it('o que é só do aluno não aparece: nem "Baixar em PDF" nem "Responder agora"', async () => {
    montar({ classificacoes_erro: [], pendencias_homologacao: [] }, comPlano);
    await screen.findByRole("region", { name: "Como o aluno vai ver" });

    expect(
      screen.queryByRole("link", { name: "Baixar em PDF" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Responder agora")).not.toBeInTheDocument();
    // A pendência em si continua legível para o revisor.
    expect(
      screen.getByText(/falta informar a taxa de juros/),
    ).toBeInTheDocument();
  });

  it("a prévia do PDF é um link para a rota do revisor", async () => {
    montar({ classificacoes_erro: [], pendencias_homologacao: [] }, comPlano);

    const link = await screen.findByRole("link", {
      name: /Abrir prévia do PDF/,
    });
    expect(link).toHaveAttribute("href", "/revisao/caso/CASO-1/plano/pdf");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it('cada dívida traz "Para o revisor" com os dados DELA, e sem a justificativa técnica (AC-191)', async () => {
    montar(
      { classificacoes_erro: [], pendencias_homologacao: [] },
      {
        ...comPlano,
        plano: {
          ...comPlano.plano,
          ordem: comPlano.plano.ordem.map((p) => ({
            ...p,
            JUSTIFICATIVA_POSICAO: "JUSTIFICATIVA-TECNICA",
          })),
        },
      },
    );

    const plano = await screen.findByRole("region", {
      name: "Como o aluno vai ver",
    });
    const secao = within(plano).getByText("Para o revisor").closest("details");
    expect(secao).not.toBeNull();
    expect(secao).toHaveTextContent("Taxa de juros ao mês");
    expect(secao).toHaveTextContent("8%");
    expect(screen.queryByText(/JUSTIFICATIVA-TECNICA/)).not.toBeInTheDocument();
  });
});

describe("TelaEquipeCaso — o que mudou desde a versão anterior (T-348, RF-123, AC-192)", () => {
  it("versão 1 (sem comparação): o cartão não existe", async () => {
    montar(
      { classificacoes_erro: [], pendencias_homologacao: [] },
      { ...CASO, mudancas: null },
    );
    await screen.findByRole("region", { name: "Como o aluno vai ver" });

    expect(
      screen.queryByText("O que mudou desde a versão anterior"),
    ).not.toBeInTheDocument();
  });

  it("versão 2: cada mudança com campo, valor anterior e atual; novo e removido marcados", async () => {
    montar(
      { classificacoes_erro: [], pendencias_homologacao: [] },
      {
        ...CASO,
        mudancas: [
          {
            secao: "Cheque especial — CAIXA",
            nome: "Taxa de juros ao mês",
            de: "4%",
            para: "8%",
            situacao: "alterado",
          },
          {
            secao: "Dados gerais",
            nome: "Despesas do mês",
            de: null,
            para: "R$ 4.085,05",
            situacao: "novo",
          },
          {
            secao: "Dados gerais",
            nome: "Campo antigo",
            de: "R$ 1,00",
            para: null,
            situacao: "removido",
          },
        ],
      },
    );

    const cartao = await screen.findByRole("region", {
      name: "O que mudou desde a versão anterior",
    });
    expect(cartao).toHaveTextContent("Taxa de juros ao mês");
    expect(cartao).toHaveTextContent("4% → 8%");
    expect(cartao).toHaveTextContent("Despesas do mês");
    expect(within(cartao).getByText("novo")).toBeInTheDocument();
    expect(within(cartao).getByText("removido")).toBeInTheDocument();
  });

  it("versão 2 sem nenhuma diferença: diz que nada mudou", async () => {
    montar(
      { classificacoes_erro: [], pendencias_homologacao: [] },
      { ...CASO, mudancas: [] },
    );

    expect(
      await screen.findByText(
        "Nada mudou nos dados de entrada desde a versão anterior.",
      ),
    ).toBeInTheDocument();
  });
});
