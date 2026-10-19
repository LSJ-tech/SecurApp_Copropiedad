/* Medidor de seguridad de contraseña en vivo (Baja/Media/Alta) + checklist
 * de las condiciones que SÍ se pueden verificar en el navegador (longitud,
 * que no sea solo números, que no se parezca a otro campo del mismo form).
 * Las reglas que no se pueden verificar sin el servidor (contraseña común,
 * ver CommonPasswordValidator) se muestran aparte como texto estático fijo
 * (ver password_validators_help_texts() en core/views.py) -- este medidor
 * nunca le dice al usuario "cumples" algo que en realidad no se comprobó.
 *
 * Distinto de medidor_contrasena.js (el que ya usa el admin de Django al
 * crear un usuario, solo la etiqueta Baja/Media/Alta, sin checklist) --
 * mismo problema, API/UI deliberadamente separada para no tocar esa
 * integración ya probada (ver core/test_admin_models.py). */
function initMedidorContrasenaVivo({ campoId, camposComparar }) {
    var campo = document.getElementById(campoId);
    if (!campo) return;
    camposComparar = camposComparar || [];

    var contenedor = document.createElement("div");
    contenedor.className = "medidor-contrasena-vivo mt-2";
    contenedor.innerHTML =
        '<div style="height:4px;border-radius:2px;background:#e5e7eb;overflow:hidden;">' +
        '<div class="medidor-relleno" style="height:100%;width:0%;transition:width .15s ease,background-color .15s ease;"></div>' +
        "</div>" +
        '<div class="medidor-etiqueta small fw-semibold mt-1"></div>' +
        '<ul class="medidor-lista small mt-1 mb-0 ps-3"></ul>';
    campo.insertAdjacentElement("afterend", contenedor);

    var relleno = contenedor.querySelector(".medidor-relleno");
    var etiqueta = contenedor.querySelector(".medidor-etiqueta");
    var lista = contenedor.querySelector(".medidor-lista");

    function seParece(valor, otroValor) {
        if (!otroValor || otroValor.length < 3) return false;
        var a = valor.toLowerCase();
        var b = otroValor.toLowerCase();
        return a.indexOf(b) !== -1 || b.indexOf(a) !== -1;
    }

    function evaluar() {
        var valor = campo.value;
        var condiciones = [
            { ok: valor.length >= 8, texto: "Al menos 8 caracteres" },
            { ok: valor.length > 0 && !/^\d+$/.test(valor), texto: "No es solo números" },
        ];
        if (camposComparar.length) {
            var pareceAOtroCampo = camposComparar.some(function (id) {
                var otro = document.getElementById(id);
                return otro && seParece(valor, otro.value);
            });
            condiciones.push({ ok: valor.length > 0 && !pareceAOtroCampo, texto: "No se parece a tu nombre, apellido o email" });
        }

        var cumplidas = condiciones.filter(function (c) { return c.ok; }).length;
        var puntaje = cumplidas;
        if (valor.length >= 12) puntaje++;
        if (/[a-z]/.test(valor) && /[A-Z]/.test(valor)) puntaje++;
        if (/[0-9]/.test(valor)) puntaje++;
        if (/[^A-Za-z0-9]/.test(valor)) puntaje++;

        var nivel = "", color = "#e5e7eb", ancho = "0%";
        if (valor) {
            if (puntaje <= 2) { nivel = "Baja"; color = "#dc2626"; ancho = "33%"; }
            else if (puntaje <= 4) { nivel = "Media"; color = "#d97706"; ancho = "66%"; }
            else { nivel = "Alta"; color = "#16a34a"; ancho = "100%"; }
        }
        relleno.style.width = ancho;
        relleno.style.backgroundColor = color;
        etiqueta.textContent = nivel ? "Seguridad de la contraseña: " + nivel : "";
        etiqueta.style.color = color;

        lista.innerHTML = "";
        condiciones.forEach(function (c) {
            var li = document.createElement("li");
            li.textContent = (valor ? (c.ok ? "✓ " : "✗ ") : "• ") + c.texto;
            li.style.color = valor ? (c.ok ? "#16a34a" : "#dc2626") : "#6b7280";
            lista.appendChild(li);
        });
    }

    campo.addEventListener("input", evaluar);
    camposComparar.forEach(function (id) {
        var otro = document.getElementById(id);
        if (otro) otro.addEventListener("input", evaluar);
    });
    evaluar();
}
