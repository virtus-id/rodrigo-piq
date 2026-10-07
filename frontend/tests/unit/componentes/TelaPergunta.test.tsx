// @vitest-environment happy-dom
/**
 * `TelaPergunta` — o valor salvo reabre marcado (`AC-102`, T-204) e o
 * localizador diz o que o número conta (`AC-96`, T-206).
 *
 * `happy-dom`, não `jsdom` — mesma nota de `CampoPergunta.test.tsx`.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import TelaPergunta from "../../../src/telas/TelaPergunta";
import * as api from "../../../src/services/api";
import type { Pergunta, TipoResposta } from "../../../src/tipos";

function fabricar(tipo: TipoResposta, extra: Partial<Pergunta> = {}): Pergunta {
  return {
    CASO_ID: "CASO-1",
    ID: "Q1",
    bloco: 3,
    tipo,
    enunciado: `Campo de teste ${tipo}`,
    opcoes: [],
    escopo_repeticao: "NENHUM",
    item_id: null,
    posicao: null,
    total_na_ficha: null,
    admite_nao_sei: false,
    valor_atual: null,
    respondida_como_nao_sei: false,
    valores_marcados: [],
    aviso: null,
    ...extra,
  };
}

function abrir(pergunta: Pergunta, totalPendencias = 0) {
  vi.spyOn(api, "obterProximaPergunta").mockResolvedValue({
    pergunta,
    total_pendencias: totalPendencias,
  });
  render(<TelaPergunta casoId="CASO-1" onColetaCompleta={vi.fn()} />);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("T-204: valor numérico salvo reabre preenchido", () => {
  it("ESCALA_0_10 com `valor_atual: 7` (int do servidor) marca o 7", async () => {
    // O servidor serializa como `int`; o tipo diz string, o dado não.
    abrir(fabricar("ESCALA_0_10", { valor_atual: 7 as unknown as string }));

    expect(await screen.findByRole("radio", { name: "7" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("NUMERO com `valor_atual: 3` mostra 3 no campo", async () => {
    abrir(fabricar("NUMERO", { valor_atual: 3 as unknown as string }));

    expect(await screen.findByLabelText(/Campo de teste NUMERO/)).toHaveValue(
      "3",
    );
  });
});

describe("T-294: opção com campo R$ reabre com o valor", () => {
  it("`valor_do_campo` do servidor volta ao campo, com a opção marcada", async () => {
    abrir(
      fabricar("SELECAO_UNICA", {
        opcoes: [
          {
            rotulo: "Sim.",
            valor_interno: "CONFIRMADA",
            admite_nao_sei: false,
            abre_campo: "MOEDA",
          },
        ],
        valor_atual: "CONFIRMADA",
        valor_do_campo: "1500.00",
      }),
    );

    expect(await screen.findByLabelText("Valor em R$")).toHaveValue("1500.00");
    expect(screen.getByRole("radio", { name: "Sim." })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });
});

describe("T-206: rótulo das pendências", () => {
  it("fora de ficha, o total não é atribuído ao bloco", async () => {
    abrir(fabricar("TEXTO_CURTO"), 28);

    await screen.findByLabelText(/Campo de teste TEXTO_CURTO/);
    // A contagem é a do servidor, intacta; só o rótulo diz o que ela é.
    expect(
      screen.getByText(/Bloco 3 · no total, 28 obrigatórias restantes/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Bloco 3 · 28/)).not.toBeInTheDocument();
  });

  it("singular quando resta uma", async () => {
    abrir(fabricar("TEXTO_CURTO"), 1);

    expect(
      await screen.findByText(/1 obrigatória restante\b/),
    ).toBeInTheDocument();
  });
});

describe("T-212: resposta que abre ficha", () => {
  function responderCom(abrirFichas: string[]) {
    vi.spyOn(api, "gravarResposta").mockResolvedValue({
      ID_PERGUNTA: "Q1",
      aviso: null,
      avanco_permitido: false,
      total_pendencias: 1,
      proxima: {
        pergunta: fabricar("TEXTO_CURTO", { ID: "Q2" }),
        coleta_completa: false,
      },
      abrir_fichas: abrirFichas,
    });
    vi.spyOn(api, "obterProximaPergunta").mockResolvedValue({
      pergunta: fabricar("TEXTO_CURTO"),
    });
    const onAbrirFichas = vi.fn();
    render(
      <TelaPergunta
        casoId="CASO-1"
        onColetaCompleta={vi.fn()}
        onAbrirFichas={onAbrirFichas}
      />,
    );
    return onAbrirFichas;
  }

  async function gravar() {
    await userEvent.type(await screen.findByLabelText(/Campo de teste/), "x");
    await userEvent.click(screen.getByRole("button", { name: "Continuar" }));
  }

  it("navega para as fichas que o servidor apontou", async () => {
    const onAbrirFichas = responderCom(["VINCULO_ID", "MARGEM_ID"]);

    await gravar();

    await waitFor(() =>
      expect(onAbrirFichas).toHaveBeenCalledWith(["VINCULO_ID", "MARGEM_ID"]),
    );
  });

  it("sem ficha apontada segue para a próxima pergunta", async () => {
    const onAbrirFichas = responderCom([]);

    await gravar();

    await waitFor(() => expect(api.gravarResposta).toHaveBeenCalled());
    expect(onAbrirFichas).not.toHaveBeenCalled();
  });
});

describe("T-240: aviso na gravação", () => {
  const AVISO = "O desconto em reais não bate com o percentual informado.";

  function responderComAviso(
    avisos: { codigo: string; mensagem: string; ID_PERGUNTA: string }[],
  ) {
    vi.spyOn(api, "gravarResposta").mockResolvedValue({
      ID_PERGUNTA: "Q1",
      aviso: null,
      avanco_permitido: false,
      total_pendencias: 1,
      proxima: {
        pergunta: fabricar("TEXTO_CURTO", {
          ID: "Q2",
          enunciado: "Pergunta seguinte",
        }),
        coleta_completa: false,
      },
      abrir_fichas: [],
      avisos,
    });
    vi.spyOn(api, "obterProximaPergunta").mockResolvedValue({
      pergunta: fabricar("TEXTO_CURTO"),
    });
    render(<TelaPergunta casoId="CASO-1" onColetaCompleta={vi.fn()} />);
  }

  it('anuncia o aviso ligado ao campo e só segue no próximo "Continuar", sem regravar', async () => {
    responderComAviso([
      { codigo: "DIVERGENCIA_DESCONTO", mensagem: AVISO, ID_PERGUNTA: "Q1" },
    ]);

    const campo = await screen.findByLabelText(/Campo de teste TEXTO_CURTO/);
    await userEvent.type(campo, "x");
    await userEvent.click(screen.getByRole("button", { name: "Continuar" }));

    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent(AVISO);
    expect(
      screen.getByLabelText(/Campo de teste TEXTO_CURTO/),
    ).toHaveAccessibleDescription(AVISO);

    await userEvent.click(screen.getByRole("button", { name: "Continuar" }));

    expect(
      await screen.findByLabelText(/Pergunta seguinte/),
    ).toBeInTheDocument();
    expect(api.gravarResposta).toHaveBeenCalledTimes(1);
  });

  it("sem aviso (`avisos: []`), segue direto como antes", async () => {
    responderComAviso([]);

    await userEvent.type(
      await screen.findByLabelText(/Campo de teste TEXTO_CURTO/),
      "x",
    );
    await userEvent.click(screen.getByRole("button", { name: "Continuar" }));

    expect(
      await screen.findByLabelText(/Pergunta seguinte/),
    ).toBeInTheDocument();
  });
});

describe("T-308/T-309/T-310: topo, anterior e trilha vêm do servidor", () => {
  it('"‹ Início" na coleta e "‹ Voltar" na correção', async () => {
    vi.spyOn(api, "obterProximaPergunta").mockResolvedValue({
      pergunta: fabricar("TEXTO_CURTO"),
      total_pendencias: 0,
    });
    const { unmount } = render(
      <TelaPergunta
        casoId="CASO-1"
        voltar={vi.fn()}
        onColetaCompleta={vi.fn()}
      />,
    );
    expect(
      await screen.findByRole("button", { name: "‹ Início" }),
    ).toBeInTheDocument();
    unmount();

    vi.spyOn(api, "obterPergunta").mockResolvedValue({
      pergunta: fabricar("TEXTO_CURTO"),
      total_pendencias: 0,
    });
    render(
      <TelaPergunta
        casoId="CASO-1"
        voltar={vi.fn()}
        onColetaCompleta={vi.fn()}
        idPergunta="Q1"
        aoCorrigir={vi.fn()}
      />,
    );
    expect(
      await screen.findByRole("button", { name: "‹ Voltar" }),
    ).toBeInTheDocument();
  });

  it('"‹ Pergunta anterior" abre exatamente a que o servidor nomeia, com o item', async () => {
    const abrirPergunta = vi.fn();
    const respostas = vi.spyOn(api, "obterRespostasDoCaso");
    vi.spyOn(api, "obterProximaPergunta").mockResolvedValue({
      pergunta: fabricar("TEXTO_CURTO", {
        anterior: { ID: "B3.05D", item_id: "EXT001" },
      }),
      total_pendencias: 0,
    });
    render(
      <TelaPergunta
        casoId="CASO-1"
        onColetaCompleta={vi.fn()}
        abrirPergunta={abrirPergunta}
      />,
    );

    await userEvent.click(
      await screen.findByRole("button", { name: "‹ Pergunta anterior" }),
    );

    expect(abrirPergunta).toHaveBeenCalledWith("B3.05D", "EXT001");
    // A ordem não é mais remontada de `/respostas` no cliente.
    expect(respostas).not.toHaveBeenCalled();
  });

  it("sem `anterior` não há botão", async () => {
    vi.spyOn(api, "obterProximaPergunta").mockResolvedValue({
      pergunta: fabricar("TEXTO_CURTO", { anterior: null }),
      total_pendencias: 0,
    });
    render(
      <TelaPergunta
        casoId="CASO-1"
        onColetaCompleta={vi.fn()}
        abrirPergunta={vi.fn()}
      />,
    );

    await screen.findByText(/Campo de teste/, { selector: "label, legend" });
    expect(
      screen.queryByRole("button", { name: /Pergunta anterior/ }),
    ).not.toBeInTheDocument();
  });

  it("a trilha marca a parte atual e a barra conta partes concluídas", async () => {
    abrir(
      fabricar("TEXTO_CURTO", {
        trilha: [
          { numero: 1, rotulo: "Seu compromisso", estado: "concluida" },
          {
            numero: 2,
            rotulo: "Como você controla os gastos",
            estado: "atual",
          },
          {
            numero: 3,
            rotulo: "O que entra e o que sai por mês",
            estado: "proxima",
          },
        ],
      }),
    );

    const barra = await screen.findByRole("progressbar", {
      name: "Progresso da coleta",
    });
    expect(barra).toHaveAttribute("aria-valuenow", "1");
    expect(barra).toHaveAttribute("aria-valuemax", "3");
    expect(document.querySelector('[aria-current="step"]')).toHaveTextContent(
      "Como você controla os gastos",
    );
    expect(screen.getByText(/Parte 2 de 3/)).toBeInTheDocument();
  });
});

describe('T-318: "Pergunta seguinte ›" depois de voltar', () => {
  function abrirComSeguinte(abrirPergunta = vi.fn()) {
    const gravar = vi.spyOn(api, "gravarResposta");
    vi.spyOn(api, "obterProximaPergunta").mockResolvedValue({
      pergunta: fabricar("TEXTO_CURTO", {
        valor_atual: "já respondida",
        seguinte: { ID: "B3.05BF", item_id: "EXT001" },
      }),
      total_pendencias: 0,
    });
    render(
      <TelaPergunta
        casoId="CASO-1"
        onColetaCompleta={vi.fn()}
        abrirPergunta={abrirPergunta}
      />,
    );
    return { abrirPergunta, gravar };
  }

  it("sem alteração só navega, com o item, sem regravar", async () => {
    const { abrirPergunta, gravar } = abrirComSeguinte();

    await userEvent.click(
      await screen.findByRole("button", { name: "Pergunta seguinte ›" }),
    );

    expect(abrirPergunta).toHaveBeenCalledWith("B3.05BF", "EXT001");
    expect(gravar).not.toHaveBeenCalled();
  });

  it("com alteração não salva, pergunta antes de descartar", async () => {
    // `happy-dom` não implementa `confirm`.
    const confirmar = vi.fn().mockReturnValue(false);
    vi.stubGlobal("confirm", confirmar);
    const { abrirPergunta, gravar } = abrirComSeguinte();

    await userEvent.type(
      await screen.findByLabelText(/Campo de teste/),
      " e mudada",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Pergunta seguinte ›" }),
    );
    expect(confirmar).toHaveBeenCalled();
    expect(abrirPergunta).not.toHaveBeenCalled();

    confirmar.mockReturnValue(true);
    await userEvent.click(
      screen.getByRole("button", { name: "Pergunta seguinte ›" }),
    );
    expect(abrirPergunta).toHaveBeenCalledWith("B3.05BF", "EXT001");
    expect(gravar).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("na fronteira (`seguinte: null`) não há botão", async () => {
    vi.spyOn(api, "obterProximaPergunta").mockResolvedValue({
      pergunta: fabricar("TEXTO_CURTO", { seguinte: null }),
      total_pendencias: 0,
    });
    render(
      <TelaPergunta
        casoId="CASO-1"
        onColetaCompleta={vi.fn()}
        abrirPergunta={vi.fn()}
      />,
    );

    await screen.findByText(/Campo de teste/, { selector: "label, legend" });
    expect(
      screen.queryByRole("button", { name: /Pergunta seguinte/ }),
    ).not.toBeInTheDocument();
  });
});
