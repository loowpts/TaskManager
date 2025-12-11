import os
from django import forms
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError

from .models import Task, TaskComment, TaskChecklist, TimeEntry, TaskAttachment


class TaskCreateForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            'title', 'description', 'status',
            'priority', 'assignee', 'deadline',
            'estimated_hours', 'tags', 'parent_task'
        ]
    
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название задачи',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Опишите задачу подробно...'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'priority': forms.Select(attrs={
                'class': 'form-select'
            }),
            'assignee': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'deadline': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'estimated_hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.5',
                'placeholder': '0.0'
            }),
            'tags': forms.CheckboxSelectMultiple(),
            'parent_task': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
    
    def clean_deadline(self):
        deadline = self.cleaned_data.get('deadline')
        
        if not deadline:
            return deadline
        
        if deadline.tzinfo is None or deadline.tzinfo.utcoffset(deadline) is None:
            deadline = timezone.make_aware(deadline)
            
        if deadline < timezone.now():
            raise ValidationError('Дедлайн не может быть в прошлом.')
        
        return deadline
    
    def clean_estimated_hours(self):
        
        estimated_hours = self.cleaned_data.get('estimated_hours')
        
        if estimated_hours is None:
            return estimated_hours
        
        if estimated_hours <= 0:
            raise ValidationError('Оценка времени должна быть больше нуля.')
        
        if estimated_hours > 999:
            raise ValidationError('Оценка времени не может превышать 999 часов.')
        
        return estimated_hours
    
    def clean_parent_task(self):
        parent = self.cleaned_data.get('parent_task')
        
        if parent is None:
            return parent
        
        self_obj = self.instance
        
        if self_obj.pk and parent.pk == self_obj.pk:
            raise ValidationError('Задача не может быть родителем самой себя.')
        
        current = parent
        visited = set() # Множество для отслеживания посещенных задач
        
        while current:
            # Защита от бесконечного цикла
            if current.pk in visited:
                raise ValidationError('Обнаружен цикл в родительских задачах.')
            
            visited.add(current.pk)
            
            # Если в цепочке нашли текущую задачу - это цикл
            if self_obj.pk and current.pk == self_obj.pk:
                raise ValidationError('Обнаружен цикл в родительских задачах.')
            
            # Переходим к следующему родителю
            current = current.parent_task
            
        return parent
    

class TaskUpdateForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            'title', 'description', 'assignee', 'status',
            'priority', 'deadline', 'estimated_hours', 'tags'
        ]
        
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название задачи'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Описание задачи'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'priority': forms.Select(attrs={
                'class': 'form-select'
            }),
            'assignee': forms.Select(attrs={
                'class': 'form-select'
            }),
            'deadline': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'estimated_hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.5'
            }),
            'tags': forms.CheckboxSelectMultiple(),
        }
    
    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('user', None)
        
        super().__init__(*args, **kwargs)
        
    def clean_deadline(self):
        deadline = self.cleaned_data.get('deadline')
        
        if not deadline:
            return deadline
        
        if deadline.tzinfo is None or deadline.tzinfo.utcoffset(deadline) is None:
            deadline = timezone.make_aware(deadline)
            
        if deadline < timezone.now():
            raise ValidationError('Дедлайн не может быть в прошлом.')
        
        return deadline
    
    def clean_estimated_hours(self):
        estimated_hours = self.cleaned_data.get('estimated_hours')
        
        if estimated_hours is None:
            return estimated_hours
        
        if estimated_hours <= 0:
            raise ValidationError('Оценка времени должна быть больше нуля.')
        
        if estimated_hours > 999:
            raise ValidationError('Оценка времени не может превышать 999 часов.')
        
        return estimated_hours
    
    def clean_status(self):
        status = self.cleaned_data.get('status')
        old_status = self.instance.status
        
        # Если статус не изменился - валидация не нужна
        if old_status == status:
            return status
        
        if old_status == 'completed' and status != 'completed':
            if self.current_user and hasattr(self.current_user, 'is_manager') and self.current_user.is_manager():
                return status
            
            raise ValidationError(
                'Нельзя изменить статус выполненной задачи. '
                'Обратитесь к менеджеру'
            )
        return status
    

class TaskCommentForm(forms.ModelForm):
    class Meta:
        model = TaskComment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Введите ваш комментарий...',
                'maxlength': '2000'
            })
        }
    
    def clean_text(self):
        text = self.cleaned_data.get('text', '').strip()
        
        if not text:
            raise ValidationError('Комментарий не может быть пустым.')
        
        if len(text) > 2000:
            raise ValidationError('Комментарий слишком длинный (максимум 2000 символов.)')
        
        return text
    
class TaskChecklistItemForm(forms.ModelForm):
    class Meta:
        model = TaskChecklist
        fields = ['item_text', 'order']
        widgets = {
            'item_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Текст пункта чеклиста...',
                'maxlength': '500'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0'
            })
        }
        
    def clean_item_text(self):
        text = self.cleaned_data.get('item_text')
        
        if not text:
            raise ValidationError('Текст пункта не может быть пустым.')
        
        if len(text) > 500:
            raise ValidationError('Текст слишком длинный (максимум 500 символов).')
        
        return text
    
class TimeEntryForm(forms.ModelForm):
    class Meta:
        model = TimeEntry
        fields = ['data', 'hours', 'description']
        widgets = {
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.1',
                'max': '24',
                'step': '0.5',
                'placeholder': '0.0'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Что было сделано?'
            })
        }
        
    def clean_hours(self):
        hours = self.cleaned_data.get('hours')
        
        if hours is None:
            raise ValidationError('Укажите количество часов.')
        
        if hours < 0.1:
            raise ValidationError('Минимально время - 0.1 часа (6 минут)')
        
        if hours > 24:
            raise ValidationError('Максимум 24 часа за один раз.')
        
        return hours
    
    def clean_date(self):
        date = self.cleaned_data.get('date')
        
        if not date:
            raise ValidationError('Укажите дату.')
        
        today = timezone.now().date()
        
        if date > today:
            raise ValidationError('Нельзя указывать будущую дату.')
        
        if date < today - timedelta(days=30):
            raise ValidationError('Можно добавлять время только за последние 30 дней.')
        
        return date
    
class TaskAttachmentForm(forms.ModelForm):
    class Meta:
        model = TaskAttachment
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.txt,.jpg,.jpeg,.png,.zip'
            })
        }
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        
        if not file:
            raise ValidationError('Выберите файл для загрузки.')
        
        max_size = 10 * 1024 *1024
        if file.size > max_size:
            raise ValidationError(f'Файл слишком большой. Максимум {max_size / (1024*1024):.0f} MB.')
        
        # Проверка расширения (белый список)
        ext = os.path.splitext(file.name)[1].lower()
        allowed_extensions = [
            '.pdf', '.doc', '.docs',
            '.xls', '.xlsx',
            '.txt', '.md',
            '.jpg', '.jpeg', '.png', '.gif',
            '.zip', '.rar'
        ]
        
        if ext not in allowed_extensions:
            raise ValidationError(
                f'Недопустимый формат файла. Разрешены: {", ".join(allowed_extensions)}'
            )
            
        # Защита от исполняемых файлов
        dangerous_extensions = ['.exe', '.bat', '.cmd', '.sh', '.py', '.php', '.js']
        if ext in dangerous_extensions:
            raise ValidationError('Загрузка исполняемых файлов запрещена.')
        
        return file
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Автоматически заполняем метаданные
        if instance.file:
            instance.file_name = instance.file.name
            instance.file_size = instance.file.size
            
        if commit:
            instance.save()
            
        return instance
    
class TaskFilterForm(forms.Form):
    
    status = forms.ChoiceField(
        choices=[('', 'Все')] + list(Task.STATUS_CHOICES.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    priority = forms.ChoiceField(
        choices=[('', 'Все')] + list(Task.PRIORITY_CHOICES.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    assignee = forms.IntegerField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    creator = forms.IntegerField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    search = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Поиск по названию или описанию...'
        })
    )
    
    deadline_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    deadlite_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class':'form-control',
            'type': 'date'
        })
    )
    
    ordering = forms.ChoiceField(
        choices=[
            ('-created_at', 'Сначала новые'),
            ('created_at', 'Сначала старые'),
            ('-deadline', 'Дедлайн: сначала поздние'),
            ('deadline', 'Дедлай: снача ранние'),
            ('-priority', 'Приоритет: убывание'),
            ('priority', 'Приоритет: возрастание'),
        ],
        required=False,
        initial='-created_at',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
        
        
        
