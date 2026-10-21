import { Drawer } from "expo-router/drawer";

import { colores } from "@/theme/colores";

export default function VecinoLayout() {
  return (
    <Drawer
      screenOptions={{
        headerStyle: { backgroundColor: colores.primary },
        headerTintColor: "#fff",
        drawerActiveTintColor: colores.primary,
      }}
    >
      <Drawer.Screen name="index" options={{ title: "Mi Barrio+" }} />
    </Drawer>
  );
}
