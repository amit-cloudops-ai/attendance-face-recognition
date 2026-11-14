# Development environment

This root wires the shared foundation, data/automation, recognition and access modules. It exports the combined Part A + Part B API route map, Cognito details and CloudFront site URL.

## Bootstrap prerequisite

The S3 backend bucket is intentionally not created by this root. Follow infra/bootstrap/README.md once, copy backend.hcl.example to backend.hcl, replace the account ID, and initialize with:

```bash
terraform init -backend-config=backend.hcl
terraform validate
terraform plan -var-file=terraform.tfvars
```

Copy terraform.tfvars.example to terraform.tfvars and supply the AWS account ID and alert email. Keep both local files out of Git.

## Cognito callback setup

The example callback and logout URLs use localhost for the first plan. After the first approved apply, read the site_url output and add that exact HTTPS URL to callback_urls and logout_urls in terraform.tfvars, then create a second plan/apply. Update web/config.js with the Cognito domain and app client ID outputs before publishing the static site.

## Safety

No AWS resources are created by init, validate or plan. Do not run terraform apply without explicit approval. The Part C frontend files and deployment workflow remain separate deliverables.
