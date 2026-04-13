# Slice 2 Infra (CDK)

This infra scope is intentionally minimal and supports the current backend slice (`POST /api/generate` + coalescing).

## What this CDK app creates

- `llmstxt-discoverable` SQS queue
- `llmstxt-discoverable-dlq` dead-letter queue
- Redrive policy from discoverable queue to DLQ (`max_receive_count=5`)
- `llmstxt-server-runtime-role` IAM role for App Runner runtime
- IAM grant: `sqs:SendMessage` from server runtime role to discoverable queue
- VPC with public subnets (challenge mode)
- PostgreSQL RDS instance in public subnets (challenge mode)
- App Runner service (`llmstxt-server`) wired to container image built from `app/server/Dockerfile`
- App Runner runtime env injection for `AWS_REGION` and `DISCOVERABLE_QUEUE_URL`
- App Runner runtime env injection for `DATABASE_URL` generated from RDS endpoint + secret

## Outputs used by the server runtime

- `DiscoverableQueueUrl` → `DISCOVERABLE_QUEUE_URL`
- `AwsRegion` → `AWS_REGION`
- `ServerRuntimeRoleArn` → App Runner instance role ARN
- App Runner runtime receives `DATABASE_URL` from `ServerDataStack`

## Commands

From `infra/`:

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
cdk synth
cdk deploy --all --require-approval never
```

Optional context overrides:

```bash
cdk deploy --all \
  -c account=123456789012 \
  -c region=us-east-1 \
  --require-approval never
```

## Notes

- This CDK app deploys both messaging baseline and App Runner runtime wiring for Slice 2.
- `DATABASE_URL` is generated from the RDS instance and injected into App Runner runtime env.
- Challenge-mode networking uses public subnets to avoid NAT cost/complexity during evaluation.
- Production should move RDS to private subnets and route egress through NAT gateways and/or VPC endpoints.
