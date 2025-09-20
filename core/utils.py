
def user_has_role(user, nombre_rol: str) -> bool:
    """
    Devuelve True si el usuario tiene asignado el rol dado.
    Usa la relación UserRole -> Role que ya definimos en models.py.
    """
    if not user.is_authenticated:
        return False
    # "roles_asignados" es el related_name en UserRole
    return user.roles_asignados.filter(rol__nombre=nombre_rol).exists()
