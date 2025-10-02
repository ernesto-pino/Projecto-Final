from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .utils import user_has_role, crear_token_reset, obtener_token_valido, generar_password
from .decorators import role_required, paciente_login_required
from .models import *
from django.contrib import messages
from .forms import LoginPacienteForm, CambioPasswordPacienteForm, SolicitarResetForm, ResetPasswordForm, PacienteCreateForm
from django.urls import reverse
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils.http import url_has_allowed_host_and_scheme

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
    if request.session.get("paciente_id"):
        return redirect("home")

    form = LoginPacienteForm(request.POST or None)
    next_url = request.GET.get("next") or reverse("home")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = reverse("home")

    error_msg = "RUT o contraseña inválidos."

    if request.method == "POST":
        if form.is_valid():
            rut = (form.cleaned_data.get("rut") or "").strip()
            password = form.cleaned_data.get("password") or ""

            # Unificamos todos los fallos bajo el mismo mensaje:
            p = Paciente.objects.filter(rut=rut, is_active=True).first()
            if not p or not p.password or not p.check_password(password):
                messages.error(request, error_msg)
            else:
                request.session.cycle_key()
                request.session["paciente_id"] = p.id
                p.last_login = timezone.now()
                p.save(update_fields=["last_login"])
                return redirect(next_url)
        else:
            # Si el form no valida (ej: RUT mal formateado), también mostramos el genérico
            messages.error(request, error_msg)

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


def solicitar_reset(request):
    form = SolicitarResetForm(request.POST or None)

    # (Opcional) Rate-limit simple por IP: 5 intentos por hora
    ip = request.META.get("REMOTE_ADDR", "unknown")
    key = f"reset-req:{ip}"
    count = cache.get(key, 0)

    if request.method == "POST" and form.is_valid():
        if count >= 5:
            messages.error(request, "Has alcanzado el límite de solicitudes. Inténtalo más tarde.")
            return render(request, "paciente/solicitar_reset.html", {"form": form})

        rut = form.cleaned_data["rut"].strip()

        # No revelar si existe o no: respuesta siempre igual.
        paciente = Paciente.objects.filter(rut=rut, is_active=True).first()
        if paciente and paciente.email:
            # Generar token y enviar correo
            token = crear_token_reset(paciente, minutos=30)
            link = request.build_absolute_uri(
                reverse("restablecer_password", args=[token])
            )
            try:
                send_mail(
                    subject="Recuperación de contraseña - MiHora Lampa",
                    message=f"Hola {paciente.nombre_completo()},\n\n"
                            f"Usa este enlace para restablecer tu contraseña (válido por 30 minutos):\n{link}\n\n"
                            "Si no solicitaste este cambio, ignora este mensaje.",
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    recipient_list=[paciente.email],
                    fail_silently=True,  # en dev no queremos romper el flujo por SMTP
                )
            except Exception:
                # En desarrollo: si no hay SMTP, al menos muestra el link en consola
                print("LINK DE RESET (DEV):", link)

        # incrementar rate
        cache.set(key, count + 1, timeout=60 * 60)  # 1 hora

        messages.success(request, "Si el RUT existe y tiene correo registrado, te enviaremos un enlace para restablecer la contraseña.")
        return redirect("login_paciente")

    return render(request, "paciente/solicitar_reset.html", {"form": form})

def restablecer_password(request, token):
    token_obj = obtener_token_valido(token)
    if not token_obj:
        messages.error(request, "El enlace es inválido o ha expirado.")
        return redirect("login_paciente")

    form = ResetPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        nueva = form.cleaned_data["nueva_password"]
        p = token_obj.paciente

        # Si quieres obligar cambio nuevamente en ingreso, deja True;
        # si se considera definitivo, marca False. Aquí lo pongo False:
        p.set_password(nueva)
        p.debe_cambiar_password = False
        p.save(update_fields=["password", "debe_cambiar_password"])

        token_obj.used_at = timezone.now()
        token_obj.save(update_fields=["used_at"])

        messages.success(request, "Tu contraseña ha sido restablecida. Ya puedes iniciar sesión.")
        return redirect("login_paciente")

    return render(request, "paciente/restablecer_password.html", {"form": form})


def registrar_paciente(request):
    if request.method == "POST":
        form = PacienteCreateForm(request.POST)
        if form.is_valid():
            paciente = form.save(commit=False)

            # Generar contraseña aleatoria
            password_generada = generar_password()
            paciente.set_password(password_generada)  # se guarda hasheada
            paciente.debe_cambiar_password = True
            paciente.save()

            # Enviar correo con la contraseña
            if paciente.email:
                send_mail(
                    subject="Bienvenido a MiHora Lampa",
                    message=(
                        f"Estimado/a {paciente.nombres},\n\n"
                        f"Su cuenta ha sido creada.\n"
                        f"RUT: {paciente.rut}\n"
                        f"Contraseña temporal: {password_generada}\n\n"
                        f"Por favor, cambie su contraseña al ingresar al sistema."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[paciente.email],
                    fail_silently=False,
                )
                msg = "Paciente creado y contraseña enviada al correo."
            else:
                # SIN correo -> SIN contraseña (queda None/“”), no puede iniciar sesión
                paciente.password = None
                paciente.debe_cambiar_password = False  # opcional
                paciente.save()
                msg = "Paciente creado sin acceso web (no tiene correo)."

            messages.success(request, msg)
            return redirect("registrar_paciente")  # o al listado
        else:
            messages.error(request, "")
    else:
        form = PacienteCreateForm()

    return render(request, "admin/recepcion/registrar.html", {"form": form})
