from django.db import models  # ORM de Django
from django.contrib.auth.models import User  # Modelo de usuario

class Reunion(models.Model):
    """Modelo para almacenar reuniones de Zoom"""
    
    # Información básica
    titulo = models.CharField(max_length=200)  # Título de la reunión
    descripcion = models.TextField(blank=True)  # Agenda/descripción (opcional)
    
    # Información de Zoom
    zoom_meeting_id = models.CharField(max_length=50, unique=True)  # ID único de Zoom (ej: 123456789)
    zoom_meeting_password = models.CharField(max_length=20, blank=True)  # Contraseña de la reunión
    join_url = models.URLField(max_length=500)  # URL para participantes unirse
    start_url = models.URLField(max_length=500)  # URL para host iniciar reunión
    
    # Fechas y horarios
    fecha_inicio = models.DateTimeField()  # Fecha y hora programada
    duracion = models.IntegerField()  # Duración en minutos
    zona_horaria = models.CharField(max_length=50, default='America/Hermosillo')  # Zona horaria
    
    # Relaciones
    creador = models.ForeignKey(User, on_delete=models.CASCADE)  # Usuario que creó la reunión
    
    # Configuraciones
    sala_espera = models.BooleanField(default=True)  # Activar sala de espera
    grabar_automaticamente = models.BooleanField(default=False)  # Grabar automáticamente
    
    # Metadatos
    creado = models.DateTimeField(auto_now_add=True)  # Fecha de creación en Django
    actualizado = models.DateTimeField(auto_now=True)  # Fecha de última modificación
    
    class Meta:
        ordering = ['-fecha_inicio']  # Ordenar por fecha descendente
        verbose_name_plural = 'Reuniones'  # Nombre en plural en admin
    
    def __str__(self):
        return f"{self.titulo} - {self.fecha_inicio.strftime('%d/%m/%Y %H:%M')}"


class Participante(models.Model):
    """Participantes invitados a reuniones"""
    
    reunion = models.ForeignKey(Reunion, on_delete=models.CASCADE, related_name='participantes')  # Reunión asociada
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  # Usuario si está registrado
    
    # Si el participante no está registrado
    nombre = models.CharField(max_length=100, blank=True)  # Nombre del invitado externo
    email = models.EmailField()  # Email del participante
    
    # Estado
    asistio = models.BooleanField(default=False)  # Marcado si asistió a la reunión
    invitacion_enviada = models.BooleanField(default=False)  # Si se envió correo de invitación
    
    creado = models.DateTimeField(auto_now_add=True)  # Fecha de creación
    
    def __str__(self):
        nombre_completo = self.usuario.get_full_name() if self.usuario else self.nombre  # Obtiene nombre
        return f"{nombre_completo} - {self.reunion.titulo}"