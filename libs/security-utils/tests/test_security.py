from datetime import timedelta
import pytest
from jose.exceptions import ExpiredSignatureError, JWTError
from security_utils.hashing import hash_password, verify_password
from security_utils.jwt import create_access_token, decode_access_token
from security_utils.hmac import verify_github_signature, verify_gitlab_token


def test_hashing_and_verification() -> None:
    """Verifica que el hashing de contraseñas sea correcto y se valide de forma segura."""
    password = "superSecretPassword123"
    hashed = hash_password(password)

    # El hash no debe ser igual al texto plano
    assert hashed != password
    # Debe contener el prefijo de bcrypt
    assert hashed.startswith("$2b$")

    # Verificar que pase con la correcta y falle con incorrectas
    assert verify_password(password, hashed) is True
    assert verify_password("wrongPassword", hashed) is False


def test_jwt_generation_and_decoding() -> None:
    """Verifica la emisión de JWTs, persistencia de payloads y expiración."""
    secret = "myTestJwtSecretKeyUsedOnlyForTesting Purposes"
    payload = {"user_id": "123-abc", "role": "admin", "tenant_id": "tenant-xyz"}

    # Crear token con expiración de 10 minutos
    token = create_access_token(payload, secret_key=secret, expires_delta=timedelta(minutes=10))
    assert isinstance(token, str)

    # Decodificar y verificar campos
    decoded = decode_access_token(token, secret_key=secret)
    assert decoded["user_id"] == "123-abc"
    assert decoded["role"] == "admin"
    assert decoded["tenant_id"] == "tenant-xyz"
    assert "exp" in decoded


def test_jwt_expired() -> None:
    """Verifica que un token expirado lance ExpiredSignatureError."""
    secret = "myTestJwtSecretKeyUsedOnlyForTesting Purposes"
    payload = {"user_id": "123-abc"}

    # Crear un token que expira hace 5 segundos
    token = create_access_token(payload, secret_key=secret, expires_delta=timedelta(seconds=-5))

    with pytest.raises(ExpiredSignatureError):
        decode_access_token(token, secret_key=secret)


def test_jwt_invalid_signature() -> None:
    """Verifica que una firma inválida en el token lance JWTError."""
    secret = "correctSecretKey"
    payload = {"user_id": "123-abc"}

    token = create_access_token(payload, secret_key=secret)
    
    with pytest.raises(JWTError):
        decode_access_token(token, secret_key="wrongSecretKey")


def test_hmac_github_signature() -> None:
    """Verifica la validación de firmas HMAC SHA256 de GitHub."""
    secret = "githubWebhookSecretKey"
    payload = b'{"ref": "refs/heads/main", "commits": []}'
    
    # Firma real esperada
    import hmac
    import hashlib
    expected_hex = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    header_val = f"sha256={expected_hex}"

    assert verify_github_signature(payload, header_val, secret) is True
    assert verify_github_signature(payload, "sha256=invalidhashvalue", secret) is False
    assert verify_github_signature(payload, "invalid_header_format", secret) is False


def test_hmac_gitlab_token() -> None:
    """Verifica la validación de tokens de GitLab."""
    secret = "gitlabWebhookToken"
    assert verify_gitlab_token(secret, secret) is True
    assert verify_gitlab_token("invalidToken", secret) is False
