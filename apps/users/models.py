from django.db import models
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import EmailValidator
from django.conf import settings

class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('E-mail must be set')
        email = self.normalize_email(email).lower()
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
        extra_fields.setdefault('is_verified', False)
        extra_fields.setdefault('is_employee', True)
        extra_fields.setdefault('is_supervisor', False)
        extra_fields.setdefault('is_watсher', False)
        return self._create_user(email, password, **extra_fields)
    
    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('is_employee', True)
        extra_fields.setdefault('is_supervisor', False)
        extra_fields.setdefault('is_watсher', False)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(
        _('email'),
        unique=True,
        db_index=True,
        validators=[EmailValidator()],
    )
    first_name = models.CharField(_('Имя'), max_length=150, blank=True)
    last_name = models.CharField(_('фамилия'), max_length=150, blank=True)

    # Служебные флаги
    is_active = models.BooleanField(_('активен'), default=True)
    is_staff = models.BooleanField(_('персонал'), default=False)
    is_verified = models.BooleanField(_('e-mail подтверждён'), default=False)
    is_employee = models.BooleanField(_('сотрудник'), default=True)
    is_supervisor = models.BooleanField(_('руководитель'), default=False)
    is_watсher = models.BooleanField(_('наблюдатель'), default=False)

    # Метаданные
    date_joined = models.DateTimeField(_('дата регистрации'), default=timezone.now)
    updated_at = models.DateTimeField(_('обновлён'), auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = _('пользователь')
        verbose_name_plural = _('пользователи')

    def __str__(self):
        return self.email
    
    @property
    def full_name(self):
        full_name = f'{self.first_name} {self.last_name}'.strip()
        return full_name if full_name else self.email

    def is_manager(self):
        return self.is_supervisor or self.is_superuser


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(max_length=1000, blank=True)
    timezone = models.CharField(max_length=50, blank=True)
    
    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'
        
    def __str__(self) -> str:
        return f'Профиль {self.user}'

    def role_display(self):
        roles = []
        
        if self.user.is_superuser:
            roles.append('Admin')
        elif self.user.is_moderator:
            roles.append('Moderator')
        elif self.user.is_watсher:
            roles.append('Freelancer')
        elif self.user.is_supervisor:
            roles.append('Seller')
            
        return ", ".join(roles) or "User"
    
    
