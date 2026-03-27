# ========================================
# reuniones/views.py
# Vistas para OAuth User-Level (gratuito)
# ========================================

from .decorators import zoom_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from django.core.cache import cache
from .zoom_service import ZoomService
from .models import Reunion, Participante
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt  # Desactivar CSRF para webhook
import json
from django.contrib.auth import login, get_user_model
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Count, Q

# =====================================
# VISTAS DE AUTENTICACIÓN OAUTH
# =====================================

def zoom_login(request):
    """
    Redirige al usuario a la página de autorización de Zoom.
    Primera vez que el usuario autoriza la app.
    """
    zoom_service = ZoomService()
    authorization_url = zoom_service.get_authorization_url()
    return redirect(authorization_url)


def zoom_oauth_callback(request):
    """
    Callback de Zoom después de que el usuario autoriza.
    Recibe el código y lo intercambia por access token.
    """
    code = request.GET.get('code')
    
    if not code:
        messages.error(request, '❌ Error: No se recibió código de autorización')
        return redirect('inicio')
    
    try:
        zoom_service = ZoomService()
        token_data = zoom_service.exchange_code_for_token(code)
        
        # ===== NUEVO: Obtener info del usuario de Zoom =====
        access_token = token_data['access_token']
        
        # Obtener datos del usuario desde Zoom API
        import requests
        headers = {'Authorization': f'Bearer {access_token}'}
        user_response = requests.get(
            'https://api.zoom.us/v2/users/me',
            headers=headers
        )
        zoom_user = user_response.json()
        
        # ===== Crear o vincular usuario de Django =====
        zoom_email = zoom_user.get('email')
        zoom_id = zoom_user.get('id')
        
        # Buscar si ya existe un usuario con este email
        try:
            user = User.objects.get(email=zoom_email)
        except User.DoesNotExist:
            # Crear nuevo usuario de Django
            user = User.objects.create_user(
                username=zoom_id,  # Usar Zoom ID como username
                email=zoom_email,
                first_name=zoom_user.get('first_name', ''),
                last_name=zoom_user.get('last_name', '')
            )
        
        # ===== Autenticar al usuario en Django =====
        login(request, user)
        
        messages.success(request, '✅ Autorización exitosa! Ya puedes crear reuniones.')
        return redirect('inicio')
    
    except Exception as e:
        messages.error(request, f'❌ Error al autorizar: {str(e)}')
        return redirect('inicio')


def verificar_autorizacion(request):
    """
    API para verificar si ya hay token (usuario ya autorizó).
    Usado por JavaScript en el frontend.
    """
    tiene_token = cache.get('zoom_access_token') is not None
    return JsonResponse({'autorizado': tiene_token})


# =====================================
# VISTAS PRINCIPALES
# =====================================

def inicio(request):
    """
    Página de inicio.
    Muestra botón de autorizar si no hay token.
    Muestra estadísticas de reuniones si el usuario está autenticado.
    """
    tiene_token = cache.get('zoom_access_token') is not None
    
    # Inicializar variables de estadísticas
    total_reuniones = 0
    proximas_reuniones = 0
    reuniones_pasadas = 0
    
    # Si el usuario está autenticado, calcular estadísticas
    if request.user.is_authenticated:
        # Obtener fecha/hora actual
        now = timezone.now()
        
        # Total de reuniones del usuario
        total_reuniones = Reunion.objects.filter(creador=request.user).count()
        
        # Próximas reuniones (fecha_inicio mayor a ahora)
        proximas_reuniones = Reunion.objects.filter(
            creador=request.user,
            fecha_inicio__gt=now
        ).count()
        
        # Reuniones pasadas (fecha_inicio menor o igual a ahora)
        reuniones_pasadas = Reunion.objects.filter(
            creador=request.user,
            fecha_inicio__lte=now
        ).count()
    
    context = {
        'autorizado': tiene_token,
        'total_reuniones': total_reuniones,
        'proximas_reuniones': proximas_reuniones,
        'reuniones_pasadas': reuniones_pasadas,
    }
    return render(request, 'reuniones/inicio.html', context)


@zoom_required
def crear_reunion(request):
    """
    Vista para crear una reunión de Zoom.
    """
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            topic = request.POST.get('topic')
            descripcion = request.POST.get('agenda')
            start_time = request.POST.get('start_time')  # Puede venir en varios formatos
            duration = int(request.POST.get('duration'))
            
            # ===== PARSING ROBUSTO DE FECHA =====
            start_datetime = None
            
            # Intentar formato completo: "2024-02-09T22:17"
            try:
                start_datetime = datetime.strptime(start_time, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
            
            # Intentar formato solo hora: "22:17" (usar fecha de hoy)
            if not start_datetime:
                try:
                    from datetime import date
                    time_obj = datetime.strptime(start_time, '%H:%M').time()
                    start_datetime = datetime.combine(date.today(), time_obj)
                except ValueError:
                    pass
            
            # Intentar formato con segundos: "2024-02-09T22:17:00"
            if not start_datetime:
                try:
                    start_datetime = datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%S')
                except ValueError:
                    pass
            
            # Si ningún formato funcionó, lanzar error
            if not start_datetime:
                raise ValueError(f"Formato de fecha inválido: {start_time}")
            
            # Convertir a formato ISO 8601 para Zoom
            start_time_iso = start_datetime.strftime('%Y-%m-%dT%H:%M:%S')
            
            # Crear reunión en Zoom
            zoom_service = ZoomService()
            meeting_data = zoom_service.crear_reunion(
                topic=topic,
                start_time=start_time_iso,
                duration=duration
            )
            
            # Guardar en base de datos
            reunion = Reunion.objects.create(
                titulo=topic,
                descripcion=descripcion,
                zoom_meeting_id=meeting_data['id'],
                join_url=meeting_data['join_url'],
                start_url=meeting_data['start_url'],
                fecha_inicio=start_datetime,
                duracion=duration,
                creador=request.user 
            )
            
            messages.success(request, f'✅ Reunión "{topic}" creada exitosamente!')
            return redirect('lista_reuniones')
        
        except Exception as e:
            messages.error(request, f'❌ Error al crear reunión: {str(e)}')
    
    return render(request, 'reuniones/crear_reunion.html')

@login_required
def lista_reuniones(request):
    """
    Lista todas las reuniones creadas.
    """
    reuniones = Reunion.objects.filter(creador=request.user)
    
    context = {
        'reuniones': reuniones
    }
    return render(request, 'reuniones/lista_reuniones.html', context)


@login_required
def detalle_reunion(request, reunion_id):
    """
    Muestra detalles de una reunión específica.
    """
    reunion = get_object_or_404(Reunion, id=reunion_id, creador=request.user)
    
    context = {
        'reunion': reunion
    }
    return render(request, 'reuniones/detalle_reunion.html', context)


@require_POST
def eliminar_reunion(request, reunion_id):
    reunion = get_object_or_404(
        Reunion,
        zoom_meeting_id=reunion_id,
        creador=request.user
    )

    try:
        zoom_service = ZoomService()
        zoom_service.eliminar_reunion(reunion.zoom_meeting_id)

        titulo = reunion.titulo  # Guardar título para mensaje
        reunion.delete()

        messages.success(request, f'✅ Reunión "{titulo}" eliminada correctamente!')
        return JsonResponse({
            'success': True,
            'message': f'Reunión "{titulo}" eliminada correctamente'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
def sincronizar_reuniones(request):
    """
    Sincroniza reuniones desde Zoom API.
    Útil para obtener reuniones creadas directamente en Zoom.
    """
    try:
        zoom_service = ZoomService()
        meetings = zoom_service.listar_reuniones()
        
        count = 0
        for meeting in meetings:
            # Crear o actualizar en base de datos
            Reunion.objects.update_or_create(
                zoom_meeting_id=meeting['id'],
                defaults={
                    'titulo': meeting['topic'],
                    'join_url': meeting['join_url'],
                    'start_url': meeting.get('start_url', ''),
                    'fecha_inicio': datetime.strptime(
                        meeting['start_time'], 
                        '%Y-%m-%dT%H:%M:%SZ'
                    ),
                    'duracion': meeting['duration'],
                    'creador': request.user
                }
            )
            count += 1
        
        messages.success(request, f'✅ Sincronizadas {count} reuniones desde Zoom.')
    
    except Exception as e:
        messages.error(request, f'❌ Error al sincronizar: {str(e)}')
    
    return redirect('lista_reuniones')

@csrf_exempt  # Zoom no puede enviar CSRF token
def zoom_webhook(request):
    """
    Endpoint que recibe notificaciones de Zoom
    URL debe ser pública: https://tudominio.com/api/zoom/webhook/
    """
    
    if request.method == 'POST':  # Zoom envía POST
        
        # Parsear payload JSON
        payload = json.loads(request.body)  # Convierte string a dict
        
        # Obtener tipo de evento
        event_type = payload.get('event')  # Ejemplo: "meeting.participant_joined"
        
        # Validación de URL (solo primera vez)
        if event_type == 'endpoint.url_validation':  # Zoom valida la URL
            plain_token = payload.get('payload', {}).get('plainToken')  # Token enviado
            return JsonResponse({  # Responder con token encriptado
                'plainToken': plain_token,
                'encryptedToken': plain_token  # En producción encriptar con SHA256
            })
        
        # Procesar evento de participante
        if event_type == 'meeting.participant_joined':
            meeting_id = payload.get('payload', {}).get('object', {}).get('id')  # ID reunión
            participant_name = payload.get('payload', {}).get('object', {}).get('participant', {}).get('user_name')  # Nombre
            
            # Actualizar asistencia en base de datos
            try:
                reunion = Reunion.objects.get(zoom_meeting_id=meeting_id)  # Busca reunión
                participante = Participante.objects.filter(  # Busca participante
                    reunion=reunion,
                    nombre__icontains=participant_name  # Coincidencia parcial
                ).first()
                
                if participante:
                    participante.asistio = True  # Marca asistencia
                    participante.save()  # Guarda en BD
            except Reunion.DoesNotExist:
                pass  # Reunión no encontrada
        
        # Responder con éxito a Zoom
        return JsonResponse({'status': 'success'}, status=200)  # Zoom espera 200 OK
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)  # Solo POST permitido