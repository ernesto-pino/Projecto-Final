from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from functools import wraps
from .utils import user_has_role

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
