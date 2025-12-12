from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    # Tasks
    path('', views.task_list, name='task_list'),
    path('<int:task_id>/', views.task_detail, name='task_detail'),
    path('create/', views.task_create, name='task_create'),
    path('<int:task_id>/update/', views.task_update, name='task_update'),
    path('<int:task_id>/delete/', views.task_delete, name='task_delete'),

    # Comments
    path('<int:task_id>/comment/create/', views.task_comment_create, name='comment_create'),
    path('comment/<int:comment_id>/update/', views.comment_update, name='comment_update'),
    path('comment/<int:comment_id>/delete/', views.task_comment_delete, name='comment_delete'),

    # Watchers
    path('<int:task_id>/watcher/add/', views.task_watcher_add, name='watcher_add'),
    path('<int:task_id>/watcher/<int:user_id>/remove/', views.task_watcher_remove, name='watcher_remove'),

    # Checklist
    path('<int:task_id>/checklist/create/', views.task_checklist_item_create, name='checklist_item_create'),
    path('checklist/<int:item_id>/toggle/', views.task_checklist_item_toggle, name='checklist_item_toggle'),
    path('checklist/<int:item_id>/delete/', views.task_checklist_item_delete, name='checklist_item_delete'),

    # Attachments
    path('<int:task_id>/attachment/upload/', views.task_attachment_upload, name='attachment_upload'),
    path('attachment/<int:attachment_id>/delete/', views.task_attachment_delete, name='attachment_delete'),

    # Time entries
    path('<int:task_id>/time/create/', views.task_time_entry_create, name='time_entry_create'),
    path('time/<int:entry_id>/delete/', views.task_time_entry_delete, name='time_entry_delete'),
]
