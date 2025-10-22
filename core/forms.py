from django import forms
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.core.exceptions import ValidationError
import re
from .models import Paciente, PlantillaAtencion, Ubicacion, Agenda
import string
from datetime import date

class CustomPasswordResetForm(PasswordResetForm):
    # Personaliza el campo para mensajes y estilos
    email = forms.EmailField(
        label="Correo electrónico",
        error_messages={
            "required": "El correo es obligatorio.",
            "invalid": "Por favor ingrese un correo válido.",
        },
        widget=forms.EmailInput(attrs={"class": "form-control", "autocomplete": "email"}),
    )

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        errors = []

        # (Opcional) chequeo extra simple de formato (si quieres reforzar)
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors.append("El formato del correo no es válido.")

        # Si acumulas errores, los lanzas todos juntos
        if errors:
            raise ValidationError(errors)

        return email

class CustomSetPasswordForm(SetPasswordForm):
    error_messages = {
        **SetPasswordForm.error_messages,
        "password_mismatch": "Las contraseñas no coinciden.",
    }

    # Mensaje de requerido en español para el 2° campo
    new_password2 = forms.CharField(
        label="Confirmar contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        error_messages={"required": "Por favor confirme la contraseña."},
    )

    # (Opcional) también puedes personalizar 'required' en new_password1:
    new_password1 = forms.CharField(
        label="Nueva contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        error_messages={"required": "Por favor ingrese una contraseña."},
    )

    def clean_new_password1(self):
        password1 = self.cleaned_data.get("new_password1") or ""
        errors = []

        # Reglas
        if len(password1) < 8:
            errors.append("Debe tener al menos 8 caracteres.")
        if not re.search(r"[a-z]", password1):
            errors.append("Debe incluir al menos una letra minúscula.")
        if not re.search(r"[A-Z]", password1):
            errors.append("Debe incluir al menos una letra mayúscula.")
        if not re.search(r"[0-9]", password1):
            errors.append("Debe incluir al menos un número.")
        if not re.search(r"[^A-Za-z0-9]", password1):
            errors.append("Debe incluir al menos un símbolo (ej: !, @, #, $).")
        if password1 and self.user.check_password(password1):
            errors.append("No puede ser igual a la contraseña anterior.")

        if errors:
            # Lanza todos los errores juntos
            raise ValidationError(errors)

        return password1

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("new_password1")
        p2 = cleaned.get("new_password2")

        # Si ambos existen pero no coinciden, error "global"
        if p1 and p2 and p1 != p2:
            raise ValidationError("Las contraseñas no coinciden.")
        return cleaned

class LoginPacienteForm(forms.Form):
    rut = forms.CharField(label="RUT", max_length=20)
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput)

    def clean(self):
        data = super().clean()
        # Solo normalizamos; NO validamos ni levantamos errores aquí
        data["rut"] = normaliza_rut(data.get("rut", ""))
        return data



class CambioPasswordPacienteForm(forms.Form):
    password_actual = forms.CharField(label="Contraseña actual", widget=forms.PasswordInput)
    nueva_password = forms.CharField(label="Nueva contraseña", widget=forms.PasswordInput)
    confirmar_password = forms.CharField(label="Confirmar nueva contraseña", widget=forms.PasswordInput)

    def clean(self):
        data = super().clean()
        nueva = (data.get("nueva_password") or "").strip()
        conf  = (data.get("confirmar_password") or "").strip()

        errores = []
        if len(nueva) < 8: errores.append("Debe tener al menos 8 caracteres.")
        if not re.search(r"[a-z]", nueva): errores.append("Debe incluir al menos una minúscula.")
        if not re.search(r"[A-Z]", nueva): errores.append("Debe incluir al menos una mayúscula.")
        if not re.search(r"\d", nueva): errores.append("Debe incluir al menos un número.")
        if not re.search(r"[^\w\s]", nueva): errores.append("Debe incluir al menos un símbolo (ej. !@#$%).")
        if nueva != conf: errores.append("La confirmación no coincide con la nueva contraseña.")
        if errores: raise ValidationError(errores)
        return data


class SolicitarResetForm(forms.Form):
    # Puedes permitir RUT O Email. Acá uso uno solo por simpleza; cambia a dos campos si prefieres.
    rut = forms.CharField(label="RUT", max_length=20)

class ResetPasswordForm(forms.Form):
    nueva_password = forms.CharField(label="Nueva contraseña", widget=forms.PasswordInput)
    confirmar_password = forms.CharField(label="Confirmar contraseña", widget=forms.PasswordInput)

    def clean(self):
        data = super().clean()
        nueva = (data.get("nueva_password") or "").strip()
        conf  = (data.get("confirmar_password") or "").strip()

        errores = []
        if len(nueva) < 8: errores.append("Debe tener al menos 8 caracteres.")
        if not re.search(r"[a-z]", nueva): errores.append("Debe incluir al menos una minúscula.")
        if not re.search(r"[A-Z]", nueva): errores.append("Debe incluir al menos una mayúscula.")
        if not re.search(r"\d", nueva): errores.append("Debe incluir al menos un número.")
        if not re.search(r"[^\w\s]", nueva): errores.append("Debe incluir al menos un símbolo (ej. !@#$%).")
        if nueva != conf: errores.append("La confirmación no coincide con la nueva contraseña.")
        if errores: raise ValidationError(errores)
        return data

# --- Helpers RUT/telefono ---
def normaliza_rut(rut: str) -> str:
    rut = (rut or "").upper().replace(".", "").replace(" ", "")
    if "-" not in rut and len(rut) > 1:
        rut = rut[:-1] + "-" + rut[-1]
    return rut

def valida_rut_chileno(rut: str) -> bool:
    rut = normaliza_rut(rut)
    if not re.match(r"^\d{1,8}-[\dkK]$", rut):
        return False
    numero, dv = rut.split("-")
    s, m = 0, 2
    for d in reversed(numero):
        s += int(d) * m
        m = 2 if m == 7 else m + 1
    r = 11 - (s % 11)
    dv_calc = "0" if r == 11 else "K" if r == 10 else str(r)
    return dv_calc == dv.upper()

def normaliza_telefono_cl(telefono: str) -> str:
    """Devuelve +56XXXXXXXXX (9 dígitos nacionales)"""
    t = (telefono or "").strip()
    # deja solo dígitos y '+'
    t = re.sub(r"[^\d+]", "", t)
    # quita +, para contar
    digits = re.sub(r"\D", "", t)
    # si empieza con 56 ya viene con país
    if digits.startswith("56"):
        digits = digits[2:]
    # ahora digits debería tener 9 dígitos (móvil o fijo nacional)
    if len(digits) != 9:
        return ""  # señal de inválido
    return "+56" + digits

def _fecha_min_200_anios():
    hoy = date.today()
    try:
        return hoy.replace(year=hoy.year - 200)
    except ValueError:
        # si es 29/FEB ajusta a 28/FEB
        return hoy.replace(year=hoy.year - 200, day=28)

# Regex solo letras (incluye tildes y ñ) y espacios, 2-50 chars
RE_SOLO_LETRAS_ESPACIOS = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]{2,50}$")

class PacienteCreateForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = ["rut", "nombres", "apellidos", "fecha_nacimiento", "telefono", "email", "direccion"]
        widgets = {"fecha_nacimiento": forms.DateInput(attrs={"type": "date"})}
        error_messages = {
            "rut": {"unique": "Ya existe un paciente con este RUT."},
            "email": {"unique": "Este correo ya está registrado."},
            "telefono": {"unique": "Este teléfono ya está registrado."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Requeridos (email opcional)
        for f in ["rut", "nombres", "apellidos"]:
            self.fields[f].required = True
        self.fields["telefono"].required = False
        self.fields["email"].required = False

        # Placeholders + validaciones HTML
        self.fields["rut"].widget.attrs.update({
            "placeholder": "12.345.678-5",
            "pattern": r"^\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]$|^\d{7,8}-[\dkK]$",
            "title": "Ej: 12.345.678-5 o 12345678-5",
        })

        # Nombres y apellidos: solo letras (incluye tildes/ñ) y espacios, 2-50
        for fname in ("nombres", "apellidos"):
            self.fields[fname].widget.attrs.update({
                "placeholder": "Ej: Juan Andrés",
                "pattern": r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]{2,50}",
                "minlength": "2",
                "maxlength": "50",
                "title": "Solo letras y espacios, entre 2 y 50 caracteres.",
            })

        # Fecha: <= hoy y >= hoy-200 años
        hoy = date.today()
        min_f = _fecha_min_200_anios()
        self.fields["fecha_nacimiento"].widget.attrs.update({
            "max": hoy.isoformat(),
            "min": min_f.isoformat(),
            "title": f"Entre {min_f.isoformat()} y {hoy.isoformat()}",
        })

        # Teléfono: +56XXXXXXXXX o 9 dígitos nacionales
        self.fields["telefono"].widget.attrs.update({
            "placeholder": "+56912345678 o 912345678",
            "pattern": r"^(\+?56)?\d{9}$",
            "title": "Formato válido: +56912345678 o 912345678",
            "inputmode": "tel",
        })

        # Dirección: máximo 100 (aunque el modelo acepte 255)
        self.fields["direccion"].widget.attrs.update({
            "maxlength": "100",
            "title": "Máximo 100 caracteres.",
            "placeholder": "Calle 123, Depto 45",
        })

        # Email opcional (EmailField ya valida formato si se ingresa)
        self.fields["email"].widget.attrs.update({
            "placeholder": "correo@dominio.cl",
        })

    # ---- Validaciones servidor ----
    def clean_rut(self):
        rut = normaliza_rut(self.cleaned_data.get("rut"))
        if not valida_rut_chileno(rut):
            raise ValidationError("RUT inválido.")
        if Paciente.objects.filter(rut=rut).exists():
            raise ValidationError("Ya existe un paciente con este RUT.")
        return rut

    def _valida_nombre_like(self, valor: str, campo: str) -> str:
        val = (valor or "").strip()
        # colapsar espacios múltiples
        val = re.sub(r"\s+", " ", val)
        if not RE_SOLO_LETRAS_ESPACIOS.fullmatch(val):
            raise ValidationError(f"{campo} inválido: solo letras y espacios (2 a 50 caracteres).")
        return val

    def clean_nombres(self):
        return self._valida_nombre_like(self.cleaned_data.get("nombres"), "Nombres")

    def clean_apellidos(self):
        return self._valida_nombre_like(self.cleaned_data.get("apellidos"), "Apellidos")

    def clean_fecha_nacimiento(self):
        fnac = self.cleaned_data.get("fecha_nacimiento")
        if not fnac:
            return fnac  # opcional
        hoy = date.today()
        min_f = _fecha_min_200_anios()
        if fnac > hoy or fnac < min_f:
            raise ValidationError(f"Fecha fuera de rango: entre {min_f.isoformat()} y {hoy.isoformat()}.")
        return fnac

    def clean_telefono(self):
        tel_raw = self.cleaned_data.get("telefono")
        # Opcional: si viene vacío, lo guardamos como None (NULL en BD)
        if not tel_raw or not tel_raw.strip():
            return None

        tel_norm = normaliza_telefono_cl(tel_raw)
        if not tel_norm:
            raise ValidationError("Formato de teléfono inválido. Use +56912345678 o 912345678.")
        if not re.fullmatch(r"^\+56\d{9}$", tel_norm):
            raise ValidationError("Formato de teléfono inválido.")
        if Paciente.objects.filter(telefono=tel_norm).exists():
            raise ValidationError("Este teléfono ya está registrado.")
        return tel_norm

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            return ""
        if Paciente.objects.filter(email=email).exists():
            raise ValidationError("Este correo ya está registrado.")
        return email

    def clean_direccion(self):
        d = (self.cleaned_data.get("direccion") or "").strip()
        if len(d) > 100:
            raise ValidationError("La dirección no puede superar 100 caracteres.")
        return d
    
NOMBRE_RE = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñÜü\s'-]{2,50}$")

def _dos_siglos_atras(hoy: date) -> date:
    try:
        return hoy.replace(year=hoy.year - 200)
    except ValueError:
        return hoy.replace(month=2, day=28, year=hoy.year - 200)

class PacienteEditForm(forms.ModelForm):
    rut = forms.CharField(disabled=True, required=False, label="RUT")

    fecha_nacimiento = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control"},
            format="%Y-%m-%d"   # ✅ Formato ISO requerido por <input type="date">
        ),
        input_formats=["%Y-%m-%d"],        # ✅ Acepta también este formato al guardar
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Guardamos el correo original
        self._original_email = ((self.instance.email or "").strip().lower())
        self.fields["email"].widget.attrs["data-original-email"] = (self.instance.email or "")

        # Si hay fecha, seteamos el initial en formato correcto (ISO)
        if self.instance and self.instance.fecha_nacimiento:
            self.fields["fecha_nacimiento"].initial = self.instance.fecha_nacimiento.strftime("%Y-%m-%d")

    class Meta:
        model = Paciente
        fields = [
            "rut", "nombres", "apellidos", "email", "telefono",
            "fecha_nacimiento", "direccion", "is_active"
        ]
        widgets = {
            "nombres": forms.TextInput(attrs={"class": "form-control"}),
            "apellidos": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(attrs={"class": "form-control", "placeholder": "+56 9 1234 5678"}),
            "direccion": forms.TextInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


    def clean_nombres(self):
        v = (self.cleaned_data.get("nombres") or "").strip()
        if not NOMBRE_RE.match(v):
            raise ValidationError("Solo letras (incluye tildes/ñ), mínimo 2 y máximo 50 caracteres.")
        return v

    def clean_apellidos(self):
        v = (self.cleaned_data.get("apellidos") or "").strip()
        if not NOMBRE_RE.match(v):
            raise ValidationError("Solo letras (incluye tildes/ñ), mínimo 2 y máximo 50 caracteres.")
        return v

    def clean_fecha_nacimiento(self):
        f = self.cleaned_data.get("fecha_nacimiento")
        if not f:
            return None
        hoy = date.today()
        if f > hoy:
            raise ValidationError("La fecha de nacimiento no puede ser futura.")
        if f < _dos_siglos_atras(hoy):
            raise ValidationError("La fecha de nacimiento no puede ser anterior a 200 años.")
        return f

    def _normaliza_tel(self, tel_raw: str) -> str:
        digits = re.sub(r"\D", "", tel_raw or "")
        if digits.startswith("56"):
            digits = digits[2:]
        return digits

    def clean_telefono(self):
        tel = self.cleaned_data.get("telefono")
        if not tel:
            return None
        digits = self._normaliza_tel(tel)
        if len(digits) != 9:
            raise ValidationError("Teléfono inválido. Usa formato chileno de 9 dígitos (ej: 9XXXXXXXX).")
        qs = Paciente.objects.filter(telefono__iexact=digits)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Este teléfono ya está registrado en otro paciente.")
        return digits

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if not email:
            return None
        qs = Paciente.objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Este correo ya está registrado en otro paciente.")
        return email

    def has_email_changed(self):
        new = ((self.cleaned_data.get("email") or "").strip().lower())
        return self._original_email != new

class ProfesionalHorarioForm(forms.Form):
    DIA_CHOICES = PlantillaAtencion.DiaSemana.choices

    dia_inicio = forms.ChoiceField(choices=DIA_CHOICES, label="Desde el día",
                                   widget=forms.Select(attrs={"class":"form-select"}))
    dia_fin = forms.ChoiceField(choices=DIA_CHOICES, label="Hasta el día",
                                widget=forms.Select(attrs={"class":"form-select"}))
    hora_inicio = forms.TimeField(label="Hora de inicio",
                                  widget=forms.TimeInput(attrs={"type": "time", "class":"form-control"}))
    hora_fin = forms.TimeField(label="Hora de fin",
                               widget=forms.TimeInput(attrs={"type": "time", "class":"form-control"}))
    duracion_minutos = forms.IntegerField(min_value=5, max_value=240, initial=30,
                                          label="Duración por cita (min)",
                                          widget=forms.NumberInput(attrs={"class":"form-control"}))
    modalidad = forms.ChoiceField(choices=Agenda.Modalidad.choices, initial=Agenda.Modalidad.PRESENCIAL,
                                  widget=forms.Select(attrs={"class":"form-select"}))
    ubicacion = forms.ModelChoiceField(queryset=Ubicacion.objects.all(), label="Ubicación",
                                       widget=forms.Select(attrs={"class":"form-select"}))

    def clean(self):
        cleaned = super().clean()
        hi = cleaned.get("hora_inicio"); hf = cleaned.get("hora_fin")
        if hi and hf and hf <= hi:
            self.add_error("hora_fin", "La hora de fin debe ser posterior a la de inicio.")
        return cleaned

    def dias_en_rango(self):
        a = int(self.cleaned_data["dia_inicio"])
        b = int(self.cleaned_data["dia_fin"])
        return list(range(a, b+1)) if a <= b else list(range(a, 7)) + list(range(0, b+1))

