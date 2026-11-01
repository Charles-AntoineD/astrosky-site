# Outils du site astrosky.gg

Ce dossier n'est pas publié : GitHub Pages ignore les dossiers qui commencent par `_` (sauf `_layouts`).

## Ce qui est construit, et ce qui ne l'est pas

`py _outils/construire.py` écrit, à partir de `etat.toml` :

- les pages en anglais et en français : accueil (`/`, `/fr/`), comment rejoindre (`/join/`, `/fr/rejoindre/`), FAQ
  (`/faq/`, `/fr/faq/`), liens officiels (`/links/`, `/fr/liens/`) et, quand le vote est ouvert, `/vote/` et `/fr/vote/` ;
- `/store` : redirection quand la boutique existe, sinon une page d'attente ;
- `/discord` et `/fr/discord/` : la page d'arrivée du Discord (âge, règles, contact, lien d'invitation sur le bouton)
  quand `discord.invitation` est renseignée et que les règles, le contact et la confidentialité sont en ligne ; sinon
  une page d'attente ;
- `/ideas` et `/fr/idees` : la page « Idées » (poster une idée dans le salon des suggestions du Discord), vers laquelle
  le jeu renvoie depuis le menu pause. Construite seulement quand le Discord est ouvert et que `discord.salon_idees`
  porte le nom du salon ; le bouton mène à `/discord/` (âge, règles), jamais directement à l'invitation ; rien sur
  l'achat ; `/report` n'y est cité que si `jeu.commande_report` est vrai ;
- `/yt` : lien d'entrée du profil YouTube (KV-Q1), qui renvoie à l'accueil ; page sans index, qui n'enregistre rien. Un
  site statique ne compte pas les visites : le comptage par chemin et par jour, sans adresse IP, demande un relais qui
  répond à `/yt` (voir la note de la session du site) ;
- `404.html`, `sitemap.xml` et le gabarit des pages légales `_layouts/legal.html` (même en-tête, style et pied). Le pied
  de page porte la ligne de crédit de la photo de la nébuleuse du Cœur (sans nom, décision de l'Owner du 2026-10-22).

Il ne touche pas aux pages légales (`contact.md`, `not-affiliated.md`, `pack.md` et, plus tard, règles,
confidentialité et conditions de la boutique) : on les publie comme le dit `PUBLIER.md` du dépôt du studio. Le site les
relie tout seul dès que leur fichier `.md` est là : relancer `construire.py` après en avoir ajouté une.

Il ne touche pas non plus aux redirections des réseaux (`tiktok/`, `youtube/`, `instagram/`, `x/`), aux icônes, à
`CNAME`, ni à `assets/` (style, polices Jost sous licence SIL OFL 1.1, logotype). Le site ne montre aucune image du spawn
(il a été acheté : aucun texte ne laisse entendre qu'AstroSky l'a construit).

## Changer un interrupteur

1. Ouvrir `_outils/etat.toml` et changer la valeur, seulement si c'est vrai ce jour-là (le fichier dit quand).
2. Lancer `py _outils/construire.py`. Le script vérifie d'abord toutes les combinaisons d'interrupteurs (mots
   interdits par la charte, nom « Astro », adresse de courriel, ressource externe, lien interne cassé, mention de
   non-affiliation, fins de ligne) ; s'il trouve une erreur, il n'écrit rien.
3. Valider et pousser :

   ```
   git add -A
   git commit -m "Site : <ce qui change>"
   git push
   ```

## Les jalons connus

| Quand | Interrupteur |
|---|---|
| Annonce de la date (jamais avant l'essai fermé) | `serveur.ouverture_en` et `serveur.ouverture_fr` (vides : « date à annoncer »), et un bloc `[[nouvelles]]` si on veut la nouvelle datée |
| Ouverture | `serveur.ouvert = true` ; `boutique.ouverte = true` si la boutique ouvre en même temps |
| Bascule du 2026-11-06 | `serveur.taille_equipe` ; `jeu.metiers` et `jeu.equipes_agrandies` si on les garde au lancement |
| Invitation Discord publique (permanente) | `py _outils/construire.py --invitation https://discord.gg/<code>` (ou `discord.invitation` dans `etat.toml`) |
| Nom du salon des suggestions connu (ouvre `/ideas` et `/fr/idees`) | `py _outils/construire.py --salon-idees #<salon>` (ou `discord.salon_idees` dans `etat.toml`) |
| Votifier actif, ligne « vote » de la confidentialité publiée, fiches en ligne | les trois `vote.sites.adresse`, puis `vote.ouvert = true` |
| `/report` livré sous ce nom | `jeu.commande_report = true` |
| Premier ping du serveur public | `serveur.versions` |
| Nouvelle à annoncer | un bloc `[[nouvelles]]` en tête de liste |
