"""Comunas de Chile agrupadas por región, para el desplegable en cascada de
región/comuna (ver RegistroCondominioForm y CondominioAdminForm).

Mismas claves que REGION_CHOICES (core.models) -- no duplicar esa lista acá.

Fuente: paquete npm "chilean-territorial-divisions" (MIT), con 5 nombres
corregidos tras cruzarlos con Wikipedia porque el paquete tenía errores de
tipeo/truncamiento: "Riconada" -> Rinconada, "Marichihue" -> Marchigüe,
"San Nico" -> San Nicolás, "Ránqui" -> Ránquil, "Capitán Pratt" -> Capitán Prat.
Total verificado: 346 comunas en 16 regiones.
"""

COMUNAS_POR_REGION = {
    "arica_parinacota": ["Arica", "Camarones", "General Lagos", "Putre"],
    "tarapaca": ["Alto Hospicio", "Camiña", "Colchane", "Huara", "Iquique", "Pica", "Pozo Almonte"],
    "antofagasta": [
        "Antofagasta", "Calama", "María Elena", "Mejillones", "Ollagüe",
        "San Pedro de Atacama", "Sierra Gorda", "Taltal", "Tocopilla",
    ],
    "atacama": [
        "Alto del Carmen", "Caldera", "Chañaral", "Copiapó", "Diego de Almagro",
        "Freirina", "Huasco", "Tierra Amarilla", "Vallenar",
    ],
    "coquimbo": [
        "Andacollo", "Canela", "Combarbalá", "Coquimbo", "Illapel", "La Higuera",
        "La Serena", "Los Vilos", "Monte Patria", "Ovalle", "Paiguano",
        "Punitaqui", "Río Hurtado", "Salamanca", "Vicuña",
    ],
    "valparaiso": [
        "Algarrobo", "Cabildo", "Calle Larga", "Cartagena", "Casablanca", "Catemu",
        "Concón", "El Quisco", "El Tabo", "Hijuelas", "Isla de Pascua",
        "Juan Fernández", "La Calera", "La Cruz", "La Ligua", "Limache", "Llaillay",
        "Los Andes", "Nogales", "Olmué", "Panquehue", "Papudo", "Petorca",
        "Puchuncaví", "Putaendo", "Quillota", "Quilpué", "Quintero", "Rinconada",
        "San Antonio", "San Esteban", "San Felipe", "Santa María", "Santo Domingo",
        "Valparaíso", "Villa Alemana", "Viña del Mar", "Zapallar",
    ],
    "metropolitana": [
        "Alhué", "Buin", "Calera de Tango", "Cerrillos", "Cerro Navia", "Colina",
        "Conchalí", "Curacaví", "El Bosque", "El Monte", "Estación Central",
        "Huechuraba", "Independencia", "Isla de Maipo", "La Cisterna", "La Florida",
        "La Granja", "La Pintana", "La Reina", "Lampa", "Las Condes", "Lo Barnechea",
        "Lo Espejo", "Lo Prado", "Macul", "Maipú", "María Pinto", "Melipilla",
        "Ñuñoa", "Padre Hurtado", "Paine", "Pedro Aguirre Cerda", "Peñaflor",
        "Peñalolén", "Pirque", "Providencia", "Pudahuel", "Puente Alto", "Quilicura",
        "Quinta Normal", "Recoleta", "Renca", "San Bernardo", "San José de Maipo",
        "San Joaquín", "San Miguel", "San Pedro", "San Ramón", "Santiago",
        "Talagante", "Tiltil", "Vitacura",
    ],
    "ohiggins": [
        "Chépica", "Chimbarongo", "Codegua", "Coinco", "Coltauco", "Doñihue",
        "Graneros", "La Estrella", "Las Cabras", "Litueche", "Lolol", "Machalí",
        "Malloa", "Marchigüe", "Mostazal", "Nancagua", "Navidad", "Olivar",
        "Palmilla", "Paredones", "Peralillo", "Peumo", "Pichidegua", "Pichilemu",
        "Placilla", "Pumanque", "Quinta de Tilcoco", "Rancagua", "Rengo",
        "Requínoa", "San Fernando", "San Vicente", "Santa Cruz",
    ],
    "maule": [
        "Cauquenes", "Chanco", "Colbún", "Constitución", "Curepto", "Curicó",
        "Empedrado", "Hualañé", "Licantén", "Linares", "Longaví", "Maule",
        "Molina", "Parral", "Pelarco", "Pelluhue", "Pencahue", "Rauco", "Retiro",
        "Río Claro", "Romeral", "Sagrada Familia", "San Clemente", "San Javier",
        "San Rafael", "Talca", "Teno", "Vichuquén", "Villa Alegre", "Yerbas Buenas",
    ],
    "nuble": [
        "Bulnes", "Chillán", "Chillán Viejo", "Cobquecura", "Coelemu", "Coihueco",
        "El Carmen", "Ninhue", "Ñiquén", "Pemuco", "Pinto", "Portezuelo", "Quillón",
        "Quirihue", "Ránquil", "San Carlos", "San Fabián", "San Ignacio",
        "San Nicolás", "Treguaco", "Yungay",
    ],
    "biobio": [
        "Alto Biobío", "Antuco", "Arauco", "Cabrero", "Cañete", "Chiguayante",
        "Concepción", "Contulmo", "Coronel", "Curanilahue", "Florida", "Hualpén",
        "Hualqui", "Laja", "Lebu", "Los Álamos", "Los Ángeles", "Lota", "Mulchén",
        "Nacimiento", "Negrete", "Penco", "Quilaco", "Quilleco",
        "San Pedro de la Paz", "San Rosendo", "Santa Bárbara", "Santa Juana",
        "Talcahuano", "Tirúa", "Tomé", "Tucapel", "Yumbel",
    ],
    "araucania": [
        "Angol", "Carahue", "Cholchol", "Collipulli", "Cunco", "Curacautín",
        "Curarrehue", "Ercilla", "Freire", "Galvarino", "Gorbea", "Lautaro",
        "Loncoche", "Lonquimay", "Los Sauces", "Lumaco", "Melipeuco",
        "Nueva Imperial", "Padre Las Casas", "Perquenco", "Pitrufquén", "Pucón",
        "Purén", "Renaico", "Saavedra", "Temuco", "Teodoro Schmidt", "Toltén",
        "Traiguén", "Victoria", "Vilcún", "Villarrica",
    ],
    "los_rios": [
        "Corral", "Futrono", "La Unión", "Lago Ranco", "Lanco", "Los Lagos",
        "Máfil", "Mariquina", "Paillaco", "Panguipulli", "Río Bueno", "Valdivia",
    ],
    "los_lagos": [
        "Ancud", "Calbuco", "Castro", "Chaitén", "Chonchi", "Cochamó",
        "Curaco de Vélez", "Dalcahue", "Fresia", "Frutillar", "Futaleufú",
        "Hualaihué", "Llanquihue", "Los Muermos", "Maullín", "Osorno", "Palena",
        "Puerto Montt", "Puerto Octay", "Puerto Varas", "Puqueldón", "Purranque",
        "Puyehue", "Queilén", "Quellón", "Quemchi", "Quinchao", "Río Negro",
        "San Juan de la Costa", "San Pablo",
    ],
    "aysen": [
        "Aisén", "Chile Chico", "Cisnes", "Cochrane", "Coihaique", "Guaitecas",
        "Lago Verde", "O'Higgins", "Río Ibáñez", "Tortel",
    ],
    "magallanes": [
        "Antártica", "Cabo de Hornos", "Laguna Blanca", "Natales", "Porvenir",
        "Primavera", "Punta Arenas", "Río Verde", "San Gregorio", "Timaukel",
        "Torres del Paine",
    ],
}


def comuna_choices_agrupadas(region_choices):
    """[(etiqueta_region, [(comuna, comuna), ...]), ...] -- choices con
    optgroup nativo de Django, para que incluso sin JS el desplegable de
    comuna ya salga organizado por región en vez de 346 opciones sueltas."""
    etiquetas = dict(region_choices)
    return [
        (etiquetas[region], [(comuna, comuna) for comuna in comunas])
        for region, comunas in COMUNAS_POR_REGION.items()
    ]
