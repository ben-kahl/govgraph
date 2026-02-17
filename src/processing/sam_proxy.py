import os
import json
import requests
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_secret(secret_arn):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_arn)
    return json.loads(response['SecretString'])


def lambda_handler(event, context):
    """
    Proxy Lambda to call SAM.gov API from outside VPC.
    """
    secret_arn = os.environ.get("SAM_API_KEY_SECRET_ARN")
    if not secret_arn:
        return {"statusCode": 500, "body": json.dumps({"error": "SAM_API_KEY_SECRET_ARN not set"})}

    try:
        secrets = get_secret(secret_arn)
        api_key = secrets.get('api_key')
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": f"Failed to fetch secret: {str(e)} "})}

    uei = event.get('ueiSAM')
    name = event.get('entityName')

    params = {
        "api_key": api_key,
    }

    if uei:
        params["ueiSAM"] = uei
    elif name:
        params["entityName"] = name
    else:
        return {"statusCode": 400, "body": json.dumps({"error": "Missing ueiSAM or entityName"})}

    url = "https://api.sam.gov/entity-information/v3/entities"

    try:
        logger.info(f"Calling SAM.gov API for {
                    'UEI: ' + uei if uei else 'Name: ' + name}")
        response = requests.get(url, params=params, timeout=10)
        return {
            "statusCode": response.status_code,
            "body": response.text
        }
    except Exception as e:
        logger.error(f"SAM.gov API request failed: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
