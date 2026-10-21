import { StyleSheet, Text, View } from "react-native";

import { colores } from "@/theme/colores";

export default function HomeScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.titulo}>Mi Barrio+</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colores.primary,
  },
  titulo: {
    color: "#fff",
    fontSize: 24,
    fontWeight: "600",
  },
});
