import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError


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


def order_response(status_code, order):
    public_order = dict(order)
    public_order.pop("requestHash", None)
    return make_response(status_code, public_order)


def lambda_handler(event, context):
    claims = (
        (event.get("requestContext") or {})
        .get("authorizer", {})
        .get("claims", {})
    )
    customer_sub = claims.get("sub")

    if not customer_sub:
        return make_response(401, {"message": "Unauthorized"})

    headers = event.get("headers") or {}
    idempotency_key = (
        headers.get("Idempotency-Key")
        or headers.get("idempotency-key")
    )
    if not idempotency_key or len(idempotency_key) > 128:
        return make_response(
            400,
            {"message": "A valid Idempotency-Key header is required"},
        )

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return make_response(400, {"message": "Request body must be valid JSON"})

    if not isinstance(body, dict):
        return make_response(400, {"message": "Request body must be a JSON object"})

    requested_items = body.get("items")
    if not isinstance(requested_items, list) or not requested_items:
        return make_response(400, {"message": "items must be a non-empty list"})

    normalized_items = []
    seen_product_ids = set()

    for item in requested_items:
        if not isinstance(item, dict):
            return make_response(400, {"message": "Each item must be an object"})

        product_id = item.get("productId")
        quantity = item.get("quantity")

        if not isinstance(product_id, str) or not product_id:
            return make_response(400, {"message": "Each item needs a productId"})

        if type(quantity) is not int or quantity < 1:
            return make_response(400, {"message": "quantity must be a positive integer"})

        if product_id in seen_product_ids:
            return make_response(400, {"message": "Duplicate productIds are not allowed"})

        seen_product_ids.add(product_id)
        normalized_items.append({
            "productId": product_id,
            "quantity": quantity,
        })

    request_hash = hashlib.sha256(
        json.dumps(
            normalized_items,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    orders_table = boto3.resource("dynamodb").Table(
        os.environ["ORDERS_TABLE_NAME"]
    )
    customer_pk = f"CUSTOMER#{customer_sub}"
    order_id = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:32]
    order_key = {
        "PK": customer_pk,
        "SK": f"ORDER#{order_id}",
    }

    existing = orders_table.get_item(Key=order_key).get("Item")
    if existing:
        if existing.get("requestHash") != request_hash:
            return make_response(
                409,
                {"message": "Idempotency-Key was already used for a different request"},
            )
        return order_response(200, existing)

    products_table = boto3.resource("dynamodb").Table(
        os.environ["PRODUCTS_TABLE_NAME"]
    )

    order_items = []
    total_cents = 0

    for requested_item in normalized_items:
        product = products_table.get_item(
            Key={"productId": requested_item["productId"]}
        ).get("Item")

        if not product or product.get("catalogStatus") != "ACTIVE":
            return make_response(
                400,
                {"message": f"Unknown or inactive product: {requested_item['productId']}"},
            )

        price = product.get("priceCents")
        if not isinstance(price, (int, Decimal)) or int(price) < 0:
            return make_response(
                500,
                {"message": "Product has an invalid stored price"},
            )

        unit_price_cents = int(price)
        quantity = requested_item["quantity"]
        total_cents += unit_price_cents * quantity

        order_items.append({
            "productId": requested_item["productId"],
            "quantity": quantity,
            "unitPriceCents": unit_price_cents,
        })

    order = {
        **order_key,
        "orderId": order_id,
        "status": "PLACED",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "currency": "USD",
        "items": order_items,
        "totalCents": total_cents,
        "requestHash": request_hash,
    }

    try:
        orders_table.put_item(
            Item=order,
            ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise

        existing = orders_table.get_item(Key=order_key).get("Item")
        if not existing:
            raise

        if existing.get("requestHash") != request_hash:
            return make_response(
                409,
                {"message": "Idempotency-Key was already used for a different request"},
            )
        return order_response(200, existing)

    return order_response(201, order)
