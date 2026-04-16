import re


PLACEHOLDER_PATTERN = re.compile(r"\{\{LLM_SUMMARY:[^}]+\}\}")


def root_summary_placeholder() -> str:
    return "{{LLM_SUMMARY:root}}"


def root_details_placeholder() -> str:
    return "{{LLM_SUMMARY:root:details}}"


def section_summary_placeholder(section_key: str) -> str:
    return f"{{{{LLM_SUMMARY:section:{section_key}}}}}"


def section_short_summary_placeholder(section_key: str) -> str:
    return f"{{{{LLM_SUMMARY:section:{section_key}:short}}}}"


def extract_placeholders(file_content: str) -> list[str]:
    return PLACEHOLDER_PATTERN.findall(file_content)


def apply_replacements(file_content: str, replacements: dict[str, str]) -> str:
    updated_content = file_content
    for placeholder_token, replacement_text in replacements.items():
        safe_replacement = replacement_text.strip() or "Summary unavailable"
        updated_content = updated_content.replace(placeholder_token, safe_replacement)
    return updated_content
