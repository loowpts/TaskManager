import logging
from decimal import Decimal
from datetime import datetime

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.conf import settings
from django.template.response import TemplateResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Max
from django.utils import timezone
from django.contrib import messages

from .models import (
    Task, TaskComment, TaskChecklist,
    TaskWatcher, TimeEntry, TaskAttachment
)
from .forms import (
    TaskCreateForm, TaskUpdateForm, TaskCommentForm,
    TaskChecklistItemForm, TimeEntryForm, TaskAttachmentForm
)

User = settings.AUTH_USER_MODEL
logger = logging.getLogger(__name__)


def can_view_task(user, task):
    """
    Проверка: может ли пользователь просматривать задачу.
    
    - Создатель задачи (creator)
    - Испольнитель задачи (assignee)
    - Наблюдатель задачи (watcher)
    - Менеджер/Администратор
    """
    return (
        task.assignee == user or
        task.creator == user or
        task.watchers.filter(user=user).exists() or
        (hasattr(user, 'is_manager') and user.is_manager())
    )
    
def can_edit_task(user, task):
    """
    Проверка: может ли пользователь редактировать задачу.
    
    Права доступа:
    - Только создатель задачи
    - Менеджер/Администратор
    """
    return (
        task.creator == user or
        (hasattr(user, 'is_manager') and user.is_manager())
    )
    
def can_delete_task(user, task):
    """
    Проверка: может ли пользователь удалять задачу.
    """
    return can_edit_task(user, task)

@login_required
def task_list(request):
    try:
        user = request.user
        
        if hasattr(user, 'is_manager') and user.is_manager():
            tasks = Task.objects.all()
        else:
            tasks = Task.objects.filter(
                Q(assignee=user) |
                Q(creator=user) |
                Q(watchers__user=user)
            ).distinct()
        
        status = request.GET.get('status')
        if status:
            tasks = tasks.filter(status=status)
        
        priority = request.GET.get('priority')
        if priority:
            tasks = tasks.filter(status=status)
            
        assignee = request.GET.get('assignee')
        if assignee:
            try:
                tasks = tasks.filter(assignee_id=int(assignee))
            except (ValueError, TypeError):
                logger.warning(f'Invalid assignee ID: {assignee}')
        
        creator = request.GET.get('creator')
        if creator:
            try:
                tasks = tasks.filter(creator_id=int(creator))
            except (ValueError, TypeError):
                logger.warning(f'Invalid creator ID: {creator}')
        
        deadline_from = request.GET.get('deadline_from')
        if deadline_from:
            try:
                deadline_from_date = datetime.strptime(deadline_from, '%Y-%m-%d')
                tasks = tasks.filter(deadline__gte=deadline_from_date)
            except ValueError:
                logger.warning(f'Invalid deadline_from format: {deadline_from}')
        
        deadline_to = request.GET.get('deadline_to')
        if deadline_to:
            try:
                deadline_to_date = datetime.strptime(deadline_to, '%Y-%m-%d')
                tasks = tasks.filter(deadline__lte=deadline_to_date)
            except ValueError:
                logger.warning(f'Invalid deadline_to format: {deadline_to}')
                
        search = request.GET.get('search')
        if search:
            if len(search) > 200:
                logger.warning(f'Search query too long: {len(search)} characters.')
                
            tasks = tasks.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search)
            )
            
        tags = request.GET.get('tags')
        if tags:
            try:
                tag_ids = [int(tid) for tid in tags.split(',') if tid.strip().isdigit()]
                if tag_ids:
                    tasks = tasks.filter(tags__id__in=tag_ids)
            except (ValueError, TypeError):
                logger.warning(f'Invalid tags format: {tags}')
                
        ordering = request.GET.get('ordering', '-created_at')
        
        allowed_ordering = [
            'created_at', '-created_at',
            'deadline', '-deadline',
            'priority', '-priority',
            'status', '-status',
            'title', '-title'
        ]
        try:
            if ordering in allowed_ordering:
                per_page = int(request.GET.get('per_page', 20))
                per_page = min(max(per_page, 1), 100)
        except (ValueError, TypeError):
            per_page = 20
            
        
        page = request.GET.get('page', 1)
        paginator = Paginator(tasks, per_page)
        
        try:
            tasks_page = paginator.page(page)
        except PageNotAnInteger:
            tasks_page = paginator.page(1)
        except EmptyPage:
            tasks_page =  paginator.page(paginator.num_pages)
            
        context = {
            'tasks': tasks_page,
            'page_obj': tasks_page,
            'total_count': paginator.count,
            'error': None
        }
        return TemplateResponse(request, 'tasks/task_list.html', context)
    
    except Exception as e:
        logger.error(f'Error in task_list: {str(e)}', exc_info=True)
        
        context = {
            'tasks': [],
            'error': 'Произошла ошибка при загрузке задач. Попробуйте позже.',
            'total_count': 0
        }    
        return TemplateResponse(request, 'tasks/task_list.html', context, status=500)
        
@login_required
def task_detail(request, task_id):
    try:   
        try:
            task_id = int(task_id)
        except (ValueError, TypeError):
            logger.warning(f'Invalid task ID format: {task_id}')
            context = {
                'error': 'Недопустимый формат идентификатора задачи.',
                'task': None
            }
            return TemplateResponse(request, 'tasks/task_detail.html', context, status=400)
        
        try:
            task = Task.objects.select_related(
                'creator', 'assignee', 'parent_task'
            ).prefetch_related(
                'tags', 'comments', 'comments__author',
                'attachments', 'attachments__uploaded_by',
                'checklist', 'watchers__user',
                'time_entries', 'time_entries__user',
                'subtasks', 'subtasks__tags'
            )
        except Task.DoesNotExist:
            logger.warning(f'Task not found: {task_id}')
            context = {
                'error': 'Задача не найдена.',
                'task': None
            }
            return TemplateResponse(request, 'task/task_detail', context, status=404)
        
        if not can_view_task(request.user, task):
            logger.warning(f'User {request.user.id} attempted to access task {task_id} without permission.')
            context = {
                'error': 'У вас нет прав для просмотра этой задачи.',
                'task': None
            }
            return TemplateResponse(request, 'task/task_detail.html', context, status=403)

        context = {
            'task': task,
            'can_edit': can_edit_task(request.user, task),
            'can_delete': can_delete_task(request, task),
            'is_watcher': task.watchers.filter(user=request.user).exists(),
            'error': None
        }
        return TemplateResponse(request, 'tasks/task_detail.html', context)
    
    except Exception as e:
        logger.error(f'Error retrieving task {task_id}: {e}', exc_info=True)
        context = {
            'error': 'Произошла ошибка при загрузке задачи.',
            'task': None
        }
        return TemplateResponse(request, 'tasks/task_detail.html', context, status=500)

@login_required
@require_http_methods(['GET', 'POST'])
def task_create(request):
    if request.method == 'GET':
        form = TaskCreateForm()
        context = {
            'form': form,
            'title': 'Создать задачу'
        }
        return TemplateResponse(request, 'tasks/task_form.html', context)
    
    form = TaskCreateForm(request.POST)
    
    if not form.is_valid():
        logger.warning(f'Task creation form invalid: {form.errors}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'Некорректные данные формы.',
                'deatils': form.errors
            }, status=400)
            
        context = {
            'form': form,
            'title': 'Создать задачу'
        }
        return TemplateResponse(request, 'tasks/task_form.html', context, status=400)
    
    task = form.save(commit=False)
    task.creator = request.user
    task._current_user = request.user
    task.save()
    
    form.save_m2m()
    
    logger.info(f'Task {task.id} created by user {request.user.id}')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'message': 'Задача успешно создана.'
        })
    messages.success(request, 'Задача успешно создана.')
    return redirect('tasks:task_detail', task_id=task.id)

@login_required
@require_http_methods(['GET', 'POST'])
def task_update(request, task_id):
    
    task = get_object_or_404(Task, id=task_id)
    
    if not can_edit_task(request.user, task):
        logger.warning(f'User {request.user.id} unauthorized to update task {task_id}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'У вас нет прав для редактирования этой задачи.',
            }, status=403)
            
        context = {
            'error': 'У вас нет прав для редактирования этой задачи.',
            'task': task
        }
        return TemplateResponse(request, 'tasks/task_detail.html', context, status=403)
    
    if request.method == 'GET':
        form = TaskUpdateForm(instance=task, user=request.user)
        context = {
            'form': form,
            'task': task,
            'title': f'Редактировать задачу: {task.title}'
        }
        return TemplateResponse(request, 'tasks/task_form.html', context)
    
    form = TaskUpdateForm(request.POST, instance=task, user=request.user)
    if not form.is_valid():
        logger.warning(f'Task update form invalid for task {task_id}: {form.errors}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'Некорректные данные формы.',
                'details': form.errors
            }, status=400)
            
        context = {
            'form': form,
            'task': task,
            'title': f'Редактировать задачу: {task.title}'
        }
        return TemplateResponse(request, 'tasks/task_form.html', context, status=400)
    
    task = form.save(commit=False)
    task._current_user = request.user
    task.save()
    
    form.save_m2m()
    
    logger.info(f'Task {task.id} updated by user {request.user.id}')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': 'Задача успешно обновлена.'
        })
    
    messages.success(request, 'Задача успешно обновлена.')
    return redirect('tasks:task_detail', task_id=task.id)

@login_required
@require_http_methods(['POST', 'DELETE'])
def task_delete(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    
    if not can_delete_task(request.user, task):
        logger.warning(f'User {request.user.id} unauthorized to delete task {task_id}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'У вас нет прав для удаления этой задачи.'
            }, status=403)
        
        messages.error(request, 'У вас нет прав для удаления этой задачи.')
        return redirect('tasks:task_detail', task_id=task.id)
    
    task_title = task.title
    
    task.delete()
    
    logger.info(f'Task {task_id}: {task_title} deleted by user {request.user.id}')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f'Задача ({task_title}) успешно удалена.'
        })
        
    messages.success(request, f'Задача ({task_title}) успешно удалена.')
    return redirect('tasks:task_list')
        

@login_required
@require_http_methods(['POST'])
def task_comment_create(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    
    if not can_view_task(request.user, task):
        logger.warning(f'User {request.user.id} attempted to comment on task {task_id} without permission.')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'У вас нет прав для комментирования этой задачи.'
            }, status=403)
        
        context = {
            'error': 'У вас нет прав для комментирования этой задачи.',
            'task': task
        } 
        return TemplateResponse(request, 'tasks/task_detail.html', context, status=403)
    
    form = TaskCommentForm(request.POST)
    
    if not form.is_valid():
        logger.warning(f'Invalid comment form to task {task_id}: {form.errors}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'Некорректные данные.',
                'details': form.errors
            }, status=400)
            
        messages.success(request, 'Ошибка при добавления комментария.')
        return redirect('tasks:task_detail', task_id=task.id)
    
    comment = form.save(commit=False)
    comment.task = task
    comment.author = request.user
    comment.is_system = False
    comment.save()
    
    logger.info(f'Comment {comment.id} added to task {task_id} by user {request.user.id}')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'comment': {
                'id': comment.id,
                'text': comment.text,
                'author': comment.author.full_name,
                'created_at': comment.created_at.isoformat()
            }
        })
    messages.success(request, 'Комментарий добавлен.')
    return redirect('tasks:task_detail', task_id=task.id)

@login_required
@require_http_methods(['POST', 'PUT', 'PATCH'])
def comment_update(request, comment_id):
    comment = get_object_or_404(TaskComment, id=comment_id)
    
    if comment.is_system:
        return JsonResponse({
            'error': 'Системные комментарии нельзя редактировать.'
        }, status=400)
        
    if comment.author != request.user and not (hasattr(request.user, 'is_manager') and request.user.is_manager()):
        return JsonResponse({
            'error': 'Вы не можете редактировать чужой комментарий.'
        }, status=403)

    form = TaskCommentForm(request.POST, instance=comment)
    
    if not form.is_valid():
        return JsonResponse({
            'error': 'Некорректные данные.',
            'details': form.errors
        }, status=400)
    
    comment = form.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': 'Комментарий обновлён.',
            'comment': {
                'id': comment.id,
                'text': comment.text,
                'updated_at': comment.updated_at.isoformat()
            }
        })
        
    messages.success(request, 'Комментарий обновлен.')
    return redirect('tasks:task_detail', task_id=comment.task.id)

@login_required
@require_http_methods(['DELETE', 'POST'])
def task_comment_delete(request, comment_id):
    comment = get_object_or_404(TaskComment, id=comment_id)
    task_id = comment.task.id
    
    if comment.author != request.user and not (hasattr(request.user, 'is_manager') and request.user.is_manager()):
        return JsonResponse({
            'error': 'Вы не можете удалить чужой комментарий. '
        }, status=403)
        
    comment.delete()
    
    logger.info(f'Comment {comment_id} deleted by user {request.user.id}')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': 'Комментарий удалён.'
        })
    messages.success(request, 'Комментарий удален.')
    return redirect('tasks:task_detail', task_id=task_id)
    
@login_required
@require_http_methods(['POST'])
def task_watcher_add(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    
    if not can_edit_task(request.user, task):
        return JsonResponse({
            'error': 'У вас нет прав для добавления наблюдателей.'
        }, status=403)
        
    user_id = request.POST.get('user_id')
    
    if not user_id:
        return JsonResponse({
            'error': 'Не указан пользователь.'
        }, status=400)
        
    try:
        user = User.objects.get(id=int(user_id))
    except (ValueError, User.DoesNotExist):
        return JsonResponse({
            'error': 'Пользователь не найден.'
        }, status=404)
    
    if TaskWatcher.objects.filter(task=task, user=user).exists():
        return JsonResponse({
            'error': 'Этот пользователь уже наблюдает за задачей.'
        })

    logger.info(f'User {user_id} added as watcher to task {task_id} by {request.user.id}')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f'Пользователь {user.full_name} добавлен в наблюдатели.'
        })
    messages.success(request, f'Пользователь {user.full_name} добавлен в наблюдатели.')
    return redirect('tasks:task_detail', task_id=task.id)

@login_required
@require_http_methods(['POST', 'DELETE'])
def task_watcher_remove(request, task_id, user_id):
    task = get_object_or_404(Task, id=task_id)
    
    user = get_object_or_404(User, id=user_id)
    
    if not can_edit_task(request.user, task) and request.user != user:
        return JsonResponse({
            'error': 'У вас нет прав для удаления наблюдателя.'
        }, status=403)
        
    try:
        watcher = TaskWatcher.objects.get(task=task, user=user)
        watcher.delete()
        
        logger.info(f'User {user.id} removed as watcher from task {task_id}')
        
        message = 'Наблюдатель удален.' if request.user != user else 'Вы отписались от задачи.'
        
        if request.headers.get('X-Request-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': message
            })
        messages.success(request, message)
        return redirect('tasks:task_detail', task_id=task.id)
    
    except TaskWatcher.DoesNotExist:
        return JsonResponse({
            'error': 'Пользователь не является наблюдателем.'
        }, status=404)
        
@login_required
@require_http_methods(['POST'])
def task_checklist_item_create(request, task_id):
    """Добавление пункта в чеклист"""
    
    task = get_object_or_404(Task, id=task_id)
    
    if not (task.creator ==  request.user or     
            task.assignee == request.user or
            (hasattr(request.user, 'is_manager') and request.user.is_manager())):
        return JsonResponse({
            'error': 'У вас нет прав для изменения чеклиста.'
        }, status=403)
        
    form = TaskChecklistItemForm(request.POST)
    
    if not form.is_valid():
        return JsonResponse({
            'error': 'Некорректные данные.',
            'details': form.errors
        }, status=400)
        
    item = form.save(commit=False)
    item.task = task
    
    if not item.order:
        max_order = task.checklist.aggregate(max_order=Max('order'))['max_order'] or 0
        item.order = max_order + 1
        
    item.save()
    
    logger.info(f'Checklist item {item.id} added to task {task_id}')
    
    if request.headers.get('X-Request-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'item': {
                'id': item.id,
                'text': item.item_text,
                'is_completed': item.is_completed
            }
        })
    messages.success(request, 'Пункт добавлен в чеклист.')
    return redirect('tasks:task_detail', task_id=task.id)

@login_required
@require_http_methods(['POST', 'PATCH'])
def task_checklist_item_toggle(request, item_id):
    item = get_object_or_404(TaskChecklist, id=item_id)
    task = item.task
    
    if not (task.creator == request.user or
            task.assignee == request.user or
            (hasattr(request.user, 'is_manager') and request.user.is_manager())):
        return JsonResponse({
            'error': 'У вас нет прав для изменения чеклиста.'
        })
        
    item.is_completed = not item.is_completed
    
    if item.is_completed:
        item.completed_at = timezone.now()
        item.completed_by = request.user
    else:
        item.completed_at = None
        item.completed_by = None
        
    item.save()
    
    logger.info(f'Checklist item {item.id} toggled by user {request.user.id}')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'is_completed': item.is_completed
        })
    
    return redirect('tasks:task_detail', task_id=task.id)

@login_required
@require_http_methods(['DELETE', 'POST'])
def task_checklist_item_delete(request, item_id):
    
    item = get_object_or_404(TaskChecklist, id=item_id)
    task = item.task
    task_id = task.id
    
    if not can_edit_task(request.user, task):
        return JsonResponse({
            'error': 'У вас нет прав для удаления пунктов чеклиста.'
        })
    
    item.delete()
    
    logger.info(f'Checklist item {item_id} deleted by user {request.user.id}')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': 'Пункт удален.'
        })
    
    messages.success(request, 'Пункт удален.')
    return redirect('tasks:task_detail', task_id=task_id)

@login_required
@require_http_methods(['POST'])
def task_attachment_upload(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    
    if not can_view_task(request.user, task):
        return JsonResponse({
            'error': 'У вас нет прав для добавления файлов.'
        }, status=403)
        
    form = TaskAttachmentForm(request.POST, request.FILES)
    
    if not form.is_valid():
        return JsonResponse({
            'error': 'Ошибка загрузки файла',
            'details': form.errors
        }, status=400)
        
    attachment = form.save(commit=False)
    attachment.task = task
    attachment.uploaded_by = request.user
    attachment.save()
    
    logger.info(f'File {attachment.file_name} uploaded to task {task_id} by user {request.user.id}')
    
    return JsonResponse({
        'success': True,
        'attachment': {
            'id': attachment.id,
            'name': attachment.file_name,
            'size': attachment.file_size,
            'url': attachment.file.url
        }
    })

@login_required
@require_http_methods(['DELETE', 'POST'])
def task_attachment_delete(request, attachment_id):
    """Удаление вложения."""

    attachment = get_object_or_404(TaskAttachment, id=attachment_id)
    task_id = attachment.task.id
    
    if not (attachment.uploaded_by == request.user or
            attachment.task.creator == request.user or
            (hasattr(request.user, 'is_manager') and request.user.is_manager())):
        return JsonResponse({
            'error': 'У вас нет прав для удаления этого файла.'
        }, status=403)
    
    if attachment.file:
        attachment.file.delete(save=False)
        
    attachment.delete()
    
    logger.info(f'Attachment {attachment_id} deleted by user {request.user.id}')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': 'Файл удален.'
        })
    
    messages.success(request, 'Файл удален.')
    return redirect('tasks:task_detail', task_id=task_id)

@login_required
@require_http_methods(['POST'])
def task_time_entry_create(request, task_id):
    """Добавление записи о затраченном времени."""
    
    task = get_object_or_404(Task, id=task_id)
    
    if not (task.assignee == request.user or 
            (hasattr(request.user, 'is_manager') and request.user.is_manager())):
        return JsonResponse({
            'error': 'У вас нет прав для учета времени по этой задаче.'
        }, status=403)
        
    form = TimeEntryForm(request.POST)
    
    if not form.is_valid():
        return JsonResponse({
            'error': 'Некорректные данные.',
            'details': form.errors
        }, status=400)
    
    entry = form.save(commit=False)
    entry.task = task
    entry.user = request.user
    entry.save()
    
    task.actual_hours = task.time_entries.aggregate(
        total=Sum('hours')
    )['total'] or Decimal('0.00')
    task.save(update_fields=['actual_hours'])
    
    logger.info(f'Time entry {entry.id} ({entry.hours}h) added to task {task_id} by user {request.user.id}')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'entry': {
                'id': entry.id,
                'hours': float(entry.hours),
                'description': entry.description,
                'date': entry.date.isoformat()
            },
            'task_actual_hours': float(task.actual_hours)
        })
        
    messages.success(request, f'Добавлено {entry.hours} часов.')
    return redirect('tasks:task_detail', task_id = task.id)

@login_required
@require_http_methods(['DELETE', 'POST'])
def task_time_entry_delete(request, entry_id):
    """Удаление записи о времени."""
    
    entry = get_object_or_404(TimeEntry, id=entry_id)
    task = entry.task
    task_id = task.id
    
    if not (entry.user == request.user or 
            (hasattr(request.user, 'is_manager') and request.user.is_manager())):
        return JsonResponse({
            'error': 'У вас нет прав для удаления этой записи.'
        }, status=403)
        
    entry.delete()
    
    task.actual_hours = task.time_entries.aggregate(
        total=Sum('hours')
    )['total'] or Decimal('0.00')
    task.save(update_fields=['actual_hours'])
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': 'Запись удалена.',
            'task_actual_hours': float(task.actual_hours)
        })
    
    messages.success(request, 'Запись удалена.')
    return redirect('tasks:task_detail', task_id=task_id)
