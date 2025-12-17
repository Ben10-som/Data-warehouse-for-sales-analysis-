FROM python:3.11-slim

WORKDIR /usr/app



RUN pip install --upgrade pip \
 && pip install dbt-redshif

COPY . .
# Ce fichier contient la configuration qui permet à dbt d'utiliser les variables d'environnement HOST/USER/PASSWORD.
COPY profiles_for_docker_dbt.yml /usr/app/profiles.yml

CMD ["dbt", "run"]
