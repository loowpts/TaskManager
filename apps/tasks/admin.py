from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.db.models import Count, Sum, Q
from django.utils import timezone

from .models import (
    Task, TaskTag, TaskComment, TaskAttachment,
    TaskHistory, TaskChecklist, TaskWatcher, TimeEntry,
    STATUS_CHOICES, PRIORITY_CHOICES
)


class TaskCommentInline(admin.TabularInline):
    """Inline для комментариев к задаче"""
    model = TaskComment
    extra = 0
    fields = ('author', 'text', 'is_system', 'created_at')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

    def has_add_permission(self, request, obj=None):
        """Разрешить добавление только системных комментариев"""
        return True


class TaskChecklistInline(admin.TabularInline):
    """Inline для чек-листа задачи"""
    model = TaskChecklist
    extra = 1
    fields = ('item_text', 'is_completed', 'order', 'completed_by', 'completed_at')
    readonly_fields = ('completed_by', 'completed_at')
    ordering = ('order',)


class TaskAttachmentInline(admin.TabularInline):
    """Inline для вложений задачи"""
    model = TaskAttachment
    extra = 0
    fields = ('file_name', 'file', 'file_size_display', 'uploaded_by', 'uploaded_at')
    readonly_fields = ('file_size_display', 'uploaded_by', 'uploaded_at')

    def file_size_display(self, obj):
        """Отображение размера файла"""
        if obj.file_size:
            size_kb = obj.file_size / 1024
            if size_kb < 1024:
                return f'{size_kb:.2f} KB'
            return f'{size_kb / 1024:.2f} MB'
        return '-'
    file_size_display.short_description = 'Размер'


class TimeEntryInline(admin.TabularInline):
    """Inline для учета времени"""
    model = TimeEntry
    extra = 0
    fields = ('user', 'date', 'hours', 'description')
    ordering = ('-date',)


class TaskWatcherInline(admin.TabularInline):
    """Inline для наблюдателей"""
    model = TaskWatcher
    extra = 0
    fields = ('user', 'added_at')
    readonly_fields = ('added_at',)


@admin.register(TaskTag)
class TaskTagAdmin(admin.ModelAdmin):
    """Админка для тегов задач"""

    list_display = ('name', 'color_badge', 'created_by', 'task_count')
    list_filter = ('created_by',)
    search_fields = ('name',)

    def color_badge(self, obj):
        """Превью цвета тега"""
        return format_html(
            '<div style="display: inline-flex; align-items: center; gap: 8px;">'
            '<span style="width: 24px; height: 24px; background: {}; border-radius: 4px; '
            'border: 1px solid #ddd; display: inline-block;"></span>'
            '<code>{}</code>'
            '</div>',
            obj.color, obj.color
        )
    color_badge.short_description = 'Цвет'

    def task_count(self, obj):
        """Количество задач с этим тегом"""
        count = obj.tasks.count()
        return format_html(
            '<span style="background: #007bff; color: white; padding: 2px 8px; '
            'border-radius: 10px; font-size: 11px;">{}</span>',
            count
        )
    task_count.short_description = 'Задач'


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Расширенная админка для задач"""

    list_display = (
        'id', 'title_with_link', 'status_badge', 'priority_badge',
        'assignee', 'creator', 'deadline_display', 'progress_display', 'created_at'
    )

    list_filter = (
        'status', 'priority', 'created_at', 'deadline',
        ('assignee', admin.RelatedOnlyFieldListFilter),
        ('creator', admin.RelatedOnlyFieldListFilter),
        ('tags', admin.RelatedOnlyFieldListFilter),
    )

    search_fields = ('title', 'description', 'id')

    date_hierarchy = 'created_at'

    # Для autocomplete в других админках и в этой
    autocomplete_fields = ['creator', 'assignee', 'parent_task']

    filter_horizontal = ('tags',)

    readonly_fields = (
        'created_at', 'updated_at', 'completed_at',
        'actual_hours', 'time_tracking_display', 'watchers_display',
        'subtasks_display'
    )

    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'tags')
        }),
        ('Назначение и приоритет', {
            'fields': (('creator', 'assignee'), ('status', 'priority'), 'parent_task')
        }),
        ('Сроки и время', {
            'fields': (
                ('deadline', 'estimated_hours'),
                ('actual_hours', 'time_tracking_display'),
            )
        }),
        ('Дополнительная информация', {
            'fields': ('watchers_display', 'subtasks_display'),
            'classes': ('collapse',)
        }),
        ('Системные данные', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [
        TaskChecklistInline,
        TimeEntryInline,
        TaskAttachmentInline,
        TaskWatcherInline,
        TaskCommentInline,
    ]

    actions = [
        'mark_as_in_progress', 'mark_as_completed', 'mark_as_review',
        'set_high_priority', 'set_low_priority'
    ]

    list_per_page = 25

    def title_with_link(self, obj):
        """Заголовок со ссылкой на задачу"""
        url = reverse('tasks:task_detail', args=[obj.id])
        return format_html(
            '<a href="{}" target="_blank" style="font-weight: 500;">{}</a>',
            url, obj.title[:60]
        )
    title_with_link.short_description = 'Название'
    title_with_link.admin_order_field = 'title'

    def status_badge(self, obj):
        """Бейдж статуса"""
        colors = {
            'new': '#7A99FF',
            'in_progress': '#FFB84D',
            'review': '#9B87FF',
            'completed': '#4ECDC4',
            'rejected': '#FF6B9D',
        }
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: 500; white-space: nowrap;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Статус'
    status_badge.admin_order_field = 'status'

    def priority_badge(self, obj):
        """Бейдж приоритета"""
        colors = {
            'low': '#94A3B8',
            'medium': '#FBBF24',
            'high': '#FB923C',
            'critical': '#F87171',
        }
        icons = {
            'low': '↓',
            'medium': '→',
            'high': '↑',
            'critical': '⚠',
        }
        color = colors.get(obj.priority, '#999')
        icon = icons.get(obj.priority, '')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: 500;">{} {}</span>',
            color, icon, obj.get_priority_display()
        )
    priority_badge.short_description = 'Приоритет'
    priority_badge.admin_order_field = 'priority'

    def deadline_display(self, obj):
        """Отображение дедлайна с подсветкой"""
        if not obj.deadline:
            return '-'

        now = timezone.now()
        is_overdue = obj.deadline < now and obj.status != 'completed'
        is_soon = obj.deadline - now < timezone.timedelta(days=3) and not is_overdue

        color = '#dc3545' if is_overdue else '#ffc107' if is_soon else '#6c757d'
        icon = '⚠' if is_overdue else '⏰' if is_soon else '📅'

        return format_html(
            '<span style="color: {}; font-weight: {};">{} {}</span>',
            color,
            'bold' if (is_overdue or is_soon) else 'normal',
            icon,
            obj.deadline.strftime('%d.%m.%Y')
        )
    deadline_display.short_description = 'Дедлайн'
    deadline_display.admin_order_field = 'deadline'

    def progress_display(self, obj):
        """Прогресс выполнения"""
        # Чек-лист
        total_items = obj.checklist.count()
        completed_items = obj.checklist.filter(is_completed=True).count()

        if total_items > 0:
            percentage = int((completed_items / total_items) * 100)
            return format_html(
                '<div style="font-size: 11px;">'
                '<div style="background: #e0e0e0; border-radius: 10px; height: 18px; position: relative; width: 80px;">'
                '<div style="background: #4ECDC4; border-radius: 10px; height: 100%; width: {}%;"></div>'
                '<span style="position: absolute; top: 0; left: 0; right: 0; text-align: center; '
                'line-height: 18px; color: #333; font-weight: 600; font-size: 10px;">{}%</span>'
                '</div>'
                '</div>',
                percentage, percentage
            )
        return '-'
    progress_display.short_description = 'Прогресс'

    def time_tracking_display(self, obj):
        """Отображение учета времени"""
        estimated = obj.estimated_hours or 0
        actual = obj.actual_hours or 0

        if estimated > 0:
            percentage = int((actual / estimated) * 100)
            color = '#28a745' if actual <= estimated else '#dc3545'
            return format_html(
                '<div style="font-size: 12px;">'
                '<strong>Оценка:</strong> {} ч<br>'
                '<strong>Факт:</strong> <span style="color: {};">{} ч ({}%)</span>'
                '</div>',
                estimated, color, actual, percentage
            )
        elif actual > 0:
            return format_html(
                '<div style="font-size: 12px;">'
                '<strong>Факт:</strong> {} ч'
                '</div>',
                actual
            )
        return 'Не указано'
    time_tracking_display.short_description = 'Учет времени'

    def watchers_display(self, obj):
        """Список наблюдателей"""
        watchers = obj.watchers.select_related('user').all()
        if not watchers:
            return 'Нет наблюдателей'

        items = []
        for watcher in watchers:
            items.append(f'• {watcher.user.get_full_name() or watcher.user.username}')

        return format_html('<br>'.join(items))
    watchers_display.short_description = 'Наблюдатели'

    def subtasks_display(self, obj):
        """Список подзадач"""
        subtasks = obj.subtasks.all()
        if not subtasks:
            return 'Нет подзадач'

        items = []
        for subtask in subtasks:
            url = reverse('admin:tasks_task_change', args=[subtask.id])
            items.append(
                f'• <a href="{url}">{subtask.title}</a> '
                f'<small>({subtask.get_status_display()})</small>'
            )

        return format_html('<br>'.join(items))
    subtasks_display.short_description = 'Подзадачи'

    # Actions
    def mark_as_in_progress(self, request, queryset):
        """Перевести в работу"""
        updated = queryset.update(status='in_progress')
        self.message_user(request, f'{updated} задач переведены в работу.')
    mark_as_in_progress.short_description = 'Перевести в работу'

    def mark_as_completed(self, request, queryset):
        """Отметить как выполненные"""
        updated = queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f'{updated} задач отмечены как выполненные.')
    mark_as_completed.short_description = 'Отметить выполненными'

    def mark_as_review(self, request, queryset):
        """Отправить на ревью"""
        updated = queryset.update(status='review')
        self.message_user(request, f'{updated} задач отправлены на ревью.')
    mark_as_review.short_description = 'Отправить на ревью'

    def set_high_priority(self, request, queryset):
        """Установить высокий приоритет"""
        updated = queryset.update(priority='high')
        self.message_user(request, f'{updated} задач получили высокий приоритет.')
    set_high_priority.short_description = 'Высокий приоритет'

    def set_low_priority(self, request, queryset):
        """Установить низкий приоритет"""
        updated = queryset.update(priority='low')
        self.message_user(request, f'{updated} задач получили низкий приоритет.')
    set_low_priority.short_description = 'Низкий приоритет'


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    """Админка для комментариев"""

    list_display = ('id', 'task_link', 'author', 'text_short', 'is_system', 'created_at')
    list_filter = ('is_system', 'created_at')
    search_fields = ('text', 'task__title', 'author__username')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')

    def task_link(self, obj):
        """Ссылка на задачу"""
        url = reverse('admin:tasks_task_change', args=[obj.task.id])
        return format_html('<a href="{}">{}</a>', url, obj.task.title[:40])
    task_link.short_description = 'Задача'

    def text_short(self, obj):
        """Короткий текст комментария"""
        return obj.text[:100] + '...' if len(obj.text) > 100 else obj.text
    text_short.short_description = 'Текст'


@admin.register(TaskHistory)
class TaskHistoryAdmin(admin.ModelAdmin):
    """Админка для истории изменений"""

    list_display = ('id', 'task_link', 'field', 'old_value_short', 'new_value_short', 'changed_by', 'changed_at')
    list_filter = ('field', 'changed_at')
    search_fields = ('task__title', 'field', 'changed_by__username')
    date_hierarchy = 'changed_at'
    readonly_fields = ('task', 'changed_by', 'changed_at', 'field', 'old_value', 'new_value')

    def has_add_permission(self, request):
        """Запретить добавление вручную"""
        return False

    def has_change_permission(self, request, obj=None):
        """Запретить изменение"""
        return False

    def task_link(self, obj):
        """Ссылка на задачу"""
        url = reverse('admin:tasks_task_change', args=[obj.task.id])
        return format_html('<a href="{}">{}</a>', url, obj.task.title[:40])
    task_link.short_description = 'Задача'

    def old_value_short(self, obj):
        return obj.old_value[:50] if obj.old_value else '-'
    old_value_short.short_description = 'Старое значение'

    def new_value_short(self, obj):
        return obj.new_value[:50] if obj.new_value else '-'
    new_value_short.short_description = 'Новое значение'


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    """Админка для учета времени"""

    list_display = ('id', 'task_link', 'user', 'hours', 'date', 'description_short')
    list_filter = ('date', 'user')
    search_fields = ('task__title', 'user__username', 'description')
    date_hierarchy = 'date'

    def task_link(self, obj):
        """Ссылка на задачу"""
        url = reverse('admin:tasks_task_change', args=[obj.task.id])
        return format_html('<a href="{}">{}</a>', url, obj.task.title[:40])
    task_link.short_description = 'Задача'

    def description_short(self, obj):
        return obj.description[:60] if obj.description else '-'
    description_short.short_description = 'Описание'
