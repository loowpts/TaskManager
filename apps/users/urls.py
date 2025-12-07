from django.urls import path, re_path
from django.contrib.auth import views as auth_views

from .views import (
    CustomLoginView,
    RegisterView, RegisterDoneView,
    ActivateEmailView, ActivationInvalidView, ResendActivationView,
    MyProfileView, UserProfileDetailView, ProfileUpdateView,
    # FollowersListView, FollowingListView,
    # FollowView, UnfollowView,
)

app_name = 'users'

urlpatterns = [
    # auth
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='users/logout.html'), name='logout'),

    path('register/', RegisterView.as_view(), name='register'),
    path('register/done/', RegisterDoneView.as_view(), name='register_done'),

    # email activation
    path('activate/<uidb64>/<token>/', ActivateEmailView.as_view(), name='activate'),
    path('activate/invalid/', ActivationInvalidView.as_view(), name='activation_invalid'),
    path('resend-activation/', ResendActivationView.as_view(), name='resend_activation'),

    # password reset
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='users/password_reset.html',
            email_template_name='users/password_reset_email.txt',
            subject_template_name='users/password_reset_subject.txt',
            success_url='/users/password-reset/done/'
        ),
        name='password_reset'
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(template_name='users/password_reset_done.html'),
        name='password_reset_done'
    ),
    re_path(
        r'^reset/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>.+)/$',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='users/password_reset_confirm.html',
            success_url='/users/reset/complete/'
        ),
        name='password_reset_confirm'
    ),
    path(
        'reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(template_name='users/password_reset_complete.html'),
        name='password_reset_complete'
    ),

    # my profile
    path('me/', MyProfileView.as_view(), name='my_profile'),
    path('me/edit/', ProfileUpdateView.as_view(), name='profile_update'),

    # public profiles (by user pk)
    path('u/<int:pk>/', UserProfileDetailView.as_view(), name='profile_detail'),
    # path('u/<int:pk>/followers/', FollowersListView.as_view(), name='profile_followers'),
    # path('u/<int:pk>/following/', FollowingListView.as_view(), name='profile_following'),

    # # follow actions
    # path('u/<int:pk>/follow/', FollowView.as_view(), name='follow'),
    # path('u/<int:pk>/unfollow/', UnfollowView.as_view(), name='unfollow'),
]
