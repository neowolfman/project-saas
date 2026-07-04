from datetime import datetime, timedelta, UTC
from typing import Any
from jose import jwt


def create_access_token(
    data: dict[str, Any],
    secret_key: str,
    expires_delta: timedelta | None = None,
    algorithm: str = "HS256",
) -> str:
    """Genera un token de acceso JWT firmado con la clave secreta y algoritmo indicados."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=15)
        
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)


def decode_access_token(
    token: str,
    secret_key: str,
    algorithms: list[str] | None = None,
) -> dict[str, Any]:
    """
    Decodifica y valida un token de acceso JWT.
    
    Lanza:
        ExpiredSignatureError: Si el token ha expirado.
        JWTError: Si la firma o el token no son válidos.
    """
    if algorithms is None:
        algorithms = ["HS256"]
    payload = jwt.decode(token, secret_key, algorithms=algorithms)
    return payload
