from django.urls import path
from . import views
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import admin

urlpatterns = [
    path("", views.home, name="home"),
    #funciones de login y logout
    path("ingreso/", LoginView.as_view(template_name="admin/ingreso.html", redirect_authenticated_user=True), name="login"),
    path("salir/", LogoutView.as_view(), name="logout"),
    #funciones de redireccionamiento por rol
    path("entrar/", views.dispatch_por_rol, name="dispatch_por_rol"),
    path("admin/login/", views.admin_login_gate, name="admin_login_gate"),

    #paneles por rol
    path("panel/recepcion/", views.recepcion_home, name="recepcion_home"),
    path("panel/profesional/", views.profesional_home, name="profesional_home"),
    #panel admin
    path('admin/', admin.site.urls),
]