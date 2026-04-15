def generated_prefix(run_id: str) -> str:
    return f"runs/{run_id}/generated/"


def generated_bundle_key(run_id: str) -> str:
    return f"{generated_prefix(run_id)}bundle.zip"
