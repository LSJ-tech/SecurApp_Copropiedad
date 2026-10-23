import { ErrorDeServidor } from "./client";
import { mensajeDetalleDeError, primerMensajeDeError } from "./erroresFormulario";

describe("primerMensajeDeError", () => {
  test("devuelve el primer mensaje de un error de validación de formulario", () => {
    const error = new ErrorDeServidor(400, { email: ["Ya existe una cuenta con ese correo."] });
    expect(primerMensajeDeError(error)).toBe("Ya existe una cuenta con ese correo.");
  });

  test("devuelve un mensaje genérico si no es el shape esperado", () => {
    expect(primerMensajeDeError(new Error("otra cosa"))).toBe("No se pudo guardar. Probá de nuevo.");
  });
});

describe("mensajeDetalleDeError", () => {
  // Hallazgo al ejecutar el plan de la Tanda 4: los endpoints nuevos de
  // pagos/api_views.py devuelven {"detail": "..."} (un string, no
  // {campo: [mensajes]} de un form de Django) -- primerMensajeDeError no
  // lo reconoce y cae siempre al mensaje genérico. Se necesita un
  // extractor aparte para este shape, que ya usan varios endpoints de
  // core/api_views.py (LogoutView, DevquadEntrarCondominioApiView, etc.).
  test("devuelve error.body.detail cuando existe", () => {
    const error = new ErrorDeServidor(400, { detail: "Agrega tu email en «Mi perfil»." });
    expect(mensajeDetalleDeError(error, "default")).toBe("Agrega tu email en «Mi perfil».");
  });

  test("devuelve el mensaje por defecto si no hay detail", () => {
    expect(mensajeDetalleDeError(new Error("otra cosa"), "default")).toBe("default");
  });
});
