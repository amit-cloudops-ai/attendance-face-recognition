from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_required_docs_exist():
    names = ["SPEC.md", "contracts.md", "STATUS.md", "AI_CONTEXT.md", "ARCHITECTURE.md", "TEAM_BRIEF.md"]
    for name in names:
        assert (ROOT / "docs" / name).exists(), f"missing docs/{name}"



def test_access_module_uses_manifest_region_and_service_correct_kms_policy():
    access_main = (ROOT / "infra/modules/access/main.tf").read_text(encoding="utf-8")
    access_variables = (ROOT / "infra/modules/access/variables.tf").read_text(encoding="utf-8")
    web_start = access_main.index('data "aws_iam_policy_document" "web_bucket"')
    key_start = access_main.index('data "aws_iam_policy_document" "attendance_kms_key"')
    key_end = access_main.index('resource "aws_kms_key_policy" "attendance"')
    web_policy = access_main[web_start:key_start]
    key_policy = access_main[key_start:key_end]

    assert 'variable "region"' in access_variables
    assert 'region = "us-east-1"' not in access_main
    assert "local.region" not in access_main
    assert "kms:" not in web_policy
    assert 'sid    = "AllowDynamoDBUseOfKeyThroughService"' in key_policy
    assert 'variable = "kms:ViaService"' in key_policy
    assert 'values   = ["dynamodb.${var.region}.amazonaws.com"]' in key_policy


def test_environment_roots_pass_manifest_region_to_access_module():
    for environment in ("dev", "prod"):
        source = (ROOT / f"infra/envs/{environment}/main.tf").read_text(encoding="utf-8")
        access_call = source.split('module "access" {', 1)[1].split("\\n}", 1)[0]
        assert "region                          = local.deployment_region" in access_call
