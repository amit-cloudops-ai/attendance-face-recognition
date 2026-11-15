import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_billing_root_has_one_project_tag_filtered_budget():
    source = (ROOT / "infra/billing/main.tf").read_text(encoding="utf-8")
    assert 'resource "aws_ce_cost_allocation_tag" "project"' in source
    assert 'tag_key = "Project"' in source
    assert 'status  = "Active"' in source
    assert source.count('resource "aws_budgets_budget"') == 1
    assert 'name         = "attendance-project-monthly-cost"' in source
    assert 'metrics      = ["UnblendedCost"]' in source
    assert 'key    = "Project"' in source
    assert 'values = ["attendance"]' in source
    assert 'depends_on = [aws_ce_cost_allocation_tag.project]' in source
    assert "attendance-dev-monthly-cost" not in source
    assert "attendance-prod-monthly-cost" not in source


def test_billing_iam_policies_are_scoped_to_project_budget_and_tag_actions():
    account_id = "123456789012"
    plan_path = ROOT / "infra/policies/github-plan-billing-core.json.tftpl"
    apply_path = ROOT / "infra/policies/github-apply-billing-core.json.tftpl"
    plan = json.loads(plan_path.read_text(encoding="utf-8").replace("${account_id}", account_id))
    apply = json.loads(apply_path.read_text(encoding="utf-8").replace("${account_id}", account_id))
    budget_arn = f"arn:aws:budgets::{account_id}:budget/attendance-project-monthly-cost"

    plan_statements = {statement["Sid"]: statement for statement in plan["Statement"]}
    apply_statements = {statement["Sid"]: statement for statement in apply["Statement"]}
    assert plan_statements["BillingBudgetRead"]["Resource"] == budget_arn
    assert apply_statements["BillingBudgetRead"]["Resource"] == budget_arn
    assert apply_statements["BillingBudgetManage"]["Resource"] == budget_arn
    assert plan_statements["CostAllocationTagRead"]["Action"] == "ce:ListCostAllocationTags"
    assert apply_statements["CostAllocationTagRead"]["Action"] == "ce:ListCostAllocationTags"
    assert apply_statements["CostAllocationTagActivate"]["Action"] == "ce:UpdateCostAllocationTagsStatus"
    assert "ce:UpdateCostAllocationTagsStatus" not in {
        action
        for statement in plan["Statement"]
        for action in (
            statement["Action"] if isinstance(statement["Action"], list) else [statement["Action"]]
        )
    }


def test_cost_sheet_explains_project_budget_scope_and_correct_rekognition_free_tier():
    source = (ROOT / "docs/COST.md").read_text(encoding="utf-8")
    assert "Project=attendance" in source
    assert "1,000 images/month in **each** of Group 1 and Group 2" in source
    assert "not 5,000 total" in source
    assert "not an automatic spending cap" in source
