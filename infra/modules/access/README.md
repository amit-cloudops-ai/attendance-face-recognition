# Access and frontend delivery Terraform module

Creates Cognito Hosted UI using authorization-code plus PKCE, the admin and kiosk groups, an API Gateway HTTP API with Cognito JWT authorization, Lambda proxy integrations for the frozen route map, API access logs and throttling, CloudFront with a private S3 OAC origin and uncached /api/* origin, static directory rewrites, security headers, and the web bucket policy.

## Inputs

The caller supplies the route map from Part A and Part B, the private web bucket details, AWS account ID, and exact Cognito callback/logout/CORS origins. Start with localhost callback URLs. After the first infrastructure plan/apply, add the CloudFront site URL to callback and logout URLs and apply the change.

## Authentication and authorization

Cognito issues access tokens. API Gateway validates JWT signature, issuer and audience. Each Lambda continues to enforce its own required Cognito group (admin, or kiosk/admin); API Gateway does not replace that group check. MFA is enabled as an optional software-token capability; it is not forced per group in this v1.

## CloudFront

The browser uses one origin: static pages at / and API routes at /api/*. API responses are never cached. Static directory paths are rewritten to their index.html object. The web bucket policy allows only the CloudFront distribution OAC and denies insecure transport.

## Safety

This module only defines infrastructure. Do not run terraform apply without explicit deployment approval.
