import json
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key


def json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def make_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "https://www.sandeep-cloud.com",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,Idempotency-Key",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            },
        "body": json.dumps(body, default=json_default),
    }

def lambda_handler(event, context):
    authorizer = (event.get("requestContext") or {}).get("authorizer") or {}
    claims = authorizer.get("claims") or {}
    customer_sub = claims.get("sub")

    if not customer_sub:
        return make_response(401, {"message": "Unauthorized"})

    table = boto3.resource("dynamodb").Table(
        os.environ["ORDERS_TABLE_NAME"]
    )
    customer_pk = f"CUSTOMER#{customer_sub}"
    path_parameters = event.get("pathParameters") or {}
    order_id = path_parameters.get("orderId")

    if order_id:
        result = table.get_item(
            Key={
                "PK": customer_pk,
                "SK": f"ORDER#{order_id}",
            }
        )
        order = result.get("Item")

        if order is None:
            return make_response(404, {"message": "Order not found"})

        return make_response(200, order)

    result = table.query(
        KeyConditionExpression=Key("PK").eq(customer_pk)
    )
    return make_response(200, {"items": result.get("Items", [])})
