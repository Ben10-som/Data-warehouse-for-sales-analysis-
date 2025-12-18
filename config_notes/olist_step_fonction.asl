{
  "Comment": "Lance dbt run via ECS Fargate et attend la complétion.",
  "StartAt": "RunDbtTask",
  "States": {
    "RunDbtTask": {
      "Type": "Task",
      "Resource": "arn:aws:states:::ecs:runTask.sync",
      "Parameters": {
        "Cluster": "arn:aws:ecs:[VOTRE_RÉGION]:[VOTRE_ID_COMPTE]:cluster/dbt-cluster-olist",
        "TaskDefinition": "arn:aws:ecs:[VOTRE_RÉGION]:[VOTRE_ID_COMPTE]:task-definition/dbt-runner-fargate",
        "LaunchType": "FARGATE",
        "Overrides": {
          "ContainerOverrides": [
            {
              "Name": "dbt-container",
              "Environment": [
                {
                  "Name": "DBT_REDSHIFT_HOST",
                  "Value": "[VOTRE_ENDPOINT_REDSHIFT]"
                },
                {
                  "Name": "DBT_REDSHIFT_USER",
                  "Value": "dbt_user"
                }
                // Le mot de passe est géré via les secrets dans la Task Definition, ne pas le mettre ici.
              ]
            }
          ]
        },
        "NetworkConfiguration": {
          "AwsvpcConfiguration": {
            "Subnets": [
              "[SUBNET_ID_DE_VOTRE_VPC_ACCEDANT_REDSHIFT]"
            ],
            "SecurityGroups": [
              "[SECURITY_GROUP_DU_CONTAINER_PERMETTANT_SORTIE_VERS_REDSHIFT]"
            ],
            "AssignPublicIp": "ENABLED"
          }
        }
      },
      "End": true
    }
  }
}