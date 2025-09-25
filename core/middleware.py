from django.shortcuts import redirect
from django.urls import reverse
from core.models import Paciente

class PacienteForcePasswordChangeMiddleware:
    """
    Si el paciente tiene 'debe_cambiar_password=True', lo obliga a ir a cambiar la contraseña
    antes de acceder a cualquier página del portal de pacientes (excepto la propia página de cambio, login y logout).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        pid = request.session.get("paciente_id")
        path = request.path

        # Rutas excluidas para evitar bucle
        try:
            cambio_url = reverse("cambiar_password")
            login_url  = reverse("login_paciente")
            logout_url = reverse("logout_paciente")
        except Exception:
            # Durante el arranque de servidor/colección de URLs
            return self.get_response(request)

        if pid and path not in (cambio_url, login_url, logout_url):
            try:
                p = Paciente.objects.get(pk=pid, is_active=True)
                if p.debe_cambiar_password:
                    # Redirige siempre a cambiar password si debe hacerlo
                    return redirect(cambio_url)
            except Paciente.DoesNotExist:
                request.session.pop("paciente_id", None)

        return self.get_response(request)
