import { colores } from "./colores";

test("usa los hex exactos de brand.css", () => {
  expect(colores).toEqual({
    primary: "#102D46",
    primaryDark: "#284E6B",
    primaryDarker: "#0A1B2A",
    secondary: "#708090",
    accent: "#0D9488",
    slate: "#5B7A8C",
  });
});
