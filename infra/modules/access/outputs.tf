output "api_id" {
  description = "API Gateway HTTP API ID."
  value       = aws_apigatewayv2_api.http.id
}

output "api_endpoint" {
  description = "Direct API Gateway endpoint; browser clients should use the same-origin CloudFront /api path."
  value       = aws_apigatewayv2_api.http.api_endpoint
}

output "user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "user_pool_client_id" {
  value = aws_cognito_user_pool_client.web.id
}

output "user_pool_issuer" {
  value = "https://cognito-idp.us-east-1.amazonaws.com/${aws_cognito_user_pool.main.id}"
}

output "cognito_domain" {
  value = "https://${local.cognito_base_url}"
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.site.id
}

output "cloudfront_domain_name" {
  value = aws_cloudfront_distribution.site.domain_name
}

output "site_url" {
  value = "https://${aws_cloudfront_distribution.site.domain_name}"
}
