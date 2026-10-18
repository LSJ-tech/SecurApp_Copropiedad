"""Genera los PNG de icono/favicon y la tarjeta OG de Mi Barrio+ a partir
del mismo mark (pin + casa + 3 personas) que core/static/core/logo.svg,
dibujado con primitivas de Pillow (sin agregar una dependencia nueva de
rasterizado de SVG). Se corre una sola vez en forma local; los PNG
resultantes se commitean como estáticos, este script no corre en
producción. Uso: venv/Scripts/python.exe scripts/generar_iconos_mibarrio.py
"""
import pathlib

from PIL import Image, ImageDraw, ImageFont

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ESTATICOS = RAIZ / "core" / "static" / "core"

NAVY = (16, 45, 70, 255)
NAVY_CLARO = (40, 78, 107, 255)
TEAL = (13, 148, 136, 255)
BLANCO = (255, 255, 255, 255)


def dibujar_mark(draw, escala, offset_x=0.0, offset_y=0.0):
    """Dibuja el pin+casa+personas sobre un lienzo ya cuadrado, en
    coordenadas relativas 0-100 (mismo sistema que logo.svg), escaladas
    por `escala` px por unidad y desplazadas por offset_x/offset_y
    unidades (para centrar el mark dentro de la zona segura maskable)."""
    p = lambda x, y: ((x + offset_x) * escala, (y + offset_y) * escala)

    # Pin: círculo + triángulo inferior, mismo color sólido -> sin costura visible.
    draw.ellipse([p(29, 14), p(71, 56)], fill=BLANCO)
    draw.polygon([p(34, 50), p(66, 50), p(50, 68)], fill=BLANCO)

    # Casa (recorte navy sobre el pin blanco): techo con alero ancho +
    # cuerpo rectangular más alto, para que se lea como casa y no como
    # una flecha. Puerta: rectángulo blanco sobre la base de la casa.
    draw.polygon(
        [p(50, 18), p(68, 32), p(62, 32), p(62, 50), p(38, 50), p(38, 32), p(32, 32)],
        fill=NAVY,
    )
    draw.rectangle([p(46, 40), p(54, 50)], fill=BLANCO)

    # Tres personas (comunidad) en turquesa, bajo el pin.
    personas = [
        (32, 76, 7, [(24, 85), (40, 85), (46, 97), (18, 97)]),
        (68, 76, 7, [(60, 85), (76, 85), (82, 97), (54, 97)]),
        (50, 72, 8, [(39, 82), (61, 82), (67, 97), (33, 97)]),
    ]
    for cx, cy, r, cuerpo in personas:
        draw.ellipse([p(cx - r, cy - r), p(cx + r, cy + r)], fill=TEAL)
        draw.polygon([p(x, y) for x, y in cuerpo], fill=TEAL)


def generar_icono(nombre, tamano, maskable=False):
    img = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if maskable:
        # Full-bleed, sin esquinas redondeadas (el SO recorta su propia
        # máscara) -- el mark se reduce y se centra para quedar dentro de
        # la "zona segura" maskable (círculo central ~80% del lienzo).
        draw.rectangle([0, 0, tamano, tamano], fill=NAVY)
        escala = tamano / 100 * 0.72
        offset_x = (tamano / escala - 100) / 2
        offset_y = (tamano / escala - 97) / 2
        dibujar_mark(draw, escala, offset_x, offset_y)
    else:
        radio = round(tamano * 0.24)
        draw.rounded_rectangle([0, 0, tamano, tamano], radius=radio, fill=NAVY)
        escala = tamano / 100
        dibujar_mark(draw, escala)
    destino = ESTATICOS / nombre
    img.convert("RGBA").save(destino)
    print(f"  {destino.relative_to(RAIZ)} ({tamano}x{tamano})")


def generar_og():
    ancho, alto = 1200, 630
    img = Image.new("RGB", (ancho, alto), NAVY[:3])
    draw = ImageDraw.Draw(img)
    # Banda diagonal más clara, simple degradado de dos tonos (sin libs extra).
    for x in range(ancho):
        t = x / ancho
        r = round(NAVY[0] + (NAVY_CLARO[0] - NAVY[0]) * t * 0.5)
        g = round(NAVY[1] + (NAVY_CLARO[1] - NAVY[1]) * t * 0.5)
        b = round(NAVY[2] + (NAVY_CLARO[2] - NAVY[2]) * t * 0.5)
        draw.line([(x, 0), (x, alto)], fill=(r, g, b))

    # Mark grande a la izquierda.
    lado_mark = 340
    mark = Image.new("RGBA", (lado_mark, lado_mark), (0, 0, 0, 0))
    mdraw = ImageDraw.Draw(mark)
    radio = round(lado_mark * 0.24)
    mdraw.rounded_rectangle([0, 0, lado_mark, lado_mark], radius=radio, fill=NAVY)
    dibujar_mark(mdraw, lado_mark / 100)
    img.paste(mark, (90, (alto - lado_mark) // 2), mark)

    # Wordmark + eslogan a la derecha.
    fuente_titulo = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 92)
    fuente_sub = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 36)
    x_texto = 90 + lado_mark + 70
    draw.text((x_texto, 250), "Mi Barrio+", font=fuente_titulo, fill=BLANCO[:3])
    draw.text((x_texto, 360), "Más conectados. Más seguros.", font=fuente_sub, fill=(167, 211, 204))

    destino = ESTATICOS / "img" / "og-mibarrio.jpg"
    img.convert("RGB").save(destino, quality=90)
    print(f"  {destino.relative_to(RAIZ)} ({ancho}x{alto})")


def main():
    print("Generando logo.svg ya existente (sin tocar) + íconos PNG derivados:")
    generar_icono("favicon-16.png", 16)
    generar_icono("favicon-32.png", 32)
    generar_icono("apple-touch-icon.png", 180)
    generar_icono("icon-192.png", 192)
    generar_icono("icon-512.png", 512)
    generar_icono("icon-512-maskable.png", 512, maskable=True)
    generar_og()
    print("Listo.")


if __name__ == "__main__":
    main()
