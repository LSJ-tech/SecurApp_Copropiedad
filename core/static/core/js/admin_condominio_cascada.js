// Conecta la cascada región->comuna en el form de Condominio del admin de
// Django (ver CondominioAdminForm en core/admin.py). Depende de que
// cascada_region_comuna.js y datos_comunas_chile.js ya se hayan cargado
// antes (Media.js los declara en ese orden).
document.addEventListener("DOMContentLoaded", function () {
    initCascadaRegionComuna({
        regionSelectId: "id_region",
        comunaSelectId: "id_comuna",
        comunasPorRegion: COMUNAS_POR_REGION,
    });
});
