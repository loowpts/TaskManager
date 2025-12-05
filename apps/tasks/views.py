import json
import logging
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from datetime import datetime

from .models import Task, TaskTag
from .permissions import can_delete_task, can_edit_task, can_view_task
from .decorators import login_required_json, require_http_methods_json
from .utils import (
    serialize_task_list,
    serialize_task_detail,
    paginate_queryset, 
    json_response
)
from .permissions import is_manager

logger = logging.getLogger(__name__)


@login_required_json
@require_http_methods(['GET'])
def task_list(request):
    user = request.user
    
    # Базовый queryset
    if is_manager(user):
        tasks = Task.objects.all()
    else:
        # Обычный пользователь видит только свои задачи
        tasks = Task.objects.filter(
            Q(assignee=user) | Q(creator=user) | Q(watchers__user=user)
        ).distinct()
    
    tasks = tasks.select_related('creator', 'assignee', 'parent_task')
    tasks = tasks.prefetch_related('tags', 'subtasks', 'comments', 'attachments')
    
    status = request.GET.get('status')
    if status:
        tasks = tasks.filter(status=status)
    
    priority = request.GET.get('priority')
    if priority:
        tasks = tasks.filter(priority=priority)
        
    assignee = request.GET.get('assignee')
    if assignee:
        try:
            tasks = tasks.filter(assignee_id=int(assignee))
        except (ValueError, TypeError):
            logger.warning(f"Invalid assignee ID: {assignee}")
    
    creator = request.GET.get('creator')
    if creator:
        try:
            tasks = tasks.filter(creator_id=int(creator))
        except (ValueError, TypeError):
            logger.warning(f"Invalid creator ID: {creator}")
        
    deadline_from = request.GET.get('deadline_from')
    if deadline_from:
        try:
            deadline_from = datetime.strptime(deadline_from, '%Y-%m-%d')
            tasks = tasks.filter(deadline__gte=deadline_from)
        except ValueError:
            logger.warning(f"Invalid deadline_from format: {deadline_from}")
    
    deadline_to = request.GET.get('deadline_to')
    if deadline_to:
        try:
            deadline_to = datetime.strptime(deadline_to, '%Y-%m-%d')
            tasks = tasks.filter(deadline__lte=deadline_to)
        except ValueError:
            logger.warning(f"Invalid deadline_to format: {deadline_to}")
    
    search = request.GET.get('search')
    if search:
        tasks = tasks.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )
        
    tags = request.GET.get('tags')
    if tags:
        try:
            tag_ids = [int(tid) for tid in tags.split(',') if tid.strip().isdigit()]
            if tag_ids:
                tasks = tasks.filter(tags__id__in=tag_ids)
        except (ValueError, AttributeError):
            logger.warning(f"Invalid tags format: {tags}")
    
    ordering = request.GET.get('ordering', '-created_at')
    allowed_ordering = [
        'created_at', '-created_at', 'deadline', '-deadline',
        'priority', '-priority', 'status', '-status',
        'title', '-title'
    ]
    
    if ordering in allowed_ordering:
        tasks = tasks.order_by(ordering)
    else:
        tasks = tasks.order_by('-created_at')
        
    try:
        per_page = int(request.GET.get('per_page', 20))
        per_page = min(max(per_page, 1), 100)
    except (ValueError, TypeError):
        per_page = 20
    
    paginated_tasks, meta = paginate_queryset(tasks, request, per_page=per_page)
    
    serialized_tasks = [serialize_task_list(task) for task in paginated_tasks]
    
    return JsonResponse({
        'success': True,
        'data': serialized_tasks,
        'meta': meta,
        'message': 'Tasks retrieved successfully',
    }, status=200)

@login_required_json
@require_http_methods(['GET'])
def task_detail(request, task_id):
    # Оптимизация запросов - делаем ДО получения объекта
    task = Task.objects.select_related(
        'creator', 'assignee', 'parent_task'
    ).prefetch_related(
        'tags', 'comments', 'attachments', 'checklist', 
        'watchers', 'watchers__user',
        'time_entries', 'time_entries__user',
        'subtasks', 'subtasks__tags'
    ).filter(id=task_id).first()
    
    # Проверка существования
    if not task:
        return JsonResponse({
            'success': False,
            'message': 'Task not found',
        }, status=404)
    
    if not can_view_task(request.user, task):
        return JsonResponse({
            'success': False,
            'message': 'Permission denied',
        }, status=403)
    
    # Сериализация
    data = serialize_task_detail(task)
    
    return JsonResponse({
        'success': True,
        'data': data,
        'message': 'Task retrieved successfully',
    }, status=200)
    
