function initMedidorContrasena({ passwordInputId, usernameInputId }) {
    var passwordInput = document.getElementById(passwordInputId);
    if (!passwordInput) {
        return;
    }
    var usernameInput = usernameInputId ? document.getElementById(usernameInputId) : null;

    var COLORES = { baja: "#dc3545", media: "#d97706", alta: "#16a34a" };
    var TEXTOS = { baja: "Baja", media: "Media", alta: "Alta" };

    var indicador = document.createElement("div");
    indicador.style.fontSize = "0.8rem";
    indicador.style.marginTop = "0.35rem";
    indicador.style.fontWeight = "600";
    indicador.style.display = "none";
    passwordInput.insertAdjacentElement("afterend", indicador);

    function evaluar(password) {
        if (!password) {
            return null;
        }
        var username = usernameInput ? usernameInput.value || "" : "";
        var muyCorta = password.length < 8;
        var soloNumeros = /^\d+$/.test(password);
        var pareceUsername = username.length >= 3 && password.toLowerCase().indexOf(username.toLowerCase()) !== -1;

        if (muyCorta || soloNumeros || pareceUsername) {
            return "baja";
        }

        var categorias = 0;
        if (/[a-z]/.test(password)) categorias++;
        if (/[A-Z]/.test(password)) categorias++;
        if (/[0-9]/.test(password)) categorias++;
        if (/[^a-zA-Z0-9]/.test(password)) categorias++;

        if (password.length >= 10 && categorias >= 3) {
            return "alta";
        }
        return "media";
    }

    function render() {
        var nivel = evaluar(passwordInput.value);
        if (!nivel) {
            indicador.style.display = "none";
            passwordInput.style.borderColor = "";
            return;
        }
        indicador.style.display = "block";
        indicador.style.color = COLORES[nivel];
        indicador.textContent = "Seguridad de la contraseña: " + TEXTOS[nivel];
        passwordInput.style.borderColor = COLORES[nivel];
    }

    passwordInput.addEventListener("input", render);
    if (usernameInput) {
        usernameInput.addEventListener("input", render);
    }
    render();
}
