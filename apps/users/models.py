from django.db import models
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.utils import timezone
from django.core.validators import EmailValidator
from django.conf import settings


class UserProxy:
    def __init__(self, id, email):
        self.id = id
        self.email = email
        
    @classmethod
    def from_api(cls, data):
        return cls(
            id=data["id"],
            email=data.get("email", ""),
        )
    
class UserManager(BaseUserManager):
    use_in_migrations = True
    
    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("E-mail must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_moderator', False) # Модератор
        extra_fields.setdefault('is_employee', True) # Сотрудник
        extra_fields.setdefault('is_watcher', False) # Наблюдатель
        extra_fields.setdefault('is_supervisor', False) # Руководитель

        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_moderator', True) 
        extra_fields.setdefault('is_employee', True)
        extra_fields.setdefault('is_watcher', False)
        extra_fields.setdefault('is_supervisor', False)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(email, password, **extra_fields)
    
class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(
        'email',
        unique=True,
        db_index=True,
        validators=[EmailValidator()],
    )
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_moderator = models.BooleanField(default=False)
    is_employee = models.BooleanField(default=True)
    is_watcher = models.BooleanField(default=False)
    is_supervisor = models.BooleanField(default=False)
    
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        
    def __str__(self) -> str:
        return self.email
    
    def full_name(self):
        return (f'{self.first_name} {self.last_name}').strip()
    
class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    timezone = models.CharField(max_length=50, blank=True, null=True)
    
    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'
    
    def __str__(self) -> str:
        return f'Профиль {self.user.first_name} {self.user.last_name}'
    
    def role_display(self):
        roles = []
        
        if self.user.is_superuser:
            roles.append('Администратор')
        if self.user.is_moderator:
            roles.append('Модератор')
        if self.user.is_employee:
            roles.append('Сотрудник')
        if self.user.is_watcher:
            roles.append('Наблюдатель')
        if self.user.is_supervisor:
            roles.append('Руководитель')
            
        return ', '.join(roles) if roles else 'Нет ролей'    
        
