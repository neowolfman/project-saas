import hashlib
import hmac


def verify_github_signature(payload: bytes, signature_header: str, secret: str) -> bool:
    """
    Verifica una firma HMAC-SHA256 enviada por GitHub en webhooks.
    
    El formato de la cabecera es 'sha256=<signature>'.
    """
    if not signature_header.startswith("sha256="):
        return False
        
    actual_signature = signature_header[7:]
    computed_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    
    return hmac.compare_digest(computed_signature, actual_signature)


def verify_gitlab_token(received_token: str, secret: str) -> bool:
    """Verifica el token estático enviado por GitLab en webhooks usando una comparación segura contra tiempo constante."""
    return hmac.compare_digest(received_token.encode(), secret.encode())
