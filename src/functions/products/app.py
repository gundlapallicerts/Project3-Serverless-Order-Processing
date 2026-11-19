import json
import os

import boto3
from boto3.dynamodb.conditions import Key


def lambda_handler(event, context):
    table = boto3.resource("dynamodb").Table(
        os.environ["PRODUCTS_TABLE_NAME"]
    )

    response = table.query(
        IndexName="CatalogIndex",
        KeyConditionExpression=Key("catalogStatus").eq("ACTIVE"),
    )

    items = response.get("Items", [])
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "https://www.sandeep-cloud.com",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,Idempotency-Key",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(items, default=int),
    }
