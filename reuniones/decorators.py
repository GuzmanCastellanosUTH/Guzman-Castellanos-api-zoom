from django.shortcuts import redirect
from django.core.cache import cache
from functools import wraps

def zoom_required(function):
    """
    Decorador que verifica si hay un token de Zoom válido.
    Similar a @login_required pero para OAuth de Zoom.
    """
    @wraps(function)
    def wrap(request, *args, **kwargs):
        # Verificar si existe access_token en caché
        access_token = cache.get('zoom_access_token')
        
        if not access_token:
            # No hay token, redirigir a login de Zoom
            return redirect('zoom_login')
        
        # Hay token válido, permitir acceso
        return function(request, *args, **kwargs)
    
    return wrap