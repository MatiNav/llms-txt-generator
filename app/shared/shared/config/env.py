import os


def required_env_value(environment_key: str) -> str:
    environment_value = os.getenv(environment_key)
    if not environment_value:
        raise RuntimeError(f"Missing required environment variable: {environment_key}")
    return environment_value
