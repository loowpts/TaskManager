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
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'assignee': forms.Select(attrs={'class': 'form-select'}),
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
            'parent_task': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_deadline(self):
        deadline = self.cleaned_data.get('deadline')

        if deadline:
            # Если datetime пришел без timezone (naive) - делаем aware
            if deadline.tzinfo is None or deadline.tzinfo.utcoffset(deadline) is None:
                deadline = timezone.make_aware(deadline)

            if deadline < timezone.now():
                raise forms.ValidationError('Дедлайн не может быть в прошлом.')

        return deadline

    def clean_estimated_hours(self):
        """
        Валидация оценки времени
        """
        estimated_hours = self.cleaned_data.get('estimated_hours')

        if estimated_hours is not None and estimated_hours <= 0:
            raise forms.ValidationError('Время должно быть больше нуля.')

        if estimated_hours is not None and estimated_hours > 999:
            raise forms.ValidationError('Время не может превышать 999 часов.')

        return estimated_hours

    def clean_parent_task(self):
        """
        Валидация родительской задачи
        Проверяем циклические зависимости
        """
        parent = self.cleaned_data.get('parent_task')

        if parent is None:
            return parent

        self_obj = self.instance

        # Проверка: задача не может быть родителем самой себя
        if self_obj.pk and parent.pk == self_obj.pk:
            raise forms.ValidationError('Задача не может быть родителем самой себя')

        current = parent
        visited = set()

        while current:
            # Защита от бесконечного цикла в случае уже существующего цикла в БД
            if current.pk in visited:
                raise forms.ValidationError('Обнаружен цикл в родительских задачах')
            visited.add(current.pk)

            if self_obj.pk and current.pk == self_obj.pk:
                raise forms.ValidationError('Обнаружен цикл в родительских задачах')

            current = current.parent_task

        return parent
    

class TaskUpdateForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            'title', 'description', 'assignee', 'status', 'priority',
            'deadline', 'estimated_hours', 'tags'
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
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'assignee': forms.Select(attrs={'class': 'form-select'}),
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

    def clean_deadline(self):
        deadline = self.cleaned_data.get('deadline')

        if deadline:
            # Если datetime пришел без timezone (naive) - делаем aware
            if deadline.tzinfo is None or deadline.tzinfo.utcoffset(deadline) is None:
                deadline = timezone.make_aware(deadline)

            if deadline < timezone.now():
                raise forms.ValidationError('Дедлайн не может быть в прошлом.')

        return deadline

    def clean_estimated_hours(self):
        """
        Валидация оценки времени
        """
        estimated_hours = self.cleaned_data.get('estimated_hours')

        if estimated_hours is not None and estimated_hours <= 0:
            raise forms.ValidationError('Время должно быть больше нуля.')

        if estimated_hours is not None and estimated_hours > 999:
            raise forms.ValidationError('Время не может превышать 999 часов.')

        return estimated_hours

    def clean_status(self):
        """
        Менеджеры могут переоткрывать выполненные задачи
        Обычные пользователи - нет
        """
        status = self.cleaned_data.get('status')
        old_status = self.instance.status

        # Если статус не изменился - все ок
        if old_status == status:
            return status

        # Если задача была выполнена, проверяем права
        if old_status == 'completed' and status != 'completed':
            user = getattr(self, 'current_user', None)

            # Если пользователь - менеджер, разрешаем переоткрыть
            if user and hasattr(user, 'is_manager') and user.is_manager():
                return status

            # Обычным пользователям нельзя
            raise forms.ValidationError(
                'Нельзя изменить статус выполненной задачи. '
                'Обратитесь к менеджеру.'
            )

        return status

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
