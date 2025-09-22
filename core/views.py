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
    esp_param = request.GET.get("especialidad", "").strip()

    # Base: solo activos
    qs = Profesional.objects.select_related("especialidad").filter(activo=True)

    # Si viene un id de especialidad, filtramos
    if esp_param.isdigit():
        qs = qs.filter(especialidad_id=int(esp_param))

    profesionales = qs.order_by("apellido", "nombre")

    # Para el <select>
    especialidades = Especialidad.objects.order_by("nombre").values("id", "nombre")

    ctx = {
        "profesionales": profesionales,
        "especialidades": especialidades,
        "selected_esp": esp_param,  # para marcar selected en el template
    }
    return render(request, "core/html/profesionales.html", ctx)


def custom_404(request, exception=None):
    # OJO: usa la ruta real de tu template
    return render(request, "core/html/404.html", status=404)
