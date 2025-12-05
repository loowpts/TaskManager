from django import forms
from django.utils import timezone
from .models import Task


class TaskCreateForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            'title', 'description', 'status',
            'priority', 'assignee', 'deadline',
            'estimated_hours', 'tags', 'parent_task'
        ]
        
    def clean_deadline(self):
        deadline = self.cleaned_data.get('deadline')
        
        # Проверяем только если deadline указан
        if deadline and deadline < timezone.now():
            raise forms.ValidationError('Дедлайн не может быть в прошлом.')
        return deadline
    
    def clean_estimated_hours(self):
        estimated_hours = self.cleaned_data.get('estimated_hours')
        if estimated_hours is not None and estimated_hours <= 0:
            raise forms.ValidationError('Время должно быть больше нуля.')
        return estimated_hours

    def clean_parent_task(self):
        parent = self.cleaned_data.get('parent_task')
        
        if parent is None:
            return parent
        
        self_obj = self.instance
        
        if self_obj.pk and parent.pk == self_obj.pk:
            raise forms.ValidationError('Задача не может быть родителем самой себя')
        
        # Проверка циклов
        p = parent
        while p:
            if self_obj.pk and p.pk == self_obj.pk:
                raise forms.ValidationError('Обнаружен цикл в родительских задачах')
            p = p.parent_task 
        
        return parent
    

class TaskUpdateForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            'title', 'description', 'assignee', 'status', 'priority',
            'deadline', 'estimated_hours', 'tags'
        ]
        
    def clean_deadline(self):
        deadline = self.cleaned_data.get('deadline')
        if deadline and deadline < timezone.now():
            raise forms.ValidationError('Дедлайн не может быть в прошлом.')
        return deadline
    
    def clean_estimated_hours(self):
        estimated_hours = self.cleaned_data.get('estimated_hours')
        if estimated_hours is not None and estimated_hours <= 0:
            raise forms.ValidationError('Время должно быть больше нуля.')
        return estimated_hours
    
    def clean_status(self):
        status = self.cleaned_data.get('status')
        old_status = self.instance.status  # старый статус
        
        # Если задача была выполнена, нельзя менять статус обратно
        if old_status == 'completed' and status != 'completed':
            raise forms.ValidationError('Нельзя изменить статус выполненной задачи.')
        
        return status
