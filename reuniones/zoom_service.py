# ========================================
# reuniones/zoom_service.py
# Servicio para OAuth User-Level (cuenta gratis)
# ========================================

import requests  # Para peticiones HTTP
from django.conf import settings  # Acceso a settings
from django.core.cache import cache  # Sistema de caché
import base64  # Codificación Base64
from datetime import datetime  # Manejo de fechas

class ZoomService:
    """
    Servicio para interactuar con Zoom API usando OAuth 2.0 User-Level.
    Compatible con cuentas Zoom Basic (gratuitas).
    """
    
    def __init__(self):
        # Credenciales OAuth (solo 2, no Account ID)
        self.client_id = settings.ZOOM_CLIENT_ID
        self.client_secret = settings.ZOOM_CLIENT_SECRET
        self.redirect_uri = settings.ZOOM_REDIRECT_URI
        
        # URLs de Zoom
        self.authorize_url = settings.ZOOM_OAUTH_AUTHORIZE_URL
        self.token_url = settings.ZOOM_OAUTH_TOKEN_URL
        self.api_base_url = settings.ZOOM_API_BASE_URL
    
    def get_authorization_url(self):
        """
        Genera URL para que el usuario autorice la app.
        El usuario hace clic en esta URL y autoriza.
        
        Returns:
            str: URL de autorización de Zoom
        """
        return (
            f"{self.authorize_url}"
            f"?response_type=code"
            f"&client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
        )
    
    def exchange_code_for_token(self, code):
        """
        Intercambia el código de autorización por Access Token.
        
        Args:
            code: Código recibido en callback después de autorizar
        
        Returns:
            dict con access_token, refresh_token, expires_in
        """
        # Crear Basic Auth header
        credentials = f"{self.client_id}:{self.client_secret}"
        b64_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {b64_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri
        }
        
        response = requests.post(self.token_url, headers=headers, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            
            # Guardar tokens en caché (55 minutos)
            cache.set('zoom_access_token', token_data['access_token'], 3300)
            cache.set('zoom_refresh_token', token_data['refresh_token'], 86400)
            
            return token_data
        else:
            raise Exception(f"Error obteniendo token: {response.text}")
    
    def refresh_access_token(self):
        """
        Renueva el Access Token usando el Refresh Token.
        
        Returns:
            str: Nuevo access token
        """
        refresh_token = cache.get('zoom_refresh_token')
        
        if not refresh_token:
            raise Exception("No hay refresh token disponible")
        
        credentials = f"{self.client_id}:{self.client_secret}"
        b64_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {b64_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        
        response = requests.post(self.token_url, headers=headers, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            cache.set('zoom_access_token', token_data['access_token'], 3300)
            return token_data['access_token']
        else:
            raise Exception(f"Error renovando token: {response.text}")
    
    def get_access_token(self):
        """
        Obtiene Access Token (desde caché o renovando).
        
        Returns:
            str: Access token válido
        """
        access_token = cache.get('zoom_access_token')
        
        if access_token:
            return access_token
        
        # Si no hay token, intentar renovar
        return self.refresh_access_token()
    
    def crear_reunion(self, topic, start_time, duration, timezone='America/Hermosillo'):
        """
        Crea una reunión en Zoom.
        
        Args:
            topic: Título de la reunión
            start_time: Fecha/hora inicio (formato: "2024-03-15T10:00:00")
            duration: Duración en minutos
            timezone: Zona horaria
        
        Returns:
            dict con datos de la reunión creada
        """
        access_token = self.get_access_token()
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'topic': topic,
            'type': 2,  # Reunión programada
            'start_time': start_time,
            'duration': duration,
            'timezone': timezone,
            'settings': {
                'host_video': True,
                'participant_video': True,
                'join_before_host': False,
                'mute_upon_entry': True,
                'waiting_room': True,
                'audio': 'both'
            }
        }
        
        # Obtener user ID
        user_response = requests.get(
            f"{self.api_base_url}/users/me",
            headers=headers
        )
        user_id = user_response.json()['id']
        
        # Crear reunión
        response = requests.post(
            f"{self.api_base_url}/users/{user_id}/meetings",
            headers=headers,
            json=data
        )
        
        if response.status_code == 201:
            return response.json()
        else:
            raise Exception(f"Error creando reunión: {response.text}")
    
    def listar_reuniones(self):
        """
        Lista todas las reuniones programadas del usuario.
        
        Returns:
            list: Lista de reuniones
        """
        access_token = self.get_access_token()
        
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        # Obtener user ID
        user_response = requests.get(
            f"{self.api_base_url}/users/me",
            headers=headers
        )
        user_id = user_response.json()['id']
        
        # Listar reuniones
        response = requests.get(
            f"{self.api_base_url}/users/{user_id}/meetings",
            headers=headers
        )
        
        if response.status_code == 200:
            return response.json()['meetings']
        else:
            raise Exception(f"Error listando reuniones: {response.text}")
    
    def eliminar_reunion(self, meeting_id):
        """
        Elimina una reunión de Zoom.
        
        Args:
            meeting_id: ID de la reunión
        
        Returns:
            bool: True si se eliminó correctamente
        """
        access_token = self.get_access_token()
        
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        response = requests.delete(
            f"{self.api_base_url}/meetings/{meeting_id}",
            headers=headers
        )
        
        if response.status_code == 204:
            return True
        else:
            raise Exception(f"Error eliminando reunión: {response.text}")