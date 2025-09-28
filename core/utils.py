import secrets, hashlib
from datetime import timedelta
from django.utils import timezone
from .models import PacienteResetToken


def user_has_role(user, nombre_rol: str) -> bool:
    """
    Devuelve True si el usuario tiene asignado el rol dado.
    Usa la relación UserRole -> Role que ya definimos en models.py.
    """
    if not user.is_authenticated:
        return False
    # "roles_asignados" es el related_name en UserRole
    return user.roles_asignados.filter(rol__nombre=nombre_rol).exists()

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def crear_token_reset(paciente, minutos=30):
    """Crea un token de un solo uso y devuelve el token en texto plano (para el link)."""
    token = secrets.token_urlsafe(32)                 # texto plano (NO se guarda)
    token_hash = _hash_token(token)                   # guardamos solo hash
    exp = timezone.now() + timedelta(minutes=minutos)
    PacienteResetToken.objects.create(
        paciente=paciente,
        token_hash=token_hash,
        expires_at=exp,
    )
    return token

def obtener_token_valido(token_plano: str):
    """Busca un token no usado y no expirado. Devuelve instancia o None."""
    token_hash = _hash_token(token_plano)
    try:
        obj = PacienteResetToken.objects.select_related("paciente").get(token_hash=token_hash)
    except PacienteResetToken.DoesNotExist:
        return None
    return obj if obj.is_valid() else None
