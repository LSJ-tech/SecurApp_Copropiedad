jest.mock("./client");

import { obtenerInvitacion } from "./invitacion";
import { apiFetch } from "./client";

afterEach(() => {
  jest.restoreAllMocks();
});

test("obtenerInvitacion pide /api/v1/invitacion/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({
    link_autoregistro: "https://...",
    mensaje_whatsapp_invitacion: "...",
  });
  await obtenerInvitacion();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/invitacion/");
});
