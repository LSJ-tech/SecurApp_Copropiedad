import { TIPOS_ALERTA } from "./tipos";
import { ICONO_POR_TIPO } from "./iconosTipo";

test("todo tipo de TIPOS_ALERTA tiene un ícono de Ionicons asignado", () => {
  for (const tipo of TIPOS_ALERTA) {
    expect(ICONO_POR_TIPO[tipo.valor]).toBeDefined();
  }
});
