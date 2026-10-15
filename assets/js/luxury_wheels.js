/*
  Código JavaScript próprio do website Luxury Wheels (Projeto Final).

  Botão "mostrar password": cada campo de password está dentro de um
  <div class="campo-password"> com um botão com o ícone de um olho.
  Ao clicar no botão, o campo alterna entre:
    - type="password" (texto escondido com pontos) e
    - type="text"     (texto visível),
  para o utilizador poder confirmar que escreveu a password corretamente.

  Isto acontece só no browser: não altera nada do que é enviado ao servidor.
*/

document.addEventListener("DOMContentLoaded", function () {
    var botoesMostrarPassword = document.querySelectorAll(".botao-mostrar-password");

    botoesMostrarPassword.forEach(function (botao) {
        botao.addEventListener("click", function () {
            var campoPassword = botao.parentElement.querySelector("input");
            var icone = botao.querySelector("i");
            var passwordEscondida = campoPassword.type === "password";

            // Troca o tipo do campo, o ícone (olho / olho riscado) e o texto de ajuda
            campoPassword.type = passwordEscondida ? "text" : "password";
            icone.className = passwordEscondida ? "fa fa-eye-slash" : "fa fa-eye";
            botao.setAttribute("aria-label", passwordEscondida ? "Esconder password" : "Mostrar password");
            botao.setAttribute("title", passwordEscondida ? "Esconder password" : "Mostrar password");
        });
    });
});
