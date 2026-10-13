// Conecta el medidor de seguridad de contraseña en "Añadir usuario" del
// admin de Django (ver UserCreationFormConMedidor en core/admin.py).
// Depende de que medidor_contrasena.js ya se haya cargado antes.
document.addEventListener("DOMContentLoaded", function () {
    initMedidorContrasena({
        passwordInputId: "id_password1",
        usernameInputId: "id_username",
    });
});
