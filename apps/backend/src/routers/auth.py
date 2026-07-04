from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from apps.backend.src.config import settings
from apps.backend.src.database import api_session_factory
from db_clients.session import tenant_context
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from security_utils import create_access_token, hash_password, verify_password
from sqlalchemy import text

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Modelos de Petición y Respuesta ---

class RegisterRequest(BaseModel):
    # Datos del Tenant
    slug: str = Field(..., min_length=3, max_length=50, pattern="^[a-z0-9-]+$")
    name: str = Field(..., min_length=3, max_length=100)
    tier: str = Field("starter", pattern="^(starter|growth|enterprise)$")
    # Datos del Administrador
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    slug: str | None = Field(None, description="Slug del inquilino si no se usa un subdominio")


class UserResponse(BaseModel):
    user_id: UUID
    email: str
    role: str
    tenant_id: UUID


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# --- Endpoints ---

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest) -> Any:
    """Onboarding de un nuevo Tenant junto con su usuario Administrador inicial.

    Crea transaccionalmente el Tenant y el Usuario Administrador en aislamiento.
    """
    # 1. Validar que el slug no exista
    async with api_session_factory() as session:
        result = await session.execute(
            text("SELECT 1 FROM tenants WHERE slug = :slug"),
            {"slug": body.slug},
        )
        if result.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El slug de inquilino ya está en uso.",
            )

    tenant_id = uuid4()

    # 2. Registrar el tenant y el usuario admin de forma transaccional bajo el contexto del nuevo tenant
    async with tenant_context(tenant_id), api_session_factory() as session:
        # Crear Tenant
        await session.execute(
            text("""
                    INSERT INTO tenants (tenant_id, slug, name, tier)
                    VALUES (:tenant_id, :slug, :name, :tier)
                """),
            {
                "tenant_id": tenant_id,
                "slug": body.slug,
                "name": body.name,
                "tier": body.tier,
            },
        )

        # Hashear la contraseña
        pass_hash = hash_password(body.password)

        # Crear Usuario
        user_result = await session.execute(
            text("""
                    INSERT INTO users (tenant_id, email, password_hash)
                    VALUES (:tenant_id, :email, :password_hash)
                    RETURNING user_id
                """),
            {
                "tenant_id": tenant_id,
                "email": body.email,
                "password_hash": pass_hash,
            },
        )
        user_row = user_result.fetchone()
        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al recuperar el ID del usuario registrado.",
            )
        user_id = user_row[0]

        # Buscar role_id de 'Tenant Admin'
        role_result = await session.execute(
            text("SELECT role_id FROM roles WHERE name = 'Tenant Admin'"),
        )
        role_row = role_result.fetchone()
        if not role_row:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="El rol 'Tenant Admin' no está registrado en la base de datos.",
            )
        role_id = role_row[0]

        # Asignar Rol
        await session.execute(
            text("""
                    INSERT INTO user_roles (user_id, role_id)
                    VALUES (:user_id, :role_id)
                """),
            {"user_id": user_id, "role_id": role_id},
        )

        await session.commit()

    # 3. Generar token de acceso JWT
    expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "email": body.email,
        "role": "Tenant Admin",
    }
    token = create_access_token(token_data, secret_key=settings.JWT_SECRET, expires_delta=expires)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user_id,
            "email": body.email,
            "role": "Tenant Admin",
            "tenant_id": tenant_id,
        },
    }


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, body: LoginRequest) -> Any:
    """Autenticación de usuario para un Tenant específico.

    Resuelve el Tenant vía subdominio/cabecera o mediante el parámetro 'slug'.
    """
    tenant_id: UUID | None = getattr(request.state, "tenant_id", None)

    # 1. Si no viene inyectado por middleware (subdominio o cabecera), intentar resolver por slug en body
    if not tenant_id:
        if not body.slug:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere el slug del inquilino o el subdominio correspondiente.",
            )

        async with api_session_factory() as session:
            result = await session.execute(
                text("SELECT tenant_id FROM tenants WHERE slug = :slug"),
                {"slug": body.slug},
            )
            row = result.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Tenant con slug '{body.slug}' no encontrado.",
                )
            tenant_id = row[0]

    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo resolver el inquilino (tenant).",
        )

    # 2. Consultar y verificar el usuario bajo el contexto aislado del tenant
    async with tenant_context(tenant_id), api_session_factory() as session:
        # Buscar usuario
        user_result = await session.execute(
            text("SELECT user_id, password_hash FROM users WHERE email = :email AND status = 'active'"),
            {"email": body.email},
        )
        user_row = user_result.fetchone()
        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas o usuario inactivo.",
            )
        user_id, password_hash = user_row

        # Verificar contraseña
        if not verify_password(body.password, password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas.",
            )

        # Obtener rol del usuario
        role_result = await session.execute(
            text("""
                    SELECT r.name FROM roles r
                    JOIN user_roles ur ON r.role_id = ur.role_id
                    WHERE ur.user_id = :user_id
                    LIMIT 1
                """),
            {"user_id": user_id},
        )
        role_row = role_result.fetchone()
        role_name = role_row[0] if role_row else "Developer"

    # 3. Generar token
    expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "email": body.email,
        "role": role_name,
    }
    token = create_access_token(token_data, secret_key=settings.JWT_SECRET, expires_delta=expires)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user_id,
            "email": body.email,
            "role": role_name,
            "tenant_id": tenant_id,
        },
    }
