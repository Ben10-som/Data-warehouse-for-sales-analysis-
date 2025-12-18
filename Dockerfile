FROM python:3.11-slim

WORKDIR /usr/app

# Correction du bug "git [ERROR]" : installation de Git au niveau système
# On nettoie les listes d'apt après installation pour garder l'image légère
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip \
 && pip install dbt-redshift

COPY . .
# Voir .dockerignore pour l'exclusion des fichiers inutiles
# Ce fichier contient la configuration qui permet à dbt d'utiliser les variables d'environnement HOST/USER/PASSWORD.
COPY profiles_for_docker_dbt.yml /usr/app/profiles.yml

CMD ["dbt", "run"]
