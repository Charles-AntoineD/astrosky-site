"""Essais des vérifications de la charte (stdlib). Lancer : py -I _outils/test_verifications.py"""
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import construire as k  # noqa: E402

BANDE = ('<div class="chiffres">\n<div class="conteneur"><ul><li><span class="nombre">18+</span>'
         '<span class="libelle">adults only</span></li></ul></div>\n</div>')


def page(corps: str, tete: str = "") -> str:
    return f"<html><head>{tete}</head><body>{corps}</body></html>"


def motif_18(erreurs: list[str]) -> list[str]:
    return [e for e in erreurs if "18+" in e]


class Exception18(unittest.TestCase):
    """Décision 18-A de l'Owner (2026-11-11) : « 18+ » permis dans la seule bande de chiffres de l'accueil."""

    def test_bande_de_l_accueil_permise(self):
        for nom in ("index.html", "fr/index.html"):
            self.assertEqual(motif_18(k.interdits(nom, page(BANDE))), [], nom)

    def test_une_seule_bande_exemptee(self):
        self.assertTrue(motif_18(k.interdits("index.html", page(BANDE + BANDE))))

    def test_reste_de_l_accueil_controle(self):
        self.assertTrue(motif_18(k.interdits("index.html", page(BANDE + "<p>Players 18+ only</p>"))))

    def test_autres_pages_controlees(self):
        for nom in ("faq/index.html", "join/index.html", "fr/rejoindre/index.html"):
            self.assertTrue(motif_18(k.interdits(nom, page(BANDE))), nom)


class Attributs(unittest.TestCase):
    """Les attributs lus (alt, title, aria-label, content des meta, placeholder) suivent la charte."""

    def test_alt(self):
        self.assertTrue(k.interdits("faq/index.html", page('<img src="/a.jpg" alt="A safe server">')))

    def test_title(self):
        self.assertTrue(k.interdits("faq/index.html", page('<a href="/" title="Best server">x</a>')))

    def test_aria_label(self):
        self.assertTrue(k.interdits("faq/index.html", page('<button aria-label="Pay-to-win">x</button>')))

    def test_meta_content(self):
        self.assertTrue(k.interdits("faq/index.html", page("", '<meta name="description" content="For all ages">')))

    def test_placeholder(self):
        self.assertTrue(k.interdits("faq/index.html", page('<input placeholder="Last chance">')))

    def test_18_dans_un_attribut_de_l_accueil(self):
        self.assertTrue(motif_18(k.interdits("index.html", page(BANDE + '<img src="/a.jpg" alt="18+">'))))

    def test_attributs_sans_probleme(self):
        self.assertEqual(k.interdits("faq/index.html", page('<img src="/a.jpg" alt="" title="AstroSky">',
                                                            '<meta name="description" content="A OneBlock server">')),
                         [])


if __name__ == "__main__":
    unittest.main()
