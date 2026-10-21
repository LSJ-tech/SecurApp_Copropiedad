import { useEffect } from "react";
import { Drawer } from "expo-router/drawer";

import { iniciarProcesamientoAutomatico } from "@/alertas/colaEnvio";
import { useAuth } from "@/auth/AuthContext";
import { colores } from "@/theme/colores";

export default function VecinoLayout() {
  const { membresia } = useAuth();

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
      }}
    >
      <Drawer.Screen name="index" options={{ title: "Mi Barrio+" }} />
      <Drawer.Screen name="alertas/index" options={{ title: "Alertas" }} />
      <Drawer.Screen name="avisos/index" options={{ title: "Avisos" }} />
      <Drawer.Screen name="perfil/index" options={{ title: "Mi perfil" }} />
      <Drawer.Screen
        name="directorio/index"
        options={{
          title: "Directorio",
          drawerItemStyle: membresia?.rol !== "delegado" ? { display: "none" } : undefined,
        }}
      />
      <Drawer.Screen
        name="alertas/[id]"
        options={{ title: "Detalle de alerta", drawerItemStyle: { display: "none" } }}
      />
    </Drawer>
  );
}
