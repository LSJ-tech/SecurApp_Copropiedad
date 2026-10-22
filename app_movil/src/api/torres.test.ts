jest.mock("./client");

import { listarTorres, crearTorre } from "./torres";
import { apiFetch } from "./client";

afterEach(() => {
  jest.restoreAllMocks();
});

test("listarTorres pide /api/v1/torres/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue([]);
  await listarTorres();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/torres/");
});

test("crearTorre manda el nombre", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 1, nombre: "A" });
  await crearTorre("A");
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/torres/", { method: "POST", body: JSON.stringify({ nombre: "A" }) });
});
