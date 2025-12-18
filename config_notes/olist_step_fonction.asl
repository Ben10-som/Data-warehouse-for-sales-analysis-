{
  "Comment": "Déclenche dbt avec cooldown de 5 minutes après détection S3",
  "StartAt": "CheckIfAnotherRunIsActive",
  "States": {
    "CheckIfAnotherRunIsActive": {
      "Type": "Task",
      "Resource": "arn:aws:states:::aws-sdk:sfn:listExecutions",
      "Parameters": {
        "StateMachineArn.$": "$$.StateMachine.Id",
        "StatusFilter": "RUNNING",
        "MaxResults": 1
      },
      "ResultPath": "$.running",
      "Next": "IsAlreadyRunning"
    },

    "IsAlreadyRunning": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.running.executions[0]",
          "IsPresent": true,
          "Next": "IgnoreEvent"
        }
      ],
      "Default": "WaitFiveMinutes"
    },

    "IgnoreEvent": {
      "Type": "Succeed"
    },

    "WaitFiveMinutes": {
      "Type": "Wait",
      "Seconds": 300,
      "Next": "RunDbtTask"
    },

    "RunDbtTask": {
      "Type": "Task",
      "Resource": "arn:aws:states:::ecs:runTask.sync",
      "Parameters": {
        "Cluster": "arn:aws:ecs:[VOTRE_RÉGION]:[VOTRE_ID_COMPTE]:cluster/dbt-cluster-olist",
        "TaskDefinition": "arn:aws:ecs:[VOTRE_RÉGION]:[VOTRE_ID_COMPTE]:task-definition/dbt-runner-fargate:2", 
        # Modification de la definition du task ==> nouvelle version car il faut:
         "secrets": [
    {
      "name": "DBT_REDSHIFT_PASSWORD",
      "valueFrom": "arn:aws:secretsmanager:eu-west-3:355142185625:secret:nom-du-secret:password::"
    }
    Le :password:: à la fin de l'ARN est crucial.
     Il indique à ECS d'extraire uniquement la valeur associée à la clé "password" dans le JSON.
        ],  
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