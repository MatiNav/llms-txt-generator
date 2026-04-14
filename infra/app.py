#!/usr/bin/env python3
import aws_cdk as cdk

from stacks.llm_txt_generator_stack import LlmTxtGeneratorStack


app = cdk.App()
deployment_environment = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1",
)

LlmTxtGeneratorStack(
    app,
    "LlmTxtGeneratorStack",
    env=deployment_environment,
)

app.synth()
