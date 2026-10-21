import { apiFetch } from "./client";

export type InvitacionOut = {
  link_autoregistro: string;
  mensaje_whatsapp_invitacion: string;
};

export function obtenerInvitacion(): Promise<InvitacionOut> {
  return apiFetch<InvitacionOut>("/api/v1/invitacion/");
}
