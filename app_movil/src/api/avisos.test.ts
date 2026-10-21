jest.mock("./client");

import { listarAvisos, marcarLeido, crearAviso } from "./avisos";
import { apiFetch } from "./client";

afterEach(() => {
  jest.restoreAllMocks();
});

test("listarAvisos pide /api/v1/avisos/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue([]);
  await listarAvisos();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/avisos/");
});

test("marcarLeido pega al endpoint correcto", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 1 });
  await marcarLeido(1);
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/avisos/1/marcar_leido/", { method: "POST" });
});

test("crearAviso manda titulo y cuerpo", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 2 });
  await crearAviso({ titulo: "Corte de agua", cuerpo: "Mañana 9-12h" });
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/avisos/", {
    method: "POST",
    body: JSON.stringify({ titulo: "Corte de agua", cuerpo: "Mañana 9-12h" }),
  });
});
