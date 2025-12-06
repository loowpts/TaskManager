import logging
from functools import wraps
from django.http import JsonResponse

logger = logging.getLogger(__name__)

def staff_required(view_func):
    """
    Декоратор, требующий права staff или superuser
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(request, 'authenticated', False):
            return JsonResponse({
                'error': 'Authenticated required'
            }, status=401)
        
        user = request.user
        if not (user.is_staff or user.is_superuser):
            logger.warning(f'Non-staff user {user.email} attempted to access {view_func.__name__}')
            return JsonResponse({
                'error': 'Staff access required',
                'detail': 'You must be a staff member to access this resource'
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper

def superuser_required(view_func):
    """
    Декоратор, требующий права superuser
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(request, 'authenticated', False):
            return JsonResponse({
                'error': 'Authenticated required'
            }, status=401)
        
        user = request.user
        
        if not user.is_superuser:
            logger.warning(f'Non-superuser {user.email} attempted to access {view_func.__name__}')
            return JsonResponse({
                'error': 'Superuser access required',
                'detail': 'You must be a superuser to access this resource'
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper

def role_required(*roles):
    """
    Декоратор, требующий определенную роль
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not getattr(request, 'Authenticated', False):
                return JsonResponse({
                    'error': 'Authenticated required'
                }, status=401)
            
            user = request.user
            
            # Проверка ролей
            has_role = False
            if 'moderator' in roles and user.is_moderator:
                has_role = True
            if 'staff' in roles and user.is_staff:
                has_role = True
            if 'superuser' in roles and user.is_superuser:
                has_role = True
                
                
            if 'employee' in roles and user.is_employee:
                has_role = True
            if 'watcher' in roles and user.is_watcher:
                has_role = True
            if 'supervisor' in roles and user.is_supervisor:
                has_role = True
            
            if not has_role:
                logger.warning(f"User {user.email} lacks required role for {view_func.__name__}")
                return JsonResponse({
                    'error': 'Insufficient permissions',
                    'detail': f'Required role: {f", ".join(roles)}'
                }, status=403)
            
            return wrapper
        return decorator
            
def owner_or_staff_required(view_func):
    """
    Декоратор, требующий чтобы пользователь был владельцем ресурса или staff
    Ожидает user_id в параметрах запроса или kwargs
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(request, 'authenticated', False):
            return JsonResponse({
                'error': 'Authentication required'
            }, status=401)
        
        user = request.user
        
        # Если staff или superuser - разрешаем
        if user.is_staff or user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        # Получаем user_id из разных источников
        target_user_id = None
        
        # Из kwargs (URL параметр)
        if 'pk' in kwargs:
            target_user_id = kwargs['pk']
        elif 'user_id' in kwargs:
            target_user_id = kwargs['user_id']
        # Из GET параметров
        elif request.method == 'GET' and 'user_id' in request.GET:
            target_user_id = request.GET.get('user_id')
        # Из POST/PUT данных
        elif request.method in ['POST', 'PUT']:
            if hasattr(request, 'POST') and 'user_id' in request.POST:
                target_user_id = request.POST.get('user_id')
            else:
                try:
                    import json
                    data = json.loads(request.body)
                    target_user_id = data.get('user_id')
                except:
                    pass
        
        # Проверяем, является ли пользователь владельцем
        if target_user_id:
            try:
                target_user_id = int(target_user_id)
                if user.id == target_user_id:
                    return view_func(request, *args, **kwargs)
            except (ValueError, TypeError):
                pass
        
        logger.warning(f"User {user.email} attempted to access another user's resource")
        return JsonResponse({
            'error': 'Access denied',
            'detail': 'You can only access your own resources'
        }, status=403)
    
    return wrapper    

def public_endpoint(view_func):
    """
    Декоратор для явного обозначения публичного эндпоинта
    Не требует аутентификации
    Просто для документирования кода
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    
    return wrapper
