from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from functools import wraps
from .utils import user_has_role
from django.shortcuts import redirect
from django.urls import reverse
from core.models import Paciente



def role_required(nombre_rol):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if user_has_role(request.user, nombre_rol):
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("No tienes permiso para acceder a esta página")
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
