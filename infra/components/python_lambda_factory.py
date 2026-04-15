from pathlib import Path

from aws_cdk import BundlingOptions, Duration, IgnoreMode
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


PYTHON_LAMBDA_EXCLUDES = [
    "infra/cdk.out",
    "infra/.venv",
    "**/__pycache__",
    "**/.pytest_cache",
]

PYTHON_LAMBDA_BUNDLING_COMMAND = (
    "pip install --no-cache-dir ./app/shared -t /asset-output "
    "&& cp -R app/handlers /asset-output/handlers"
)


def build_python_lambda(
    *,
    scope: Construct,
    construct_id: str,
    function_name: str,
    handler: str,
    timeout_seconds: int,
    memory_size: int,
    environment: dict[str, str],
) -> lambda_.Function:
    repository_root = Path(__file__).resolve().parents[2]
    return lambda_.Function(
        scope,
        construct_id,
        function_name=function_name,
        runtime=lambda_.Runtime.PYTHON_3_12,
        architecture=lambda_.Architecture.ARM_64,
        handler=handler,
        timeout=Duration.seconds(timeout_seconds),
        memory_size=memory_size,
        code=lambda_.Code.from_asset(
            str(repository_root),
            ignore_mode=IgnoreMode.GLOB,
            exclude=PYTHON_LAMBDA_EXCLUDES,
            bundling=BundlingOptions(
                image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                command=[
                    "bash",
                    "-lc",
                    PYTHON_LAMBDA_BUNDLING_COMMAND,
                ],
            ),
        ),
        environment=environment,
    )
