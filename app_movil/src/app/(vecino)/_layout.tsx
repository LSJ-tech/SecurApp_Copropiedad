import { useCallback, useEffect } from "react";
import { Pressable, Text } from "react-native";
import { Drawer } from "expo-router/drawer";

import { iniciarProcesamientoAutomatico } from "@/alertas/colaEnvio";
import { useAuth } from "@/auth/AuthContext";
import { colores } from "@/theme/colores";

function BotonCerrarSesion({ onCerrar }: Readonly<{ onCerrar: () => void }>) {
  return (
    <Pressable testID="boton-cerrar-sesion" onPress={onCerrar} style={{ marginRight: 16 }}>
      <Text style={{ color: "#fff", fontWeight: "600" }}>Cerrar sesión</Text>
    </Pressable>
  );
}

export default function VecinoLayout() {
  const { membresia, cerrarSesion } = useAuth();
  const headerRight = useCallback(() => <BotonCerrarSesion onCerrar={cerrarSesion} />, [cerrarSesion]);

  useEffect(() => {
    // Solo mientras hay sesión de residente (este layout no renderiza
    // si no) -- una alerta encolada le pertenece a quien la mandó
    // (hallazgo C1 de la revisión final: antes nada llamaba nunca a
    // procesarCola() en producción).
    return iniciarProcesamientoAutomatico();
  }, []);

  return (
    <Drawer
      screenOptions={{
        headerStyle: { backgroundColor: colores.primary },
        headerTintColor: "#fff",
        drawerActiveTintColor: colores.primary,
        // Igual criterio que (admin)/_layout.tsx: una acción de cuenta
        // (no una ruta real) vive en el header, no como ítem de Drawer
        // -- Expo Router solo acepta Drawer.Screen para rutas que
        // existen de verdad como archivo. Hallazgo real probando en el
        // emulador (2026-10-26): el residente no tenía NINGUNA forma de
        // cerrar sesión, a diferencia del modo administrador.
        headerRight,
      }}
    >
      <Drawer.Screen name="index" options={{ title: "Mi Barrio+" }} />
      <Drawer.Screen name="alertas/index" options={{ title: "Alertas" }} />
      <Drawer.Screen name="numeros-emergencia/index" options={{ title: "Números de emergencia" }} />
      <Drawer.Screen name="avisos/index" options={{ title: "Avisos" }} />
      <Drawer.Screen name="perfil/index" options={{ title: "Mi perfil" }} />
      <Drawer.Screen
        name="directorio/index"
        options={{
          title: "Directorio",
          drawerItemStyle: membresia?.rol !== "delegado" ? { display: "none" } : undefined,
        }}
      />
      <Drawer.Screen name="invitar/index" options={{ title: "Invitar vecinos" }} />
      <Drawer.Screen name="donar/index" options={{ title: "Donar" }} />
      <Drawer.Screen
        name="alertas/[id]"
        options={{ title: "Detalle de alerta", drawerItemStyle: { display: "none" } }}
      />
    </Drawer>
  );
}
