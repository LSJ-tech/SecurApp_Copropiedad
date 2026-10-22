import { useEffect, useState } from "react";
import { FlatList, Modal, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { crearMiembro, listarMiembros, CrearMiembroResultado, Miembro } from "@/api/miembros";
import { listarUnidades, Unidad } from "@/api/unidades";
import { primerMensajeDeError } from "@/api/erroresFormulario";
import { colores } from "@/theme/colores";

const ROLES: { valor: "residente" | "delegado"; etiqueta: string }[] = [
  { valor: "residente", etiqueta: "Residente" },
  { valor: "delegado", etiqueta: "Delegado" },
];

export default function MiembrosScreen() {
  const [miembros, setMiembros] = useState<Miembro[]>([]);
  const [unidades, setUnidades] = useState<Unidad[]>([]);
  const [nombre, setNombre] = useState("");
  const [apellido, setApellido] = useState("");
  const [email, setEmail] = useState("");
  const [rol, setRol] = useState<"residente" | "delegado">("residente");
  const [unidadElegida, setUnidadElegida] = useState<Unidad | null>(null);
  const [selectorAbierto, setSelectorAbierto] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Separado de la lista a propósito -- es la ÚNICA vez que la
  // contraseña es visible, no puede depender de que listarMiembros()
  // se vuelva a cargar con éxito después (Review Focus de la Tanda 3).
  const [credencialesNuevas, setCredencialesNuevas] = useState<CrearMiembroResultado | null>(null);

  useEffect(() => {
    listarMiembros()
      .then(setMiembros)
      .catch(() => setError("No se pudieron cargar los miembros."));
    listarUnidades().then(setUnidades).catch(() => {});
  }, []);

  async function manejarCrear() {
    setError(null);
    try {
      const resultado = await crearMiembro({
        nombre,
        apellido,
        email,
        rol,
        ...(unidadElegida ? { unidad: unidadElegida.id } : {}),
      });
      setCredencialesNuevas(resultado);
      setNombre("");
      setApellido("");
      setEmail("");
      setUnidadElegida(null);
    } catch (error) {
      setError(primerMensajeDeError(error));
    }
  }

  return (
    <View style={styles.container}>
      {error && <Text style={styles.error}>{error}</Text>}

      {credencialesNuevas && (
        <View style={styles.credenciales}>
          <Text style={styles.credencialesTitulo}>Cuenta creada</Text>
          <Text>Usuario: {credencialesNuevas.username}</Text>
          <Text>Contraseña: {credencialesNuevas.password_temporal}</Text>
        </View>
      )}

      <View style={styles.formulario}>
        <TextInput style={styles.input} placeholder="Nombre" value={nombre} onChangeText={setNombre} />
        <TextInput style={styles.input} placeholder="Apellido" value={apellido} onChangeText={setApellido} />
        <TextInput
          style={styles.input}
          placeholder="Correo"
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
        />
        <View style={styles.roles}>
          {ROLES.map((item) => (
            <Pressable
              key={item.valor}
              style={[styles.rolBoton, rol === item.valor && styles.rolBotonActivo]}
              onPress={() => setRol(item.valor)}
            >
              <Text style={rol === item.valor ? styles.rolTextoActivo : undefined}>{item.etiqueta}</Text>
            </Pressable>
          ))}
        </View>
        <Pressable style={styles.selector} onPress={() => setSelectorAbierto(true)}>
          <Text>{unidadElegida?.numero ?? "Sin unidad"}</Text>
        </Pressable>
        <Pressable style={styles.boton} onPress={manejarCrear}>
          <Text style={styles.botonTexto}>Crear miembro</Text>
        </Pressable>
      </View>

      <Modal visible={selectorAbierto} transparent animationType="fade" onRequestClose={() => setSelectorAbierto(false)}>
        <Pressable style={styles.fondo} onPress={() => setSelectorAbierto(false)}>
          <View style={styles.lista}>
            <FlatList
              data={unidades}
              keyExtractor={(u) => String(u.id)}
              renderItem={({ item }) => (
                <Pressable
                  style={styles.opcion}
                  onPress={() => {
                    setUnidadElegida(item);
                    setSelectorAbierto(false);
                  }}
                >
                  <Text>{item.numero}</Text>
                </Pressable>
              )}
            />
          </View>
        </Pressable>
      </Modal>

      <FlatList
        data={miembros}
        keyExtractor={(m) => String(m.id)}
        renderItem={({ item }) => (
          <View style={styles.fila}>
            <Text>{item.nombre}</Text>
            <Text style={styles.filaSub}>{item.rol_display}</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  formulario: { gap: 8, marginBottom: 16 },
  input: { borderWidth: 1, borderColor: colores.slate, borderRadius: 8, padding: 12 },
  selector: { borderWidth: 1, borderColor: colores.slate, borderRadius: 8, padding: 12 },
  roles: { flexDirection: "row", gap: 8 },
  rolBoton: { borderWidth: 1, borderColor: colores.slate, borderRadius: 8, padding: 10, flex: 1, alignItems: "center" },
  rolBotonActivo: { backgroundColor: colores.primary, borderColor: colores.primary },
  rolTextoActivo: { color: "#fff" },
  boton: { backgroundColor: colores.primary, borderRadius: 8, padding: 12, alignItems: "center" },
  botonTexto: { color: "#fff", fontWeight: "600" },
  fila: { padding: 12, borderBottomWidth: 1, borderBottomColor: "#eee" },
  filaSub: { color: colores.slate, fontSize: 12 },
  error: { color: "#b00020", textAlign: "center", marginBottom: 8 },
  credenciales: { backgroundColor: "#eef7f5", borderRadius: 8, padding: 12, marginBottom: 16 },
  credencialesTitulo: { fontWeight: "700", color: colores.primary, marginBottom: 4 },
  fondo: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "center", padding: 24 },
  lista: { backgroundColor: "#fff", borderRadius: 12, maxHeight: "60%" },
  opcion: { padding: 16, borderBottomWidth: 1, borderBottomColor: "#eee" },
});
