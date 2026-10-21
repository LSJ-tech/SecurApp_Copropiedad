jest.mock("@/auth/AuthContext", () => ({ useAuth: () => ({ membresia: { rol: "residente" } }) }));

import { render, screen } from "@testing-library/react-native";
import ListaAvisosScreen from "@/app/(vecino)/avisos/index";
import * as avisosApi from "@/api/avisos";
import { ErrorDeRed } from "@/api/client";

afterEach(() => jest.restoreAllMocks());

test("al listar, marca cada aviso como leido de forma pasiva (mismo comportamiento que la web)", async () => {
  jest.spyOn(avisosApi, "listarAvisos").mockResolvedValue([
    {
      id: 1,
      titulo: "A",
      cuerpo: "...",
      fecha_creacion: "2026-01-01T00:00:00Z",
      autor_nombre: null,
      torre_nombre: null,
      leido_por_count: null,
      total_destinatarios: null,
    },
  ]);
  const marcarSpy = jest.spyOn(avisosApi, "marcarLeido").mockResolvedValue({} as any);
  await render(<ListaAvisosScreen />);
  await screen.findByText("A");
  expect(marcarSpy).toHaveBeenCalledWith(1);
});

test("un residente (no delegado) no ve el formulario de crear aviso", async () => {
  jest.spyOn(avisosApi, "listarAvisos").mockResolvedValue([]);
  await render(<ListaAvisosScreen />);
  expect(screen.queryByText(/publicar aviso/i)).toBeNull();
});

test("si falla la carga, muestra un error en vez de un rechazo sin manejar", async () => {
  jest.spyOn(avisosApi, "listarAvisos").mockRejectedValue(new ErrorDeRed("sin red"));
  await render(<ListaAvisosScreen />);
  await screen.findByText(/no se pudieron cargar los avisos/i);
});
