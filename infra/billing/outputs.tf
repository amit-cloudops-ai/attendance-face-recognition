output "budget_names" {
  description = "Names of the separately managed dev and prod monthly cost budgets."
  value       = [for budget in aws_budgets_budget.monthly : budget.name]
}
