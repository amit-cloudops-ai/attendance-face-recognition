# Part C: Cognito, HTTP API access (JWT authorizer + route integrations),
# private web bucket and CloudFront (OAC).

data "aws_caller_identity" "me" {}

locals {
  prefix         = "attendance-${var.env}-"
  web_url        = "https://${aws_cloudfront_distribution.web.domain_name}"
  cognito_domain = "https://${aws_cognito_user_pool_domain.this.domain}.auth.ap-south-1.amazoncognito.com"
  origins        = concat([local.web_url], var.extra_origins)
  callbacks      = [for o in local.origins : "${o}/index.html"]
}

# ---------- Identity ----------
resource "aws_cognito_user_pool" "this" {
  name                     = "${local.prefix}users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = true
  }
}

resource "aws_cognito_user_group" "admin" {
  name         = "admin"
  user_pool_id = aws_cognito_user_pool.this.id
}

resource "aws_cognito_user_group" "kiosk" {
  name         = "kiosk"
  user_pool_id = aws_cognito_user_pool.this.id
}

resource "aws_cognito_user_pool_domain" "this" {
  domain       = "${local.prefix}${data.aws_caller_identity.me.account_id}"
  user_pool_id = aws_cognito_user_pool.this.id
}

resource "aws_cognito_user_pool_client" "web" {
  name                                 = "${local.prefix}web"
  user_pool_id                         = aws_cognito_user_pool.this.id
  generate_secret                      = false
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["openid", "email"]
  supported_identity_providers         = ["COGNITO"]
  callback_urls                        = local.callbacks
  logout_urls                          = local.callbacks
  explicit_auth_flows                  = ["ALLOW_REFRESH_TOKEN_AUTH"]
  prevent_user_existence_errors        = "ENABLED"
  id_token_validity                    = 60
  refresh_token_validity               = 12

  token_validity_units {
    id_token      = "minutes"
    refresh_token = "hours"
  }
}

# ---------- API access ----------
resource "aws_apigatewayv2_api" "this" {
  name          = "${local.prefix}api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = local.origins
    allow_methods = ["GET", "POST", "DELETE", "OPTIONS"]
    allow_headers = ["authorization", "content-type"]
    max_age       = 3600
  }
}

resource "aws_apigatewayv2_authorizer" "jwt" {
  api_id           = aws_apigatewayv2_api.this.id
  authorizer_type  = "JWT"
  name             = "${local.prefix}jwt"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.web.id]
    issuer   = "https://cognito-idp.ap-south-1.amazonaws.com/${aws_cognito_user_pool.this.id}"
  }
}

resource "aws_apigatewayv2_integration" "route" {
  for_each               = var.route_map
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = each.value.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "route" {
  for_each           = var.route_map
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = each.key
  target             = "integrations/${aws_apigatewayv2_integration.route[each.key].id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_lambda_permission" "route" {
  for_each      = var.route_map
  statement_id  = "AllowApi-${substr(sha1(each.key), 0, 12)}"
  action        = "lambda:InvokeFunction"
  function_name = each.value.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_rate_limit  = var.throttle_rate_limit
    throttling_burst_limit = var.throttle_burst_limit
  }
}

# ---------- Web hosting ----------
resource "aws_s3_bucket" "web" {
  bucket = "${local.prefix}web-${data.aws_caller_identity.me.account_id}"
}

resource "aws_s3_bucket_public_access_block" "web" {
  bucket                  = aws_s3_bucket.web.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "web" {
  bucket = aws_s3_bucket.web.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.kms_key_arn == null ? "AES256" : "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
  }
}

resource "aws_cloudfront_origin_access_control" "web" {
  name                              = "${local.prefix}web"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "web" {
  enabled             = true
  default_root_object = "index.html"
  comment             = "${local.prefix}kiosk-admin-ui"

  origin {
    domain_name              = aws_s3_bucket.web.bucket_regional_domain_name
    origin_id                = "web"
    origin_access_control_id = aws_cloudfront_origin_access_control.web.id
  }

  default_cache_behavior {
    target_origin_id           = "web"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" # Managed-CachingDisabled
    response_headers_policy_id = "67f7725c-6f97-4210-82d7-5512b31e9d03" # Managed-SecurityHeadersPolicy
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

resource "aws_s3_bucket_policy" "web" {
  bucket = aws_s3_bucket.web.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.web.arn}/*"
      Condition = { StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.web.arn } }
    }]
  })
}

# config.json is generated from real outputs, so nothing is hardcoded in the UI.
resource "aws_s3_object" "config" {
  bucket       = aws_s3_bucket.web.id
  key          = "config.json"
  content_type = "application/json"
  content = jsonencode({
    apiBase       = aws_apigatewayv2_api.this.api_endpoint
    cognitoDomain = local.cognito_domain
    clientId      = aws_cognito_user_pool_client.web.id
  })
}
