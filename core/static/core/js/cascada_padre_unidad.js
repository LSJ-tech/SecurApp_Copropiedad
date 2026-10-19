/* Selector en cascada genérico: elegir un "padre" (ej. un condominio)
 * repuebla un segundo <select> con sus unidades ({id, numero}). Mismo
 * patrón que ya usa registro_residente.html para torre->unidad, pero
 * parametrizado para reusarlo acá con condominio->unidad (ver
 * MoverMiembroView). */
function initCascadaPadreUnidad({ padreSelectId, unidadSelectId, unidadesPorPadre, textoElegirPrimero, textoElegirUnidad }) {
    var padreSelect = document.getElementById(padreSelectId);
    var unidadSelect = document.getElementById(unidadSelectId);
    if (!padreSelect || !unidadSelect) return;

    function agregarOpcion(select, valor, texto) {
        var opcion = document.createElement("option");
        opcion.value = valor;
        opcion.textContent = texto;
        select.appendChild(opcion);
    }

    function actualizar() {
        var padreId = padreSelect.value;
        unidadSelect.innerHTML = "";
        if (!padreId) {
            agregarOpcion(unidadSelect, "", textoElegirPrimero || "— Elige primero —");
            unidadSelect.disabled = true;
            return;
        }
        var unidades = unidadesPorPadre[padreId] || [];
        agregarOpcion(unidadSelect, "", textoElegirUnidad || "— Elige la unidad —");
        unidades.forEach(function (u) { agregarOpcion(unidadSelect, u.id, u.numero); });
        unidadSelect.disabled = false;
    }

    padreSelect.addEventListener("change", actualizar);
    actualizar();
}
