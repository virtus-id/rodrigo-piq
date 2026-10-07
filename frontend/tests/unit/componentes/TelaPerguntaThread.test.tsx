// @vitest-environment happy-dom
/**
 * `TelaPergunta` — a thread de perguntas complementares (`RF-99`, `AC-157`,
 * T-307).
 *
 * As filhas vêm do servidor em `complementares[valor_interno]`; a tela só as
 * desenha sob a opção escolhida e grava a mãe antes delas.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import TelaPergunta from "../../../src/telas/TelaPergunta";
import * as api from "../../../src/services/api";
import type {
  ConfirmacaoDeResposta,
  Pergunta,
  TipoResposta,
} from "../../../src/tipos";

function fabricar(
  ID: string,
  tipo: TipoResposta,
  extra: Partial<Pergunta> = {},
): Pergunta {
  return {
    CASO_ID: "CASO-1",
    ID,
    bloco: 3,
    tipo,
    enunciado: `Pergunta ${ID}`,
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

const mae = fabricar("M1", "SELECAO_UNICA", {
  opcoes: [
    { rotulo: "Fixa", valor_interno: "FIXA", admite_nao_sei: false },
    { rotulo: "Variável", valor_interno: "VARIAVEL", admite_nao_sei: false },
  ],
  complementares: {
    VARIAVEL: [fabricar("F1", "TEXTO_CURTO"), fabricar("F2", "TEXTO_CURTO")],
  },
});

function confirmacao(proxima: Pergunta | null): ConfirmacaoDeResposta {
  return {
    ID_PERGUNTA: "M1",
    aviso: null,
    avanco_permitido: false,
    total_pendencias: 1,
    proxima: { pergunta: proxima, coleta_completa: proxima === null },
    abrir_fichas: [],
    avisos: [],
  };
}

function abrir() {
  vi.spyOn(api, "obterProximaPergunta").mockResolvedValue({ pergunta: mae });
  render(<TelaPergunta casoId="CASO-1" onColetaCompleta={vi.fn()} />);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("T-307: thread de complementares", () => {
  it("a opção que abre mostra as filhas abaixo; trocar de opção as esconde", async () => {
    abrir();
    await userEvent.click(await screen.findByRole("radio", { name: "Fixa" }));
    expect(
      screen.queryByRole("group", { name: /abertas pela sua resposta/ }),
    ).toBeNull();

    await userEvent.click(screen.getByRole("radio", { name: "Variável" }));
    const thread = screen.getByRole("group", {
      name: /abertas pela sua resposta/,
    });
    expect(thread).toHaveTextContent("Pergunta F1");
    expect(thread).toHaveTextContent("Pergunta F2");

    await userEvent.click(screen.getByRole("radio", { name: "Fixa" }));
    expect(screen.queryByLabelText("Pergunta F1")).toBeNull();
  });

  it("grava a mãe primeiro e as filhas depois, e segue com a última confirmação", async () => {
    const seguinte = fabricar("Q9", "TEXTO_CURTO");
    const gravar = vi
      .spyOn(api, "gravarResposta")
      .mockResolvedValueOnce(confirmacao(fabricar("F1", "TEXTO_CURTO")))
      .mockResolvedValueOnce(confirmacao(fabricar("F2", "TEXTO_CURTO")))
      .mockResolvedValueOnce(confirmacao(seguinte));
    abrir();
    await userEvent.click(
      await screen.findByRole("radio", { name: "Variável" }),
    );
    await userEvent.type(screen.getByLabelText("Pergunta F1"), "a");
    await userEvent.type(screen.getByLabelText("Pergunta F2"), "b");
    await userEvent.click(screen.getByRole("button", { name: "Continuar" }));

    await screen.findByLabelText("Pergunta Q9");
    expect(
      gravar.mock.calls.map(([, entrada]) => [
        entrada.idPergunta,
        entrada.valor,
      ]),
    ).toEqual([
      ["M1", "VARIAVEL"],
      ["F1", "a"],
      ["F2", "b"],
    ]);
  });

  it("opção que não abre nada não envia filha nenhuma", async () => {
    const gravar = vi
      .spyOn(api, "gravarResposta")
      .mockResolvedValue(confirmacao(fabricar("Q9", "TEXTO_CURTO")));
    abrir();
    await userEvent.click(
      await screen.findByRole("radio", { name: "Variável" }),
    );
    await userEvent.type(screen.getByLabelText("Pergunta F1"), "a");
    await userEvent.click(screen.getByRole("radio", { name: "Fixa" }));
    await userEvent.click(screen.getByRole("button", { name: "Continuar" }));

    await screen.findByLabelText("Pergunta Q9");
    expect(gravar).toHaveBeenCalledTimes(1);
  });

  it("filha recusada mostra o erro junto dela e a tela não avança", async () => {
    vi.spyOn(api, "gravarResposta")
      .mockResolvedValueOnce(confirmacao(fabricar("F1", "TEXTO_CURTO")))
      .mockRejectedValueOnce(new Error("Resposta não aceita: entrada vazia."));
    abrir();
    await userEvent.click(
      await screen.findByRole("radio", { name: "Variável" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Continuar" }));

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("entrada vazia");
    expect(alerta.parentElement).toHaveTextContent("Pergunta F1");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Continuar" })).toBeEnabled(),
    );
    expect(screen.getByRole("radio", { name: "Variável" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });
});
