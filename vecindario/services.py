import logging

import pygeohash as pgh
import requests

from alertas.services import TITULOS_POR_TIPO
from core.comunas_chile import COMUNAS_POR_REGION
from notificaciones.services import enviar_push_a_usuarios, enviar_web_push_a_usuarios

from .models import PerfilGeografico

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org"
# Nominatim exige un User-Agent identificable -- sin esto, rechaza las
# solicitudes (ver su política de uso).
NOMINATIM_HEADERS = {"User-Agent": "SecurApp-Copropiedad/1.0 (contacto@devquad.cl)"}

# comuna (minúscula) -> slug de región, construido una sola vez desde
# COMUNAS_POR_REGION (346 comunas oficiales) -- nunca se usa el texto de
# región que devuelve Nominatim, que viene en formatos inconsistentes
# ("Valparaíso Region", "Región de Valparaíso", etc.).
_REGION_POR_COMUNA = {
    comuna.lower(): region
    for region, comunas in COMUNAS_POR_REGION.items()
    for comuna in comunas
}


def region_de_comuna(comuna):
    """Busca la región oficial de una comuna contra nuestros propios datos
    (COMUNAS_POR_REGION) -- None si la comuna no existe en Chile o el
    nombre no calza exactamente (ver nota de normalización en el form)."""
    return _REGION_POR_COMUNA.get((comuna or "").strip().lower())


def _adyacente_seguro(geohash, direccion):
    """pgh.get_adjacent lanza ValueError en el borde de los polos (no hay
    celda "top" más allá del polo norte) -- Chile nunca cae ahí, pero la
    función debe ser robusta igual. None = no hay vecina en esa dirección."""
    try:
        return pgh.get_adjacent(geohash, direccion)
    except ValueError:
        return None


def calcular_geohash(lat, lng):
    """Codifica lat/lng a la precisión de "barrio" usada en todo el proyecto
    -- pequeño helper para no repetir `pgh.encode(..., precision=...)` en
    cada lugar que crea o actualiza un PerfilGeografico/AlertaCiudadana."""
    from .models import PRECISION_GEOHASH

    return pgh.encode(float(lat), float(lng), precision=PRECISION_GEOHASH)


def vecinos_geohash(geohash):
    """La celda propia + sus 8 vecinas (geohash no es perfectamente
    circular -- un punto justo al otro lado del borde de una celda puede
    estar geográficamente cerca pero tener un geohash totalmente distinto,
    por eso hay que cubrir también las vecinas)."""
    top = _adyacente_seguro(geohash, "top")
    bottom = _adyacente_seguro(geohash, "bottom")
    left = _adyacente_seguro(geohash, "left")
    right = _adyacente_seguro(geohash, "right")
    candidatas = [
        geohash, top, bottom, left, right,
        _adyacente_seguro(top, "left") if top else None,
        _adyacente_seguro(top, "right") if top else None,
        _adyacente_seguro(bottom, "left") if bottom else None,
        _adyacente_seguro(bottom, "right") if bottom else None,
    ]
    return list({c for c in candidatas if c is not None})


def geocodificar_inverso(lat, lng):
    """Coordenadas -> {region, comuna} vía Nominatim (OpenStreetMap, sin
    API key). Devuelve None si Nominatim no responde o no reconoce el
    punto -- nunca inventa una comuna."""
    try:
        respuesta = requests.get(
            f"{NOMINATIM_URL}/reverse",
            params={"lat": lat, "lon": lng, "format": "json", "addressdetails": 1, "accept-language": "es"},
            headers=NOMINATIM_HEADERS, timeout=10,
        )
        respuesta.raise_for_status()
        datos = respuesta.json()
    except (requests.RequestException, ValueError):
        logger.exception("No se pudo geocodificar inverso (%s, %s) en Nominatim.", lat, lng)
        return None

    direccion = datos.get("address") or {}
    # Nominatim no tiene un campo "comuna" chileno -- "city"/"town"/"municipality"
    # son los candidatos más cercanos según la zona (urbana vs rural).
    comuna = direccion.get("city") or direccion.get("town") or direccion.get("municipality") or direccion.get("county")
    region = direccion.get("state")
    if not comuna or not region:
        return None
    return {"comuna": comuna, "region": region}


def geocodificar_direccion(texto):
    """Dirección en texto -> {lat, lng, region, comuna} vía Nominatim.
    Solo se usa cuando la persona no dio permiso de GPS -- si hay
    coordenadas reales del navegador, se prefieren siempre (ver
    RegistroVecinoForm)."""
    try:
        respuesta = requests.get(
            f"{NOMINATIM_URL}/search",
            params={"q": f"{texto}, Chile", "format": "json", "addressdetails": 1, "limit": 1, "accept-language": "es"},
            headers=NOMINATIM_HEADERS, timeout=10,
        )
        respuesta.raise_for_status()
        resultados = respuesta.json()
    except (requests.RequestException, ValueError):
        logger.exception("No se pudo geocodificar la dirección %r en Nominatim.", texto)
        return None

    if not resultados:
        return None
    resultado = resultados[0]
    direccion = resultado.get("address") or {}
    comuna = direccion.get("city") or direccion.get("town") or direccion.get("municipality") or direccion.get("county")
    region = direccion.get("state")
    if not comuna or not region:
        return None
    try:
        lat, lng = float(resultado["lat"]), float(resultado["lon"])
    except (KeyError, ValueError):
        return None
    return {"lat": lat, "lng": lng, "comuna": comuna, "region": region}


def notificar_alerta_ciudadana(alerta):
    """Avisa a los PerfilGeografico dentro del radio de barrio (celda +
    vecinas), sin incluir al propio autor."""
    geohashes = vecinos_geohash(alerta.geohash_momento)
    user_ids = list(
        PerfilGeografico.objects.filter(geohash__in=geohashes)
        .exclude(user_id=alerta.autor.user_id)
        .values_list("user_id", flat=True)
    )
    if not user_ids:
        return

    titulo = TITULOS_POR_TIPO.get(alerta.tipo, TITULOS_POR_TIPO["otro"])
    cuerpo = alerta.mensaje or f"{alerta.autor.user.get_full_name()} activó una alerta en tu barrio."
    data = {"tipo": "alerta_ciudadana", "alerta_id": alerta.id}
    enviar_push_a_usuarios(user_ids, titulo, cuerpo, data=data)
    enviar_web_push_a_usuarios(user_ids, titulo, cuerpo, data=data)
