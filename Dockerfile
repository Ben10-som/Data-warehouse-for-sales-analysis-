FROM python:3.11-slim

# Définir l'environnement de travail dans le conteneur
WORKDIR /usr/app

# Copier le fichier des dépendances Python
COPY requirement.txt .

# Installer dbt-redshift et les autres dépendances
RUN pip install --no-cache-dir -r requirement.txt

# Copier l'intégralité de votre projet dbt dans le conteneur
COPY . .

# Définir la commande par défaut : dbt run
# Note : Nous injecterons le fichier profiles.yml via le mécanisme de secrets/variables d'environnement 
CMD ["dbt", "run"]