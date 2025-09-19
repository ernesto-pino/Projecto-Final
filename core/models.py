from django.db import models
from django.conf import settings
from django.utils import timezone

# =========================
#  ROLES (RBAC simple)
# =========================

class Role(models.Model):
    class Meta:
        db_table = "roles"
        verbose_name = "Rol"
        verbose_name_plural = "Roles"

    # Ej: Administrador, Recepción, Profesional, Auditor
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre


class UserRole(models.Model):
    class Meta:
        db_table = "usuario_rol"
        unique_together = (("usuario", "rol"),)
        verbose_name = "Rol de usuario"
        verbose_name_plural = "Roles de usuario"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="roles_asignados"
    )
    rol = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="usuarios"
    )


# =========================
#  ESPECIALIDADES / PROFESIONALES
# =========================

class Especialidad(models.Model):
    class Meta:
        db_table = "especialidades"
        verbose_name = "Especialidad"
        verbose_name_plural = "Especialidades"

    # Ej: Psicología, Psiquiatría, Terapia Ocupacional
    nombre = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.nombre


class Profesional(models.Model):
    class Meta:
        db_table = "profesionales"
        verbose_name = "Profesional"
        verbose_name_plural = "Profesionales"

    # Opcional: si el profesional también usa el sistema (tiene login)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="perfil_profesional"
    )
    nombre = models.CharField(max_length=120)
    apellido = models.CharField(max_length=120)
    especialidad = models.ForeignKey(
        Especialidad,
        on_delete=models.PROTECT,
        related_name="profesionales"
    )
    email = models.EmailField(max_length=190, blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True, null=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre} {self.apellido} – {self.especialidad.nombre}"


# =========================
#  UBICACIONES (Box / Sala)
# =========================

class Ubicacion(models.Model):
    class Meta:
        db_table = "ubicaciones"
        verbose_name = "Ubicación"
        verbose_name_plural = "Ubicaciones"
        constraints = [
            models.UniqueConstraint(fields=["nombre"], name="uk_ubicacion_nombre"),
        ]

    # Ej: "Box 1", "Box 2", "Sala grupal"
    nombre = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.nombre


# =========================
#  ESTADOS DE CITA
# =========================

class EstadoCita(models.Model):
    class Meta:
        db_table = "estados_cita"
        verbose_name = "Estado de cita"
        verbose_name_plural = "Estados de cita"

    # Ej: Pendiente, Confirmada, Atendida, Ausente, Cancelada
    nombre = models.CharField(max_length=80, unique=True)

    def __str__(self):
        return self.nombre


# =========================
#  AGENDAS (Bloques de disponibilidad)
# =========================

class Agenda(models.Model):
    class Modalidad(models.TextChoices):
        PRESENCIAL = "presencial", "Presencial"
        TELECONSULTA = "teleconsulta", "Teleconsulta"

    class Meta:
        db_table = "agendas"
        verbose_name = "Agenda (bloque)"
        verbose_name_plural = "Agendas (bloques)"
        indexes = [
            models.Index(fields=["inicio"]),
            models.Index(fields=["profesional", "inicio", "fin"]),
        ]
        constraints = [
            # Evita bloques duplicados exactos para el mismo profesional
            models.UniqueConstraint(fields=["profesional", "inicio", "fin"], name="uk_agenda_prof_inicio_fin"),
        ]

    profesional = models.ForeignKey(Profesional, on_delete=models.PROTECT, related_name="agendas")
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.PROTECT, related_name="agendas")
    inicio = models.DateTimeField()
    fin = models.DateTimeField()
    capacidad = models.PositiveSmallIntegerField(default=1)  # >1 si es grupal
    modalidad = models.CharField(max_length=20, choices=Modalidad.choices, default=Modalidad.PRESENCIAL)
    observaciones = models.CharField(max_length=255, blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.fin and self.inicio and self.fin <= self.inicio:
            raise ValidationError("El fin debe ser posterior al inicio.")

    def __str__(self):
        return f"{self.profesional} | {self.inicio:%d/%m %H:%M}-{self.fin:%H:%M} ({self.ubicacion})"


# =========================
#  PACIENTES
# =========================

class Paciente(models.Model):
    class Meta:
        db_table = "pacientes"
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["apellido"]),
        ]

    # RUT obligatorio y único (email opcional)
    rut = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=120)
    apellido = models.CharField(max_length=120)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    email = models.EmailField(max_length=190, blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True, null=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre} {self.apellido}"


# =========================
#  CITAS (Reservas)
# =========================

class Cita(models.Model):
    class Meta:
        db_table = "citas"
        verbose_name = "Cita"
        verbose_name_plural = "Citas"
        indexes = [
            models.Index(fields=["agenda", "estado"]),
            models.Index(fields=["paciente"]),
        ]

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="citas")
    agenda = models.ForeignKey(Agenda, on_delete=models.CASCADE, related_name="citas")
    estado = models.ForeignKey(EstadoCita, on_delete=models.PROTECT, related_name="citas")

    motivo = models.CharField(max_length=255, blank=True, null=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="citas_registradas"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now_add=False, auto_now=True)

    # Nota: si quieres "1 cita por agenda" cuando capacidad=1,
    # valida a nivel de servicio usando select_for_update() y conteo antes de crear.

    def __str__(self):
        return f"Cita de {self.paciente} con {self.agenda.profesional} el {self.agenda.inicio:%d/%m %H:%M}"


# =========================
#  AUDITORÍA DE CITAS (historial de cambios)
# =========================

class AuditoriaCita(models.Model):
    class Accion(models.TextChoices):
        CREAR = "crear", "Crear"
        ACTUALIZAR = "actualizar", "Actualizar"
        CAMBIAR_ESTADO = "cambiar_estado", "Cambiar estado"
        CANCELAR = "cancelar", "Cancelar"
        REPROGRAMAR = "reprogramar", "Reprogramar"

    class Meta:
        db_table = "auditoria_citas"
        verbose_name = "Auditoría de cita"
        verbose_name_plural = "Auditoría de citas"
        indexes = [
            models.Index(fields=["cita"]),
            models.Index(fields=["usuario"]),
            models.Index(fields=["creado_en"]),
        ]

    cita = models.ForeignKey(Cita, on_delete=models.CASCADE, related_name="auditoria")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="auditorias_citas"
    )
    accion = models.CharField(max_length=20, choices=Accion.choices)
    detalle = models.JSONField(blank=True, null=True)  # requiere Django 3.1+ y MySQL 5.7+/8.0+
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.creado_en:%Y-%m-%d %H:%M}] {self.accion} (cita {self.cita_id})"


# =========================
#  CONTACTO MANUAL (gestiones de confirmación/aviso)
# =========================

class ContactoCita(models.Model):
    class Canal(models.TextChoices):
        LLAMADA = "llamada", "Llamada"
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        WHATSAPP = "whatsapp", "WhatsApp"
        OTRO = "otro", "Otro"

    class Resultado(models.TextChoices):
        CONFIRMADO = "confirmado", "Confirmado"
        RECHAZADO = "rechazado", "Rechazado"
        SIN_RESPUESTA = "sin_respuesta", "Sin respuesta"
        OTRO = "otro", "Otro"

    class Meta:
        db_table = "contactos_cita"
        verbose_name = "Contacto de cita"
        verbose_name_plural = "Contactos de cita"
        indexes = [
            models.Index(fields=["cita"]),
            models.Index(fields=["fecha_contacto"]),
        ]

    cita = models.ForeignKey(Cita, on_delete=models.CASCADE, related_name="contactos")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contactos_realizados"
    )
    fecha_contacto = models.DateTimeField(auto_now_add=True)
    canal = models.CharField(max_length=20, choices=Canal.choices)
    resultado = models.CharField(max_length=20, choices=Resultado.choices)
    contacto_con = models.CharField(max_length=120, blank=True, null=True)  # ej. "madre del paciente"
    descripcion = models.TextField(blank=True, null=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.canal} - {self.resultado} (cita {self.cita_id})"