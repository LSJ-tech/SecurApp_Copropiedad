jest.mock("./client");

import { listarDirectorio } from "./directorio";
import { apiFetch } from "./client";

afterEach(() => {
  jest.restoreAllMocks();
});

test("listarDirectorio pide /api/v1/directorio/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue([]);
  await listarDirectorio();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/directorio/");
});
