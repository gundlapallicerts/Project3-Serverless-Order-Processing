# Project 3 Architecture

This diagram shows the intended serverless order-processing design. Project 1
continues to host the Shopme storefront; Project 3 provides the API and backend.

```mermaid
flowchart LR
    subgraph Client["Customer"]
        Browser["Browser"]
        Storefront["Shopme storefront<br/>Project 1: CloudFront + S3"]
    end

    subgraph Identity["Identity"]
        Cognito["Amazon Cognito<br/>User Pool + app client"]
    end

    subgraph Project3["Project 3: AWS serverless backend"]
        WAF["AWS WAF<br/>Web ACL"]
        API["API Gateway REST API<br/>Regional • prod stage"]
        Authorizer["Cognito User Pool authorizer"]

        ListProducts["ListProducts<br/>AWS Lambda"]
        CreateOrder["CreateOrder<br/>AWS Lambda"]
        ReadOrders["ReadOrders<br/>AWS Lambda"]

        Products[("Products table<br/>CatalogIndex")]
        Orders[("Orders table<br/>PK: customer • SK: order")]
    end

    Browser -->|"Open storefront"| Storefront
    Storefront -->|"Serve website"| Browser
    Browser -->|"Sign in"| Cognito
    Cognito -->|"Tokens"| Browser

    Browser -->|"HTTPS API requests"| WAF
    WAF -->|"Filter, then forward"| API
    Authorizer -.->|"Protects order routes"| API

    API -->|"GET /products • public"| ListProducts
    API -->|"POST /orders • authenticated"| CreateOrder
    API -->|"GET /orders and /orders/{orderId}<br/>• authenticated"| ReadOrders

    ListProducts -->|"Query active catalog"| Products
    CreateOrder -->|"Look up trusted prices"| Products
    CreateOrder -->|"Write order"| Orders
    ReadOrders -->|"Read customer orders"| Orders
```

## Implementation status

The deployed stack includes the Regional API Gateway, Cognito authorizer, WAF
association, DynamoDB tables, and product/order Lambda handlers. The public
product endpoint and Cognito Hosted UI sign-up have been tested. The Project 1
page has local changes for PKCE sign-in, authenticated checkout, and order
history; those changes still need to be uploaded and verified end to end. The
latest API Gateway error-response CORS changes also need to be deployed.
