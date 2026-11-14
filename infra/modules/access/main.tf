locals {
  region            = "ap-south-1"
  cognito_prefix    = "attendance-${var.account_id}-${var.env}"
  cognito_base_url  = "${aws_cognito_user_pool_domain.hosted.domain}.auth.ap-south-1.amazoncognito.com"
  api_origin_domain = replace(aws_apigatewayv2_api.http.api_endpoint, "https://", "")
  api_log_format     = jsonencode({
    requestId      = "$context.requestId"
    routeKey       = "$context.routeKey"
    status         = "$context.status"
    responseLength = "$context.responseLength"
    sourceIp       = "$context.identity.sourceIp"
    userAgent      = "$context.identity.userAgent"
  })
  web_content_security_policy = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self' https://cognito-idp.ap-south-1.amazonaws.com https://${local.cognito_base_url}; form-action 'self' https://${local.cognito_base_url}; frame-ancestors 'none'; base-uri 'self'; object-src 'none'"
}

resource "aws_cognito_user_pool" "main" {
  name                     = "attendance-${var.env}-users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  mfa_configuration        = "OPTIONAL"

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }

  software_token_mfa_configuration {
    enabled = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  schema {
    attribute_data_type = "String"
    name                = "email"
    required            = true
    mutable             = true
  }

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "access"
  }
}

resource "aws_cognito_user_group" "admin" {
  name         = "admin"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Human administrators with access to employee and reporting operations."
  precedence   = 1
}

resource "aws_cognito_user_group" "kiosk" {
  name         = "kiosk"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Kiosk identities allowed to submit and poll attendance scans."
  precedence   = 2
}

resource "aws_cognito_user_pool_domain" "hosted" {
  domain       = local.cognito_prefix
  user_pool_id = aws_cognito_user_pool.main.id
}

resource "aws_cognito_user_pool_client" "web" {
  name                                 = "attendance-${var.env}-web"
  user_pool_id                         = aws_cognito_user_pool.main.id
  generate_secret                      = false
  enable_token_revocation              = true
  prevent_user_existence_errors        = "ENABLED"
  explicit_auth_flows                  = ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]
  callback_urls                        = var.callback_urls
  logout_urls                          = var.logout_urls
  access_token_validity                = 60
  id_token_validity                    = 60
  refresh_token_validity               = 30
  read_attributes                      = ["email", "email_verified"]
  write_attributes                     = ["email"]

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/apigateway/attendance-${var.env}-http-api"
  retention_in_days = 30

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "access"
  }
}

resource "aws_apigatewayv2_api" "http" {
  name          = "attendance-${var.env}-http-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = var.allowed_origins
    allow_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allow_headers = ["Authorization", "Content-Type", "Accept"]
    max_age       = 300
  }

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "access"
  }
}

resource "aws_apigatewayv2_authorizer" "jwt" {
  api_id           = aws_apigatewayv2_api.http.id
  name             = "attendance-${var.env}-cognito-jwt"
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.web.id]
    issuer   = "https://cognito-idp.ap-south-1.amazonaws.com/${aws_cognito_user_pool.main.id}"
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  for_each = var.api_routes

  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_method     = "POST"
  integration_uri        = each.value.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 30000
}

resource "aws_apigatewayv2_route" "api" {
  for_each = var.api_routes

  api_id             = aws_apigatewayv2_api.http.id
  route_key          = each.key
  target             = "integrations/${aws_apigatewayv2_integration.lambda[each.key].id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_lambda_permission" "api" {
  for_each = var.api_routes

  statement_id  = "AllowHttpApi-${replace(replace(replace(replace(each.key, "/", "-"), " ", "-"), "{", ""), "}", "")}"
  action        = "lambda:InvokeFunction"
  function_name = each.value.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    detailed_metrics_enabled = true
    throttling_burst_limit   = 20
    throttling_rate_limit    = 10
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api.arn
    format          = local.api_log_format
  }

  depends_on = [aws_apigatewayv2_route.api]
}

resource "aws_cloudfront_origin_access_control" "web" {
  name                              = "attendance-${var.env}-web-oac"
  description                       = "CloudFront access to the private attendance web bucket."
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_cache_policy" "static" {
  name        = "attendance-${var.env}-static-cache"
  comment     = "Cache fingerprinted static assets while keeping query/cookie/header variants out of the key."
  min_ttl     = 0
  default_ttl = 86400
  max_ttl     = 31536000

  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_brotli = true
    enable_accept_encoding_gzip   = true

    cookies_config {
      cookie_behavior = "none"
    }

    headers_config {
      header_behavior = "none"
    }

    query_strings_config {
      query_string_behavior = "none"
    }
  }
}

resource "aws_cloudfront_cache_policy" "api" {
  name        = "attendance-${var.env}-api-no-cache"
  comment     = "Never cache authenticated API responses."
  min_ttl     = 0
  default_ttl = 0
  max_ttl     = 0

  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_brotli = false
    enable_accept_encoding_gzip   = false

    cookies_config {
      cookie_behavior = "none"
    }

    headers_config {
      header_behavior = "none"
    }

    query_strings_config {
      query_string_behavior = "none"
    }
  }
}

resource "aws_cloudfront_origin_request_policy" "api" {
  name    = "attendance-${var.env}-api-origin-requests"
  comment = "Forward bearer authorization, cookies and query strings to the HTTP API."

  cookies_config {
    cookie_behavior = "all"
  }

  headers_config {
    header_behavior = "allViewerExceptHostHeader"
  }

  query_strings_config {
    query_string_behavior = "all"
  }
}

resource "aws_cloudfront_response_headers_policy" "security" {
  name = "attendance-${var.env}-security-headers"

  security_headers_config {
    content_security_policy {
      content_security_policy = local.web_content_security_policy
      override                = true
    }

    content_type_options {
      override = true
    }

    frame_options {
      frame_option = "DENY"
      override     = true
    }

    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }

    strict_transport_security {
      access_control_max_age_sec = 63072000
      include_subdomains         = true
      preload                    = true
      override                   = true
    }
  }

  custom_headers_config {
    items {
      header   = "Permissions-Policy"
      value    = "camera=(self), microphone=(), geolocation=()"
      override = true
    }
  }
}

resource "aws_cloudfront_function" "directory_index" {
  name    = "attendance-${var.env}-directory-index"
  runtime = "cloudfront-js-1.0"
  publish = true
  comment = "Rewrite static directory routes to their index.html object."

  code = <<-JAVASCRIPT
    function handler(event) {
      var request = event.request;
      if (request.uri.endsWith("/")) {
        request.uri += "index.html";
      } else if (!request.uri.split("/").pop().includes(".")) {
        request.uri += "/index.html";
      }
      return request;
    }
  JAVASCRIPT
}

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Attendance kiosk, admin and API distribution."
  default_root_object = "index.html"
  price_class         = "PriceClass_200"

  origin {
    domain_name              = var.web_bucket_regional_domain_name
    origin_id                = "web"
    origin_access_control_id = aws_cloudfront_origin_access_control.web.id

    s3_origin_config {
      origin_access_identity = ""
    }
  }

  origin {
    domain_name = local.api_origin_domain
    origin_id   = "api"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id           = "web"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD", "OPTIONS"]
    compress                   = true
    cache_policy_id            = aws_cloudfront_cache_policy.static.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.directory_index.arn
    }
  }

  ordered_cache_behavior {
    path_pattern               = "/api/*"
    target_origin_id           = "api"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = aws_cloudfront_cache_policy.api.id
    origin_request_policy_id   = aws_cloudfront_origin_request_policy.api.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id
  }

  custom_error_response {
    error_code            = 403
    response_code         = 404
    response_page_path    = "/404.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 404
    response_page_path    = "/404.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
    minimum_protocol_version       = "TLSv1.2_2021"
  }

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "access"
  }
}

data "aws_iam_policy_document" "web_bucket" {
  statement {
    sid    = "AllowCloudFrontOACRead"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    actions   = ["s3:GetObject"]
    resources = ["${var.web_bucket_arn}/*"]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }

  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions   = ["s3:*"]
    resources = [var.web_bucket_arn, "${var.web_bucket_arn}/*"]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "web" {
  bucket = var.web_bucket_name
  policy = data.aws_iam_policy_document.web_bucket.json
}
