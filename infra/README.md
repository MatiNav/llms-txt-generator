# Slice 2 Infra (CDK)

This infra scope is intentionally minimal and supports the current backend slice (`POST /api/generate` + coalescing).

## What this CDK app creates

- `llmstxt-discoverable` SQS queue
- `llmstxt-discoverable-dlq` dead-letter queue
- Redrive policy from discoverable queue to DLQ (`max_receive_count=5`)
- `llmstxt-server-runtime-role` IAM role for App Runner runtime
- IAM grant: `sqs:SendMessage` from server runtime role to discoverable queue
- App Runner service (`llmstxt-server`) wired to container image built from `app/server/Dockerfile`
- App Runner runtime env injection for `AWS_REGION` and `DISCOVERABLE_QUEUE_URL`

## Outputs used by the server runtime

- `DiscoverableQueueUrl` → `DISCOVERABLE_QUEUE_URL`
- `AwsRegion` → `AWS_REGION`
- `ServerRuntimeRoleArn` → App Runner instance role ARN

## Commands

From `infra/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cdk synth
cdk deploy --require-approval never
```

Optional context overrides:

```bash
cdk deploy -c account=123456789012 -c region=us-east-1 --require-approval never
```

## Notes

- This CDK app now deploys both messaging baseline and App Runner runtime wiring for Slice 2.
- DB env + network wiring remain required for the server runtime to access PostgreSQL.
