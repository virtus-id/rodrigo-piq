// @vitest-environment happy-dom
/**
 * `TelaCalculando` — `T-196` (o POST que dispara o Bloco 6) e `T-197` (a
 * recusa chega ao aluno). `fetch` é dublado inteiro, não `api.ts`: assim o
 * teste cobre também `pedir` lendo `mensagem`/`pendencias` do corpo.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import TelaCalculando from "../../../src/telas/TelaCalculando";

const CASO = "CASO-1";

/** Sem navegação: os testes que não a exercitam não precisam dela. */
const semNavegar = () => undefined;

function resposta(status: number, corpo: object): Response {
  return { ok: status < 400, status, json: async () => corpo } as Response;
}

/** Dubla `fetch`: o POST responde `post`; o GET de progresso, `calculando`. */
function dublarFetch(post: Response, calculando = true) {
  const chamadas: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push(`${init?.method ?? "GET"} ${url}`);
      if (init?.method === "POST") return post;
      return resposta(200, { CASO_ID: CASO, estado: "CALCULANDO", calculando });
    }),
  );
  return chamadas;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("TelaCalculando", () => {
  it("faz exatamente um POST de cálculo antes do primeiro GET de progresso", async () => {
    const chamadas = dublarFetch(
      resposta(200, { CASO_ID: CASO, calculando: true }),
    );
    render(
      <TelaCalculando
        casoId={CASO}
        voltar={() => undefined}
        onTerminou={() => undefined}
        onAbrirPergunta={semNavegar}
      />,
    );

    await waitFor(() =>
      expect(chamadas).toContain(`GET /caso/${CASO}/calculo/progresso`),
    );
    expect(chamadas[0]).toBe(`POST /caso/${CASO}/calculo`);
    expect(chamadas.filter((c) => c.startsWith("POST"))).toHaveLength(1);
  });

  it("409 (caso já calculando) segue para o polling sem mensagem de erro", async () => {
    const chamadas = dublarFetch(
      resposta(409, { mensagem: "Caso não está pronto para calcular." }),
    );
    render(
      <TelaCalculando
        casoId={CASO}
        voltar={() => undefined}
        onTerminou={() => undefined}
        onAbrirPergunta={semNavegar}
      />,
    );

    await waitFor(() =>
      expect(chamadas).toContain(`GET /caso/${CASO}/calculo/progresso`),
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it.each([400, 422])(
    "recusa %i mostra o enunciado das pendências, nunca só o ID, e não volta ao Início",
    async (status) => {
      const chamadas = dublarFetch(
        resposta(status, {
          mensagem: "Algumas respostas precisam de revisão.",
          pendencias: [
            {
              ID: "B5.03",
              item_id: "D001",
              enunciado: "Quanto você deve na D001?",
            },
          ],
        }),
        false,
      );
      const onTerminou = vi.fn();
      render(
        <TelaCalculando
          casoId={CASO}
          voltar={() => undefined}
          onTerminou={onTerminou}
          onAbrirPergunta={semNavegar}
        />,
      );

      const alerta = await screen.findByRole("alert");
      expect(alerta.textContent).toContain(
        "Algumas respostas precisam de revisão.",
      );
      expect(alerta.textContent).toContain("Quanto você deve na D001?");
      expect(alerta.textContent).not.toContain("B5.03");
      expect(chamadas.some((c) => c.startsWith("GET"))).toBe(false);
      expect(onTerminou).not.toHaveBeenCalled();
    },
  );

  it('"Responder" abre a pergunta certa com o item certo (T-210)', async () => {
    dublarFetch(
      resposta(400, {
        mensagem: "Há perguntas obrigatórias pendentes.",
        pendencias: [
          { ID: "B1.01", item_id: null, enunciado: "Qual é o seu nome?" },
          { ID: "B5.03", item_id: "D002", enunciado: "Quanto você deve?" },
        ],
      }),
      false,
    );
    const onAbrirPergunta = vi.fn();
    const usuario = userEvent.setup();
    render(
      <TelaCalculando
        casoId={CASO}
        voltar={() => undefined}
        onTerminou={() => undefined}
        onAbrirPergunta={onAbrirPergunta}
      />,
    );

    const botoes = await screen.findAllByRole("button", { name: /Responder/ });
    await usuario.click(botoes[1]);
    expect(onAbrirPergunta).toHaveBeenCalledWith("B5.03", "D002");
    await usuario.click(botoes[0]);
    expect(onAbrirPergunta).toHaveBeenLastCalledWith("B1.01", null);
  });
});
