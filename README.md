# GlyConnect Enrichment — Re-Glyco Batch Pipeline

Projet réalisé dans le cadre du cours **Applications Informatiques (12X015)**, Université de Genève, Printemps 2026.

**Équipe :** Layal Saleh, Rania El Hadj, Sina Divine Abina  
**Superviseure :** Mme Frédérique Lisacek



## Description

Ce projet a pour objectif d'enrichir la base de données [GlyConnect](https://glyconnect.expasy.org/) avec des structures 3D de glycoprotéines générées par l'outil [Re-Glyco](https://glycoshape.org/reglyco) de GlycoShape.

Pour chaque protéine de GlyConnect, le pipeline :
1. Crée une session Re-Glyco à partir de l'identifiant UniProt
2. Lance un job de scan GlcNAc pour détecter les sites de glycosylation accessibles
3. Télécharge le fichier `.pdb` enrichi (structure 3D avec glycanes attachés) et génère des rapports de progression



## Prérequis et Installation

- Python 3.8 ou supérieur
- La librairie `requests` :

```bash
pip install requests
```



## Structure du dépôt

```text
data/
    proteins.txt          - liste complète des identifiants UniProt à traiter
pv_2026.*.pdf             - procès-verbaux des réunions
enrich_glyconnect.py      - script principal
LICENCE.md                - licence du projet
README.md                 - documentation du dépôt
```



## Configuration

Avant de lancer le script, modifier les variables suivantes dans `enrich_glyconnect.py` :

```python
# Dossier où les fichiers .pdb et les rapports seront sauvegardés
SAVE_FOLDER = "/chemin/vers/votre/dossier"

# Fichier contenant les identifiants UniProt à traiter
with open("data/proteins.txt") as f:
    PROTEINS = [line.strip() for line in f if line.strip()]
```

Le fichier d'entrée doit contenir un identifiant UniProt par ligne.

Si certaines protéines doivent être exclues du traitement, les ajouter à la liste `PROTEINS_IGNORE` en haut du script :

```python
PROTEINS_IGNORE = {
    "Q04637", "Q09666", ...  # ajouter ou retirer des identifiants ici
}
```

Ces protéines seront automatiquement ignorées sans appel à l'API.



## Lancement

```bash
python3 enrich_glyconnect.py
```

Le script traite les protéines une par une. Si un fichier `{uniprot_id}.pdb` existe déjà dans `SAVE_FOLDER`, la protéine est automatiquement ignorée — ce qui permet de reprendre l'exécution après une interruption sans tout recommencer.

Pour arrêter proprement : `Ctrl+C` — le rapport partiel est sauvegardé automatiquement.



## Fichiers de sortie

- `{uniprot_id}.pdb` : structure 3D enrichie de la protéine avec les glycanes
- `batch_report.csv` : tableau récapitulatif : statut, erreur, taille PDB
- `batch_report.json` : rapport détaillé par protéine
- `succes.txt` : liste des protéines traitées avec succès
- `erreurs.txt` : détails des erreurs rencontrées
- `proteins_failed.txt` : liste des protéines en erreur, prête à relancer



## Erreurs connues

| Type d'erreur | Cause | Action |
|---|---|---|
| `API_ERROR (422)` | Protéine absente de GlycoShape | Ignorée automatiquement |
| `API_ERROR (500)` | Erreur serveur temporaire | Relancer sur `proteins_failed.txt` |
| `NO_PDB` | Aucun fichier généré (clash stérique) | Voir `erreurs.txt` |
| `TIMEOUT` | Job dépassant 5 minutes | Relancer |
| `SESSION_ERROR` | Aucune session valide n'a pu être créée | Vérifier l'identifiant UniProt |

### Relancer les protéines en erreur

Remplacer le fichier de protéines dans `enrich_glyconnect.py` :

```python
with open("proteins_failed.txt") as f:
    PROTEINS = [line.strip() for line in f if line.strip()]
```



## Données et licence

Le code source de ce projet est distribué sous licence MIT — voir `LICENCE.md`.

Les données externes utilisées par le projet proviennent de GlyConnect, UniProt, PDB et GlycoShape/Re-Glyco, selon leurs conditions d'utilisation respectives.



## Références

- GlycoShape & Re-Glyco : Ives, C.M., Singh, O. et al. *Restoring protein glycosylation with GlycoShape.* Nat Methods (2024)
- GlyConnect : [glyconnect.expasy.org](https://glyconnect.expasy.org/)
- UniProt : [uniprot.org](https://www.uniprot.org/)
- PDB : [rcsb.org](https://www.rcsb.org/)

- GlycoShape & Re-Glyco : Ives, C.M., Singh, O. et al. *Restoring protein glycosylation with GlycoShape.* Nat Methods (2024)
- GlyConnect : [glyconnect.expasy.org](https://glyconnect.expasy.org/)
- UniProt : [uniprot.org](https://www.uniprot.org/)
- PDB : [rcsb.org](https://www.rcsb.org/)

