output "budget_name" {
  description = "Name of the project-tag-filtered monthly attendance cost budget."
  value       = aws_budgets_budget.project_monthly.name
}

output "cost_allocation_tag" {
  description = "Cost allocation tag activated for project-level budget attribution."
  value       = aws_ce_cost_allocation_tag.project.tag_key
}
