from datetime import datetime, timedelta, time
from django.utils import timezone
from django.db import transaction
from core.models import Agenda, PlantillaAtencion, Profesional

def _daterange_days(start_date, end_date):
    cur = start_date
    while cur < end_date:
        yield cur
        cur += timedelta(days=1)

def _combine(d, t, tz):
    naive = datetime.combine(d, t)
    return timezone.make_aware(naive, tz)

def _slots_for_day(d, plantilla, tz):
    start_dt = _combine(d, plantilla.hora_inicio, tz)
    end_dt   = _combine(d, plantilla.hora_fin, tz)
    delta = timedelta(minutes=plantilla.duracion_minutos)
    slots, cursor = [], start_dt
    while cursor + delta <= end_dt:
        slots.append((cursor, cursor + delta))
        cursor += delta
    return slots

@transaction.atomic
def crear_plantillas_basicas(prof: Profesional, dias, hora_inicio, hora_fin, duracion, modalidad, ubicacion):
    # Desactiva plantillas activas (reemplazo simple)
    PlantillaAtencion.objects.filter(profesional=prof, activo=True).update(activo=False)
    nuevas = [
        PlantillaAtencion(
            profesional=prof,
            dia_semana=d,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            duracion_minutos=duracion,
            modalidad=modalidad,
            ubicacion=ubicacion,
            activo=True
        ) for d in dias
    ]
    PlantillaAtencion.objects.bulk_create(nuevas, ignore_conflicts=True)
    return len(nuevas)

@transaction.atomic
def generar_agendas_para_profesional(prof: Profesional, weeks_ahead: int = 8, tz=None):
    if tz is None:
        tz = timezone.get_current_timezone()
    hoy = timezone.localdate()
    fin = hoy + timedelta(weeks=weeks_ahead)

    plantillas = (PlantillaAtencion.objects
                  .filter(profesional=prof, activo=True)
                  .select_related("ubicacion"))
    if not plantillas.exists():
        return 0

    to_create = []
    for day in _daterange_days(hoy, fin):
        wd = day.weekday()
        for p in plantillas:
            if p.dia_semana != wd:
                continue
            for inicio, termino in _slots_for_day(day, p, tz):
                to_create.append(Agenda(
                    profesional=prof,
                    ubicacion=p.ubicacion,
                    inicio=inicio,
                    fin=termino,
                    modalidad=p.modalidad,
                ))

    created = Agenda.objects.bulk_create(to_create, ignore_conflicts=True)  # no duplica por unique
    return len(created)

def _inicio_de_hoy(tz=None):
    if tz is None:
        tz = timezone.get_current_timezone()
    hoy = timezone.localdate()
    return timezone.make_aware(datetime.combine(hoy, time.min), tz)

@transaction.atomic
def eliminar_bloques_futuros_libres(prof: Profesional, desde=None, cubrir_hoy_completo=False):
    """
    Elimina agendas (slots) LIBRES del profesional:
    - Si cubrir_hoy_completo=True, borra desde el inicio del día actual.
    - Si no, borra desde 'desde' (por defecto: ahora).
    """
    tz = timezone.get_current_timezone()
    if cubrir_hoy_completo:
        desde = _inicio_de_hoy(tz)
    elif desde is None:
        desde = timezone.now()

    qs = Agenda.objects.filter(profesional=prof, inicio__gte=desde, cita__isnull=True)
    count = qs.count()
    qs.delete()
    return count

@transaction.atomic
def actualizar_disponibilidad_y_regenerar(
    prof: Profesional, *, dias, hora_inicio, hora_fin,
    duracion, modalidad, ubicacion, weeks_ahead=8,
):
    """
    - Desactiva plantillas activas y crea las nuevas.
    - Elimina SIEMPRE bloques futuros libres desde el inicio del día (no toca los con cita).
    - Regenera horizonte (8 semanas por defecto).
    """
    # 1) Plantillas
    PlantillaAtencion.objects.filter(profesional=prof, activo=True).update(activo=False)
    nuevas = [
        PlantillaAtencion(
            profesional=prof, dia_semana=d,
            hora_inicio=hora_inicio, hora_fin=hora_fin,
            duracion_minutos=duracion, modalidad=modalidad,
            ubicacion=ubicacion, activo=True
        ) for d in dias
    ]
    PlantillaAtencion.objects.bulk_create(nuevas, ignore_conflicts=True)

    # 2) Borrar HOY completo en adelante (solo libres)
    eliminar_bloques_futuros_libres(prof, cubrir_hoy_completo=True)

    # 3) Regenerar
    return generar_agendas_para_profesional(prof, weeks_ahead=weeks_ahead, tz=timezone.get_current_timezone())
