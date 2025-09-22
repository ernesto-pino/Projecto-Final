from django import forms
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.core.exceptions import ValidationError
import re

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
