from django import forms
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.core.exceptions import ValidationError
import re
from .models import Paciente

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
    suma, mult = 0, 2
    for d in reversed(numero):
        suma += int(d) * mult
        mult = 2 if mult == 7 else mult + 1
    resto = 11 - (suma % 11)
    dv_calc = "0" if resto == 11 else "K" if resto == 10 else str(resto)
    return dv_calc == dv.upper()

def normaliza_telefono_cl(telefono: str) -> str:
    t = (telefono or "").strip()
    t = re.sub(r"[^\d+]", "", t)  # deja sólo dígitos y +
    if t.startswith("+56"):
        return t
    if t.startswith("56"):
        return "+" + t
    solo = re.sub(r"\D", "", t)
    if solo:  # asume Chile
        return "+56" + solo
    return t

class PacienteCreateForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = [
            "rut", "nombres", "apellidos", "fecha_nacimiento",
            "telefono", "email", "direccion",
        ]
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
        }
        error_messages = {
            "rut": {"unique": "Ya existe un paciente con este RUT."},
            "email": {"unique": "Este correo ya está registrado."},
            "telefono": {"unique": "Este teléfono ya está registrado."},
            "nombres": {"required": "El nombre es obligatorio."},
            "apellidos": {"required": "El apellido es obligatorio."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Requeridos según tu modelo/negocio:
        self.fields["rut"].required = True
        self.fields["nombres"].required = True
        self.fields["apellidos"].required = True
        self.fields["telefono"].required = False   # aunque en el modelo es blank=True, tú lo quieres obligatorio
        self.fields["email"].required = False      # idem

        # Placeholders y patterns (esto reemplaza lo que intentabas poner en el template)
        self.fields["rut"].widget.attrs.update({
            "placeholder": "12.345.678-5",
            "pattern": r"^\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]$|^\d{7,8}-[\dkK]$",
            "title": "Ej: 12.345.678-5 o 12345678-5",
        })
        self.fields["telefono"].widget.attrs.update({
            "placeholder": "+56912345678",
            "title": "Ej: +56912345678 o 912345678",
        })
        self.fields["email"].widget.attrs.update({
            "placeholder": "correo@dominio.cl",
        })

    # --- Validaciones ---

    def clean_rut(self):
        rut = normaliza_rut(self.cleaned_data.get("rut"))
        if not valida_rut_chileno(rut):
            raise ValidationError("RUT inválido. Revisa formato y dígito verificador.")
        if Paciente.objects.filter(rut=rut).exists():
            raise ValidationError("Ya existe un paciente con este RUT.")
        return rut

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            return None
        if Paciente.objects.filter(email=email).exists():
            raise ValidationError("Este correo ya está registrado.")
        return email

    def clean_telefono(self):
        tel_raw = self.cleaned_data.get("telefono")
        if not tel_raw:
            return None
        tel = normaliza_telefono_cl(tel_raw)
        digits = re.sub(r"\D", "", tel)
        # Validamos que sea Chile (+56…) y largo razonable (móvil = 56 + 9 + 8 dígitos = 12; fijos ~11-12)
        if not digits.startswith("56") or len(digits) < 11 or len(digits) > 12:
            raise ValidationError("Formato de teléfono inválido. Ej: +56912345678")
        if Paciente.objects.filter(telefono=tel).exists():
            raise ValidationError("Este teléfono ya está registrado.")
        return tel