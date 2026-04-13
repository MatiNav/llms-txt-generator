#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.server_messaging_stack import ServerMessagingStack
from stacks.server_runtime_stack import ServerRuntimeStack


def _required_context_value(app: cdk.App, key: str) -> str:
    value = app.node.try_get_context(key)
    if not value and key == "database_url":
        value = os.environ.get("DATABASE_URL")
    if not value:
        raise ValueError(f"Missing required CDK context value: {key}")
    return str(value)


app = cdk.App()
database_url = _required_context_value(app, "database_url")
deployment_environment = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1",
)

messaging_stack = ServerMessagingStack(
    app,
    "LlmstxtServerMessaging",
    env=deployment_environment,
)

runtime_stack = ServerRuntimeStack(
    app,
    "LlmstxtServerRuntime",
    discoverable_queue_url=messaging_stack.discoverable_queue.queue_url,
    database_url=database_url,
    server_runtime_role_arn=messaging_stack.server_runtime_role.role_arn,
    env=deployment_environment,
)
runtime_stack.add_dependency(messaging_stack)

app.synth()
