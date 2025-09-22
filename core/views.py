from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .utils import user_has_role
from .decorators import role_required
from .models import Profesional


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
    profesionales = (
        Profesional.objects
        .select_related('especialidad')
        .filter(activo=True)
        .order_by('apellido', 'nombre')
        .only('nombre','apellido','email','telefono','especialidad__nombre')
    )
    return render(request, "core/html/profesionales.html", {"profesionales": profesionales})