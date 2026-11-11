/* astrosky.gg : bouton « Menu » sur téléphone. Sans script, le menu reste affiché en entier. Aucune donnée envoyée. */
(function () {
  "use strict";
  var bouton = document.querySelector(".menu-bouton");
  var menu = document.getElementById("menu-principal");
  if (!bouton || !menu) { return; }
  document.documentElement.classList.add("js");
  bouton.hidden = false;

  function basculer(ouvrir) {
    bouton.setAttribute("aria-expanded", ouvrir ? "true" : "false");
    menu.classList.toggle("ouvert", ouvrir);
  }

  bouton.addEventListener("click", function () {
    basculer(bouton.getAttribute("aria-expanded") !== "true");
  });
  document.addEventListener("keydown", function (evenement) {
    if (evenement.key === "Escape" && bouton.getAttribute("aria-expanded") === "true") {
      basculer(false);
      bouton.focus();
    }
  });
}());
