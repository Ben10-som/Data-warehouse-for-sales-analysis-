README — Faker Lambda Layer

Pourquoi
AWS Lambda ne fournit pas la librairie Faker par défaut dans les runtimes Python.
Cette layer permet d’utiliser Faker dans les fonctions Lambda sans embarquer les dépendances dans chaque fonction.

Principe
AWS Lambda charge les dépendances Python depuis le chemin /opt/python.
Pour cette raison, le dossier python doit exister à la racine de l’archive ZIP.

Structure attendue
faker-layer/
├─ python/
│  ├─ faker/
│  ├─ dateutil/
│  └─ …
└─ README.md

Création locale
Créer le dossier python puis installer Faker dedans :

pip install faker -t python/

Créer ensuite l’archive ZIP en incluant uniquement le dossier python :

zip -r faker-layer.zip python

Déploiement sur AWS
Dans AWS Lambda :
Lambda → Layers → Create layer

Nom : FakerLayer
Archive : faker-layer.zip


Utilisation
Ajouter la layer à une fonction Lambda existante
