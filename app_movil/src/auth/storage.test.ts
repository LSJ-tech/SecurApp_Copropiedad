jest.mock("expo-secure-store", () => {
  const almacen = new Map<string, string>();
  return {
    getItemAsync: jest.fn(async (clave: string) => almacen.get(clave) ?? null),
    setItemAsync: jest.fn(async (clave: string, valor: string) => {
      almacen.set(clave, valor);
    }),
    deleteItemAsync: jest.fn(async (clave: string) => {
      almacen.delete(clave);
    }),
  };
});

import { guardarTokens, obtenerTokens, borrarTokens } from "./storage";

test("guarda y devuelve los tokens", async () => {
  await guardarTokens("acc1", "ref1");
  expect(await obtenerTokens()).toEqual({ access: "acc1", refresh: "ref1" });
});

test("borrarTokens limpia el almacenamiento", async () => {
  await guardarTokens("acc1", "ref1");
  await borrarTokens();
  expect(await obtenerTokens()).toBeNull();
});
