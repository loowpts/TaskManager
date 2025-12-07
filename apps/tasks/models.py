from django.db import models
from django.core.exceptions import ValidationError
import os

class TaskTag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default='#808080')
    created_by = models.ForeignKey('users.User', on_delete=models.CASCADE)
    
    class Meta:
        verbose_name = 'Тег задачи'
        verbose_name_plural = 'Теги задач'
    
    def __str__(self):
        return self.name


class PRIORITY_CHOICES(models.TextChoices):
    LOW = 'low', 'Низкая'
    MEDIUM = 'medium', 'Средняя'
    HIGH = 'high', 'Высокая'
    CRITICAL = 'critical', 'Критическая'
    
    
class STATUS_CHOICES(models.TextChoices):
    NEW = 'new', 'Новая'
    IN_PROGRESS = 'in_progress', 'В ходе выполнения'
    REVIEW = 'review', 'Обзор'
    COMPLETED = 'completed', 'Выполнено'
    REJECTED = 'rejected', 'Отклонено'
    
    
class Task(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    creator = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='created_tasks')
    assignee = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        related_name='assigned_tasks',
        null=True,
        blank=False,
        help_text='Исполнитель задачи (обязательно)'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CHOICES.NEW)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_CHOICES.LOW)
    deadline = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    estimated_hours = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    actual_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tags = models.ManyToManyField(TaskTag, related_name='tasks', blank=True)
    parent_task = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subtasks')
    
    class Meta:
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['creator', 'status']),
            models.Index(fields=['assignee', 'status']),
            models.Index(fields=['priority']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['deadline']),
        ]
    
    def __str__(self):
        return f'{self.title} ({self.get_status_display()})'

    def clean(self):
        if self.parent_task:
            current = self.parent_task
            visited = set()

            while current:
                if current.pk == self.pk:
                    raise ValidationError({
                        'parent_task': 'Обнаружен цикл в родительских задачах.'
                    })

                if current.pk in visited:
                    raise ValidationError({
                        'parent_task': 'Обнаружен цикл в родительских задачах.'
                    })

                visited.add(current.pk)
                current = current.parent_task
        

class TaskComment(models.Model):
    task = models.ForeignKey('tasks.Task', on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey('users.User', on_delete=models.CASCADE)
    text = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_system = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'
        ordering = ['created_at']
    
    def __str__(self):
        return f'Comment by {self.author} on {self.task}'


class TaskAttachment(models.Model):
    task = models.ForeignKey('tasks.Task', on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='task_attachments/')
    uploaded_by = models.ForeignKey('users.User', on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField()
    
    class Meta:
        verbose_name = 'Вложение'
        verbose_name_plural = 'Вложения'
    
    def __str__(self):
        return f'{self.file_name} - {self.task}'
    
    def get_file_extension(self):
        """Получить расширение файла"""
        _, extension = os.path.splitext(self.file_name)
        return extension.lower().lstrip('.')

 
class TaskHistory(models.Model):
    task = models.ForeignKey('tasks.Task', on_delete=models.CASCADE, related_name='history')
    changed_by = models.ForeignKey('users.User', on_delete=models.CASCADE)
    changed_at = models.DateTimeField(auto_now_add=True)
    field = models.CharField(max_length=100)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'История изменений'
        verbose_name_plural = 'История изменений'
        ordering = ['-changed_at']
    
    def __str__(self):
        return f'{self.task} - {self.field} changed by {self.changed_by}'


class TaskChecklist(models.Model):
    task = models.ForeignKey('tasks.Task', on_delete=models.CASCADE, related_name='checklist')
    item_text = models.CharField(max_length=500)
    is_completed = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Чеклист'
        verbose_name_plural = 'Чеклисты'
        ordering = ['order']
    
    def __str__(self):
        status = '✓' if self.is_completed else '○'
        return f'{status} {self.item_text}'


class TaskWatcher(models.Model):
    """Наблюдатели за задачей"""
    task = models.ForeignKey('tasks.Task', on_delete=models.CASCADE, related_name='watchers')
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Наблюдатель'
        verbose_name_plural = 'Наблюдатели'
        unique_together = ['task', 'user']
    
    def __str__(self):
        return f'{self.user} watching {self.task}'


class TimeEntry(models.Model):
    """Учет затраченного времени"""
    task = models.ForeignKey('tasks.Task', on_delete=models.CASCADE, related_name='time_entries')
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    description = models.TextField(blank=True)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Запись времени'
        verbose_name_plural = 'Записи времени'
        ordering = ['-date']
    
    def __str__(self):
        return f'{self.user} - {self.hours}h on {self.task}'
