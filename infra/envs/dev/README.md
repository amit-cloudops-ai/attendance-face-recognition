# Development environment

This root wires the shared foundation, data/automation and recognition modules. It exports the combined Part A + Part B API route map for the Part C access module.

## Bootstrap prerequisite

The S3 backend bucket is intentionally not created by this root. Follow `infra/bootstrap/README.md` once, copy `backend.hcl.example` to `backend.hcl`, replace the account ID, and initialize with:

```bash
terraform init -backend-config=backend.hcl
terraform validate
terraform plan -var-file=terraform.tfvars
```

Copy `terraform.tfvars.example` to `terraform.tfvars` and supply the AWS account ID and alert email. Keep both local files out of Git.

## Safety

No AWS resources are created by `init`, `validate` or `plan`. Do not run `terraform apply` without explicit approval. Part C still needs to add Cognito, HTTP API, CloudFront OAC, web bucket policy and frontend deployment wiring.
