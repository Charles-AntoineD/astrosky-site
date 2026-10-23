"""Construit les pages HTML d'astrosky.gg (anglais et français) à partir de _outils/etat.toml.

    py _outils/construire.py              construit les pages, puis les vérifie
    py _outils/construire.py --verifier   vérifie seulement (toutes les combinaisons d'interrupteurs)

Bibliothèque standard seulement (Python 3.11 ou plus récent). Règle du site : une phrase ne s'affiche que le jour où
elle est vraie ; chaque phrase conditionnelle dépend d'un interrupteur de etat.toml ou de la présence d'une page
légale (.md) dans le dépôt. Les fichiers produits sont listés dans _outils/genere.txt ; un fichier qui n'est plus
produit est supprimé. GitHub Pages copie ces pages telles quelles (aucun en-tête Jekyll) et ignore _outils/.
"""

from __future__ import annotations

import argparse
import html
import itertools
import json
import re
import struct
import sys
import tomllib
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
OUTILS = RACINE / "_outils"
SITE = "https://astrosky.gg"
MANIFESTE = OUTILS / "genere.txt"

# Pages légales reconnues : clé -> (chemin anglais, chemin français)
LEGALES = {
    "contact": ("/contact/", "/fr/contact/"),
    "non_affiliation": ("/not-affiliated/", "/fr/non-affiliation/"),
    "regles": ("/rules/", "/fr/regles/"),
    "confidentialite": ("/privacy/", "/fr/confidentialite/"),
    "conditions": ("/store-terms/", "/fr/boutique-conditions/"),
    "pack": ("/pack/", "/fr/pack/"),
}

CHEMINS = {
    "accueil": ("/", "/fr/"),
    "rejoindre": ("/join/", "/fr/rejoindre/"),
    "faq": ("/faq/", "/fr/faq/"),
    "liens": ("/links/", "/fr/liens/"),
    "vote": ("/vote/", "/fr/vote/"),
}

IMAGES = RACINE / "assets" / "img"

CSP = ("default-src 'none'; style-src 'self'; font-src 'self'; img-src 'self'; script-src 'self'; "
       "manifest-src 'self'; base-uri 'none'; form-action 'none'")


def t(lang: str, en: str, fr: str) -> str:
    return en if lang == "en" else fr


def e(texte: str) -> str:
    return html.escape(str(texte), quote=True)


# Lecture de l'état et des pages légales ──────────────────────────────────────────────────

def charger_etat(chemin: Path = OUTILS / "etat.toml") -> dict:
    with chemin.open("rb") as f:
        return tomllib.load(f)


def pages_markdown(racine: Path = RACINE) -> set[str]:
    """Chemins (permalink) des pages .md présentes dans le dépôt du site."""
    trouves = set()
    for fichier in list(racine.glob("*.md")) + list(racine.glob("fr/*.md")):
        texte = fichier.read_text(encoding="utf-8")
        m = re.match(r"---\s*\n(.*?)\n---", texte, re.S)
        if not m:
            continue
        lien = re.search(r"^permalink:\s*(\S+)\s*$", m.group(1), re.M)
        if lien:
            trouves.add(lien.group(1))
    return trouves


def taille_png(chemin: Path) -> tuple[int, int]:
    data = chemin.read_bytes()[16:24]
    return struct.unpack(">II", data)


def ligne_vote_publiee(racine: Path = RACINE) -> bool:
    """La politique de confidentialité publiée (EN et FR) contient-elle la ligne « vote » ? (spec 043, TS-1/TS-2)"""
    try:
        en = (racine / "privacy-policy.md").read_text(encoding="utf-8").lower()
        fr = (racine / "fr" / "politique-de-confidentialite.md").read_text(encoding="utf-8").lower()
    except OSError:
        return False
    return "vote journal" in en and "journal des votes" in fr


class Contexte:
    def __init__(self, etat: dict, legales_presentes: set[str], ligne_vote: bool = False):
        self.etat = etat
        self.presentes = legales_presentes
        s = etat["serveur"]
        self.adresse = s["adresse"]
        self.versions = s["versions"]
        self.ouvert = bool(s["ouvert"])
        self.equipe = int(s.get("taille_equipe", 0))
        self.jeu = etat["jeu"]
        prive = all(p in legales_presentes for p in LEGALES["confidentialite"])
        conditions = all(p in legales_presentes for p in LEGALES["conditions"])
        # La boutique ne s'affiche ouverte qu'avec ses conditions et la politique de confidentialité en ligne
        # (règles de Mojang : prix et historique d'achats ; contact.md : conditions publiées à l'ouverture).
        self.boutique_demandee = bool(etat["boutique"]["ouverte"])
        self.boutique = self.boutique_demandee and prive and conditions
        self.boutique_url = etat["boutique"]["adresse"]
        self.discord = etat["discord"]["invitation"].strip()
        sites = [v for v in etat["vote"]["sites"] if v["adresse"].strip()]
        # Le vote ne s'ouvre qu'avec ses trois adresses et la politique de confidentialité en ligne avec sa ligne
        # « vote » (« Vote journal » / « journal des votes », ajoutée par la PR du vote).
        self.vote_demande = bool(etat["vote"]["ouvert"])
        self.vote = self.vote_demande and len(sites) == len(etat["vote"]["sites"]) and prive and ligne_vote
        self.votes = etat["vote"]["sites"]
        self.comptes = etat["comptes"]
        self.nouvelles = etat.get("nouvelles", [])

    def legale(self, cle: str, lang: str) -> str | None:
        chemin = LEGALES[cle][0 if lang == "en" else 1]
        return chemin if chemin in self.presentes else None

    def page(self, cle: str, lang: str) -> str:
        return CHEMINS[cle][0 if lang == "en" else 1]


# Gabarit commun ──────────────────────────────────────────────────────────────────────────

def entete(c: Contexte, lang: str, courant: str | None, autre: str) -> str:
    items = [("accueil", t(lang, "Home", "Accueil")), ("rejoindre", t(lang, "How to join", "Rejoindre")),
             ("faq", "FAQ"), ("liens", t(lang, "Links", "Liens"))]
    lis = []
    for cle, libelle in items:
        cur = ' aria-current="page"' if cle == courant else ""
        lis.append(f'<li><a href="{c.page(cle, lang)}"{cur}>{libelle}</a></li>')
    langue = t(lang, '<a href="{0}" lang="fr" hreflang="fr">Français</a>',
               '<a href="{0}" lang="en" hreflang="en">English</a>').format(autre)
    lis.append(f'<li class="langue">{langue}</li>')
    return f"""<a class="saut" href="#contenu">{t(lang, "Skip to content", "Aller au contenu")}</a>
<header class="entete">
<div class="conteneur">
<a class="marque" href="{c.page("accueil", lang)}"><img src="/assets/img/logotype.svg" width="180" height="58" alt="AstroSky"></a>
<nav class="menu" aria-label="{t(lang, "Main", "Principal")}"><ul>{"".join(lis)}</ul></nav>
</div>
</header>"""


def liens_pied(c: Contexte, lang: str) -> str:
    morceaux = []
    contact = c.legale("contact", lang)
    if contact:
        morceaux.append(f'<a href="{contact}">astrosky.gg{contact.rstrip("/")}</a>')
    for cle, en, fr in (("regles", "Rules", "Règles"), ("confidentialite", "Privacy", "Confidentialité")):
        chemin = c.legale(cle, lang)
        if chemin:
            morceaux.append(f'<a href="{chemin}">{t(lang, en, fr)}</a>')
    if c.boutique:
        morceaux.append(f'<a href="/store">{t(lang, "Store and prices", "Boutique et prix")}</a>')
    chemin = c.legale("conditions", lang)
    if chemin:
        morceaux.append(f'<a href="{chemin}">{t(lang, "Store terms", "Conditions de la boutique")}</a>')
    chemin = c.legale("non_affiliation", lang)
    if chemin:
        morceaux.append(f'<a href="{chemin}">{t(lang, "Not affiliated", "Non-affiliation")}</a>')
    liens_officiels = CHEMINS["liens"][0 if lang == "en" else 1]
    morceaux.append(f'<a href="{liens_officiels}">{t(lang, "Official links", "Liens officiels")}</a>')
    return " · ".join(morceaux)


def pied(c: Contexte) -> str:
    en = liens_pied(c, "en")
    fr = liens_pied(c, "fr")
    return f"""<footer class="pied">
<div class="conteneur">
<p class="mention" lang="en">NOT AN OFFICIAL MINECRAFT SERVICE. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT.<br>
AstroSky is run by an independent operator, not by Mojang or Microsoft. Who we are and how to reach us: {en}</p>
<p class="mention" lang="fr">Ceci n'est pas un service officiel Minecraft. Non approuvé par Mojang ou Microsoft, ni associé à eux.<br>
AstroSky est exploité par un exploitant indépendant, et non par Mojang ni Microsoft. Qui nous sommes et comment nous joindre : {fr}</p>
<p><span lang="en">This site sets no cookies and uses no analytics.</span> · <span lang="fr">Ce site ne dépose aucun témoin et n'utilise aucune analytique.</span></p>
<p class="credit"><span lang="en">The Heart Nebula (IC 1805) in our visuals was photographed by AstroSky’s founder.</span> · <span lang="fr">La nébuleuse du Cœur (IC 1805) de nos visuels a été photographiée par le fondateur d’AstroSky.</span></p>
</div>
</footer>"""


def document(c: Contexte, lang: str, chemin: str, autre: str, courant: str | None, titre: str, description: str,
             corps: str, image: str | None = "constellation-1280.png", donnees: dict | None = None,
             script: bool = False, refresh: str | None = None, image_alt: str | None = None,
             noindex: bool = False, canonique: str | None = None) -> str:
    alternes = ""
    if autre:
        en_ch, fr_ch = (chemin, autre) if lang == "en" else (autre, chemin)
        alternes = (f'<link rel="alternate" hreflang="en" href="{SITE}{en_ch}">\n'
                    f'<link rel="alternate" hreflang="fr" href="{SITE}{fr_ch}">\n'
                    f'<link rel="alternate" hreflang="x-default" href="{SITE}{en_ch}">\n')
    og = ""
    if image:
        w, h = taille_png(IMAGES / image)
        og = (f'<meta property="og:image" content="{SITE}/assets/img/{image}">\n'
              f'<meta property="og:image:width" content="{w}">\n<meta property="og:image:height" content="{h}">\n'
              f'<meta property="og:image:alt" content="{e(image_alt or t(lang, ALT_CONSTELLATION_EN, ALT_CONSTELLATION_FR))}">\n'
              '<meta name="twitter:card" content="summary_large_image">\n')
    ld = ""
    if donnees:
        ld = ('<script type="application/ld+json">' + json.dumps(donnees, ensure_ascii=False, separators=(",", ":"))
              .replace("</", "<\\/") + "</script>\n")
    rafraichir = f'<meta http-equiv="refresh" content="0; url={e(refresh)}">\n' if refresh else ""
    js = '<script src="/assets/copier.js" defer></script>\n' if script else ""
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="no-referrer">
{rafraichir}<title>{e(titre)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{SITE}{canonique or chemin}">
{'<meta name="robots" content="noindex">' + chr(10) if noindex else ""}
{alternes}<meta property="og:type" content="website">
<meta property="og:site_name" content="AstroSky">
<meta property="og:title" content="{e(titre)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{SITE}{chemin}">
<meta property="og:locale" content="{t(lang, "en_US", "fr_CA")}">
{og}<meta name="theme-color" content="#0A0F1F">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/jost-400.woff" as="font" type="font/woff" crossorigin>
<link rel="stylesheet" href="/assets/site.css">
{js}{ld}</head>
<body>
{entete(c, lang, courant, autre or chemin)}
<main id="contenu">
{corps}
</main>
{pied(c)}
</body>
</html>
"""


# Morceaux réutilisés ─────────────────────────────────────────────────────────────────────

ALT_CONSTELLATION_EN = ("Render of the AstroSky spawn at night: round floating islands linked by bridges, "
                        "under a glowing eight-point pole star.")
ALT_CONSTELLATION_FR = ("Rendu du spawn d’AstroSky la nuit : des îles rondes et flottantes reliées par des passerelles, "
                        "sous une étoile polaire lumineuse à huit branches.")


ALT_ARRIVEE = {
    "en": "Render of the arrival island at night: a brass path leads toward the glowing eight-point pole star.",
    "fr": "Rendu de l’île d’arrivée la nuit : un chemin de laiton mène vers l’étoile polaire lumineuse à huit branches.",
}


def bouton_copier(c: Contexte, lang: str, ident: str) -> str:
    return (f'<button type="button" class="bouton" hidden data-copier="{e(c.adresse)}" data-statut="{ident}" '
            f'data-libelle="{t(lang, "Copy address", "Copier l’adresse")}" '
            f'data-ok="{t(lang, "Copied", "Copiée")}" '
            f'data-echec="{t(lang, "Select it, then copy", "Sélectionne-la, puis copie")}" '
            f'data-annonce="{t(lang, "Address copied: ", "Adresse copiée : ")}{e(c.adresse)}">'
            f'{t(lang, "Copy address", "Copier l’adresse")}</button>'
            f'<span id="{ident}" class="hors-ecran" role="status" aria-live="polite"></span>')


def carte_adresse(c: Contexte, lang: str, ident: str) -> str:
    return f"""<div class="adresse-carte">
<p class="etiquette">{t(lang, "Server address", "Adresse du serveur")}</p>
<div class="adresse-ligne"><span class="adresse">{e(c.adresse)}</span>{bouton_copier(c, lang, ident)}</div>
<p class="meta">{t(lang, "Minecraft: Java Edition", "Minecraft: Java Edition")} {e(c.versions)} · {t(lang, "Java only, no Bedrock", "Java seulement, pas Bedrock")} · {t(lang, "For players 18 and over", "Pour les 18 ans et plus")}</p>
</div>"""


def statut(c: Contexte, lang: str) -> str:
    if c.ouvert:
        return t(lang, "AstroSky is open. Copy the address, then in Minecraft: Multiplayer → Add Server.",
                 "AstroSky est ouvert. Copie l’adresse, puis dans Minecraft : Multijoueur → Ajouter un serveur.")
    return t(lang, "Opens Monday, November 16, 2026, at 6 p.m. Eastern Time (Québec time).",
             "Ouverture le lundi 16 novembre 2026, à 18 h, heure du Québec.")


def image(nom: str, alt: str, legende: str, prioritaire: bool = False, tailles: str = "(max-width: 68rem) 100vw, 66rem") -> str:
    base = nom.rsplit("-", 1)[0]
    variantes = sorted(IMAGES.glob(f"{base}-*.png"), key=lambda p: taille_png(p)[0])
    grand = IMAGES / nom
    w, h = taille_png(grand)
    srcset = ", ".join(f"/assets/img/{p.name} {taille_png(p)[0]}w" for p in variantes)
    charge = 'fetchpriority="high"' if prioritaire else 'loading="lazy"'
    return (f'<figure class="rendu"><img src="/assets/img/{nom}" srcset="{srcset}" sizes="{tailles}" width="{w}" '
            f'height="{h}" alt="{e(alt)}" {charge} decoding="async">'
            f'<figcaption>{legende}</figcaption></figure>')


def legende_rendu(lang: str) -> str:
    return t(lang, "Render made by code from the spawn’s build files: plain block colours, no game textures.",
             "Rendu fait par code à partir des fichiers de construction du spawn : couleurs de blocs unies, sans les textures du jeu.")


def equipe(c: Contexte, lang: str) -> str:
    if c.equipe > 0:
        return t(lang, f", up to {c.equipe} players per island", f", jusqu’à {c.equipe} joueurs par île")
    return ""


def economie(c: Contexte, lang: str) -> str | None:
    j = c.jeu
    morceaux = []
    morceaux.append(t(lang, "sell to the server", "vends au serveur"))
    if j["coffres_boutiques"]:
        morceaux.append(t(lang, "run chest shops on your island", "tiens un coffre-boutique sur ton île"))
    if j["hotel_des_ventes"]:
        morceaux.append(t(lang, "list items at the auction house", "mets des objets en vente à l’hôtel des ventes"))
    if j["banque_ile"]:
        morceaux.append(t(lang, "share an island bank with your team", "partage le compte de l’île avec ton équipe"))
    if len(morceaux) == 1:
        return None
    phrase = ", ".join(morceaux[:-1]) + t(lang, " and ", " et ") + morceaux[-1]
    return phrase[0].upper() + phrase[1:] + "."


def a_venir(c: Contexte, lang: str) -> str | None:
    j = c.jeu
    prevu = []
    if not j["metiers"]:
        prevu.append(t(lang, "jobs", "métiers"))
    if not j["equipes_agrandies"]:
        prevu.append(t(lang, "bigger island teams", "équipes d’île agrandies"))
    if not prevu:
        return None
    return t(lang, f"Update 1 is planned: {' and '.join(prevu)}.",
             f"La Mise à jour 1 est prévue : {' et '.join(prevu)}.")


def boutique_phrase(c: Contexte, lang: str) -> str:
    phrase = t(lang, "The store sells cosmetics and donations only, such as titles and name colours. Nothing sold "
                     "changes how the game plays, coins are never sold, and no purchase is random.",
               "La boutique ne vend que des cosmétiques et des dons, par exemple des titres et des couleurs de pseudo. "
               "Rien de ce qui est vendu ne change le jeu, les coins ne se vendent jamais, et aucun achat n’est au "
               "hasard.")
    if c.boutique:
        phrase += t(lang, ' Prices are visible without an account at <a href="/store">astrosky.gg/store</a>.',
                    ' Les prix sont visibles sans compte sur <a href="/store">astrosky.gg/store</a>.')
    return phrase


# Accueil ─────────────────────────────────────────────────────────────────────────────────

def accueil(c: Contexte, lang: str) -> str:
    j = c.jeu
    rejoindre = c.page("rejoindre", lang)
    if c.discord:
        second = f'<a class="bouton secondaire" href="/discord">{t(lang, "Join the Discord", "Rejoindre le Discord")}</a>'
    else:
        second = f'<a class="bouton secondaire" href="{c.page("faq", lang)}">FAQ</a>'
    cartes = []
    cartes.append((t(lang, "One block, then a whole island", "Un bloc, puis toute une île"),
                   t(lang, "Start on a single magic block floating among the stars. Break it, and it comes back as "
                           "something new: wood, ores, animals, and new phases as you go. Invite friends to your "
                           f"island and build it together{equipe(c, lang)}.",
                     "Commence sur un seul bloc magique qui flotte parmi les étoiles. Casse-le : il revient en autre "
                     "chose, bois, minerais, animaux, et de nouvelles phases au fil du jeu. Invite tes amis sur ton île "
                     f"et bâtissez-la ensemble{equipe(c, lang)}.")))
    eco = economie(c, lang)
    if eco:
        cartes.append((t(lang, "An economy run by players", "Une économie tenue par les joueurs"), eco))
    buts = []
    if j["defis"]:
        buts.append(t(lang, "Challenges guide your first hours, then give longer goals.",
                      "Des défis guident tes premières heures, puis donnent des buts plus longs."))
    if j["classement_iles"]:
        buts.append(t(lang, "The island level ranking measures what you build.",
                      "Le classement du niveau d’île mesure ce que tu construis."))
    if buts:
        cartes.append((t(lang, "Goals for every session", "Un but à chaque séance"), " ".join(buts)))
    if j["metiers"]:
        cartes.append((t(lang, "Jobs", "Métiers"),
                       t(lang, "Pick a job and earn coins for the work you already do on your island.",
                         "Choisis un métier et gagne des coins pour le travail que tu fais déjà sur ton île.")))
    cartes.append((t(lang, "A store for looks only", "Une boutique pour le style seulement"), boutique_phrase(c, lang)))
    grille = "\n".join(f'<div class="carte"><h3>{titre}</h3><p>{texte}</p></div>' for titre, texte in cartes)
    prevu = a_venir(c, lang)
    prevu_html = f'<p class="intro">{prevu}</p>' if prevu else ""

    nouvelles = ""
    if c.nouvelles:
        lis = "".join(f'<li><time datetime="{n["date"].isoformat()}">{n["date"].isoformat()}</time>{e(n[lang])}</li>'
                      for n in c.nouvelles[:3])
        nouvelles = f"""<section class="bloc" aria-labelledby="t-nouvelles">
<div class="conteneur">
<h2 id="t-nouvelles">{t(lang, "News", "Nouvelles")}</h2>
<ul class="nouvelles">{lis}</ul>
</div>
</section>"""

    comptes = "".join(f'<li><a href="{e(k["adresse"])}" rel="noopener">{e(k["reseau"])} {e(k["nom"])}</a></li>'
                      for k in c.comptes)
    pack = c.legale("pack", lang)
    pack_html = ""
    if pack:
        pack_html = t(lang, f' Optional: <a href="{pack}">the resource packs we recommend</a> polish the night sky.',
                      f' Facultatif : <a href="{pack}">les packs de ressources qu’on conseille</a> soignent le ciel de nuit.')

    corps = f"""<section class="heros">
<div class="conteneur">
<p class="descripteur">{t(lang, "AstroSky — a Minecraft SkyBlock server", "AstroSky — un serveur SkyBlock Minecraft")}</p>
<h1>{t(lang, "Co-op SkyBlock among the stars", "Le SkyBlock coopératif parmi les étoiles")}</h1>
<p class="chapeau">{t(lang, "Grow an island from a single block with your friends, trade with other players, and climb the island ranking.", "Fais grandir une île à partir d’un seul bloc avec tes amis, échange avec les autres joueurs et grimpe au classement des îles.") if j["classement_iles"] else t(lang, "Grow an island from a single block with your friends and trade with other players.", "Fais grandir une île à partir d’un seul bloc avec tes amis et échange avec les autres joueurs.")}</p>
{carte_adresse(c, lang, "copie-haut")}
<p class="statut">{statut(c, lang)}</p>
<div class="actions"><a class="bouton" href="{rejoindre}">{t(lang, "How to join", "Comment rejoindre")}</a>{second}</div>
{image("constellation-1280.png", t(lang, ALT_CONSTELLATION_EN, ALT_CONSTELLATION_FR), legende_rendu(lang), prioritaire=True)}
</div>
</section>

<section class="bloc" aria-labelledby="t-constellation">
<div class="conteneur deux">
<div>
<h2 id="t-constellation">{t(lang, "Arrive in the Constellation", "Arrive dans la Constellation")}</h2>
<p>{t(lang, "The spawn is called the Constellation: seven floating islands linked by bridges, like stars joined into a constellation, under an eight-point pole star.", "Le spawn s’appelle la Constellation : sept îles flottantes reliées par des passerelles, comme des étoiles qui dessinent une constellation, sous une étoile polaire à huit branches.")}</p>
<p>{t(lang, "At its edge floats a monument: a dog astronaut swimming in zero gravity, looking toward the pole star.", "À son bord flotte un monument : un chien astronaute qui nage en apesanteur, le regard tourné vers l’étoile polaire.")}</p>
</div>
{image("carte-768.png", t(lang, "Top view of the spawn: seven round islands linked by bridges, the pole star above, and the monument at the lower left.", "Vue de dessus du spawn : sept îles rondes reliées par des passerelles, l’étoile polaire en haut et le monument en bas à gauche."), legende_rendu(lang), tailles="(max-width: 52rem) 100vw, 28rem")}
</div>
</section>

<section class="bloc" aria-labelledby="t-atouts">
<div class="conteneur">
<h2 id="t-atouts">{t(lang, "What you do on AstroSky", "Ce qu’on fait sur AstroSky")}</h2>
<div class="grille">
{grille}
</div>
{prevu_html}
</div>
</section>

{nouvelles}

<section class="bloc" aria-labelledby="t-appel">
<div class="conteneur">
<h2 id="t-appel">{t(lang, "See you among the stars", "On se voit parmi les étoiles")}</h2>
{carte_adresse(c, lang, "copie-bas")}
<p>{t(lang, "Four steps:", "Quatre étapes :")} <a href="{rejoindre}">{t(lang, "how to join AstroSky", "comment rejoindre AstroSky")}</a>.{pack_html}</p>
<h3>{t(lang, "Follow AstroSky", "Suivre AstroSky")}</h3>
<ul class="comptes">{comptes}</ul>
<p>{t(lang, "Only the addresses on <a href=\"/links/\">our official links page</a> are ours.", "Seules les adresses de <a href=\"/fr/liens/\">notre page des liens officiels</a> sont à nous.")}</p>
</div>
</section>"""
    titre = t(lang, "AstroSky — Co-op SkyBlock among the stars", "AstroSky — Le SkyBlock coopératif parmi les étoiles")
    desc = t(lang, f"AstroSky is a co-op OneBlock SkyBlock server for Minecraft: Java Edition {c.versions}, for "
                   f"players 18 and over. Server address: {c.adresse}.",
             f"AstroSky est un serveur SkyBlock OneBlock coopératif pour Minecraft: Java Edition {c.versions}, "
             f"pour les 18 ans et plus. Adresse du serveur : {c.adresse}.")
    return document(c, lang, c.page("accueil", lang), CHEMINS["accueil"][1 if lang == "en" else 0], "accueil",
                    titre, desc, corps, script=True)


# Rejoindre ───────────────────────────────────────────────────────────────────────────────

def rejoindre(c: Contexte, lang: str) -> str:
    v = e(c.versions)
    premiere = e(re.split(r"[–\-]", c.versions)[0].strip())
    avant = ""
    if not c.ouvert:
        avant = f'<div class="avis"><p>{statut(c, lang)} ' + t(
            lang, "Until then, the server is closed to players (whitelist).",
            "D’ici là, le serveur est fermé aux joueurs (liste blanche).") + "</p></div>"
    pack = c.legale("pack", lang)
    pack_html = ""
    if pack:
        pack_html = f"""<h2>{t(lang, "Optional: a resource pack", "Facultatif : un pack de ressources")}</h2>
<p>{t(lang, f'AstroSky works with the default Minecraft textures. If you like, <a href="{pack}">the resource packs we recommend</a> polish the night sky. The server sends you nothing.', f'AstroSky fonctionne avec les textures de base de Minecraft. Si tu veux, <a href="{pack}">les packs de ressources qu’on conseille</a> soignent le ciel de nuit. Le serveur ne t’envoie rien.')}</p>"""
    contact = c.legale("contact", lang)
    aide = ""
    if contact:
        aide = t(lang, f'<p>Still stuck? Write to us from the <a href="{contact}">contact page</a> (subject "Support") with your Minecraft username and the exact error message.</p>',
                 f'<p>Ça bloque encore ? Écris-nous depuis la <a href="{contact}">page de contact</a> (objet « Support ») avec ton pseudo Minecraft et le message d’erreur exact.</p>')
    liste_blanche = ""
    if c.ouvert and contact:
        liste_blanche = t(lang, f'<li><strong>A message saying you are banned or suspended</strong>: you can appeal within 14 days from the <a href="{contact}">contact page</a> (subject "Appeal").</li>',
                          f'<li><strong>Un message qui dit que tu es banni ou suspendu</strong> : tu peux faire appel dans les 14 jours depuis la <a href="{contact}">page de contact</a> (objet « Appel »).</li>')
    if not c.ouvert:
        liste_blanche = t(lang, "<li><strong>A message saying you are not on the whitelist</strong>: the server isn’t open yet. Come back on November 16, 2026, at 6 p.m. Eastern Time.</li>",
                          "<li><strong>Un message qui dit que tu n’es pas sur la liste blanche</strong> : le serveur n’est pas encore ouvert. Reviens le 16 novembre 2026, à 18 h, heure du Québec.</li>")
    corps = f"""<section class="page">
<div class="conteneur">
<h1>{t(lang, "How to join AstroSky", "Comment rejoindre AstroSky")}</h1>
<p class="chapeau">{t(lang, f"AstroSky runs on Minecraft: Java Edition {v}, on computers (Windows, macOS, Linux). Bedrock Edition (consoles, phones, tablets) can’t join.", f"AstroSky tourne sur Minecraft: Java Edition {v}, sur ordinateur (Windows, macOS, Linux). L’édition Bedrock (consoles, téléphones, tablettes) ne peut pas s’y connecter.")}</p>
{carte_adresse(c, lang, "copie-rejoindre")}
{avant}
<h2>{t(lang, "Before you start", "Avant de commencer")}</h2>
<ul>
<li>{t(lang, "Minecraft: Java Edition, on your own Microsoft account.", "Minecraft: Java Edition, sur ton propre compte Microsoft.")}</li>
<li>{t(lang, "Being 18 or over: AstroSky is for players 18 and over.", "Avoir 18 ans ou plus : AstroSky est réservé aux 18 ans et plus.")}</li>
</ul>
<h2>{t(lang, "Join in four steps", "Rejoindre en quatre étapes")}</h2>
<ol class="etapes">
<li><p>{t(lang, "Open the Minecraft Launcher and choose <strong>Minecraft: Java Edition</strong>.", "Ouvre le Minecraft Launcher et choisis <strong>Minecraft: Java Edition</strong>.")}</p></li>
<li><p>{t(lang, f"Use version <strong>{v}</strong>. If the launcher starts another version: <strong>Installations → New installation</strong>, pick version <strong>{premiere}</strong>, click <strong>Create</strong>, then <strong>Play</strong>.", f"Utilise la version <strong>{v}</strong>. Si le launcher lance une autre version : <strong>Installations → Nouvelle installation</strong>, choisis la version <strong>{premiere}</strong>, clique sur <strong>Créer</strong>, puis sur <strong>Jouer</strong>.")}</p></li>
<li><p>{t(lang, f"In the game: <strong>Multiplayer → Add Server</strong>. Server Name: <code>AstroSky</code>. Server Address: <code>{e(c.adresse)}</code>. Click <strong>Done</strong>.", f"Dans le jeu : <strong>Multijoueur → Ajouter un serveur</strong>. Nom du serveur : <code>AstroSky</code>. Adresse du serveur : <code>{e(c.adresse)}</code>. Clique sur <strong>Terminé</strong>.")}</p></li>
<li><p>{t(lang, "Select AstroSky in the list and click <strong>Join Server</strong>. In game, type <code>/ob</code> to reach your island and <code>/help</code> for help.", "Choisis AstroSky dans la liste et clique sur <strong>Rejoindre le serveur</strong>. En jeu, tape <code>/ob</code> pour aller sur ton île et <code>/help</code> pour l’aide.")}</p></li>
</ol>
{image("arrivee-1280.png", ALT_ARRIVEE[lang], t(lang, "Your first view: the arrival island, facing the pole star. ", "Ta première vue : l’île d’arrivée, face à l’étoile polaire. ") + legende_rendu(lang))}
{pack_html}
<h2>{t(lang, "If it doesn’t work", "Si ça ne marche pas")}</h2>
<ul>
{liste_blanche}
<li>{t(lang, f"<strong>“Outdated client” or “Outdated server”</strong>: your version doesn’t match. Use {v} (step 2).", f"<strong>« Outdated client » ou « Outdated server »</strong> : ta version ne correspond pas. Utilise {v} (étape 2).")}</li>
<li>{t(lang, f"<strong>“Can’t resolve hostname” or “Can’t connect to server”</strong>: check the address, <code>{e(c.adresse)}</code>, with no www and no port, then try again in a few minutes.", f"<strong>« Can’t resolve hostname » ou « Can’t connect to server »</strong> : vérifie l’adresse, <code>{e(c.adresse)}</code>, sans www ni port, puis réessaie dans quelques minutes.")}</li>
<li>{t(lang, "<strong>“Failed to log in” or “Invalid session”</strong>: close the game, restart the Minecraft Launcher and sign in again.", "<strong>« Failed to log in » ou « Invalid session »</strong> : ferme le jeu, relance le Minecraft Launcher et reconnecte-toi.")}</li>
</ul>
{aide}
</div>
</section>"""
    titre = t(lang, "How to join AstroSky — Minecraft: Java Edition", "Rejoindre AstroSky — Minecraft: Java Edition")
    desc = t(lang, f"Join AstroSky in four steps: Minecraft: Java Edition {c.versions}, server address {c.adresse}.",
             f"Rejoindre AstroSky en quatre étapes : Minecraft: Java Edition {c.versions}, adresse du serveur {c.adresse}.")
    return document(c, lang, c.page("rejoindre", lang), CHEMINS["rejoindre"][1 if lang == "en" else 0], "rejoindre",
                    titre, desc, corps, image="arrivee-1280.png", script=True, image_alt=ALT_ARRIVEE[lang])


# FAQ ─────────────────────────────────────────────────────────────────────────────────────

def questions(c: Contexte, lang: str) -> list[tuple[str, str]]:
    j = c.jeu
    q: list[tuple[str, str]] = []
    rejoindre = c.page("rejoindre", lang)
    contact = c.legale("contact", lang)
    lien_contact = (f'<a href="{contact}">{t(lang, "contact page", "page de contact")}</a>' if contact else None)
    q.append((t(lang, "What is AstroSky?", "Qu’est-ce qu’AstroSky ?"),
              t(lang, "A co-op OneBlock SkyBlock server for Minecraft: Java Edition: you start on a single block "
                      "floating among the stars and grow it into an island with your friends. AstroSky is run by an "
                      "independent operator, not by Mojang or Microsoft.",
                "Un serveur SkyBlock OneBlock coopératif pour Minecraft: Java Edition : tu commences sur un seul bloc "
                "qui flotte parmi les étoiles et tu en fais une île avec tes amis. AstroSky est exploité par un "
                "exploitant indépendant, et non par Mojang ni Microsoft.")))
    q.append((t(lang, "What is the server address and version?", "Quelle est l’adresse du serveur, et quelle version ?"),
              t(lang, f'<code>{e(c.adresse)}</code>, on Minecraft: Java Edition {e(c.versions)}. Step by step: '
                      f'<a href="{rejoindre}">how to join</a>.',
                f'<code>{e(c.adresse)}</code>, sur Minecraft: Java Edition {e(c.versions)}. Pas à pas : '
                f'<a href="{rejoindre}">comment rejoindre</a>.')))
    q.append((t(lang, "Can I play on Bedrock, a console or a phone?", "Puis-je jouer sur Bedrock, une console ou un téléphone ?"),
              t(lang, "No. AstroSky is for Minecraft: Java Edition on a computer only.",
                "Non. AstroSky est réservé à Minecraft: Java Edition, sur ordinateur.")))
    if not c.ouvert:
        q.append((t(lang, "When does AstroSky open?", "Quand AstroSky ouvre-t-il ?"),
                  statut(c, lang) + " " + t(lang, "Until then, the server is closed to players (whitelist).",
                                            "D’ici là, le serveur est fermé aux joueurs (liste blanche).")))
    q.append((t(lang, "Is it free?", "Est-ce gratuit ?"),
              t(lang, "Yes. You need your own copy of Minecraft: Java Edition; the rest is free.",
                "Oui. Il te faut ton propre Minecraft: Java Edition ; le reste est gratuit.")))
    age = t(lang, "Players 18 and over. We never ask for your age or an ID. If you’re under 18, please don’t join; if "
                  "we learn a player is under 18, we remove access kindly, not as a punishment.",
            "Les joueurs de 18 ans et plus. On ne demande jamais ton âge ni une pièce d’identité. Si tu as moins de "
            "18 ans, ne rejoins pas le jeu ; si on apprend qu’un joueur a moins de 18 ans, on retire son accès avec "
            "bienveillance, sans sanction.")
    if lien_contact:
        age += t(lang, f" A parent or guardian can write to us from the {lien_contact} (subject “Privacy”) to ask us "
                       "to remove a player’s access and delete their data. A person reviews each request; the "
                       "player is told and can contest it.",
                 f" Un parent ou un tuteur peut nous écrire depuis la {lien_contact} (objet « Confidentialité ») pour "
                 "demander le retrait de l’accès d’un joueur et la suppression de ses données. Une personne examine "
                 "chaque demande ; le joueur en est informé et peut la contester.")
    q.append((t(lang, "Who can play?", "Qui peut jouer ?"), age))
    amis = t(lang, "Yes: invite them to your island and build it together", "Oui : invite-les sur ton île et bâtissez-la ensemble")
    partage = []
    if j["defis"]:
        partage.append(t(lang, "challenges", "les défis"))
    if j["banque_ile"]:
        partage.append(t(lang, "the island bank", "le compte de l’île"))
    amis += equipe(c, lang)
    amis += (t(lang, "; your team shares ", " ; ton équipe partage ") + t(lang, " and ", " et ").join(partage) + "."
             if partage else ".")
    q.append((t(lang, "Can I play with friends?", "Puis-je jouer avec mes amis ?"), amis))
    q.append((t(lang, "Can you buy an advantage?", "Peut-on acheter un avantage ?"),
              t(lang, "No. ", "Non. ") + boutique_phrase(c, lang)))
    if c.vote:
        q.append((t(lang, "How do I vote for AstroSky?", "Comment voter pour AstroSky ?"),
                  t(lang, f'Voting is optional: <a href="{c.page("vote", lang)}">the vote page</a> lists the three sites and how vote points work.',
                    f'Le vote est facultatif : <a href="{c.page("vote", lang)}">la page de vote</a> donne les trois sites et le fonctionnement des points de vote.')))
    regles = c.legale("regles", lang)
    if regles:
        q.append((t(lang, "What are the rules?", "Quelles sont les règles ?"),
                  t(lang, f'Read them before you play: <a href="{regles}">AstroSky rules</a> (sanctions and appeals included).',
                    f'Lis-les avant de jouer : <a href="{regles}">règles d’AstroSky</a> (sanctions et appels compris).')))
    if lien_contact:
        signaler = t(lang, f"Write to us from the {lien_contact} with the subject “Report”: we review reports within "
                           "48 hours (24 hours for serious harassment).",
                     f"Écris-nous depuis la {lien_contact} avec l’objet « Signalement » : on examine les signalements "
                     "sous 48 heures (24 heures pour un harcèlement grave).")
        if j["commande_report"]:
            signaler = t(lang, "In game, use <code>/report</code>. ", "En jeu, utilise <code>/report</code>. ") + signaler
        signaler += t(lang, " If someone is in immediate danger, call your local emergency number (911 in Canada and "
                            "the United States) first.",
                      " Si quelqu’un est en danger immédiat, appelle d’abord les secours de ton pays (911 au Canada et "
                      "aux États-Unis).")
        q.append((t(lang, "How do I report a player or a problem?", "Comment signaler un joueur ou un problème ?"), signaler))
    if c.discord:
        q.append((t(lang, "Is there a Discord?", "Y a-t-il un Discord ?"),
                  t(lang, 'Yes: <a href="/discord">astrosky.gg/discord</a>. Only this address leads to our Discord.',
                    'Oui : <a href="/discord">astrosky.gg/discord</a>. Seule cette adresse mène à notre Discord.')))
    else:
        q.append((t(lang, "Is there a Discord?", "Y a-t-il un Discord ?"),
                  t(lang, "Not yet. When it opens, its invite will be posted only on this site.",
                    "Pas encore. Quand il ouvrira, son invitation sera publiée seulement sur ce site.")))
    prevu = a_venir(c, lang)
    if prevu:
        q.append((t(lang, "What’s next?", "Et ensuite ?"), prevu))
    contact_txt = t(lang, "Staff never ask for your password, codes or a payment.",
                    "L’équipe ne demande jamais ton mot de passe, tes codes ni un paiement.")
    if lien_contact:
        contact_txt = t(lang, f"From the {lien_contact}. We answer in English or French. ",
                        f"Depuis la {lien_contact}. On répond en français ou en anglais. ") + contact_txt
    q.append((t(lang, "How do I contact you?", "Comment vous joindre ?"), contact_txt))
    return q


def texte_brut(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment))


def faq(c: Contexte, lang: str) -> str:
    qs = questions(c, lang)
    items = "\n".join(f"<details><summary>{q}</summary><div><p>{r}</p></div></details>" for q, r in qs)
    donnees = {"@context": "https://schema.org", "@type": "FAQPage",
               "mainEntity": [{"@type": "Question", "name": texte_brut(q),
                               "acceptedAnswer": {"@type": "Answer", "text": texte_brut(r)}} for q, r in qs]}
    corps = f"""<section class="page">
<div class="conteneur">
<h1>{t(lang, "Questions and answers", "Questions et réponses")}</h1>
<p class="chapeau">{t(lang, f'Server address: <code>{e(c.adresse)}</code> · Minecraft: Java Edition {e(c.versions)}', f'Adresse du serveur : <code>{e(c.adresse)}</code> · Minecraft: Java Edition {e(c.versions)}')}</p>
{items}
</div>
</section>"""
    titre = t(lang, "AstroSky — FAQ", "AstroSky — FAQ")
    desc = t(lang, "Questions and answers about AstroSky: address, version, who can play, store, friends, reports.",
             "Questions et réponses sur AstroSky : adresse, version, qui peut jouer, boutique, amis, signalements.")
    return document(c, lang, c.page("faq", lang), CHEMINS["faq"][1 if lang == "en" else 0], "faq", titre, desc,
                    corps, donnees=donnees)


# Liens officiels ─────────────────────────────────────────────────────────────────────────

def liens(c: Contexte, lang: str) -> str:
    lignes = []
    lignes.append((t(lang, "Server", "Serveur"),
                   f'<code>{e(c.adresse)}</code> (Minecraft: Java Edition {e(c.versions)})'))
    lignes.append((t(lang, "Website", "Site"), '<a href="/">astrosky.gg</a>'))
    if c.vote:
        lignes.append((t(lang, "Vote", "Vote"),
                       f'<a href="{c.page("vote", lang)}">astrosky.gg{c.page("vote", "en").rstrip("/")}</a> · '
                       + " · ".join(f'<a href="{e(v["adresse"])}" rel="noopener">{e(v["nom"])}</a>' for v in c.votes)))
    if c.boutique:
        lignes.append((t(lang, "Store", "Boutique"),
                       t(lang, '<a href="/store">astrosky.gg/store</a> (cosmetics and donations only, prices visible without an account)',
                         '<a href="/store">astrosky.gg/store</a> (cosmétiques et dons seulement, prix visibles sans compte)')))
    else:
        lignes.append((t(lang, "Store", "Boutique"),
                       t(lang, "not open yet; when it opens, it will be reachable only from this page",
                         "pas encore ouverte ; quand elle ouvrira, on n’y accédera que par cette page")))
    if c.discord:
        lignes.append(("Discord", '<a href="/discord">astrosky.gg/discord</a>'))
    else:
        lignes.append(("Discord", t(lang, "not open yet; its invite will appear only on this page",
                                    "pas encore ouvert ; son invitation sera publiée seulement sur cette page")))
    for cle, en, fr in (("regles", "Rules", "Règles"), ("confidentialite", "Privacy", "Confidentialité"),
                        ("conditions", "Store terms", "Conditions de la boutique"), ("contact", "Contact", "Contact"),
                        ("pack", "Resource pack (optional)", "Pack de ressources (facultatif)")):
        chemin = c.legale(cle, lang)
        if chemin:
            lignes.append((t(lang, en, fr), f'<a href="{chemin}">astrosky.gg{chemin.rstrip("/")}</a>'))
    table = "\n".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in lignes)
    comptes = "\n".join(f'<tr><td>{e(k["reseau"])}</td><td><a href="{e(k["adresse"])}" rel="noopener">{e(k["nom"])}</a></td></tr>'
                        for k in c.comptes)
    signaler = ""
    contact = c.legale("contact", lang)
    if contact:
        signaler = t(lang, f' To report an imitation, write to us from the <a href="{contact}">contact page</a> (subject “Report”).',
                     f' Pour signaler une imitation, écris-nous depuis la <a href="{contact}">page de contact</a> (objet « Signalement »).')
    paiement = t(lang, "Our team will never ask you for your password, a code or a payment, by message, by email or "
                       "anywhere else, and no sanction is ever lifted for a payment.",
                 "Notre équipe ne te demandera jamais ton mot de passe, un code ni un paiement, ni par message, ni par "
                 "courriel, ni ailleurs, et aucune sanction n’est levée contre un paiement.")
    corps = f"""<section class="page">
<div class="conteneur">
<h1>{t(lang, "Official links", "Liens officiels")}</h1>
<p class="chapeau">{t(lang, "These are AstroSky’s only official addresses and accounts.", "Voici les seules adresses et les seuls comptes officiels d’AstroSky.")}</p>
<table>
<caption class="hors-ecran">{t(lang, "Official addresses", "Adresses officielles")}</caption>
{table}
</table>
<h2>{t(lang, "Our only official accounts", "Nos seuls comptes officiels")}</h2>
<table>
<caption class="hors-ecran">{t(lang, "Official social accounts", "Comptes sociaux officiels")}</caption>
{comptes}
</table>
<div class="avis">
<p>{t(lang, "Any other server address, account, Discord or store that claims to be AstroSky is not ours.", "Toute autre adresse de serveur, tout autre compte, Discord ou boutique qui se dit AstroSky n’est pas à nous.")}</p>
<p>{paiement}{signaler}</p>
</div>
</div>
</section>"""
    titre = t(lang, "AstroSky — Official links", "AstroSky — Liens officiels")
    desc = t(lang, "AstroSky’s only official addresses: server, website, store, Discord, social accounts.",
             "Les seules adresses officielles d’AstroSky : serveur, site, boutique, Discord, réseaux sociaux.")
    return document(c, lang, c.page("liens", lang), CHEMINS["liens"][1 if lang == "en" else 0], "liens", titre,
                    desc, corps)


# Vote (seulement quand il est ouvert) ────────────────────────────────────────────────────

def vote(c: Contexte, lang: str) -> str:
    contact = c.legale("contact", lang)
    contester = ""
    if contact:
        contester = t(lang, f' You can contest a correction within 14 days from the <a href="{contact}">contact page</a> (subject "Appeal").',
                      f' Tu peux contester une correction dans les 14 jours depuis la <a href="{contact}">page de contact</a> (objet « Appel »).')
    chemin = c.legale("confidentialite", lang)
    politique = t(lang, f'Details: <a href="{chemin}">privacy policy</a>.',
                  f'Détails : <a href="{chemin}">politique de confidentialité</a>.')
    sites = "\n".join(f'<li><p><a class="bouton secondaire" href="{e(v["adresse"])}" rel="noopener">{e(v["nom"])}</a></p></li>'
                      for v in c.votes)
    corps = f"""<section class="page">
<div class="conteneur">
<h1>{t(lang, "Vote for AstroSky", "Voter pour AstroSky")}</h1>
<p class="chapeau">{t(lang, "Optional. Once a day per site, whenever you like. 1 vote = 1 vote point, on every site. Points have no expiry date and buy cosmetics only: never coins, items, discounts or anything sold. No streaks.", "Facultatif. Une fois par jour et par site, quand tu veux. 1 vote = 1 point de vote, sur chaque site. Les points n’ont pas de date d’expiration et n’achètent que des cosmétiques : jamais de coins, d’objets, de rabais ni rien de ce qui est vendu. Aucune série.")}</p>
<ol class="etapes">
{sites}
</ol>
<p>{t(lang, "Join AstroSky once first, then vote with your exact Minecraft name. One vote per person per site per day, even with several accounts. Spend your points in game: <code>/vote</code>.", "Rejoins AstroSky une première fois, puis vote avec ton pseudo Minecraft exact. Un vote par personne, par site et par jour, même avec plusieurs comptes. Dépense tes points en jeu : <code>/vote</code>.")}</p>
<div class="avis">
<p>{t(lang, "No bots, scripts or auto-vote mods, no VPN or proxy to vote more than once a day on the same site, and no votes under someone else’s name: rewards gained that way are removed.", "Ni robot, ni script, ni mod de vote automatique, ni VPN ou mandataire pour voter plus d’une fois par jour sur un même site, ni vote au nom d’un autre : les récompenses obtenues ainsi sont retirées.")}{contester}</p>
<p>{t(lang, "Each of these sites publishes the names of its voters (“Top voters”, “Latest votes”). Vote only if you’re fine with your Minecraft name appearing there.", "Chacun de ces sites publie le pseudo de ses votants (« Top voters », « Latest votes »). Ne vote que si tu acceptes que ton pseudo Minecraft y apparaisse.")}</p>
<p>{t(lang, "When you vote, the site sends us your Minecraft name and your IP address. We read the name to credit your account and never keep the address. A vote journal (account, site, date, purchases and corrections) is kept 88 days to correct fraud.", "Quand tu votes, le site nous envoie ton pseudo Minecraft et ton adresse IP. On lit le pseudo pour créditer ton compte et on ne garde jamais l’adresse. Un journal des votes (compte, site, date, achats et corrections) est gardé 88 jours pour corriger la fraude.")} {politique}</p>
</div>
</div>
</section>"""
    titre = t(lang, "AstroSky — Vote", "AstroSky — Vote")
    desc = t(lang, "Vote for AstroSky on three server lists. Optional; vote points buy cosmetics only.",
             "Vote pour AstroSky sur trois listes de serveurs. Facultatif ; les points de vote n’achètent que des cosmétiques.")
    return document(c, lang, c.page("vote", lang), CHEMINS["vote"][1 if lang == "en" else 0], None, titre, desc, corps)


# Redirections et 404 ─────────────────────────────────────────────────────────────────────

def renvoi(c: Contexte, chemin: str, cible: str | None, titre: str, attente_en: str, attente_fr: str) -> str:
    if cible:
        corps = f"""<section class="page"><div class="conteneur">
<h1>{e(titre)}</h1>
<p lang="en">Taking you to <a href="{e(cible)}">{e(cible)}</a>.</p>
<p lang="fr">Redirection vers <a href="{e(cible)}">{e(cible)}</a>.</p>
</div></section>"""
    else:
        corps = f"""<section class="page"><div class="conteneur">
<h1>{e(titre)}</h1>
<p lang="en">{attente_en} <a href="/links/">Official links</a></p>
<p lang="fr">{attente_fr} <a href="/fr/liens/">Liens officiels</a></p>
</div></section>"""
    return document(c, "en", chemin, "", None, titre, titre, corps, image=None, refresh=cible)


def entree(c: Contexte, chemin: str) -> str:
    """Lien d'entrée propre à une plateforme (/yt) : renvoie à l'accueil, sans index, sans rien enregistrer."""
    corps = """<section class="page"><div class="conteneur">
<h1>AstroSky</h1>
<p lang="en">Taking you to <a href="/">astrosky.gg</a>.</p>
<p lang="fr">Redirection vers <a href="/fr/">astrosky.gg</a>.</p>
</div></section>"""
    return document(c, "en", chemin, "", None, "AstroSky — Co-op SkyBlock among the stars", "AstroSky", corps,
                    image=None, refresh="/", noindex=True, canonique="/")


def page_404(c: Contexte) -> str:
    corps = """<section class="page"><div class="conteneur">
<h1>Page not found · Page introuvable</h1>
<p lang="en">This page doesn’t exist. <a href="/">Back to astrosky.gg</a></p>
<p lang="fr">Cette page n’existe pas. <a href="/fr/">Retour à astrosky.gg</a></p>
</div></section>"""
    return document(c, "en", "/404.html", "", None, "AstroSky — Page not found", "Page not found", corps, image=None)


# Gabarit des pages légales (Jekyll) ──────────────────────────────────────────────────────

def gabarit_legal(c: Contexte) -> str:
    """_layouts/legal.html : mêmes en-tête, style et pied que les pages construites ; Jekyll y verse le Markdown."""
    def nav(lang: str) -> str:
        items = [("accueil", t(lang, "Home", "Accueil")), ("rejoindre", t(lang, "How to join", "Rejoindre")),
                 ("faq", "FAQ"), ("liens", t(lang, "Links", "Liens"))]
        lis = "".join(f'<li><a href="{c.page(k, lang)}">{v}</a></li>' for k, v in items)
        return f"""<a class="saut" href="#contenu">{t(lang, "Skip to content", "Aller au contenu")}</a>
<header class="entete">
<div class="conteneur">
<a class="marque" href="{c.page("accueil", lang)}"><img src="/assets/img/logotype.svg" width="180" height="58" alt="AstroSky"></a>
<nav class="menu" aria-label="{t(lang, "Main", "Principal")}"><ul>{lis}</ul></nav>
</div>
</header>"""
    return f"""<!doctype html>
<html lang="{{{{ page.lang }}}}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="no-referrer">
<title>{{{{ page.title }}}}</title>
<meta name="theme-color" content="#0A0F1F">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="stylesheet" href="/assets/site.css">
</head>
<body>
{{% if page.lang == "fr" %}}
{nav("fr")}
{{% else %}}
{nav("en")}
{{% endif %}}
<main id="contenu" class="page prose">
<div class="conteneur">
{{{{ content }}}}
</div>
</main>
{pied(c)}
</body>
</html>
"""


def plan_du_site(chemins: list[str]) -> str:
    urls = "\n".join(f"  <url><loc>{SITE}{p}</loc></url>" for p in sorted(chemins))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}
</urlset>
"""


# Construction ────────────────────────────────────────────────────────────────────────────

def construire(c: Contexte) -> dict[str, str]:
    sorties: dict[str, str] = {}
    publiques: list[str] = []
    for lang in ("en", "fr"):
        for cle, fonction in (("accueil", accueil), ("rejoindre", rejoindre), ("faq", faq), ("liens", liens)):
            chemin = c.page(cle, lang)
            sorties[chemin.lstrip("/") + "index.html"] = fonction(c, lang)
            publiques.append(chemin)
        if c.vote:
            chemin = c.page("vote", lang)
            sorties[chemin.lstrip("/") + "index.html"] = vote(c, lang)
            publiques.append(chemin)
    sorties["store/index.html"] = renvoi(
        c, "/store/", c.boutique_url if c.boutique else None, "AstroSky — Store",
        "The AstroSky store isn’t open yet. When it opens, this address will lead to it.",
        "La boutique d’AstroSky n’est pas encore ouverte. Quand elle ouvrira, cette adresse y mènera.")
    sorties["discord/index.html"] = renvoi(
        c, "/discord/", c.discord or None, "AstroSky — Discord",
        "Our Discord isn’t open yet. When it opens, its invite will be posted only on this site.",
        "Notre Discord n’est pas encore ouvert. Quand il ouvrira, son invitation sera publiée seulement sur ce site.")
    sorties["yt/index.html"] = entree(c, "/yt/")
    sorties["404.html"] = page_404(c)
    sorties["_layouts/legal.html"] = gabarit_legal(c)
    publiques += sorted(c.presentes)
    sorties["sitemap.xml"] = plan_du_site(publiques)
    return sorties


# Vérifications ───────────────────────────────────────────────────────────────────────────

INTERDITS = [
    (r"(?i)\bsafe\b", "promesse « safe » (charte, section 8)"),
    (r"(?i)family[- ]friendly|for all ages|pour tous les âges", "promesse familiale (charte)"),
    (r"(?i)pay[- ]to[- ]win", "slogan « pay-to-win » (charte, MARKETING_GROWTH)"),
    (r"(?i)anti[- ]?cheat|anti-triche", "promesse anti-triche (charte)"),
    (r"(?i)\bmod[ée]r[ée]\b|\bmoderated\b", "promesse de modération (charte)"),
    (r"(?i)countdown|compte à rebours|limited[- ]time|last chance|dernière chance", "urgence (charte)"),
    (r"(?i)\bastro\b(?!sky)", "nom « Astro » (exception 8.1)"),
    (r"(?i)\b(best|ultimate|number one|meilleur)\b|#1\b", "superlatif (charte, ton)"),
    (r"18\+", "« 18+ » (charte : « 18 and over »)"),
    (r"(?i)forever|pour toujours|never expire|n.expirent jamais", "promesse de durée"),
    (r"(?i)official minecraft(?! service)|minecraft official", "« Official » à côté de Minecraft"),
    (r"(?i)\b(stardust|wish|poussière d’étoiles|vœu)\b", "vocabulaire réservé (charte, O8)"),
    (r"[\w.+-]+@[\w-]+\.[\w.]+", "adresse de courriel (garder la page de contact)"),
    (r"\{\{|\{%", "balise de gabarit non résolue"),
]


def ressources_externes(page: str) -> list[str]:
    """Ressources chargées par la page (pas les liens) qui ne viennent pas du site."""
    trouvees = []
    for balise, attr in (("img", "src"), ("script", "src"), ("link", "href"), ("source", "srcset"),
                         ("iframe", "src"), ("img", "srcset")):
        for m in re.finditer(rf"<{balise}\b[^>]*\b{attr}=\"([^\"]+)\"", page):
            valeur = m.group(1)
            if balise == "link" and re.search(r'rel="(canonical|alternate)"', m.group(0)):
                continue
            for morceau in valeur.split(","):
                url = morceau.strip().split(" ")[0]
                if url.startswith(("http://", "https://", "//")) and not url.startswith(SITE):
                    trouvees.append(url)
    return trouvees


def verifier(sorties: dict[str, str], c: Contexte) -> list[str]:
    erreurs = []
    for nom, page in sorties.items():
        if not nom.endswith(".html"):
            continue
        for motif, raison in INTERDITS:
            if nom.startswith("_layouts/") and raison == "balise de gabarit non résolue":
                continue
            visible = html.unescape(re.sub(r"<[^>]+>", " ", page))
            m = re.search(motif, visible if raison != "balise de gabarit non résolue" else page)
            if m:
                erreurs.append(f"{nom} : {raison} ({m.group(0)!r})")
        for url in ressources_externes(page):
            erreurs.append(f"{nom} : ressource externe {url}")
        if "\r" in page:
            erreurs.append(f"{nom} : fin de ligne CRLF")
        for m in re.finditer(r'(?:href|src)="(/[^"#?]*)"', page):
            chemin = m.group(1)
            if not lien_existe(chemin, sorties, c):
                erreurs.append(f"{nom} : lien interne cassé {chemin}")
        if not nom.startswith("_layouts/") and "NOT AN OFFICIAL MINECRAFT SERVICE" not in page:
            erreurs.append(f"{nom} : mention de non-affiliation absente")
    return erreurs


def lien_existe(chemin: str, sorties: dict[str, str], c: Contexte) -> bool:
    if chemin in c.presentes or chemin.rstrip("/") + "/" in c.presentes:
        return True
    if chemin in ("/store", "/discord"):
        return f"{chemin.lstrip('/')}/index.html" in sorties
    nom = chemin.lstrip("/")
    if nom == "" or nom.endswith("/"):
        nom += "index.html"
    if nom in sorties:
        return True
    return (RACINE / nom).is_file()


def combinaisons(etat: dict):
    """Toutes les combinaisons des interrupteurs qui changent le texte."""
    cles = [("serveur", "ouvert"), ("boutique", "ouverte"), ("vote", "ouvert"), ("jeu", "metiers"),
            ("jeu", "equipes_agrandies"), ("jeu", "hotel_des_ventes"), ("jeu", "banque_ile"),
            ("jeu", "coffres_boutiques"), ("jeu", "defis"), ("jeu", "classement_iles"), ("jeu", "commande_report")]
    for valeurs in itertools.product((False, True), repeat=len(cles)):
        variante = json.loads(json.dumps(etat, default=str))
        for (bloc, cle), valeur in zip(cles, valeurs):
            variante[bloc][cle] = valeur
        for n, original in zip(variante.get("nouvelles", []), etat.get("nouvelles", [])):
            n["date"] = original["date"]
        if variante["vote"]["ouvert"]:
            for i, site in enumerate(variante["vote"]["sites"]):
                site["adresse"] = site["adresse"] or f"https://example.org/vote/{i}"
        variante["discord"]["invitation"] = "https://discord.gg/exemple" if valeurs[0] else ""
        variante["serveur"]["taille_equipe"] = 4 if valeurs[3] else 0
        yield variante


def ecrire(sorties: dict[str, str]) -> None:
    anciens = set(MANIFESTE.read_text(encoding="utf-8").split()) if MANIFESTE.exists() else set()
    for nom in sorted(anciens - set(sorties)):
        fichier = RACINE / nom
        if fichier.is_file():
            fichier.unlink()
            print(f"retiré : {nom}")
    for nom, contenu in sorties.items():
        fichier = RACINE / nom
        fichier.parent.mkdir(parents=True, exist_ok=True)
        with fichier.open("w", encoding="utf-8", newline="\n") as f:
            f.write(contenu)
    with MANIFESTE.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(sorted(sorties)) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Construit les pages d'astrosky.gg.")
    parser.add_argument("--verifier", action="store_true", help="vérifier seulement, sans écrire")
    args = parser.parse_args(argv)
    etat = charger_etat()
    presentes = pages_markdown()
    erreurs = []
    nombre = 0
    toutes = presentes | {p for paire in LEGALES.values() for p in paire}
    for jeu_de_pages in (presentes, toutes):
        for variante in combinaisons(etat):
            nombre += 1
            c = Contexte(variante, jeu_de_pages, ligne_vote=True)
            for err in verifier(construire(c), c):
                if err not in erreurs:
                    erreurs.append(err)
    c = Contexte(etat, presentes, ligne_vote=ligne_vote_publiee())
    sorties = construire(c)
    for err in verifier(sorties, c):
        if err not in erreurs:
            erreurs.append(err)
    if erreurs:
        print("\n".join(erreurs), file=sys.stderr)
        print(f"{len(erreurs)} erreur(s) ; rien n'est écrit.", file=sys.stderr)
        return 1
    if c.boutique_demandee and not c.boutique:
        print("Attention : boutique.ouverte est vrai, mais les conditions de la boutique ou la politique de "
              "confidentialité (EN et FR) ne sont pas dans le dépôt : la boutique reste affichée fermée.")
    if c.vote_demande and not c.vote:
        print("Attention : vote.ouvert est vrai, mais une adresse de vote, la politique de confidentialité (EN et "
              "FR) ou sa ligne « vote » manque : la page de vote n'est pas construite.")
    print(f"Vérifié : {nombre} combinaisons d'interrupteurs et de pages légales, {len(sorties)} fichiers.")
    if not args.verifier:
        ecrire(sorties)
        print(f"Écrit : {len(sorties)} fichiers (liste dans _outils/genere.txt).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
