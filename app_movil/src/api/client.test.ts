import { apiFetch } from "./client";
import * as storage from "../auth/storage";

afterEach(() => {
  jest.restoreAllMocks();
});

test("adjunta el Authorization header con el access token guardado", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "acc1", refresh: "ref1" });
  global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ ok: true }) }) as any;
  await apiFetch("/api/v1/auth/me/");
  expect(global.fetch).toHaveBeenCalledWith(
    expect.stringContaining("/api/v1/auth/me/"),
    expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer acc1" }) })
  );
});

test("ante un 401, refresca una vez y reintenta la request original", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "vencido", refresh: "ref1" });
  const guardarSpy = jest.spyOn(storage, "guardarTokens").mockResolvedValue();
  global.fetch = jest
    .fn()
    .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) })
    .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ access: "nuevo" }) })
    .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ ok: true }) }) as any;
  const resultado = await apiFetch("/api/v1/auth/me/");
  expect(resultado).toEqual({ ok: true });
  expect(guardarSpy).toHaveBeenCalledWith("nuevo", "ref1");
  expect(global.fetch).toHaveBeenCalledTimes(3);
});

test("si el refresh también falla, borra los tokens y lanza sesionExpirada", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "vencido", refresh: "vencido" });
  const borrarSpy = jest.spyOn(storage, "borrarTokens").mockResolvedValue();
  global.fetch = jest
    .fn()
    .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) })
    .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) }) as any;
  await expect(apiFetch("/api/v1/auth/me/")).rejects.toMatchObject({ sesionExpirada: true });
  expect(borrarSpy).toHaveBeenCalled();
});

test("con requiereAuth=false, no adjunta Authorization ni reintenta ante un 401", async () => {
  const obtenerSpy = jest.spyOn(storage, "obtenerTokens");
  global.fetch = jest
    .fn()
    .mockResolvedValue({ ok: false, status: 401, json: async () => ({ detail: "credenciales invalidas" }) }) as any;
  await expect(apiFetch("/api/v1/auth/login/", { method: "POST" }, false)).rejects.toBeDefined();
  expect(obtenerSpy).not.toHaveBeenCalled();
  expect(global.fetch).toHaveBeenCalledTimes(1);
});
