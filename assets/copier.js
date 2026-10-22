/* astrosky.gg : bouton « Copier l'adresse ». Aucun script tiers, aucune donnée envoyée, aucun témoin. */
(function () {
  "use strict";

  function copierSecours(texte) {
    var champ = document.createElement("textarea");
    champ.value = texte;
    champ.setAttribute("readonly", "");
    champ.className = "hors-ecran";
    document.body.appendChild(champ);
    champ.select();
    var reussi = false;
    try { reussi = document.execCommand("copy"); } catch (e) { reussi = false; }
    document.body.removeChild(champ);
    return reussi;
  }

  function signaler(bouton, reussi) {
    var zone = document.getElementById(bouton.getAttribute("data-statut"));
    var libelle = bouton.getAttribute("data-libelle");
    bouton.textContent = reussi ? bouton.getAttribute("data-ok") : bouton.getAttribute("data-echec");
    if (zone) { zone.textContent = reussi ? bouton.getAttribute("data-annonce") : bouton.getAttribute("data-echec"); }
    window.setTimeout(function () { bouton.textContent = libelle; }, 2500);
  }

  var boutons = document.querySelectorAll("[data-copier]");
  Array.prototype.forEach.call(boutons, function (bouton) {
    bouton.hidden = false;
    bouton.addEventListener("click", function () {
      var texte = bouton.getAttribute("data-copier");
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(texte).then(
          function () { signaler(bouton, true); },
          function () { signaler(bouton, copierSecours(texte)); }
        );
      } else {
        signaler(bouton, copierSecours(texte));
      }
    });
  });
})();
