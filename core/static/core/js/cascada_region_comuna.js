function initCascadaRegionComuna({ regionSelectId, comunaSelectId, comunasPorRegion }) {
    var regionSelect = document.getElementById(regionSelectId);
    var comunaSelect = document.getElementById(comunaSelectId);
    if (!regionSelect || !comunaSelect || !comunasPorRegion) {
        return;
    }

    var comunaInicial = comunaSelect.value;

    function repoblar(conservarSeleccionActual) {
        var comunas = comunasPorRegion[regionSelect.value] || [];
        var seleccionPrevia = conservarSeleccionActual ? comunaSelect.value : comunaInicial;

        comunaSelect.innerHTML = "";
        var vacia = document.createElement("option");
        vacia.value = "";
        vacia.textContent = "---------";
        comunaSelect.appendChild(vacia);

        comunas.forEach(function (nombre) {
            var opcion = document.createElement("option");
            opcion.value = nombre;
            opcion.textContent = nombre;
            if (nombre === seleccionPrevia) {
                opcion.selected = true;
            }
            comunaSelect.appendChild(opcion);
        });
    }

    regionSelect.addEventListener("change", function () {
        repoblar(false);
    });

    // Si ya hay una región elegida al cargar (ej. se volvió a mostrar el
    // formulario por un error de validación), repobla conservando la
    // comuna ya seleccionada en vez de perderla.
    if (regionSelect.value) {
        repoblar(true);
    }
}
