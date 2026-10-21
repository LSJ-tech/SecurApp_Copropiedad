import { apiFetch, alSesionExpirada, ErrorDeRed, ErrorDeServidor } from "./client";
import * as storage from "../auth/storage";

afterEach(() => {
  jest.restoreAllMocks();
  alSesionExpirada(null);
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

test("ante un 401, refresca una vez y reintenta la request original -- guardando el refresh NUEVO (rotación)", async () => {
  // El backend tiene ROTATE_REFRESH_TOKENS=True + BLACKLIST_AFTER_ROTATION=True
  // (config/settings.py) -- /auth/refresh/ invalida el refresh usado y
  // devuelve uno nuevo. Guardar el viejo (en vez del que vino en esta
  // respuesta) deja la sesión muerta en el próximo refresh.
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "vencido", refresh: "ref-viejo" });
  const guardarSpy = jest.spyOn(storage, "guardarTokens").mockResolvedValue();
  global.fetch = jest
    .fn()
    .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) })
    .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ access: "nuevo", refresh: "ref-nuevo" }) })
    .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ ok: true }) }) as any;
  const resultado = await apiFetch("/api/v1/auth/me/");
  expect(resultado).toEqual({ ok: true });
  expect(guardarSpy).toHaveBeenCalledWith("nuevo", "ref-nuevo");
  expect(global.fetch).toHaveBeenCalledTimes(3);
});

test("dos requests en paralelo que reciben 401 solo refrescan una vez (single-flight)", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "vencido", refresh: "ref-viejo" });
  jest.spyOn(storage, "guardarTokens").mockResolvedValue();
  let llamadasDeRefresh = 0;
  global.fetch = jest.fn((url: string) => {
    if (url.includes("/auth/refresh/")) {
      llamadasDeRefresh += 1;
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ access: "nuevo", refresh: "ref-nuevo" }) });
    }
    return Promise.resolve({ ok: false, status: 401, json: async () => ({}) });
  }) as any;
  // La segunda respuesta (tras el refresh) siempre dice 401 en este mock
  // simplificado -- lo único que importa es que /auth/refresh/ se haya
  // llamado una sola vez para ambas requests en vuelo.
  await Promise.allSettled([apiFetch("/api/v1/a/"), apiFetch("/api/v1/b/")]);
  expect(llamadasDeRefresh).toBe(1);
});

test("si el refresh también falla, borra los tokens, lanza sesionExpirada y avisa al listener registrado", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "vencido", refresh: "vencido" });
  const borrarSpy = jest.spyOn(storage, "borrarTokens").mockResolvedValue();
  const listener = jest.fn();
  alSesionExpirada(listener);
  global.fetch = jest
    .fn()
    .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) })
    .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) }) as any;
  await expect(apiFetch("/api/v1/auth/me/")).rejects.toMatchObject({ sesionExpirada: true });
  expect(borrarSpy).toHaveBeenCalled();
  expect(listener).toHaveBeenCalled();
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

test("si el servidor responde con un error (4xx/5xx), lanza ErrorDeServidor -- no es un fallo transitorio de red", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "acc1", refresh: "ref1" });
  global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 400, json: async () => ({}) }) as any;
  await expect(apiFetch("/api/v1/alertas/")).rejects.toBeInstanceOf(ErrorDeServidor);
});

test("si fetch() mismo rechaza (sin red), lanza ErrorDeRed -- ese sí es transitorio", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "acc1", refresh: "ref1" });
  global.fetch = jest.fn().mockRejectedValue(new TypeError("Network request failed")) as any;
  await expect(apiFetch("/api/v1/alertas/")).rejects.toBeInstanceOf(ErrorDeRed);
});

test("si la request se cuelga más de 8s, se cancela y se trata como ErrorDeRed", async () => {
  jest.useFakeTimers();
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "acc1", refresh: "ref1" });
  global.fetch = jest.fn((_url: string, opciones: RequestInit) => {
    return new Promise((_resolve, reject) => {
      (opciones.signal as AbortSignal).addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    });
  }) as any;
  const promesa = expect(apiFetch("/api/v1/alertas/")).rejects.toBeInstanceOf(ErrorDeRed);
  await jest.advanceTimersByTimeAsync(8000);
  await promesa;
  jest.useRealTimers();
});

test("ErrorDeServidor carga el cuerpo de la respuesta (para mostrar mensajes de validación reales)", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "acc1", refresh: "ref1" });
  global.fetch = jest.fn().mockResolvedValue({
    ok: false,
    status: 400,
    json: async () => ({ email: ["Ya existe otra cuenta con ese correo."] }),
  }) as any;
  try {
    await apiFetch("/api/v1/auth/me/", { method: "PATCH" });
    throw new Error("no debería llegar acá");
  } catch (error) {
    expect(error).toBeInstanceOf(ErrorDeServidor);
    expect((error as ErrorDeServidor).body).toEqual({ email: ["Ya existe otra cuenta con ese correo."] });
  }
});
