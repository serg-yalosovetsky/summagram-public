import re


def sanitize_input(text: str) -> str:
    """
    Strips control characters and null bytes to prevent low-level injection/corruption.
    """
    if not text:
        return ""
    # Remove null bytes
    text = text.replace("\0", "")
    # Remove non-printable characters (except newlines/tabs)
    # This regex matches control characters that are NOT \n, \r, \t
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text.strip()


def wrap_user_data(text: str) -> str:
    """
    Wraps untrusted user content in XML tags to prevent prompt injection.
    """
    safe_text = sanitize_input(text)
    # Escape existing tags if necessary, though simpler is often better for LLMs.
    # We will just wrap it.
    return f"<user_data>\n{safe_text}\n</user_data>"


def mask_pii(text: str) -> str:
    """
    Masks PII (Email, Phone, Credit Card) in the given text.
    """
    if not text:
        return ""

    # Email Regex
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    text = re.sub(email_pattern, "<EMAIL_MASKED>", text)

    # Phone Regex (Simple international or domestic 7-10+ digits)
    # Matches +1-555-..., 555-555-5555, 555-5555
    # Warning: Can be aggressive.
    phone_pattern = r"\b(?:\+?\d{1,3}[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b|\b\d{3}[-. ]\d{4}\b"
    text = re.sub(phone_pattern, "<PHONE_MASKED>", text)

    # Credit Card Regex (Simple generic 13-16 digits)
    cc_pattern = r"\b(?:\d[ -]*?){13,16}\b"
    text = re.sub(cc_pattern, "<CC_MASKED>", text)

    # Password / Secret Regex (Assignment patterns)
    # Matches: password = "...", api_key: ..., secret is ...
    # Captures the value part and replaces it.
    secret_pattern = (
        r"(?i)\b(password|passwd|pwd|secret|api_key|token)\s*([:=]|\bis\b)\s*([^\s]+)"
    )
    text = re.sub(secret_pattern, r"\1: <SECRET_MASKED>", text)

    return text
