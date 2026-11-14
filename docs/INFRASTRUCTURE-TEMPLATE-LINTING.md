# Infrastructure template linting audit

**Status:** complete for the repository's current infrastructure formats. No CloudFormation or SAM template is present.

## Repository inventory

A recursive Git tree audit of the Phase B branch found 220 paths and no:
- template.yaml or template.yml
- template.json
- samconfig.toml
- CloudFormation template directory
- Serverless Framework template

The infrastructure is Terraform. IAM boundaries, GitHub OIDC trust documents, and dev/prod plan/apply permissions are rendered from 28 JSON policy templates ending in .json.tftpl.

## Existing CI validation

- Terraform formatting and validation run for all four modules (foundation, data, recognition, access), dev/prod environment roots and the separate billing root.
- Dev/prod provider lockfiles are checked with terraform init -lockfile=readonly.
- GitHub Actions workflow YAML is parsed in CI.
- All policy templates are rendered with dummy account/state-bucket values and parsed as JSON.
- Each managed policy is checked against the 6,144-character IAM size limit.
- Dedicated validators check action/resource scope, dev/prod isolation, permissions boundaries, PassRole service conditions, state and lockfile access, KMS ViaService/alias constraints, OIDC subjects and plan artifact controls.

## Future CloudFormation/SAM guard

CI now scans the repository for CloudFormation/SAM template filenames and known template directories. If one is introduced, CI fails with an explicit message until an appropriate cfn-lint and/or sam validate --lint step is added. This avoids silently introducing an unvalidated infrastructure template.

## Decision

Do not install cfn-lint or AWS SAM CLI for the current repository because there is no CloudFormation or SAM source to validate. Continue validating Terraform and the actual JSON policy templates with their native tools. Revisit this task if a template.yaml/template.yml or CloudFormation stack is added.
