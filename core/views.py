from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .utils import user_has_role, crear_token_reset, obtener_token_valido, generar_password
from .decorators import role_required, paciente_login_required
from .models import *
from django.contrib import messages
from .forms import LoginPacienteForm, CambioPasswordPacienteForm, ProCitaEstadoNotaForm, SolicitarResetForm, ResetPasswordForm, PacienteCreateForm, PacienteEditForm , ProfesionalHorarioForm, AsignarCitaForm, CambiarEstadoCitaForm
from django.urls import reverse
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models.functions import Replace, Upper
from django.db.models import F, Value, Prefetch
from django.core.paginator import Paginator
import re
import datetime as dat
from django.db import transaction
from django.utils.dateparse import parse_date
from core.agendas import (
    generar_agendas_para_profesional,
    actualizar_disponibilidad_y_regenerar,
)
from .citas import asignar_cita, cancelar_cita, cambiar_estado, pro_actualizar_cita_estado_y_nota
from django.core.exceptions import ValidationError, PermissionDenied
from datetime import time, datetime
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import HttpResponse
from django.shortcuts import redirect
from urllib.parse import urlencode, quote
from django.utils import timezone

#renderizado de paginas
def home(request):
    return render(request, 'core/html/home.html')

@role_required("Recepción")
def recepcion_home(request):
    hoy = timezone.localdate()
    ayer = hoy - dat.timedelta(days=1)

    # Traer últimos pacientes
    ultimos = list(
        Paciente.objects.order_by('-date_joined').only(
            'rut', 'nombres', 'apellidos', 'date_joined'
        )[:10]
    )

    # Badge según fecha de registro
    for p in ultimos:
        if p.date_joined.date() == hoy:
            p.badge = "Nuevo"
        elif p.date_joined.date() == ayer:
            p.badge = "Ayer"
        else:
            p.badge = "Actualizado"

    # Datos resumen
    pacientes_nuevos_hoy = Paciente.objects.filter(date_joined__date=hoy).count()
    stats = {
        "citas_hoy": 0,  # reemplaza con tu modelo Cita si existe
        "pacientes_nuevos_hoy": pacientes_nuevos_hoy,
        "llamadas_hoy": 0
    }

    return render(request, "admin/recepcion/home.html", {
        "ultimos_pacientes": ultimos,
        "stats": stats
    })

@role_required("Profesional")
def profesional_home(request):
    _prof_required(request.user)
    prof = _get_prof(request.user)

    tz   = timezone.get_current_timezone()
    now  = timezone.now()
    hoy  = timezone.localdate()
    ini  = timezone.make_aware(datetime.combine(hoy, time.min), tz)
    fin  = timezone.make_aware(datetime.combine(hoy, time.max), tz)

    # Bloques de HOY (del profesional)
    agendas_hoy_qs = Agenda.objects.filter(
        profesional=prof, inicio__gte=ini, inicio__lte=fin
    )

    total_hoy   = agendas_hoy_qs.count()
    ocupados_hoy = Cita.objects.filter(agenda__in=agendas_hoy_qs).count()
    libres_hoy   = total_hoy - ocupados_hoy

    # Conteos por estado (solo hoy)
    estado_ids = dict(
        EstadoCita.objects
        .filter(nombre__in=["Pendiente", "Ausente"])
        .values_list("nombre", "id")
    )
    pendientes_hoy = Cita.objects.filter(
        agenda__in=agendas_hoy_qs, estado_id=estado_ids.get("Pendiente", 0)
    ).count() if estado_ids.get("Pendiente") else 0

    ausentes_hoy = Cita.objects.filter(
        agenda__in=agendas_hoy_qs, estado_id=estado_ids.get("Ausente", 0)
    ).count() if estado_ids.get("Ausente") else 0

    # Próximas atenciones (sólo con cita) – próximas 6
    proximas = list(
        Cita.objects
        .select_related("paciente", "estado", "agenda", "agenda__ubicacion")
        .filter(
            agenda__profesional=prof,
            agenda__inicio__gte=ini,   # inicio del día
            agenda__inicio__lte=fin    # fin del día
        )
        .order_by("agenda__inicio")[:6]
    )

    # Etiqueta tipo "En 2 h", "Mañana", "En 3 d"
    def eta_label(dt):
        delta = dt - now
        mins = int(delta.total_seconds() // 60)
        if mins >= 0:
            if mins < 60:
                return f"En {max(mins,1)} min"
            horas = mins // 60
            if dt.date() == hoy:
                return f"En {horas} h"
            if dt.date() == hoy + timedelta(days=1):
                return "Mañana"
            dias = (dt.date() - hoy).days
            return f"En {dias} d"
        else:
            mins = abs(mins)
            if mins < 60:
                return f"Hace {mins} min"
            horas = mins // 60
            if dt.date() == hoy:
                return f"Hace {horas} h"
            dias = (hoy - dt.date()).days
            return f"Hace {dias} d"


    proximas_items = [{
        "paciente": c.paciente.nombre_completo(),
        "sub": f"{c.agenda.inicio:%d/%m %H:%M} — {c.agenda.ubicacion.nombre} · {c.agenda.get_modalidad_display()}",
        "badge": eta_label(c.agenda.inicio),
        "url": reverse("pro_cita_detail", args=[c.id]),
    } for c in proximas]

    ctx = {
        # saludo ya usa request.user.first_name en tu template
        "stats_atenciones_hoy": ocupados_hoy,   # para tu caja "Atenciones hoy"
        "stats_pendientes": pendientes_hoy,     # para tu caja "Pendientes"
        "stats_ausencias": ausentes_hoy,        # para tu caja "Ausencias"
        "proximas_items": proximas_items,       # para la lista de la izquierda
    }
    return render(request, "admin/profesional/home.html", ctx)

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

@role_required("Recepción")
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

def probar_404(request):
    return render(request, "core/html/404.html", status=404)

@role_required("Recepción")
def paciente_list(request):
    q = (request.GET.get("q") or "").strip()
    estado = (request.GET.get("estado") or "todos").strip().lower()

    qs = Paciente.objects.all()

    # Filtro Activos / Inactivos
    if estado == "activos":
        qs = qs.filter(is_active=True)
    elif estado == "inactivos":
        qs = qs.filter(is_active=False)

    # Buscador por RUT (ignora . y - / mayúsculas)
    if q:
        q_norm = re.sub(r"[^0-9Kk]", "", q).upper()
        qs = qs.annotate(
            rut_norm=Replace(
                Replace(Upper(F("rut")), Value("."), Value("")),
                Value("-"),
                Value(""),
            )
        ).filter(rut_norm__contains=q_norm)

    # Ordena por apellidos, nombres
    qs = qs.order_by("apellidos", "nombres")

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "admin/recepcion/listado_paciente.html", {
        "page_obj": page_obj,
        "q": q,
        "estado": estado,
    })

@role_required("Recepción")
def paciente_detail(request, pk):
    p = get_object_or_404(Paciente, pk=pk)
    return render(request, "admin/recepcion/listado_perfil_paciente.html", {"p": p})

@role_required("Recepción")
def paciente_edit(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)

    if request.method == "POST":
        form = PacienteEditForm(request.POST, instance=paciente)
        if form.is_valid():
            email_cambio = form.has_email_changed()
            nuevo_email = form.cleaned_data.get("email")
            nueva_clave_plana = None

            try:
                with transaction.atomic():
                    obj = form.save(commit=False)

                    if email_cambio:
                        if nuevo_email:
                            nueva_clave_plana = generar_password(12)
                            obj.set_password(nueva_clave_plana)
                            obj.debe_cambiar_password = True
                        else:
                            obj.password = None
                            obj.debe_cambiar_password = True

                    obj.save()
                    if email_cambio and not nuevo_email:
                        Paciente.objects.filter(pk=obj.pk).update(password=None)

                if email_cambio and nuevo_email:
                    try:
                        send_mail(
                            subject="MiHora Lampa – Acceso a tu cuenta",
                            message=(
                                f"Hola {obj.nombre_completo()},\n\n"
                                "Tu correo fue actualizado en MiHora Lampa.\n"
                                "Hemos generado una contraseña temporal para que puedas iniciar sesión:\n\n"
                                f"Usuario (RUT): {obj.rut}\n"
                                f"Correo: {obj.email}\n"
                                f"Contraseña temporal: {nueva_clave_plana}\n\n"
                                "Por seguridad, al ingresar se te pedirá cambiar la contraseña.\n\n"
                                "Saludos,\nEquipo MiHora Lampa"
                            ),
                            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                            recipient_list=[obj.email],
                            fail_silently=False,
                        )
                        messages.success(request, "Paciente actualizado. Se envió la nueva contraseña al correo.")
                    except Exception as e:
                        messages.error(request, f"Paciente actualizado, pero ocurrió un error al enviar el correo: {e}")
                else:
                    if email_cambio and not nuevo_email:
                        messages.success(request, "Paciente actualizado. Se eliminó el correo y la contraseña (sin acceso web).")
                    else:
                        messages.success(request, "Paciente actualizado correctamente.")

                return redirect("paciente_detail", pk=obj.pk)

            except Exception as e:
                messages.error(request, f"Ocurrió un error al guardar: {e}")
        else:
            messages.error(request, "Revisa los errores del formulario.")
    else:
        form = PacienteEditForm(instance=paciente)

    return render(request, "admin/recepcion/listado_editar_paciente.html", {"form": form, "paciente": paciente})

@role_required("Recepción")
def recep_agendas_list(request):
    fecha_str = request.GET.get("fecha")    # yyyy-mm-dd
    prof_id = request.GET.get("prof")       # id profesional
    estado = request.GET.get("estado", "todos")  # todos | libres | ocupados

    fecha = parse_date(fecha_str) if fecha_str else timezone.localdate()
    tz = timezone.get_current_timezone()
    inicio_dia = timezone.make_aware(datetime.combine(fecha, time.min), tz)
    fin_dia    = timezone.make_aware(datetime.combine(fecha, time.max), tz)


    qs = (Agenda.objects
          .filter(inicio__gte=inicio_dia, inicio__lte=fin_dia)
          .select_related("profesional", "ubicacion", "profesional__especialidad")
          .order_by("inicio", "profesional__apellido", "profesional__nombre"))

    if prof_id:
        qs = qs.filter(profesional_id=prof_id)

    qs = qs.prefetch_related(Prefetch("cita", queryset=Cita.objects.select_related("paciente", "estado")))

    if estado == "libres":
        agendas = [a for a in qs if not hasattr(a, "cita")]
    elif estado == "ocupados":
        agendas = [a for a in qs if hasattr(a, "cita")]
    else:
        agendas = list(qs)

    profesionales = Profesional.objects.filter(activo=True).order_by("apellido", "nombre")

    ctx = {
        "agendas": agendas,
        "profesionales": profesionales,
        "fecha": fecha,
        "f_fecha": fecha.strftime("%Y-%m-%d"),
        "prof_id": int(prof_id) if prof_id else None,
        "estado": estado,
    }
    return render(request, "admin/recepcion/listado_agendas.html", ctx)

@role_required("Profesional")
def pro_setup_horario(request):
    if not user_has_role(request.user, "Profesional"):
        messages.error(request, "No tienes permisos para esta sección.")
        return redirect("recep_agendas_list")

    prof = get_object_or_404(Profesional, usuario=request.user, activo=True)

    initial = {}
    sala = Ubicacion.objects.filter(nombre__iexact="Sala").first()
    if sala:
        initial["ubicacion"] = sala.pk

    if request.method == "POST":
        form = ProfesionalHorarioForm(request.POST)
        if form.is_valid():
            dias = form.dias_en_rango()
            metrics = actualizar_disponibilidad_y_regenerar(
                prof=prof,
                dias=dias,
                hora_inicio=form.cleaned_data["hora_inicio"],
                hora_fin=form.cleaned_data["hora_fin"],
                duracion=form.cleaned_data["duracion_minutos"],
                modalidad=form.cleaned_data["modalidad"],
                ubicacion=form.cleaned_data["ubicacion"],
                weeks_ahead=8,
            )

            msg = (
                "Disponibilidad actualizada. "
                f"Eliminados (libres futuros): {metrics.get('deleted_free', 0)}. "
                f"Generados: {metrics.get('created', 0)}. "
                f"Omitidos por pasado: {metrics.get('skipped_past', 0)}. "
                f"Omitidos por choque con agendas existentes: {metrics.get('skipped_overlap', 0)}."
            )
            messages.success(request, msg)
            return redirect("pro_agendas_list")
        else:
            messages.error(request, "Revisa los errores del formulario.")
    else:
        activa = (PlantillaAtencion.objects
                  .filter(profesional=prof, activo=True)
                  .order_by("dia_semana", "hora_inicio"))
        form = ProfesionalHorarioForm(initial=initial)
        if activa.exists():
            dias = sorted({p.dia_semana for p in activa})
            if dias:
                form.fields["dia_inicio"].initial = str(min(dias))
                form.fields["dia_fin"].initial = str(max(dias))
            form.fields["hora_inicio"].initial = min(p.hora_inicio for p in activa)
            form.fields["hora_fin"].initial  = max(p.hora_fin for p in activa)
            form.fields["duracion_minutos"].initial = activa.first().duracion_minutos
            form.fields["modalidad"].initial = activa.first().modalidad
            form.fields["ubicacion"].initial = activa.first().ubicacion_id

    return render(request, "admin/profesional/disponibilidad.html", {"form": form, "prof": prof})

def _back_to_list(request, default="recep_agendas_list"):
    # Vuelve al listado preservando filtros si venían en ?next=...
    next_url = request.GET.get("next") or request.POST.get("next")
    return redirect(next_url or reverse(default))

@role_required("Recepción")
def recep_asignar_cita(request, agenda_id: int):
    # next permite volver al listado con los filtros
    if request.method == "POST":
        form = AsignarCitaForm(request.POST)
        if form.is_valid():
            try:
                p = form.cleaned_data["paciente"]
                estado = form.cleaned_data["estado"]
                motivo = form.cleaned_data.get("motivo") or ""
                asignar_cita(agenda_id=agenda_id, paciente=p, estado=estado, usuario=request.user, motivo=motivo)
                messages.success(request, "Cita creada correctamente.")
                return _back_to_list(request)
            except ValidationError as e:
                form.add_error(None, e.message)
            except Exception as e:
                form.add_error(None, f"Ocurrió un error al asignar: {e}")
    else:
        form = AsignarCitaForm()

    return render(request, "admin/recepcion/citas_asignar.html", {
        "form": form,
        "agenda_id": agenda_id,
        "next": request.GET.get("next", ""),
    })

@role_required("Recepción")
def recep_cancelar_cita(request, cita_id: int):
    if request.method == "POST":
        try:
            cancelar_cita(cita_id=cita_id, usuario=request.user)
            messages.success(request, "Cita cancelada y bloque liberado.")
        except Exception as e:
            messages.error(request, f"No se pudo cancelar la cita: {e}")
        return _back_to_list(request)
    return render(request, "admin/recepcion/citas_confirmar_cancelar.html", {
        "cita_id": cita_id,
        "next": request.GET.get("next", ""),
    })

@role_required("Recepción")
def recep_cambiar_estado(request, cita_id: int):
    if request.method == "POST":
        form = CambiarEstadoCitaForm(request.POST)
        if form.is_valid():
            try:
                cambiar_estado(cita_id=cita_id, nuevo_estado=form.cleaned_data["estado"], usuario=request.user)
                messages.success(request, "Estado de la cita actualizado.")
                return _back_to_list(request)
            except Exception as e:
                form.add_error(None, f"No se pudo actualizar el estado: {e}")
    else:
        form = CambiarEstadoCitaForm()
    return render(request, "admin/recepcion/citas_cambiar_estado.html", {
        "form": form,
        "cita_id": cita_id,
        "next": request.GET.get("next", ""),
    })

def _prof_required(user):
    if not user_has_role(user, "Profesional"):
        raise PermissionDenied("No eres profesional.")

def _get_prof(user):
    return get_object_or_404(Profesional, usuario=user, activo=True)

@role_required("Profesional")
def pro_agendas_list(request):
    _prof_required(request.user)
    prof = _get_prof(request.user)

    fecha_str = request.GET.get("fecha")
    fecha = parse_date(fecha_str) if fecha_str else timezone.localdate()

    tz = timezone.get_current_timezone()
    inicio_dia = timezone.make_aware(datetime.combine(fecha, time.min), tz)
    fin_dia    = timezone.make_aware(datetime.combine(fecha, time.max), tz)

    qs = (Agenda.objects
          .filter(profesional=prof, inicio__gte=inicio_dia, inicio__lte=fin_dia)
          .select_related("ubicacion")
          .order_by("inicio"))

    # Trae la cita si existe
    qs = qs.prefetch_related(Prefetch("cita", queryset=Cita.objects.select_related("paciente", "estado")))

    ctx = {
        "agendas": qs,
        "fecha": fecha,
        "f_fecha": fecha.strftime("%Y-%m-%d"),
    }
    return render(request, "admin/profesional/agendas.html", ctx)

@role_required("Profesional")
def pro_cita_detail(request, cita_id: int):
    _prof_required(request.user)
    prof = _get_prof(request.user)

    cita = get_object_or_404(Cita.objects.select_related("agenda", "agenda__profesional", "paciente", "estado"), pk=cita_id)
    if cita.agenda.profesional_id != prof.id:
        raise PermissionDenied("No puedes gestionar citas de otros profesionales.")

    if request.method == "POST":
        form = ProCitaEstadoNotaForm(request.POST)
        if form.is_valid():
            try:
                pro_actualizar_cita_estado_y_nota(
                    cita_id=cita.id,
                    nuevo_estado=form.cleaned_data["estado"],
                    nota=form.cleaned_data.get("nota") or "",
                    usuario=request.user,
                )
                messages.success(request, "Cita actualizada.")
                # Volver a la misma página (PRG) o a su agenda del día
                return redirect(reverse("pro_cita_detail", args=[cita.id]))
            except Exception as e:
                messages.error(request, f"No se pudo actualizar la cita: {e}")
    else:
        form = ProCitaEstadoNotaForm(
            initial={
                "estado": cita.estado_id,
                "nota": cita.nota or "",
            }
        )

    return render(request, "admin/profesional/cita_detail.html", {
        "cita": cita,
        "form": form,
        "volver_agenda_url": reverse("pro_agendas_list") + f"?fecha={cita.agenda.inicio.date():%Y-%m-%d}",
    })

@paciente_login_required
def paciente_citas(request):
    paciente = request.paciente
    now = timezone.now()

    base_qs = (Cita.objects
        .filter(paciente=paciente)
        .select_related(
            "estado",
            "agenda",
            "agenda__profesional",
            "agenda__profesional__especialidad",
            "agenda__ubicacion",
        )
    )

    proximas = base_qs.filter(agenda__inicio__gte=now).order_by("agenda__inicio")
    pasadas_qs = base_qs.filter(agenda__inicio__lt=now).order_by("-agenda__inicio")

    paginator = Paginator(pasadas_qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    ctx = {"proximas": proximas, "page_obj": page_obj}
    return render(request, "paciente/mis_citas.html", ctx)


# --- Utilidades internas ---

def _utcstamp(dt):
    """Retorna dt en UTC con formato iCal YYYYMMDDTHHMMSSZ."""
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.strftime("%Y%m%dT%H%M%SZ")

def _cita_title(cita: Cita) -> str:
    prof = cita.agenda.profesional
    return f"Cita COSAM Lampa con {prof.nombre} {prof.apellido}".strip()

def _cita_location(cita: Cita) -> str:
    # Si la modalidad es teleconsulta, puedes personalizar el texto.
    if cita.agenda.modalidad == Agenda.Modalidad.TELECONSULTA:
        return "Teleconsulta (COSAM Lampa)"
    return cita.agenda.ubicacion.nombre or "COSAM Lampa"

def _cita_description(cita: Cita) -> str:
    paciente = cita.paciente
    estado   = cita.estado.nombre
    motivo   = cita.motivo or ""
    nota     = cita.nota or ""
    return (
        f"Paciente: {paciente.nombre_completo()}\n"
        f"Estado: {estado}\n"
        f"Motivo: {motivo}\n"
        f"Nota: {nota}\n"
        "Generado por MiHora Lampa."
    ).strip()

def _time_range_from_agenda(cita: Cita):
    """Usa Agenda.inicio/fin (tu modelo ya los tiene)."""
    start_dt = cita.agenda.inicio
    end_dt   = cita.agenda.fin
    # por si viniera naive
    if timezone.is_naive(start_dt):
        start_dt = timezone.make_aware(start_dt, timezone.get_current_timezone())
    if timezone.is_naive(end_dt):
        end_dt = timezone.make_aware(end_dt, timezone.get_current_timezone())
    return start_dt, end_dt

# --- Descarga .ICS ---

@paciente_login_required
def paciente_cita_ics(request, cita_id: int):
    # solo el dueño de la cita
    cita = get_object_or_404(
        Cita.objects.select_related(
            "paciente", "estado", "agenda", "agenda__profesional", "agenda__ubicacion"
        ),
        pk=cita_id, paciente=request.paciente
    )

    start_dt, end_dt = _time_range_from_agenda(cita)
    uid      = f"cita-{cita.id}@mihora-lampa"
    dtstamp  = _utcstamp(timezone.now())
    dtstart  = _utcstamp(start_dt)
    dtend    = _utcstamp(end_dt)
    summary  = _cita_title(cita)
    location = _cita_location(cita)
    desc     = _cita_description(cita).replace("\n", "\\n")

    ics = (
        "BEGIN:VCALENDAR\r\n"
        "PRODID:-//MiHora Lampa//ES\r\n"
        "VERSION:2.0\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:PUBLISH\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{dtstamp}\r\n"
        f"DTSTART:{dtstart}\r\n"
        f"DTEND:{dtend}\r\n"
        f"SUMMARY:{summary}\r\n"
        f"DESCRIPTION:{desc}\r\n"
        f"LOCATION:{location}\r\n"
        "BEGIN:VALARM\r\n"
        "ACTION:DISPLAY\r\n"
        "DESCRIPTION:Recordatorio de cita\r\n"
        "TRIGGER:-PT60M\r\n"
        "END:VALARM\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    resp = HttpResponse(ics, content_type="text/calendar; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="cita-{cita.id}.ics"'
    return resp

# --- Deep link Google Calendar ---

@paciente_login_required
def paciente_cita_google(request, cita_id: int):
    cita = get_object_or_404(
        Cita.objects.select_related(
            "paciente", "estado", "agenda", "agenda__profesional", "agenda__ubicacion"
        ),
        pk=cita_id, paciente=request.paciente
    )
    start_dt, end_dt = _time_range_from_agenda(cita)

    params = {
        "action": "TEMPLATE",
        "text": _cita_title(cita),
        "dates": f"{_utcstamp(start_dt)}/{_utcstamp(end_dt)}",
        "details": _cita_description(cita),
        "location": _cita_location(cita),
        "trp": "false",
    }
    url = "https://calendar.google.com/calendar/render?" + urlencode(params, quote_via=quote)
    return redirect(url)

def acceso_denegado(request):
    return render(request, "core/html/acceso_denegado.html", status=403)



