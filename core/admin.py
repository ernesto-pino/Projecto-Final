from django.contrib import admin
from .models import (
    Role, UserRole,
    Especialidad, Profesional,
    Ubicacion, EstadoCita,
    Agenda, Paciente, Cita,
    AuditoriaCita, ContactoCita
)


# =========================
#  ROLES / USUARIOS
# =========================

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre")
    search_fields = ("nombre",)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "rol")
    list_filter = ("rol",)
    search_fields = ("usuario__username", "rol__nombre")


# =========================
#  ESPECIALIDAD / PROFESIONAL
# =========================

@admin.register(Especialidad)
class EspecialidadAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre")
    search_fields = ("nombre",)


@admin.register(Profesional)
class ProfesionalAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "apellido", "especialidad", "email", "telefono", "activo")
    list_filter = ("activo", "especialidad")
    search_fields = ("nombre", "apellido", "email", "telefono")


# =========================
#  UBICACIONES
# =========================

@admin.register(Ubicacion)
class UbicacionAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre")
    search_fields = ("nombre",)


# =========================
#  ESTADOS DE CITA
# =========================

@admin.register(EstadoCita)
class EstadoCitaAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre")
    search_fields = ("nombre",)


# =========================
#  AGENDA
# =========================

@admin.register(Agenda)
class AgendaAdmin(admin.ModelAdmin):
    list_display = ("id", "profesional", "ubicacion", "inicio", "fin", "capacidad", "modalidad")
    list_filter = ("profesional", "ubicacion", "modalidad")
    search_fields = ("profesional__nombre", "profesional__apellido", "ubicacion__nombre")
    date_hierarchy = "inicio"


# =========================
#  PACIENTES
# =========================

@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ("id", "rut", "nombre", "apellido", "email", "telefono")
    search_fields = ("rut", "nombre", "apellido", "email", "telefono")
    list_filter = ("apellido",)


# =========================
#  CITAS
# =========================

@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ("id", "paciente", "agenda", "estado", "creado_por", "creado_en")
    list_filter = ("estado", "agenda__profesional", "agenda__ubicacion")
    search_fields = ("paciente__nombre", "paciente__apellido", "agenda__profesional__nombre")
    date_hierarchy = "creado_en"


# =========================
#  AUDITORÍA DE CITAS
# =========================

@admin.register(AuditoriaCita)
class AuditoriaCitaAdmin(admin.ModelAdmin):
    list_display = ("id", "cita", "usuario", "accion", "creado_en")
    list_filter = ("accion", "usuario")
    search_fields = ("cita__paciente__nombre", "cita__paciente__apellido", "accion")
    date_hierarchy = "creado_en"


# =========================
#  CONTACTOS DE CITA
# =========================

@admin.register(ContactoCita)
class ContactoCitaAdmin(admin.ModelAdmin):
    list_display = ("id", "cita", "usuario", "canal", "resultado", "fecha_contacto")
    list_filter = ("canal", "resultado", "usuario")
    search_fields = ("cita__paciente__nombre", "cita__paciente__apellido", "descripcion")
    date_hierarchy = "fecha_contacto"

class CustomAdminSite(admin.AdminSite):
    class Media:
        css = {
            "all": ("core/css/admin_custom.css",)
        }

# Aplica el CSS al admin actual
admin.site.__class__.Media = CustomAdminSite.Media