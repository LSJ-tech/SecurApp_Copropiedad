import { useEffect, useRef } from "react";
import { Platform } from "react-native";
import * as Notifications from "expo-notifications";
import { Stack, useRouter, useSegments } from "expo-router";

import { AuthProvider, useAuth } from "@/auth/AuthContext";
import { configurarManejadorDeNotificaciones, obtenerAlertaIdDeNotificacionFria } from "@/notificaciones/push";

function GuardDeRutas() {
  const { estado } = useAuth();
  const router = useRouter();
  const segmentos = useSegments();

  useEffect(() => {
    if (estado === "cargando") return;
    const enLogin = segmentos[0] === "login";
    const enElegirCondominio = segmentos[0] === "elegir-condominio";
    const enAdmin = segmentos[0] === "(admin)";

    if (estado === "sin_sesion" && !enLogin) {
      router.replace("/login");
    } else if (estado === "devquad_sin_condominio" && !enElegirCondominio) {
      router.replace("/elegir-condominio");
    } else if (estado === "devquad_con_condominio" && !enAdmin) {
      // (admin)/ no tiene index.tsx propio -- colisionaría con
      // (vecino)/index.tsx en la ruta "/" (verificado en la Tarea 2 de
      // la Tanda 3). "Mi condominio" hace de landing del modo
      // administrador.
      router.replace("/condominio");
    } else if (estado === "autenticado" && (enLogin || enElegirCondominio || enAdmin)) {
      router.replace("/");
    }
  }, [estado, segmentos, router]);

  // Tocar la notificación de una alerta lleva directo a su detalle.
  // Acotado a celular -- Expo for Web no integra push (ver notificaciones/push.ts).
  useEffect(() => {
    if (Platform.OS === "web") return;
    const suscripcion = Notifications.addNotificationResponseReceivedListener((respuesta) => {
      const alertaId = respuesta.notification.request.content.data?.alerta_id;
      if (typeof alertaId === "number") router.push(`/alertas/${alertaId}`);
    });
    return () => suscripcion.remove();
  }, [router]);

  // Hallazgo I7 de la revisión final: con la app cerrada (el caso más
  // común en una emergencia real), el listener de arriba no alcanza --
  // hay que preguntar explícitamente si la app se abrió tocando una
  // notificación. Una sola vez por sesión de la app (la ref evita que
  // un segundo render, ej. al cambiar de estado de auth, repita la
  // navegación).
  const yaRevisoNotificacionFria = useRef(false);
  useEffect(() => {
    if (Platform.OS === "web" || estado !== "autenticado" || yaRevisoNotificacionFria.current) return;
    yaRevisoNotificacionFria.current = true;
    const alertaId = obtenerAlertaIdDeNotificacionFria();
    if (alertaId) router.push(`/alertas/${alertaId}`);
  }, [estado, router]);

  return <Stack screenOptions={{ headerShown: false }} />;
}

export default function RootLayout() {
  useEffect(() => {
    configurarManejadorDeNotificaciones();
  }, []);

  return (
    <AuthProvider>
      <GuardDeRutas />
    </AuthProvider>
  );
}
