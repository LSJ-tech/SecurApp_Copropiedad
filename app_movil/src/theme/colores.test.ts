import { colores } from "./colores";

test("usa los hex exactos de brand.css", () => {
  // objectContaining, no toEqual exacto: el sistema visual de la app
  // móvil (2026-10-25) agregó tokens propios (peligro/apoyo/fondo*) que
  // no vienen de brand.css -- fuera de alcance a propósito (ver el spec
  // de ese trabajo, "cambiar nada de la web"). Esto sigue garantizando
  // que los 6 colores de marca compartidos no se desvíen.
  expect(colores).toEqual(
    expect.objectContaining({
      primary: "#102D46",
      primaryDark: "#284E6B",
      primaryDarker: "#0A1B2A",
      secondary: "#708090",
      accent: "#0D9488",
      slate: "#5B7A8C",
    })
  );
});
