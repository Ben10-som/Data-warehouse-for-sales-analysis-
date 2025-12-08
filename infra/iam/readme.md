## Organisation des utilisateurs IAM

Nous allons utiliser le service **AWS Organizations** pour structurer la gestion des comptes et des permissions.  
À l’intérieur de cette organisation, nous créerons un **groupe d’utilisateurs superAdmin** afin de centraliser les droits élevés et garantir une administration cohérente.  

Cette approche permet :  
- Une gestion simplifiée des accès et des rôles.  
- Une séparation claire entre les utilisateurs standards et les administrateurs.  
- Une meilleure conformité avec les bonnes pratiques de sécurité AWS.  

Problème initial résolu : l’absence de stratégie claire pour l’organisation des utilisateurs IAM.  