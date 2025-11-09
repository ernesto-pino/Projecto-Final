from django.contrib.auth.decorators import login_required
from functools import wraps
from .utils import user_has_role
from django.shortcuts import redirect
from django.urls import reverse
from core.models import Paciente
from django.contrib import messages


def role_required(nombre_rol):
    """
    Decorador que verifica si el usuario tiene el rol indicado.
    - Permite el acceso si el usuario tiene el rol requerido o es Administrador.
    - Si no, redirige a una página de error con un mensaje.
    """
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect("login")  # seguridad adicional

            # Si el usuario tiene el rol solicitado o es Administrador, dejar pasar
            if user_has_role(user, nombre_rol) or user_has_role(user, "Administrador"):
                return view_func(request, *args, **kwargs)

            # Si no tiene permiso, mensaje y redirección a página bonita
            messages.error(request, "No tienes permiso para acceder a esta sección.")
            return redirect("acceso_denegado")  # <-- crea esta vista o URL
        return _wrapped_view
    return decorator


def paciente_login_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        pid = request.session.get("paciente_id")
        if not pid:
            # No hay sesión → al login
            return redirect(f"{reverse('login_paciente')}?next={request.path}")

        try:
            paciente = Paciente.objects.get(pk=pid, is_active=True)
        except Paciente.DoesNotExist:
            # ID inválido o paciente inactivo → limpiar sesión y al login
            request.session.pop("paciente_id", None)
            return redirect(reverse("login_paciente"))

        # Opcional: inyectar el paciente en el request
        request.paciente = paciente
        return view_func(request, *args, **kwargs)

    return _wrapped
