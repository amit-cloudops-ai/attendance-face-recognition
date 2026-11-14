# Serverless Face-Recognition Attendance System

Contactless employee clock-in/clock-out prototype using browser camera capture, Amazon Rekognition, AWS Lambda and DynamoDB.

**Monday delivery target:** 16 November 2026. Read [finish line](docs/FINISH_LINE.md), [work allocation](docs/TASKS.md), [status](docs/STATUS.md) and [frozen contracts](docs/contracts.md).

## Branch ownership
- `solo/amit-monday`: Amit's independent end-to-end implementation and guaranteed demo track.
- `develop`: team integration branch.
- Sushmita: Part B (data and attendance logic), via PR to develop.
- Gopi: Part C (access and frontend), via PR to develop.
Team contributions are not automatically included in the solo branch. Amit reviews and chooses whether to integrate them.

## Monday sprint architecture
The sprint uses one SAM/CloudFormation template (`template.yaml`) as the infrastructure source of truth. Terraform is deferred for this sprint. See docs/FINISH_LINE.md for scope and limitations. The API/data interfaces remain governed by docs/contracts.md.

## Repository layout
```
docs/       finish line, frozen contracts, work briefs, architecture and status
shared/     shared Python attendance library
services/   recognition and data Lambda handlers
web/        kiosk and admin applications
template.yaml   SAM/CloudFormation infrastructure target
tests/      unit, contract and integration tests
scripts/    local checks, smoke tests and deployment helpers
```

## Development checks
```bash
python -m pip install -r requirements-dev.txt
ruff check .
pytest -q
# Once template.yaml exists:
cfn-lint template.yaml
sam validate --lint
sam build
```

Do not provision or modify AWS resources without Amit's explicit approval. Never commit secrets, credentials, AWS account IDs or biometric images.
