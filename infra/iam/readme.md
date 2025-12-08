

# README – IAM du Projet Data Warehouse

Ce dossier contient les ressources IAM nécessaires pour la gestion des accès et des workflows de traitement de données du projet .

L’objectif est de fournir une base IAM cohérente, segmentée, auditable et conforme au principe du moindre privilège, tout en permettant aux administrateurs du projet de travailler efficacement.

---


### **1) Pollicy_OlistDW-AdminProjectPolicy.json**

Cette policy regroupe l’ensemble des **droits d’administration** nécessaires au pilotage du projet.
Elle donne un accès large aux services critiques :

* Amazon S3
* AWS Glue
* Amazon Redshift et Redshift Serverless
* AWS CloudFormation
* certaines opérations IAM (création, suppression, attachement de policy)

Ces privilèges sont **filtrés par tag**, ce qui limite leur portée aux ressources portant :

```
Project = OlistDWSENSAE2025
```

Elle inclut également des autorisations globales indispensables, comme `iam:PassRole`, la lecture des rôles IAM, ou encore `s3:ListAllMyBuckets`.

Cette politique est pensée pour être attachée au **groupe des administrateurs du projet**.
Elle inclut également des autorisations globales indispensables pour assurer le bon fonctionnement du projet :

-  permet aux services (Glue, Redshift, CloudFormation) d’assumer un rôle IAM afin d’exécuter leurs tâches. Sans cette permission, les workflows ne pourraient pas déléguer correctement les droits nécessaires.
- Lecture des rôles IAM : offre une visibilité sur les rôles existants, essentielle pour auditer, vérifier et attacher les bons rôles aux services.
- donne une vue d’ensemble des buckets disponibles dans le compte, utile pour identifier rapidement les ressources de stockage et valider leur existence avant usage.


### **2) Pollicy_OlistDW-ExecutionPolicy.json**

La policy ExecutionPolicy est également attachée au groupe des administrateurs du projet et constitue le complément opérationnel indispensable à la gouvernance. Elle ne vise pas à donner de nouveaux privilèges d’infrastructure, mais à permettre aux administrateurs de mettre en mouvement les workflows de données et d’exploiter les ressources du Data Warehouse. Grâce à elle, les administrateurs peuvent lancer et suivre les jobs AWS Glue, consulter les bases et tables du Glue Catalog, exécuter des requêtes SQL via Redshift Data API et en récupérer les résultats, ainsi que lire et lister les objets stockés dans les buckets S3 du projet, notamment dans les zones Bronze et Bronze Parquet.  sans elle, les administrateurs auraient la capacité de déployer et sécuriser l’infrastructure, mais resteraient incapables de déclencher les traitements . En associant AdminProjectPolicy et ExecutionPolicy, le groupe des administrateurs dispose à la fois du pouvoir de gouvernance et des moyens d’action opérationnelle, dans un cadre sécurisé et conforme au principe du moindre privilège.

---