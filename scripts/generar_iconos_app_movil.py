"""Genera los íconos de Mi Barrio+ para app_movil/ -- mismo mark (pin +
casa + 3 personas) que ya usa la web (core/static/core/logo.svg), reusa
dibujar_mark() de generar_iconos_mibarrio.py en vez de duplicarlo.

El icon.png/favicon/splash que trae app_movil por defecto son los de la
plantilla de Expo (el chevron azul genérico) -- nunca se habían
reemplazado por el logo real. Uso:
    venv/Scripts/python.exe scripts/generar_iconos_app_movil.py
"""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

from PIL import Image, ImageDraw  # noqa: E402

from generar_iconos_mibarrio import dibujar_mark, NAVY, BLANCO  # noqa: E402

ASSETS = RAIZ / "app_movil" / "assets" / "images"


def icono_app(tamano=1024):
    """icon.png -- fallback para iOS y para donde Android no use el
    ícono adaptativo. Full-bleed, sin esquinas pre-redondeadas: cada SO
    aplica su propia máscara."""
    img = Image.new("RGBA", (tamano, tamano), NAVY)
    draw = ImageDraw.Draw(img)
    dibujar_mark(draw, tamano / 100)
    destino = ASSETS / "icon.png"
    img.save(destino)
    print(f"  {destino.relative_to(RAIZ)} ({tamano}x{tamano})")


def _mark_en_zona_segura(tamano, fondo):
    """Lienzo cuadrado con el mark centrado en la zona segura maskable
    de Android (círculo central, ~66% del lienzo) -- mismo criterio que
    generar_icono(maskable=True) en generar_iconos_mibarrio.py."""
    img = Image.new("RGBA", (tamano, tamano), fondo)
    draw = ImageDraw.Draw(img)
    escala = tamano / 100 * 0.66
    offset_x = (tamano / escala - 100) / 2
    offset_y = (tamano / escala - 97) / 2
    return img, draw, escala, offset_x, offset_y


def icono_adaptativo_foreground(tamano=1024):
    """Solo el mark, fondo transparente -- Android compone esta capa
    sobre android-icon-background.png por separado."""
    img, draw, escala, ox, oy = _mark_en_zona_segura(tamano, (0, 0, 0, 0))
    dibujar_mark(draw, escala, ox, oy)
    destino = ASSETS / "android-icon-foreground.png"
    img.save(destino)
    print(f"  {destino.relative_to(RAIZ)} ({tamano}x{tamano})")


def icono_adaptativo_background(tamano=1024):
    """Capa de fondo sólida -- sin mark, Android la dibuja detrás del
    foreground."""
    img = Image.new("RGBA", (tamano, tamano), NAVY)
    destino = ASSETS / "android-icon-background.png"
    img.save(destino)
    print(f"  {destino.relative_to(RAIZ)} ({tamano}x{tamano})")


def icono_adaptativo_monochrome(tamano=1024):
    """Silueta de un solo color (blanco), fondo transparente -- Android
    13+ la tiñe con el color del tema del usuario."""
    img, draw, escala, ox, oy = _mark_en_zona_segura(tamano, (0, 0, 0, 0))
    # dibujar_mark ya usa varios colores (navy/blanco/teal) -- acá se
    # fuerza todo a blanco dibujando sobre una máscara de alpha.
    mascara = Image.new("L", (tamano, tamano), 0)
    mdraw = ImageDraw.Draw(mascara)
    dibujar_mark_mascara(mdraw, escala, ox, oy)
    blanco_total = Image.new("RGBA", (tamano, tamano), BLANCO)
    img = Image.composite(blanco_total, img, mascara)
    destino = ASSETS / "android-icon-monochrome.png"
    img.save(destino)
    print(f"  {destino.relative_to(RAIZ)} ({tamano}x{tamano})")


def dibujar_mark_mascara(draw, escala, offset_x, offset_y):
    """Mismas formas que dibujar_mark() pero todas con fill=255 sobre un
    lienzo "L" -- da la silueta completa (pin+casa+personas) de una, sin
    reimplementar la geometría a mano."""
    p = lambda x, y: ((x + offset_x) * escala, (y + offset_y) * escala)
    draw.ellipse([p(29, 14), p(71, 56)], fill=255)
    draw.polygon([p(34, 50), p(66, 50), p(50, 68)], fill=255)
    draw.polygon(
        [p(50, 18), p(68, 32), p(62, 32), p(62, 50), p(38, 50), p(38, 32), p(32, 32)],
        fill=255,
    )
    personas = [
        (32, 76, 7, [(24, 85), (40, 85), (46, 97), (18, 97)]),
        (68, 76, 7, [(60, 85), (76, 85), (82, 97), (54, 97)]),
        (50, 72, 8, [(39, 82), (61, 82), (67, 97), (33, 97)]),
    ]
    for cx, cy, r, cuerpo in personas:
        draw.ellipse([p(cx - r, cy - r), p(cx + r, cy + r)], fill=255)
        draw.polygon([p(x, y) for x, y in cuerpo], fill=255)


def favicon(tamano=48):
    img = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radio = round(tamano * 0.24)
    draw.rounded_rectangle([0, 0, tamano, tamano], radius=radio, fill=NAVY)
    dibujar_mark(draw, tamano / 100)
    destino = ASSETS / "favicon.png"
    img.save(destino)
    print(f"  {destino.relative_to(RAIZ)} ({tamano}x{tamano})")


def splash_icon(tamano=200):
    """Mismo tamaño aproximado que el splash-icon.png de la plantilla
    -- sin fondo propio, app.json ya define backgroundColor del splash
    por separado (#208AEF) y lo pinta detrás."""
    img = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    mascara = Image.new("L", (tamano, tamano), 0)
    mdraw = ImageDraw.Draw(mascara)
    dibujar_mark_mascara(mdraw, tamano / 100, 0, 0)
    blanco_total = Image.new("RGBA", (tamano, tamano), BLANCO)
    img = Image.composite(blanco_total, img, mascara)
    destino = ASSETS / "splash-icon.png"
    img.save(destino)
    print(f"  {destino.relative_to(RAIZ)} ({tamano}x{tamano})")


def main():
    print("Generando íconos de Mi Barrio+ para app_movil/:")
    icono_app()
    icono_adaptativo_foreground()
    icono_adaptativo_background()
    icono_adaptativo_monochrome()
    favicon()
    splash_icon()
    print("Listo.")


if __name__ == "__main__":
    main()
