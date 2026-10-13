"""Sugerencias de empresas de electricidad/agua por región -- SOLO el
nombre de la empresa, nunca un teléfono: el teléfono varía, cambia con el
tiempo y no se pudo verificar con certeza para todas las empresas durante
la investigación. Directiva/administración confirma el número real (de su
propia boleta o del sitio oficial de la empresa) al agregarlo en
NumeroEmergenciaForm -- esto solo pre-llena el nombre.

Cobertura deliberadamente incompleta: solo se listan las regiones donde la
investigación (octubre 2026) encontró una asignación razonablemente clara
y sin contradicciones entre fuentes. El resto de las regiones no muestra
sugerencia, pero de todas formas se puede agregar cualquier número a mano
-- que es, en los hechos, la única fuente realmente confiable acá.

No incluye Plan Cuadrante: varía por sector dentro de la misma comuna, sin
ninguna forma confiable de aproximarlo ni por región ni por comuna.

Fuentes: La Tercera ("El mapa de las distribuidoras de energía por
región"), SISS (listado oficial de sanitarias por región), sitios propios
de Chilquinta/CGE/ESVAL.
"""

EMPRESAS_SUGERIDAS_POR_REGION = {
    "metropolitana": {"electricidad": ["Enel Distribución", "CGE"], "agua": ["Aguas Andinas"]},
    "valparaiso": {"electricidad": ["Chilquinta", "CGE"], "agua": ["ESVAL"]},
    "ohiggins": {"electricidad": ["CGE"], "agua": ["Essbio"]},
    "biobio": {"agua": ["Essbio"]},
    "los_rios": {"agua": ["Essal"]},
    "los_lagos": {"agua": ["Essal"]},
}
