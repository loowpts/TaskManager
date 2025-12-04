from functools import wraps
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


def login_required_json(function):
    """
    Декоратор для проверки авторизации с JSON ответом
    """
    @wraps(function)
    def wrap(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'message': 'Authentication required',
                'errors': {'auth': 'You must be logged in to access this resource'}
            }, status=401)
        return function(request, *args, **kwargs)
    return wrap


def manager_required(function):
    """
    Декоратор для проверки что пользователь - руководитель
    """
    @wraps(function)
    def wrap(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'message': 'Authentication required'
            }, status=401)
        
        # Проверка роли (предполагается что у User есть поле role или is_manager)
        # Адаптируй под свою модель User
        if not hasattr(request.user, 'is_manager') or not request.user.is_manager:
            return JsonResponse({
                'success': False,
                'message': 'Manager role required',
                'errors': {'permission': 'You do not have permission to perform this action'}
            }, status=403)
        
        return function(request, *args, **kwargs)
    return wrap


def require_http_methods_json(methods):
    """
    Декоратор для проверки HTTP методов с JSON ответом
    """
    def decorator(function):
        @wraps(function)
        def wrap(request, *args, **kwargs):
            if request.method not in methods:
                return JsonResponse({
                    'success': False,
                    'message': f'Method {request.method} not allowed',
                    'errors': {'method': f'Allowed methods: {", ".join(methods)}'}
                }, status=405)
            return function(request, *args, **kwargs)
        return wrap
    return decorator
