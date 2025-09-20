from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .utils import user_has_role

def home(request):
    return render(request, 'core/html/home.html')

@login_required
def recepcion_home(request):
    return render(request, "admin/recepcion/home.html")

@login_required
def profesional_home(request):
    return render(request, "admin/profesional/home.html")

@login_required
def auditor_home(request):
    return render(request, "admin/auditor/home.html")

@login_required
def dispatch_por_rol(request):
    u = request.user
    if u.is_superuser:
        return redirect("/admin/")
    if user_has_role(u, "Recepción"):
        return redirect("panel_recepcion")
    if user_has_role(u, "Profesional"):
        return redirect("panel_profesional")
    if user_has_role(u, "Auditor"):
        return redirect("panel_auditor")
    return redirect("panel_recepcion")  # fallback

def admin_login_gate(request):
    u = request.user
    if u.is_authenticated:
        if u.is_superuser:
            return redirect("/admin/")          # entra al admin clásico
        return redirect("dispatch_por_rol")      # tu dispatcher por rol (/entrar/)
    return redirect("login")  # name de tu ruta /ingreso/
