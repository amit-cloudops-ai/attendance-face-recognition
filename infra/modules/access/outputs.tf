output "api_id" {
  value = aws_apigatewayv2_api.this.id
}

output "api_endpoint" {
  value = aws_apigatewayv2_api.this.api_endpoint
}

output "authorizer_id" {
  value = aws_apigatewayv2_authorizer.jwt.id
}

output "user_pool_id" {
  value = aws_cognito_user_pool.this.id
}

output "client_id" {
  value = aws_cognito_user_pool_client.web.id
}

output "cognito_domain" {
  value = local.cognito_domain
}

output "web_bucket" {
  value = aws_s3_bucket.web.id
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.web.id
}

output "web_url" {
  description = "Origin to allow in CORS on the raw-capture bucket (Part A / lead)."
  value       = local.web_url
}
