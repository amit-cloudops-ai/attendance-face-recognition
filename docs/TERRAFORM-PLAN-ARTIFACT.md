# Encrypted Terraform plan artifact lifecycle

**Status:** workflow hardening and documentation only. No Terraform plan was generated and no artifact was uploaded or downloaded.

## Plan creation

1. The plan job runs only on the environment's release branch and uses the plan-specific GitHub environment and AWS role.
2. Terraform writes a binary plan to the runner workspace.
3. age encrypts the plan using the public recipient stored in TF_PLAN_AGE_RECIPIENT.
4. A shell EXIT trap removes the plaintext tfplan even if encryption fails.
5. Only tfplan.age is uploaded as a GitHub Actions artifact, with a one-day retention period and if-no-files-found=error.
6. The artifact name includes environment, workflow run ID and run attempt. This avoids collisions and ambiguity when a workflow run is re-run.

## Apply provenance checks

Before downloading the artifact, the apply job verifies the referenced workflow run:

- The run exists and has conclusion success.
- The run event is workflow_dispatch.
- The run path is exactly .github/workflows/deploy.yml.
- The run branch is develop for dev or main for prod.
- The plan head SHA equals the apply job's current GITHUB_SHA.
- The run attempt is numeric and is used in the artifact name.

The download action is given the exact plan run ID and artifact name including the verified run attempt. A plan from another workflow, branch, commit or run attempt cannot satisfy these checks.

## Decryption and cleanup

- The private age identity is a GitHub environment secret named TF_PLAN_AGE_IDENTITY and is available only to the matching apply environment.
- The identity is written to a runner-temporary file after setting umask 077 and is removed by an EXIT trap.
- The encrypted artifact is removed after decryption.
- The decrypted plan is removed by an always()-guarded cleanup step after apply, including failed apply paths.
- The apply command consumes only the previously reviewed saved plan. It does not create a fresh plan.

Use separate dev and prod age identities/recipients. Rotate them through an owner-approved process; do not place private identities in repository variables, artifacts, logs or source control.

## Access and retention

The artifact is private to the repository's Actions artifact access model. The workflow grants actions:read for run inspection and artifact download; it does not grant artifact write permissions beyond the standard workflow upload action. Retention is one day. Expired artifacts cannot be applied; the operator must generate and review a new plan.

## Residual trust

GitHub environment protection and branch restrictions are required because OIDC trust is bound to the repository/environment subject. Branch protection and CODEOWNERS review of the deployment workflow are required to prevent unreviewed changes to plan/apply logic. The apply job validates the plan run provenance, but reviewer approval and the human review of the Terraform plan remain operational gates.

No AWS or GitHub environment configuration is changed by this document. No deployment has been initiated.
