# AWS Cost Sheet

**Assumptions:** 100 employees, 2 scans per employee per day (clock-in, clock-out), 22 working days/month, region us-east-1, 3 enrolled photos per employee, no free tier (worst case). **Prices below are estimates; confirm every line in the AWS Pricing Calculator for us-east-1 and attach the saved estimate link before submission.**

| Item | Calculation | Est. monthly |
|---|---|---|
| Rekognition scan calls | 100 x 2 x 22 = 4,400 scans x 2 API calls (DetectFaces + SearchFacesByImage) = 8,800 images at about 0.001 USD | about 8.80 USD |
| Rekognition enrollment | 300 IndexFaces (one-time) at about 0.001 USD | about 0.30 USD (once) |
| Rekognition face storage | 300 faces at about 0.00001 USD | under 0.01 USD |
| KMS | 1 customer key + requests | about 1.00 to 1.50 USD |
| Lambda | about 5k invocations + jobs + keep-warm | under 0.50 USD (inside free tier) |
| API Gateway (HTTP) | about 20k requests incl. polling | under 0.10 USD |
| DynamoDB on-demand | tens of thousands of requests | under 0.50 USD |
| S3 + CloudFront | MBs of storage, tiny transfer | under 0.50 USD |
| Cognito | under 10 active users | 0 USD |
| CloudWatch logs/alarms | 30-day retention, about 10 alarms | about 1.00 USD |
| EventBridge Scheduler, SNS | tiny | 0 USD |
| **Total (worst case)** | | **about 12 to 14 USD / month** |

**Budget and cost-control caveats**
- The estimate is for one active environment at the stated workload. Running dev and prod simultaneously at similar volume can approach twice the application-service cost.
- The current two $15 budget resources have no environment cost filters; both track total account spend and duplicate account-wide alerts. Resolve the budget scope before applying the billing root.
- AWS Budgets notifications are not a hard spending cap. AWS reports that budget data is refreshed periodically and notifications can arrive after charges have accrued; see [AWS Budgets best practices](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-best-practices.html).

**Sensitivities**
- 30-day month instead of 22 working days: Rekognition about 12 USD.
- Skip separate DetectFaces (rely on SearchFacesByImage only): halves Rekognition cost, loses the multiple-faces and quality checks. We keep both for correctness.
- New AWS accounts may have a Rekognition free tier (about 5,000 images/month for the first 12 months): cost drops to about 4 to 5 USD. Verify eligibility.
- Scaling: Rekognition is about 0.001 USD per call; 1,000 employees would be roughly 10x.
- Guardrails: AWS Budget 15 USD with alerts at 80% and 100%; reserved concurrency on `recognize`.
