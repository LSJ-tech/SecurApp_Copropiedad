import { Pressable, Text } from "react-native";
import { Drawer } from "expo-router/drawer";

import { useAuth } from "@/auth/AuthContext";
import { colores } from "@/theme/colores";

function BotonCambiarCondominio({ onCambiar }: Readonly<{ onCambiar: () => void }>) {
  return (
    <Pressable onPress={onCambiar} style={{ marginRight: 16 }}>
      <Text style={{ color: "#fff", fontWeight: "600" }}>Cambiar</Text>
    </Pressable>
  );
}

export default function AdminLayout() {
  const { condominioActivo, volverAElegirCondominio } = useAuth();

  return (
    <Drawer
      screenOptions={{
        headerShown: true,
        headerTitle: condominioActivo?.nombre ?? "Modo administrador",
        headerStyle: { backgroundColor: colores.primary },
        headerTintColor: "#fff",
        drawerActiveTintColor: colores.primary,
        // "Cambiar condominio" vive en el header, no como un ítem más
        // del Drawer -- Expo Router solo acepta Drawer.Screen para
        // rutas que existen de verdad como archivo (D-07 tampoco exige
        // que esté en el menú, solo que el modo administrador no
        // comparta navegación con el drawer del vecino).
        headerRight: () => <BotonCambiarCondominio onCambiar={volverAElegirCondominio} />,
      }}
    >
      <Drawer.Screen name="condominio/index" options={{ title: "Mi condominio" }} />
      <Drawer.Screen name="torres/index" options={{ title: "Torres" }} />
      <Drawer.Screen name="unidades/index" options={{ title: "Unidades" }} />
      <Drawer.Screen name="miembros/index" options={{ title: "Miembros" }} />
    </Drawer>
  );
}
