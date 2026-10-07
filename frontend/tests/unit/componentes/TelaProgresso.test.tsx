// @vitest-environment happy-dom
/**
 * `TelaProgresso` — segundo caminho para as fichas do Bloco 3 (`T-212`).
 *
 * Quem diz se o escopo está aberto é o servidor (`GET /escopos`, `RF-52`);
 * a tela só oferece os abertos que ela sabe nomear.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import TelaProgresso from "../../../src/telas/TelaProgresso";
import * as api from "../../../src/services/api";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TelaProgresso — fichas por escopo aberto", () => {
  it("oferece só os escopos abertos, despesas inclusive (T-217)", async () => {
    vi.spyOn(api, "listarEscopos").mockResolvedValue({
      CASO_ID: "CASO-1",
      escopos: [
        { escopo: "DIVIDA_ID", aberto: true },
        { escopo: "ITEM_DESPESA", aberto: true },
        { escopo: "MARGEM_ID", aberto: false },
        { escopo: "RENDA_ADICIONAL_ID", aberto: true },
      ],
    });
    const verFichas = vi.fn();
    render(
      <TelaProgresso
        casoId="CASO-1"
        inicio={null}
        voltar={vi.fn()}
        continuar={vi.fn()}
        verFichas={verFichas}
      />,
    );

    await userEvent.click(
      await screen.findByRole("button", {
        name: "Ver e editar: rendas adicionais",
      }),
    );

    expect(verFichas).toHaveBeenCalledWith("RENDA_ADICIONAL_ID");
    expect(
      screen.getByRole("button", { name: "Ver e editar minhas dívidas" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /margens/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Ver e editar: despesas" }),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: /Ver e editar/ }),
    ).toHaveLength(3);
  });
});
