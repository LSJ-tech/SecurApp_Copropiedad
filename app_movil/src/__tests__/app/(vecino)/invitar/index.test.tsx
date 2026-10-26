import { Share } from "react-native";
import { render, fireEvent, screen } from "@testing-library/react-native";
import InvitarScreen from "@/app/(vecino)/invitar/index";
import * as invitacionApi from "@/api/invitacion";
import { ErrorDeRed } from "@/api/client";
import { colores } from "@/theme/colores";

afterEach(() => jest.restoreAllMocks());

test("al tocar Compartir, abre la hoja de compartir nativa con el mensaje", async () => {
  jest.spyOn(invitacionApi, "obtenerInvitacion").mockResolvedValue({
    link_autoregistro: "https://x/registro/abc",
    mensaje_whatsapp_invitacion: "Te invito a...",
  });
  const shareSpy = jest.spyOn(Share, "share").mockResolvedValue({ action: Share.sharedAction } as any);
  await render(<InvitarScreen />);
  await screen.findByText(/compartir/i);
  await fireEvent.press(screen.getByText(/compartir/i));
  expect(shareSpy).toHaveBeenCalledWith({ message: "Te invito a..." });
});

test("si Share.share rechaza (ej. cancelado), no rompe la pantalla", async () => {
  jest.spyOn(invitacionApi, "obtenerInvitacion").mockResolvedValue({
    link_autoregistro: "https://x",
    mensaje_whatsapp_invitacion: "Te invito a...",
  });
  jest.spyOn(Share, "share").mockRejectedValue(new Error("cancelado"));
  await render(<InvitarScreen />);
  await fireEvent.press(await screen.findByText(/compartir/i));
  await screen.findByText(/compartir/i);
});

test("si falla obtener la invitacion, muestra un error", async () => {
  jest.spyOn(invitacionApi, "obtenerInvitacion").mockRejectedValue(new ErrorDeRed("sin red"));
  await render(<InvitarScreen />);
  await screen.findByText(/no se pudo cargar la invitación/i);
});

test("la tarjeta principal usa el color de fondo de apoyo", async () => {
  jest.spyOn(invitacionApi, "obtenerInvitacion").mockResolvedValue({
    link_autoregistro: "https://x", mensaje_whatsapp_invitacion: "Te invito a...",
  });
  await render(<InvitarScreen />);
  const tarjeta = await screen.findByTestId("tarjeta-invitar");
  expect(tarjeta.props.style).toEqual(
    expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoApoyo })])
  );
});
