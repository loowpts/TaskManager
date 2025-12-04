
def can_view_task(user, task):
    """
    Может ли пользователь видеть задачу
    """
    
    if not user.is_authenticated:
        return False
    
    # admin видит все
    if user.is_staff or user.is_superuser:
        return True
    
    # Создатель видит своб задачу
    if task.creator == user:
        return True
    
    if task.assignee == user:
        return True
    
    # Наблюдатель видит задачу
    if task.watchers.filter(user=user).exists():
        return True
    
    # Руководитель видит задачи своих подчиненных
    if hasattr(user, 'is_manager') and user.is_manager:
        if task.assignee in user.subordinates.all():
            return True
    return False

def can_edit_task(user, task):
    """
    Может ли пользователь редактировать задачу
    """
    if not user.is_authenticated:
        return False
    
    # Админ может редактировать все
    if user.is_staff or user.is_superuser:
        return True
    
    # Создатель может редактировать
    if task.creator == user:
        return True
    
    # Руководитель может редактировать задачи подчиненных
    if hasattr(user, 'is_manager') and user.is_manager:
        if task.assignee in user.subordinates.all():
            return True
    
    return False

def can_delete_task(user, task):
    """
    Может ли пользователь удалить задачу
    """
    if not user.is_authenticated:
        return False
    
    # Только админ и создатель
    if user.is_staff or user.is_superuser or task.creator == user:
        return True
    return False

def is_manager(user):
    """
    Является ли пользователь руководителем
    """
    if not user.is_authenticated:
        return False
    
    return getattr(user, 'is_manager', False)
    
