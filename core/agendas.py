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

def _overlaps(a_start, a_end, b_start, b_end) -> bool:
    """Devuelve True si [a_start, a_end) se solapa con [b_start, b_end)."""
    return a_start < b_end and a_end > b_start

@transaction.atomic
def generar_agendas_para_profesional(prof: Profesional, weeks_ahead: int = 8, tz=None):
    """
    Genera slots desde HOY hasta 'weeks_ahead', sin crear:
    - slots que ya terminaron (pasado),
    - slots que se solapen con agendas existentes (normalmente serán las que tienen cita).
    """
    if tz is None:
        tz = timezone.get_current_timezone()

    hoy = timezone.localdate()
    fin = hoy + timedelta(weeks=weeks_ahead)
    now = timezone.now()

    plantillas = (PlantillaAtencion.objects
                  .filter(profesional=prof, activo=True)
                  .select_related("ubicacion"))
    if not plantillas.exists():
        return {"created": 0, "skipped_past": 0, "skipped_overlap": 0}

    # Cargamos las agendas existentes futuras (tras haber eliminado las libres, suelen quedar las con cita)
    existentes = (Agenda.objects
                  .filter(profesional=prof, inicio__gte=_inicio_de_hoy(tz))
                  .select_related("ubicacion"))  # pueden incluir libres si no se eliminaron por alguna razón

    # Agrupar por día para chequeo de solapamiento eficiente
    existentes_por_dia = {}
    for a in existentes:
        d = a.inicio.date()
        existentes_por_dia.setdefault(d, []).append((a.inicio, a.fin))

    to_create = []
    skipped_past = 0
    skipped_overlap = 0

    for day in _daterange_days(hoy, fin):
        wd = day.weekday()
        dia_agendas = existentes_por_dia.get(day, [])
        for p in plantillas:
            if p.dia_semana != wd:
                continue
            for inicio, termino in _slots_for_day(day, p, tz):
                # 1) No crear slots en el pasado (ya terminados)
                if termino <= now:
                    skipped_past += 1
                    continue
                # 2) Evitar solapamiento con agendas existentes (reservadas u otras supervivientes)
                choque = False
                for (ei, ef) in dia_agendas:
                    if _overlaps(inicio, termino, ei, ef):
                        choque = True
                        break
                if choque:
                    skipped_overlap += 1
                    continue
                to_create.append(Agenda(
                    profesional=prof,
                    ubicacion=p.ubicacion,
                    inicio=inicio,
                    fin=termino,
                    modalidad=p.modalidad,
                ))

    created = Agenda.objects.bulk_create(to_create, ignore_conflicts=True)
    return {"created": len(created), "skipped_past": skipped_past, "skipped_overlap": skipped_overlap}

@transaction.atomic
def actualizar_disponibilidad_y_regenerar(
    prof: Profesional, *, dias, hora_inicio, hora_fin,
    duracion, modalidad, ubicacion, weeks_ahead=8,
):
    """
    - Reemplaza completamente las plantillas del profesional.
    - Elimina HOY-> futuro (solo libres).
    - Regenera evitando choques y slots en pasado.
    Devuelve métricas.
    """
    # 1) Reemplazo REAL de plantillas (borra todo lo del profesional)
    PlantillaAtencion.objects.filter(profesional=prof).delete()

    nuevas = [
        PlantillaAtencion(
            profesional=prof,
            dia_semana=d,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            duracion_minutos=duracion,
            modalidad=modalidad,
            ubicacion=ubicacion,
            activo=True,
        )
        for d in dias
    ]
    # Sin ignore_conflicts: como acabamos de borrar, no habrá colisiones
    PlantillaAtencion.objects.bulk_create(nuevas)

    # 2) Borrar HOY completo en adelante (solo libres)
    eliminados = eliminar_bloques_futuros_libres(prof, cubrir_hoy_completo=True)

    # 3) Regenerar evitando choques (ya tienes esta lógica)
    metrics = generar_agendas_para_profesional(
        prof, weeks_ahead=weeks_ahead, tz=timezone.get_current_timezone()
    )
    metrics["deleted_free"] = eliminados
    return metrics