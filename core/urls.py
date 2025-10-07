from django.urls import path, reverse_lazy
from . import views
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import admin
from django.contrib.auth import views as auth_views
from .forms import CustomPasswordResetForm, CustomSetPasswordForm

urlpatterns = [
    path("", views.home, name="home"),
    path("profesionales/", views.profesionales_list, name="profesionales"),


    #funciones de login y logout
    path("ingreso/", LoginView.as_view(template_name="admin/ingreso.html", redirect_authenticated_user=True), name="login"),
    path("salir/", LogoutView.as_view(), name="logout"),

    #funciones de redireccionamiento por rol
    path("entrar/", views.dispatch_por_rol, name="dispatch_por_rol"),
    path("admin/login/", views.admin_login_gate, name="admin_login_gate"),

    #funciones de recuperación de contraseña
    path("cuenta/clave/recuperar/",auth_views.PasswordResetView.as_view(
            template_name="admin/recuperar_contra/password_reset_form.html",
            email_template_name="admin/recuperar_contra/password_reset_email.txt",
            html_email_template_name="admin/recuperar_contra/password_reset_email.html",
            subject_template_name="admin/recuperar_contra/password_reset_subject.txt",
            success_url=reverse_lazy("password_reset_done"),
            from_email=None,  # usa DEFAULT_FROM_EMAIL
            form_class=CustomPasswordResetForm,
        ),name="password_reset",),
    path("cuenta/clave/recuperar/enviada/",auth_views.PasswordResetDoneView.as_view(
            template_name="admin/recuperar_contra/password_reset_done.html"
        ),name="password_reset_done",),
    path("cuenta/clave/restablecer/<uidb64>/<token>/",auth_views.PasswordResetConfirmView.as_view(
            template_name="admin/recuperar_contra/password_reset_confirm.html",
            form_class=CustomSetPasswordForm,
            success_url=reverse_lazy("password_reset_complete"),
        ),name="password_reset_confirm",),
    path("cuenta/clave/restablecer/completa/",auth_views.PasswordResetCompleteView.as_view(
            template_name="admin/recuperar_contra/password_reset_complete.html"
        ),name="password_reset_complete",),

    #paneles por rol
    #recepcion
    path("panel/recepcion/", views.recepcion_home, name="recepcion_home"),
    path("panel/recepcion/registrar/", views.registrar_paciente, name="registrar_paciente"),
    #profesional
    path("panel/profesional/", views.profesional_home, name="profesional_home"),

    #portal pacientes    
    path("paciente/ingreso/", views.login_paciente, name="login_paciente"),
    path("paciente/salir/", views.logout_paciente, name="logout_paciente"),
    path("paciente/perfil/", views.perfil_paciente, name="perfil"),
    path("cambiar-password/", views.cambiar_password, name="cambiar_password"),
    # Recuperación de contraseña
    path("olvido-clave/", views.solicitar_reset, name="solicitar_reset"),
    path("restablecer/<str:token>/", views.restablecer_password, name="restablecer_password"),

    #panel admin
    path('admin/', admin.site.urls),

    #error 404 solo pacientes
    path("404/", views.probar_404, name="404"),

]