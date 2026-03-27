
from django.urls import path
from . import views

urlpatterns = [
    # ===== Autenticación OAuth =====
    path('zoom/login/', views.zoom_login, name='zoom_login'),
    path('zoom/oauth/callback/', views.zoom_oauth_callback, name='zoom_oauth_callback'),
    path('api/verificar-autorizacion/', views.verificar_autorizacion, name='verificar_autorizacion'),
    
    # ===== Vistas principales =====
    path('', views.inicio, name='inicio'),
    path('crear/', views.crear_reunion, name='crear_reunion'),
    path('lista/', views.lista_reuniones, name='lista_reuniones'),
    path('detalle/<int:reunion_id>/', views.detalle_reunion, name='detalle_reunion'),
    path('eliminar/<int:reunion_id>/', views.eliminar_reunion, name='eliminar_reunion'),
    path('sincronizar/', views.sincronizar_reuniones, name='sincronizar_reuniones'),
]