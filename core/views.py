from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .utils import user_has_role
from .decorators import role_required, paciente_login_required
from .models import *
from django.contrib import messages
from .forms import LoginPacienteForm, CambioPasswordPacienteForm
from django.urls import reverse

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

def login_paciente(request):
    # Si ya está logeado como paciente, lo mandamos directo
    if request.session.get("paciente_id"):
        return redirect("home")

    form = LoginPacienteForm(request.POST or None)
    next_url = request.GET.get("next") or reverse("home")

    if request.method == "POST" and form.is_valid():
        rut = form.cleaned_data["rut"].strip()
        password = form.cleaned_data["password"]

        try:
            p = Paciente.objects.get(rut=rut, is_active=True)
        except Paciente.DoesNotExist:
            messages.error(request, "RUT o contraseña inválidos.")
        else:
            if p.check_password(password):
                # Seguridad: evitar fijación de sesión
                request.session.cycle_key()
                request.session["paciente_id"] = p.id
                # Expiración opcional (ej. 4 horas)
                # request.session.set_expiry(4 * 60 * 60)

                p.last_login = timezone.now()
                p.save(update_fields=["last_login"])
                return redirect(next_url)
            else:
                messages.error(request, "RUT o contraseña inválidos.")

    return render(request, "paciente/login.html", {"form": form})

def logout_paciente(request):
    request.session.pop("paciente_id", None)
    messages.success(request, "Has cerrado sesión.")
    return redirect("login_paciente")

def cambiar_password(request):
    pid = request.session.get("paciente_id")
    if not pid:
        return redirect("login_paciente")

    try:
        paciente = Paciente.objects.get(pk=pid, is_active=True)
    except Paciente.DoesNotExist:
        request.session.pop("paciente_id", None)
        return redirect("login_paciente")

    form = CambioPasswordPacienteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        actual = form.cleaned_data["password_actual"]
        nueva  = form.cleaned_data["nueva_password"]

        # validar actual correcta
        if not paciente.check_password(actual):
            form.add_error("password_actual", "La contraseña actual no es correcta.")
        # evitar repetir la misma
        elif paciente.check_password(nueva):
            form.add_error("nueva_password", "La nueva contraseña no puede ser igual a la anterior.")
        else:
            paciente.set_password(nueva)
            paciente.debe_cambiar_password = False
            paciente.last_login = timezone.now()
            paciente.save(update_fields=["password", "debe_cambiar_password", "last_login"])
            messages.success(request, "Tu contraseña ha sido cambiada correctamente.")
            return redirect("home")

    return render(request, "paciente/cambiar_password.html", {"form": form})



# VISTA DE PRUEBA (ELMINIAR Y REMPLAZAR POR PERFIL REAL)
@paciente_login_required
def perfil_paciente(request):
    # Como el decorador ya validó la sesión, acá tienes el paciente listo:
    paciente = request.paciente
    return render(request, "paciente/perfil.html", {"paciente": paciente})
