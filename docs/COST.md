# AWS Cost Sheet

**Workload model:** 100 employees, 2 scans per employee per working day (clock-in and clock-out), 22 working days/month, 3 enrolled photos per employee, region us-east-1. The recurring estimate does **not** rely on the 12-month AWS Free Tier. It assumes direct Cognito user-pool sign-in on the Lite or Essentials tier and no paid SMS MFA or Cognito Plus features.

| Item | Calculation / assumption | Estimated monthly |
|---|---|---:|
| Rekognition scan calls | 100 × 2 × 22 = 4,400 scans. Each scan uses one Group 1 SearchFacesByImage call and one Group 2 DetectFaces call. At $0.001/image for the first 1M images in each group: 4,400 × $0.001 × 2 | **$8.80** |
| Rekognition enrollment | 300 IndexFaces calls × $0.001; one-time enrollment, not recurring | **$0.30 one-time** |
| Rekognition face metadata storage | 300 face vectors × $0.00001 per vector/month | **about $0.003** |
| KMS | One customer-managed key at $1/month plus a low request volume | **$1.00–$1.50** |
| Lambda | Approximately 30,000 recognition, scheduled keep-warm and reporting invocations/month; modeled at 512 MB and no more than 1 second average duration | **under $0.50** |
| API Gateway HTTP API | About 20,000 requests/month | **under $0.10** |
| DynamoDB on-demand | Attendance, employee, settings, audit and report metadata traffic at this workload | **under $0.50** |
| S3 + CloudFront | Small static site, short-lived raw photos, compact reports and low traffic | **under $0.50** |
| Cognito | About 100 direct user-pool MAUs on Lite or Essentials | **$0 at current 10,000-MAU free tier** |
| CloudWatch | 30-day log retention and about 10 standard alarms; depends on log ingestion | **about $1.00** |
| EventBridge Scheduler / SNS | Low-volume scheduled invocations and notifications | **under $0.10** |
| **Estimated recurring total** | Excludes taxes, support, unrelated account resources, one-time enrollment and unexpected traffic | **about $12–$14/month** |

## Pricing notes and sensitivities

- Rekognition bills each API call against its own image group. Calling DetectFaces and SearchFacesByImage on the same capture counts as two image analyses. AWS's current pricing page lists both groups at $0.001/image for the first million images in each group. See [Amazon Rekognition pricing](https://aws.amazon.com/rekognition/pricing/).
- Rekognition's 12-month Free Tier is 1,000 images/month in **each** of Group 1 and Group 2, not 5,000 total. If this account is still eligible, the modeled 4,400 calls in each group would reduce the image-analysis portion by about $2/month, from $8.80 to $6.80. The estimate above does not assume eligibility.
- Cognito Lite and Essentials currently include 10,000 direct user-pool MAUs per account/organization each month, and this free tier does not automatically expire after 12 months. Plus has no MAU free tier. SMS MFA and SES email delivery can incur separate charges. See [Amazon Cognito pricing](https://aws.amazon.com/cognito/pricing/).
- The KMS estimate uses the current $1/month customer-managed key charge plus request charges; actual KMS request count depends on S3 and DynamoDB activity.
- A 30-day scanning month (including weekends) raises Rekognition image analysis to about $12/month by itself. The $12–$14 baseline assumes 22 working days.
- Skipping DetectFaces would reduce the image-analysis charge, but removes the current multiple-face and image-quality checks. We keep both APIs for correctness.
- 1,000 employees at the same attendance pattern would increase the Rekognition portion roughly tenfold; the $15 target would no longer be appropriate.

## Budget guardrail

The billing root manages one **project-scoped** monthly budget named `attendance-project-monthly-cost`, limited to $15, with actual-spend notifications at 80% and 100%. It filters on the `Project=attendance` cost-allocation tag shared by dev and prod resources. This is deliberately one combined project budget, not two misleading unfiltered dev/prod budgets.

The billing root activates the `Project` cost-allocation tag. The tag must already exist on deployed resources before activation; AWS notes that newly applied user-defined tags can take up to 24 hours to appear for activation. Apply the billing root only after the first tagged dev resources exist and the tag is visible. Cost allocation data may lag activation, so verify the tag status and budget filter before relying on alerts. The budget is a notification guardrail, **not an automatic spending cap**.

The $12–$14 estimate is a planning model, not a saved AWS Pricing Calculator quote. Before production approval, verify the account's current pricing tier, region, actual log volume and the saved [AWS Pricing Calculator](https://calculator.aws/) estimate. Existing resources outside the `Project=attendance` tag are not included in this project budget or estimate.
