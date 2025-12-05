from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from decimal import Decimal
import json


def serialize_user(user):
    """Сериализация пользователя в dict"""
    if not user:
        return None
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'full_name': user.get_full_name() if hasattr(user, 'get_full_name') else f"{user.first_name} {user.last_name}",
    }


def serialize_tag(tag):
    """Сериализация тега в dict"""
    return {
        'id': tag.id,
        'name': tag.name,
        'color': tag.color,
    }


def serialize_task_list(task):
    """Сериализация задачи для списка (краткая информация)"""
    return {
        'id': task.id,
        'title': task.title,
        'status': task.status,
        'status_display': task.get_status_display(),
        'priority': task.priority,
        'priority_display': task.get_priority_display(),
        'creator': serialize_user(task.creator),
        'assignee': serialize_user(task.assignee),
        'deadline': task.deadline.isoformat() if task.deadline else None,
        'created_at': task.created_at.isoformat(),
        'updated_at': task.updated_at.isoformat(),
        'completed_at': task.completed_at.isoformat() if task.completed_at else None,
        'estimated_hours': str(task.estimated_hours) if task.estimated_hours else None,
        'actual_hours': str(task.actual_hours),
        'tags': [serialize_tag(tag) for tag in task.tags.all()],
        'has_subtasks': task.subtasks.exists(),
        'comments_count': task.comments.count(),
        'attachments_count': task.attachments.count(),
    }


def serialize_task_detail(task):
    """Сериализация задачи с полной информацией"""
    from .models import TaskComment, TaskAttachment, TaskChecklist, TimeEntry
    
    return {
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'status': task.status,
        'status_display': task.get_status_display(),
        'priority': task.priority,
        'priority_display': task.get_priority_display(),
        'creator': serialize_user(task.creator),
        'assignee': serialize_user(task.assignee),
        'deadline': task.deadline.isoformat() if task.deadline else None,
        'created_at': task.created_at.isoformat(),
        'updated_at': task.updated_at.isoformat(),
        'completed_at': task.completed_at.isoformat() if task.completed_at else None,
        'estimated_hours': str(task.estimated_hours) if task.estimated_hours else None,
        'actual_hours': str(task.actual_hours),
        'tags': [serialize_tag(tag) for tag in task.tags.all()],
        'parent_task': task.parent_task.id if task.parent_task else None,
        'subtasks': [serialize_task_list(subtask) for subtask in task.subtasks.all()],
        'comments': [serialize_comment(comment) for comment in task.comments.all()[:10]],  # последние 10
        'attachments': [serialize_attachment(att) for att in task.attachments.all()],
        'checklist': [serialize_checklist(item) for item in task.checklist.all()],
        'watchers': [serialize_user(watcher.user) for watcher in task.watchers.all()],
        'time_entries_total': str(task.time_entries.count()),
    }


def serialize_comment(comment):
    """Сериализация комментария"""
    return {
        'id': comment.id,
        'author': serialize_user(comment.author),
        'text': comment.text,
        'is_system': comment.is_system,
        'created_at': comment.created_at.isoformat(),
        'updated_at': comment.updated_at.isoformat(),
    }


def serialize_attachment(attachment):
    """Сериализация вложения"""
    return {
        'id': attachment.id,
        'file_name': attachment.file_name,
        'file_url': attachment.file.url if attachment.file else None,
        'file_size': attachment.file_size,
        'uploaded_by': serialize_user(attachment.uploaded_by),
        'uploaded_at': attachment.uploaded_at.isoformat(),
        'extension': attachment.get_file_extension(),
    }


def serialize_checklist(item):
    """Сериализация пункта чеклиста"""
    return {
        'id': item.id,
        'item_text': item.item_text,
        'is_completed': item.is_completed,
        'order': item.order,
        'completed_at': item.completed_at.isoformat() if item.completed_at else None,
        'completed_by': serialize_user(item.completed_by) if item.completed_by else None,
    }


def paginate_queryset(queryset, request, per_page=20):
    """
    Пагинация queryset
    Возвращает: (paginated_data, meta_info)
    """
    page = request.GET.get('page', 1)
    paginator = Paginator(queryset, per_page)
    
    try:
        paginated = paginator.page(page)
    except PageNotAnInteger:
        paginated = paginator.page(1)
    except EmptyPage:
        paginated = paginator.page(paginator.num_pages)
    
    meta = {
        'total': paginator.count,
        'page': paginated.number,
        'per_page': per_page,
        'total_pages': paginator.num_pages,
        'has_next': paginated.has_next(),
        'has_previous': paginated.has_previous(),
    }
    
    return paginated.object_list, meta


def json_response(data=None, success=True, message='', errors=None, status=200):
    """
    Единообразный JSON ответ
    """
    from django.http import JsonResponse
    
    response_data = {
        'success': success,
    }
    
    if data is not None:
        response_data['data'] = data
    
    if message:
        response_data['message'] = message
    
    if errors:
        response_data['errors'] = errors
    
    return JsonResponse(response_data, status=status, safe=False)
