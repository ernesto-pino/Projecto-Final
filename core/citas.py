from django.db import transaction
from django.core.exceptions import ValidationError
from core.models import Agenda, Cita, EstadoCita, AuditoriaCita, Paciente

@transaction.atomic
def asignar_cita(agenda_id: int, paciente: Paciente, estado: EstadoCita, usuario, motivo: str | None = None) -> Cita:
    # Lock del slot para evitar carreras
    slot = Agenda.objects.select_for_update().get(pk=agenda_id)
    if hasattr(slot, "cita"):
        raise ValidationError("Este horario ya fue asignado.")

    cita = Cita.objects.create(
        agenda=slot,
        paciente=paciente,
        estado=estado,
        motivo=motivo or "",
        creado_por=usuario,
    )
    AuditoriaCita.objects.create(
        cita=cita,
        usuario=usuario,
        accion=AuditoriaCita.Accion.CREAR,
        detalle={"motivo": motivo or "", "paciente_id": paciente.id, "estado": estado.nombre},
    )
    return cita

@transaction.atomic
def cancelar_cita(cita_id: int, usuario):
    cita = Cita.objects.select_related("agenda", "paciente").get(pk=cita_id)
    AuditoriaCita.objects.create(
        cita=cita,
        usuario=usuario,
        accion=AuditoriaCita.Accion.CANCELAR,
        detalle={"paciente_id": cita.paciente_id},
    )
    # Eliminar la cita => el slot queda libre
    cita.delete()

@transaction.atomic
def cambiar_estado(cita_id: int, nuevo_estado: EstadoCita, usuario):
    cita = Cita.objects.select_related("agenda", "paciente").get(pk=cita_id)
    anterior = cita.estado
    if anterior_id := getattr(anterior, "id", None) == nuevo_estado.id:
        return cita  # sin cambios
    cita.estado = nuevo_estado
    cita.save(update_fields=["estado"])
    AuditoriaCita.objects.create(
        cita=cita,
        usuario=usuario,
        accion=AuditoriaCita.Accion.CAMBIAR_ESTADO,
        detalle={"antes": getattr(anterior, "nombre", None), "despues": nuevo_estado.nombre},
    )
    return cita

@transaction.atomic
def pro_actualizar_cita_estado_y_nota(*, cita_id: int, nuevo_estado: EstadoCita, nota: str, usuario):
    """
    Cambia el estado y/o la nota de una cita y registra auditoría.
    """
    cita = Cita.objects.select_related("agenda", "agenda__profesional").get(pk=cita_id)
    cambios = {}

    # estado
    if cita.estado_id != nuevo_estado.id:
        anterior = cita.estado.nombre
        cita.estado = nuevo_estado
        cambios["estado"] = {"antes": anterior, "despues": nuevo_estado.nombre}

    # nota
    nota = (nota or "").strip()
    if (cita.nota or "") != nota:
        cambios["nota"] = {"antes": cita.nota, "despues": nota}
        cita.nota = nota

    if cambios:
        cita.save(update_fields=["estado", "nota", "actualizado_en"])
        AuditoriaCita.objects.create(
            cita=cita,
            usuario=usuario,
            accion=AuditoriaCita.Accion.ACTUALIZAR,
            detalle=cambios,
        )

    return cita