// @vitest-environment happy-dom
/**
 * `T-342` (`RF-118`) — com plano liberado e o caso de volta à coleta, o plano
 * atual continua à vista e a tela diz por quê.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import TelaInicio from "../../../src/telas/TelaInicio";
import * as api from "../../../src/services/api";
import type { Inicio } from "../../../src/tipos";

afterEach(() => {
  vi.restoreAllMocks();
});

function inicio(extra: Partial<Inicio>): Inicio {
  return {
    CASO_ID: "CASO-1",
    estado: "COLETA_INICIAL",
    fase: "coleta",
    mensagem: "Sua coleta está em andamento.",
    proxima_etapa: { destino: "calculando", ID_PERGUNTA: null, item_id: null },
    progresso: { respondidas: 337, total: 337 },
    valor_em_destaque: null,
    plano_liberado: true,
    versao_do_plano: 1,
    correcao_pedida: null,
    ...extra,
  } as Inicio;
}

const renderizar = (i: Inicio, irPara = vi.fn()) => {
  render(
    <TelaInicio inicio={i} irPara={irPara} eRevisor={false} aoSair={vi.fn()} />,
  );
  return irPara;
};

const LIBERADO = {
  estado: "PLANO_LIBERADO",
  fase: "acompanhamento",
  mensagem: "Seu plano está liberado.",
  proxima_etapa: { destino: "acoes", ID_PERGUNTA: null, item_id: null },
  pode_refazer_plano: true,
} as const;

describe("Início — plano novo depois da liberação", () => {
  it('em coleta COM plano liberado: "Ver meu plano" continua e a nota explica', () => {
    renderizar(inicio({}));

    expect(
      screen.getByRole("button", { name: "Ver meu plano" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Seu plano atual continua disponível."),
    ).toBeInTheDocument();
  });

  it("primeira coleta (sem plano liberado): nada disso aparece", () => {
    renderizar(inicio({ plano_liberado: false, versao_do_plano: null }));

    expect(
      screen.queryByRole("button", { name: "Ver meu plano" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Seu plano atual continua disponível."),
    ).not.toBeInTheDocument();
  });
});

describe('Início — "Gerar um novo plano" (RF-120, AC-186)', () => {
  it("respostas atualizadas: o aviso diz o que aconteceu e oferece o plano novo", () => {
    renderizar(inicio({ ...LIBERADO, respostas_atualizadas: true }));

    expect(
      screen.getByText("Você atualizou suas respostas depois do seu plano."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Quer enviá-las para gerar um novo plano?"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "Gerar um novo plano com as minhas respostas",
      }),
    ).toBeInTheDocument();
  });

  it.each([false, null])(
    "respostas_atualizadas = %s: a ação existe, sem afirmar mudança",
    (v) => {
      renderizar(inicio({ ...LIBERADO, respostas_atualizadas: v }));

      expect(
        screen.getByText("Mudou algo? Você pode pedir um plano novo."),
      ).toBeInTheDocument();
      expect(
        screen.queryByText(
          "Você atualizou suas respostas depois do seu plano.",
        ),
      ).not.toBeInTheDocument();
      expect(
        screen.getByRole("button", {
          name: "Gerar um novo plano com as minhas respostas",
        }),
      ).toBeInTheDocument();
    },
  );

  it("confirmar pede o plano ao servidor e vai ao cálculo", async () => {
    const refazer = vi
      .spyOn(api, "refazerPlano")
      .mockResolvedValue({ estado: "COLETA_INICIAL" });
    const irPara = renderizar(
      inicio({ ...LIBERADO, respostas_atualizadas: true }),
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Gerar um novo plano com as minhas respostas",
      }),
    );
    const texto =
      screen.getByRole("group", { name: "Confirmar o plano novo" })
        .textContent ?? "";
    expect(texto).toContain("conferido de novo pela equipe");
    expect(texto).toContain("tempo da fila");
    expect(refazer).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Pedir o plano novo" }));

    await vi.waitFor(() =>
      expect(irPara).toHaveBeenCalledWith({ tela: "calculando" }),
    );
    expect(refazer).toHaveBeenCalledWith("CASO-1");
  });

  it("sem o campo do servidor (plano ainda não liberado) nada disso aparece", () => {
    renderizar(inicio({ plano_liberado: false, versao_do_plano: null }));

    expect(
      screen.queryByRole("button", {
        name: "Gerar um novo plano com as minhas respostas",
      }),
    ).not.toBeInTheDocument();
  });
});

describe('Início — "Quero editar minhas respostas" em conferência (AC-187)', () => {
  const EM_CONFERENCIA = {
    estado: "AGUARDANDO_REVISAO",
    fase: "revisao",
    mensagem: "Seu plano está em revisão.",
    proxima_etapa: { destino: "aguardando", ID_PERGUNTA: null, item_id: null },
    plano_liberado: false,
    versao_do_plano: null,
    pode_retomar_edicao: true,
  } as const;

  it('oferece a retirada, confirma e leva a "Minhas respostas"', async () => {
    const retomar = vi
      .spyOn(api, "retomarEdicao")
      .mockResolvedValue({ estado: "COLETA_INICIAL" });
    const irPara = renderizar(inicio(EM_CONFERENCIA));

    fireEvent.click(
      screen.getByRole("button", { name: "Quero editar minhas respostas" }),
    );
    expect(
      screen.getByText(
        "Seu plano sai da conferência. Quando você enviar de novo, ele volta para a fila.",
      ),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Retirar o plano e editar" }),
    );

    await vi.waitFor(() =>
      expect(irPara).toHaveBeenCalledWith({ tela: "respostas" }),
    );
    expect(retomar).toHaveBeenCalledWith("CASO-1");
  });

  it("fora da conferência a ação não existe", () => {
    renderizar(inicio({}));
    expect(
      screen.queryByRole("button", { name: "Quero editar minhas respostas" }),
    ).not.toBeInTheDocument();
  });
});
