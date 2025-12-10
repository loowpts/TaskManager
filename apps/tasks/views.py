import logging
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.conf import settings
from django.template.response import TemplateResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from datetime import datetime
from django.contrib import messages


from .models import Task, TaskTag
from .forms import TaskCreateForm, TaskUpdateForm

User = settings.AUTH_USER_MODEL

logger = logging.getLogger(__name__)

@login_required
def task_list(request):
    try:
        user = request.user

        if hasattr(user, 'is_manager') and user.is_manager():
            tasks = Task.objects.all()
        else:
            # Показываем задачи, где пользователь - создатель, исполнитель или наблюдатель
            tasks = Task.objects.filter(
                Q(assignee=user) | Q(creator=user) | Q(watchers__user=user)
            ).distinct()

        # Оптимизация запросов
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

        # Фильтрация по создателю
        creator = request.GET.get('creator')
        if creator:
            try:
                tasks = tasks.filter(creator_id=int(creator))
            except (ValueError, TypeError):
                logger.warning(f"Invalid creator ID: {creator}")

        # Фильтрация по дедлайну (от)
        deadline_from = request.GET.get('deadline_from')
        if deadline_from:
            try:
                deadline_from = datetime.strptime(deadline_from, '%Y-%m-%d')
                tasks = tasks.filter(deadline__gte=deadline_from)
            except ValueError:
                logger.warning(f"Invalid deadline_from format: {deadline_from}")
                
        # Фильтрация по дедлайну (до)
        deadline_to = request.GET.get('deadline_to')
        if deadline_to:
            try:
                deadline_to = datetime.strptime(deadline_to, '%Y-%m-%d')
                tasks = tasks.filter(deadline__lte=deadline_to)
            except ValueError:
                logger.warning(f"Invalid deadline_to format: {deadline_to}")

        search = request.GET.get('search')
        if search:
            if len(search) > 200:
                logger.warning(f"Search query too long: {len(search)} characters")
                search = search[:200]
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

        page = request.GET.get('page', 1)
        paginator = Paginator(tasks, per_page)

        try:
            tasks_page = paginator.page(page)
        except PageNotAnInteger:
            tasks_page = paginator.page(1)
        except EmptyPage:
            tasks_page = paginator.page(paginator.num_pages)

        context = {
            'tasks': tasks_page,
            'page_obj': tasks_page,
            'total_count': paginator.count,
            'error': None
        }

        return TemplateResponse(request, 'tasks/task_list.html', context)

    except Exception as e:
        logger.error(f"Error in task_list: {str(e)}", exc_info=True)
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
            logger.warning(f"Invalid task ID format: {task_id}")
            context = {
                'error': 'Недопустимый формат идентификатора задачи.',
                'task': None
            }
            return TemplateResponse(request, 'tasks/task_detail.html', context, status=400)

        try:
            task = Task.objects.select_related(
                'creator', 'assignee', 'parent_task'
            ).prefetch_related(
                'tags', 'comments', 'attachments', 'checklist',
                'watchers__user',
                'time_entries', 'time_entries__user',
                'subtasks', 'subtasks__tags'
            ).get(id=task_id)
        except Task.DoesNotExist:
            logger.warning(f'Task not found: {task_id}')
            context = {
                'error': 'Задача не найдена.',
                'task': None
            }
            return TemplateResponse(request, 'tasks/task_detail.html', context, status=404)
        
        user = request.user
        
        has_access = (
            task.assignee == user or
            task.creator == user or
            (hasattr(user, 'is_manager') and user.is_manager()) or
            task.watchers.filter(user=user).exists()
        )
        
        if not has_access:
            logger.warning(f"User {user.id} attempted to access task {task_id} without permission.")
            context = {
                'error': 'У вас нет прав для просмотра этой задачи.',
                'task': None
            }
            return TemplateResponse(request, 'tasks/task_detail.html', context, status=403)
        
        context = {
            'task': task,
            'can_edit': task.creator == user or (hasattr(user, 'is_manager') and user.is_manager()),
            'can_delete': task.creator == user or (hasattr(user, 'is_manager') and user.is_manager()),
            'is_watcher': task.watchers.filter(user=user).exists(),
            'error': None
        }
        
        return TemplateResponse(request, 'tasks/task_detail.html', context)
    
    except Exception as e:
        logger.error(f"Error retrieving task {task_id}: {e}")
        context = {
            'error': 'Произошла ошибка при загрузке задачи.',
            'task': None
        }
        return TemplateResponse(request, 'tasks/task_detail.html', context, status=500)
    
@login_required
@require_http_methods(["GET", "POST"])
def task_create(request, user_id):
    if request.method == 'GET':
        form = TaskCreateForm()
        context = {
            'form': form,
            'title': 'Создать задачу'
        }
        return TemplateResponse(request, 'tasks/task_create.html', context)
    
    form = TaskCreateForm(request.POST)
    if not form.is_valid():
        logger.warning(f'Task creation form invalid: {form.errors}')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'Некорректные данные формы.',
                'details': form.errors
            }, status=400)
        else:
            context = {
                'form': form,
                'title': 'Создать задачу'
            }
            return TemplateResponse(request, 'tasks/task_form.html', context, status=400)
        
    task = form.save(commit=False)
    task.save()
    
    form.save_m2m()
    
    logger.info(f'Task {task.id} created by user {request.user.id}')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return TemplateResponse(request, 'tasks/partials/task_item.html', {
            'task': task,
            'message': 'Задача успешно создана.'
        })
    else:
        return redirect('task_detail', task_id=task.id)


@login_required
@require_http_methods(['GET', 'POST'])
def task_update(request, task_id):
    
    task = get_object_or_404(Task, task_id)
    
    if task.creator != request.user and not (hasattr(request.user, 'is_manager') and request.user.is_manager()):
        logger.warning(f'User {request.user.id} unauthorized to update task {task_id}')

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'У вас нет прав для редактирования этой задачи.'
            }, status=403)
        else:
            context ={
                'error': 'У вас нет прав для редактирования этой задачи',
                'task': task
            }
            return TemplateResponse(request, 'task/task_detail.html', context, status=403)
    
    if request.method == 'GET':
        form = TaskUpdateForm(instance=task)
        context = {
            'form': form,
            'task': task,
            'title': f'Редактировать задачу {task.title}'
        }
        return TemplateResponse(request, 'task/task_form.html', context)
    
    form = TaskUpdateForm(request.POST, instance=task)
    
    if not form.is_valid():
        logger.warning(f'Task update form invalid for task {task_id}: {form.errors}')

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'Некорректные данные формы.',
                'form': form.errors
            }, status=400)
        else:
            context = {
                'form': form,
                'task': task,
                'title': f'Редактировать задачу {task.title}'
            }
            return TemplateResponse(request, 'task/task_form.html', context, status=400)
        
    task._current_user = request.user
    task = form.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return TemplateResponse(request, 'tasks/partials/task_item.html', {
            'task': task,
            'message': 'Задача успешно обновлена.'
        })
    else:
        return redirect('task_detail', task_id=task.id)
    
@login_required
@require_http_methods(['DELETE'])
def task_delete(request, task_id):
    
    task = get_object_or_404(Task, task_id)
    
    if task.creator != request.user and not (hasattr(request.user, 'is_manager') and request.user.is_manager()):
        logger.warning(f'User {request.user.id} unauthorized to delete task {task_id}')

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'У вас нет прав для удаления этой задачи.'
            }, status=403)
        else:
            messages.error(request, 'У вас нет прав для удаления этой задачи.')
            return redirect('task_detail', task_id=task.id)
        
    task_title = task.title
    task.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f'Задача "{task_title}" успешно удалена.'
        })
    else:
        messages.success(request, f'Задача "{task_title}" успешно удалена.')
        return redirect('task_list')
    
    
    
    
    
    
