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

import { Platform } from "react-native";
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

describe("en Expo for Web", () => {
  // expo-secure-store no soporta Web -- ahí se usa localStorage, camino
  // sin cubrir hasta ahora (la app sí se despliega para Web, ver
  // app.json "web": {"output": "server"}).
  const osOriginal = Platform.OS;

  beforeEach(() => {
    Object.defineProperty(Platform, "OS", { value: "web", configurable: true });
    (globalThis as any).localStorage = {
      almacen: new Map<string, string>(),
      getItem(clave: string) {
        return this.almacen.get(clave) ?? null;
      },
      setItem(clave: string, valor: string) {
        this.almacen.set(clave, valor);
      },
      removeItem(clave: string) {
        this.almacen.delete(clave);
      },
    };
  });

  afterEach(() => {
    Object.defineProperty(Platform, "OS", { value: osOriginal, configurable: true });
    delete (globalThis as any).localStorage;
  });

  test("guarda y devuelve los tokens vía localStorage", async () => {
    await guardarTokens("acc-web", "ref-web");
    expect(await obtenerTokens()).toEqual({ access: "acc-web", refresh: "ref-web" });
  });

  test("borrarTokens limpia localStorage", async () => {
    await guardarTokens("acc-web", "ref-web");
    await borrarTokens();
    expect(await obtenerTokens()).toBeNull();
  });
});
