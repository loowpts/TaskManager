from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import models
from .models import Task, TaskHistory, TaskComment, TimeEntry


@receiver(pre_save, sender=Task)
def track_task_changes(sender, instance, **kwargs):
    """
    Отслеживаем изменения перед сохранением задачи
    Сохраняем историю изменений полей
    """
    if instance.pk:  # если задача уже существует (обновление)
        try:
            old_task = Task.objects.get(pk=instance.pk)
            
            # Поля которые отслеживаем
            fields_to_track = {
                'status': 'Статус',
                'assignee': 'Исполнитель',
                'priority': 'Приоритет',
                'deadline': 'Дедлайн',
                'title': 'Название',
            }
            
            # Получаем пользователя который делает изменение
            # Этот пользователь должен быть передан через instance._current_user
            changed_by = getattr(instance, '_current_user', instance.creator)
            
            for field, field_name in fields_to_track.items():
                old_value = getattr(old_task, field)
                new_value = getattr(instance, field)
                
                if old_value != new_value:
                    # Сохраняем в историю
                    TaskHistory.objects.create(
                        task=instance,
                        changed_by=changed_by,
                        field=field_name,
                        old_value=str(old_value) if old_value else '',
                        new_value=str(new_value) if new_value else ''
                    )
                    
        except Task.DoesNotExist:
            pass


@receiver(post_save, sender=Task)
def create_system_comments(sender, instance, created, **kwargs):
    """
    Создаем системные комментарии при важных изменениях
    """
    if created:
        # При создании новой задачи
        comment_text = f"Задача создана пользователем {instance.creator}"
        if instance.assignee:
            comment_text += f" и назначена на {instance.assignee}"
        
        TaskComment.objects.create(
            task=instance,
            author=instance.creator,
            text=comment_text,
            is_system=True
        )
    else:
        # При обновлении проверяем что изменилось
        try:
            old_task = Task.objects.get(pk=instance.pk)
            changed_by = getattr(instance, '_current_user', instance.creator)
            
            # Изменение статуса
            if hasattr(instance, '_old_status') and instance._old_status != instance.status:
                TaskComment.objects.create(
                    task=instance,
                    author=changed_by,
                    text=f"Статус изменен: {instance._old_status} → {instance.get_status_display()}",
                    is_system=True
                )
            
            # Переназначение задачи
            if hasattr(instance, '_old_assignee') and instance._old_assignee != instance.assignee:
                old_assignee_name = instance._old_assignee.get_full_name() if instance._old_assignee else "Не назначено"
                new_assignee_name = instance.assignee.get_full_name() if instance.assignee else "Не назначено"
                
                TaskComment.objects.create(
                    task=instance,
                    author=changed_by,
                    text=f"Задача переназначена: {old_assignee_name} → {new_assignee_name}",
                    is_system=True
                )
            
            # Изменение дедлайна
            if hasattr(instance, '_old_deadline') and instance._old_deadline != instance.deadline:
                old_deadline = instance._old_deadline.strftime('%d.%m.%Y %H:%M') if instance._old_deadline else "Не установлен"
                new_deadline = instance.deadline.strftime('%d.%m.%Y %H:%M') if instance.deadline else "Не установлен"
                
                TaskComment.objects.create(
                    task=instance,
                    author=changed_by,
                    text=f"Дедлайн изменен: {old_deadline} → {new_deadline}",
                    is_system=True
                )
                
        except Task.DoesNotExist:
            pass


@receiver(post_save, sender=Task)
def set_completed_date(sender, instance, created, **kwargs):
    """
    Автоматически устанавливаем дату завершения
    когда статус меняется на COMPLETED
    """
    if not created and instance.status == 'completed' and not instance.completed_at:
        instance.completed_at = timezone.now()
        Task.objects.filter(pk=instance.pk).update(completed_at=instance.completed_at)


@receiver(post_save, sender=TimeEntry)
def update_actual_hours(sender, instance, created, **kwargs):
    """
    Обновляем actual_hours в задаче при добавлении TimeEntry
    """
    task = instance.task
    total_hours = task.time_entries.aggregate(
        total=models.Sum('hours')
    )['total'] or 0
    
    if task.actual_hours != total_hours:
        Task.objects.filter(pk=task.pk).update(actual_hours=total_hours)


# Дополнительный helper для сохранения старых значений перед изменением
@receiver(pre_save, sender=Task)
def store_old_values(sender, instance, **kwargs):
    """
    Сохраняем старые значения полей для последующего сравнения
    """
    if instance.pk:
        try:
            old_task = Task.objects.get(pk=instance.pk)
            instance._old_status = old_task.status
            instance._old_assignee = old_task.assignee
            instance._old_deadline = old_task.deadline
        except Task.DoesNotExist:
            pass
