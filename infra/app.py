#!/usr/bin/env python3
import aws_cdk as cdk

from stacks.server_data_stack import ServerDataStack
from stacks.server_messaging_stack import ServerMessagingStack
from stacks.server_runtime_stack import ServerRuntimeStack


app = cdk.App()
deployment_environment = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1",
)

data_stack = ServerDataStack(
    app,
    "LlmstxtServerData",
    env=deployment_environment,
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
    database_url=data_stack.database_url,
    server_runtime_role_arn=messaging_stack.server_runtime_role.role_arn,
    env=deployment_environment,
)
runtime_stack.add_dependency(data_stack)
runtime_stack.add_dependency(messaging_stack)

app.synth()
