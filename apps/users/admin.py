from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db.models import Count, Q

from .models import User, UserProfile


class UserProfileInline(admin.StackedInline):
    """Inline для профиля пользователя"""
    model = UserProfile
    can_delete = False
    verbose_name = 'Профиль'
    verbose_name_plural = 'Профиль'

    fields = ('avatar', 'avatar_preview', 'bio', 'timezone')
    readonly_fields = ('avatar_preview',)

    def avatar_preview(self, obj):
        """Превью аватара"""
        if obj.avatar:
            return format_html(
                '<img src="{}" width="100" height="100" '
                'style="border-radius: 50%; object-fit: cover;" />',
                obj.avatar.url
            )
        return format_html(
            '<div style="width: 100px; height: 100px; border-radius: 50%; '
            'background: #e0e0e0; display: flex; align-items: center; '
            'justify-content: center; color: #999;">Нет фото</div>'
        )
    avatar_preview.short_description = 'Превью'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Расширенная админка для пользователей"""

    list_display = (
        'email', 'full_name_display', 'role_badge',
        'is_active_badge', 'task_stats', 'date_joined'
    )
    list_filter = (
        'is_active', 'is_staff', 'is_superuser',
        'is_supervisor', 'is_employee', 'is_watcher',
        'is_verified', 'date_joined'
    )
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-date_joined',)

    # Для autocomplete в других админках
    autocomplete_fields = []

    fieldsets = (
        (None, {
            'fields': ('email', 'password')
        }),
        (_('Личная информация'), {
            'fields': ('first_name', 'last_name')
        }),
        (_('Роли и права'), {
            'fields': (
                'is_active', 'is_verified',
                'is_employee', 'is_supervisor', 'is_watcher',
                'is_staff', 'is_superuser',
                'groups', 'user_permissions'
            ),
            'classes': ('collapse',)
        }),
        (_('Важные даты'), {
            'fields': ('last_login', 'date_joined', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'password1', 'password2',
                'first_name', 'last_name',
                'is_supervisor', 'is_watcher'
            ),
        }),
    )

    readonly_fields = ('date_joined', 'updated_at')

    inlines = [UserProfileInline]

    actions = ['make_supervisor', 'remove_supervisor', 'activate_users', 'deactivate_users', 'verify_users']

    def full_name_display(self, obj):
        """Полное имя пользователя"""
        full_name = obj.full_name
        return full_name if full_name else '-'
    full_name_display.short_description = 'Полное имя'
    full_name_display.admin_order_field = 'first_name'

    def role_badge(self, obj):
        """Бейдж роли пользователя"""
        roles = []
        if obj.is_superuser:
            roles.append('<span style="background: #dc3545; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">ADMIN</span>')
        if obj.is_supervisor:
            roles.append('<span style="background: #ffc107; color: #000; padding: 3px 8px; border-radius: 3px; font-size: 11px;">SUPERVISOR</span>')
        if obj.is_watcher:
            roles.append('<span style="background: #17a2b8; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">WATCHER</span>')
        if obj.is_employee and not (obj.is_supervisor or obj.is_superuser):
            roles.append('<span style="background: #28a745; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">EMPLOYEE</span>')
        if obj.is_staff and not obj.is_superuser:
            roles.append('<span style="background: #6c757d; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">STAFF</span>')

        if not roles:
            roles.append('<span style="background: #e0e0e0; color: #666; padding: 3px 8px; border-radius: 3px; font-size: 11px;">USER</span>')

        return format_html(' '.join(roles))
    role_badge.short_description = 'Роль'

    def is_active_badge(self, obj):
        """Бейдж активности"""
        badges = []

        if obj.is_active:
            badges.append('<span style="color: #28a745; font-weight: bold;">✓ Активен</span>')
        else:
            badges.append('<span style="color: #dc3545; font-weight: bold;">✗ Неактивен</span>')

        if obj.is_verified:
            badges.append('<span style="color: #17a2b8; font-size: 11px; margin-left: 5px;">✓ Email подтвержден</span>')

        return format_html(' '.join(badges))
    is_active_badge.short_description = 'Статус'

    def task_stats(self, obj):
        """Статистика задач пользователя"""
        created = obj.created_tasks.count()
        assigned = obj.assigned_tasks.count()

        return format_html(
            '<div style="font-size: 11px;">'
            '<span style="color: #007bff;">Создано: {}</span><br>'
            '<span style="color: #28a745;">Назначено: {}</span>'
            '</div>',
            created, assigned
        )
    task_stats.short_description = 'Задачи'

    def make_supervisor(self, request, queryset):
        """Сделать руководителем"""
        updated = queryset.update(is_supervisor=True)
        self.message_user(request, f'{updated} пользователей назначены руководителями.')
    make_supervisor.short_description = 'Назначить руководителем'

    def remove_supervisor(self, request, queryset):
        """Убрать роль руководителя"""
        updated = queryset.update(is_supervisor=False)
        self.message_user(request, f'{updated} пользователей лишены роли руководителя.')
    remove_supervisor.short_description = 'Убрать роль руководителя'

    def activate_users(self, request, queryset):
        """Активировать пользователей"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} пользователей активированы.')
    activate_users.short_description = 'Активировать выбранных'

    def deactivate_users(self, request, queryset):
        """Деактивировать пользователей"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} пользователей деактивированы.')
    deactivate_users.short_description = 'Деактивировать выбранных'

    def verify_users(self, request, queryset):
        """Подтвердить email пользователей"""
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} email адресов подтверждены.')
    verify_users.short_description = 'Подтвердить email'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Админка для профилей пользователей"""

    list_display = ('user', 'avatar_preview', 'bio_short', 'timezone')
    list_filter = ('timezone',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'bio')
    readonly_fields = ('avatar_preview',)

    fields = ('user', 'avatar', 'avatar_preview', 'bio', 'timezone')

    def avatar_preview(self, obj):
        """Превью аватара"""
        if obj.avatar:
            return format_html(
                '<img src="{}" width="80" height="80" '
                'style="border-radius: 50%; object-fit: cover;" />',
                obj.avatar.url
            )
        return '-'
    avatar_preview.short_description = 'Аватар'

    def bio_short(self, obj):
        """Короткое описание биографии"""
        if obj.bio:
            return obj.bio[:50] + '...' if len(obj.bio) > 50 else obj.bio
        return '-'
    bio_short.short_description = 'Биография'
