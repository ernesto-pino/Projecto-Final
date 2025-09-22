from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .utils import user_has_role
from .decorators import role_required
from .models import *


#renderizado de paginas
def home(request):
    return render(request, 'core/html/home.html')

@role_required("Recepción")
def recepcion_home(request):
    return render(request, "admin/recepcion/home.html")

@role_required("Profesional")
def profesional_home(request):
    return render(request, "admin/profesional/home.html")

#funciones
@login_required
def dispatch_por_rol(request):
    u = request.user
    if u.is_superuser:
        return redirect("/admin/")
    if user_has_role(u, "Recepción"):
        return redirect("recepcion_home")
    if user_has_role(u, "Profesional"):
        return redirect("profesional_home")
    return redirect("panel_recepcion")  # fallback

def admin_login_gate(request):
    u = request.user
    if u.is_authenticated:
        if u.is_superuser:
            return redirect("/admin/")          # entra al admin clásico
        return redirect("dispatch_por_rol")      # tu dispatcher por rol (/entrar/)
    return redirect("login")  # name de tu ruta /ingreso/


# Llamar lista de profesionales para mostrar a los pacientes;

def profesionales_list(request):
# Parámetros GET
    esp_param = (request.GET.get("especialidad") or "").strip()
    q_param   = (request.GET.get("q") or "").strip()

    # Base: solo activos
    qs = Profesional.objects.select_related("especialidad").filter(activo=True)

    # Filtro por especialidad (si viene un id válido)
    if esp_param:
        try:
            esp_id = int(esp_param)
            qs = qs.filter(especialidad_id=esp_id)
        except ValueError:
            pass  # ignora valores no numéricos

    # (Opcional) Buscador por nombre/apellido
    if q_param:
        qs = qs.filter(
            Q(nombre__icontains=q_param) | Q(apellido__icontains=q_param)
        )

    profesionales = qs.order_by("apellido", "nombre")

    # Para rellenar el <select> (todas las especialidades)
    especialidades = Especialidad.objects.order_by("nombre").values("id", "nombre")

    ctx = {
        "profesionales": profesionales,
        "especialidades": especialidades,
        "selected_esp": esp_param,  # lo usamos para marcar el selected
        "q": q_param,
    }
    return render(request, "core/html/profesionales.html", ctx)


def custom_404(request, exception=None):
    return render(request, "core/html/404.html", status=404)
