from django.shortcuts import redirect
from django.urls import reverse
from core.models import Paciente, Profesional, PlantillaAtencion
from core.utils import user_has_role

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

EXEMPT_PATH_PREFIXES = (
    "/admin", "/static", "/media",
    "/ingreso", "/salir", "/cuenta", "/cambiar-password",
    "/paciente",  # todo el flujo de pacientes
    "/panel/recepcion",  # recepción no debe ser forzada al setup
)

def ensure_prof_setup_middleware(get_response):
    def middleware(request):
        user = getattr(request, "user", None)
        path = request.path

        # 1) Excepciones por prefijo (admin, estáticos, recepción, etc.)
        if any(path.startswith(p) for p in EXEMPT_PATH_PREFIXES):
            return get_response(request)

        # 2) URL del setup (por name, con fallback correcto)
        try:
            setup_url = reverse("pro_setup_horario")  # -> /panel/profesional/disponibilidad/
        except Exception:
            setup_url = "/panel/profesional/disponibilidad/"

        # 3) Evitar loop (GET o POST del propio setup)
        if path.startswith(setup_url):
            return get_response(request)

        # 4) Solo si está autenticado y ES profesional
        if user and user.is_authenticated:
            # Opcional: salir rápido si NO tiene rol Profesional
            if not user_has_role(user, "Profesional"):
                return get_response(request)

            # 5) Tiene perfil de profesional activo?
            try:
                prof = Profesional.objects.get(usuario=user, activo=True)
            except Profesional.DoesNotExist:
                return get_response(request)

            # 6) ¿Tiene plantillas activas? Si no, forzar setup
            tiene = PlantillaAtencion.objects.filter(profesional=prof, activo=True).exists()
            if not tiene:
                return redirect(setup_url)

        return get_response(request)
    return middleware
