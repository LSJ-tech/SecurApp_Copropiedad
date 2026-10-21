import { useEffect } from "react";
import { Platform } from "react-native";
import * as Notifications from "expo-notifications";
import { Stack, useRouter, useSegments } from "expo-router";

import { AuthProvider, useAuth } from "@/auth/AuthContext";

function GuardDeRutas() {
  const { estado } = useAuth();
  const router = useRouter();
  const segmentos = useSegments();

  useEffect(() => {
    if (estado === "cargando") return;
    const enLogin = segmentos[0] === "login";
    const enSinMembresia = segmentos[0] === "sin-membresia";

    if (estado === "sin_sesion" && !enLogin) {
      router.replace("/login");
    } else if (estado === "sin_membresia" && !enSinMembresia) {
      router.replace("/sin-membresia");
    } else if (estado === "autenticado" && (enLogin || enSinMembresia)) {
      router.replace("/");
    }
  }, [estado, segmentos, router]);

  // Tocar la notificación de una alerta lleva directo a su detalle.
  // Acotado a celular -- Expo for Web no integra push (ver notificaciones/push.ts).
  useEffect(() => {
    if (Platform.OS === "web") return;
    const suscripcion = Notifications.addNotificationResponseReceivedListener((respuesta) => {
      const alertaId = respuesta.notification.request.content.data?.alerta_id;
      if (alertaId) router.push(`/alertas/${alertaId}`);
    });
    return () => suscripcion.remove();
  }, [router]);

  return <Stack screenOptions={{ headerShown: false }} />;
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <GuardDeRutas />
    </AuthProvider>
  );
}
