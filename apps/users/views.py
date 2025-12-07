from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.generic import FormView, TemplateView, View, DetailView, UpdateView
from .models import UserProfile
from .forms import RegisterForm, ProfileForm, LoginForm
from .email import send_activation_email
from .tokens import email_activation_token
from .models import User


class CustomLoginView(LoginView):
    template_name = 'users/login.html'
    authentication_form = LoginForm


class RegisterView(FormView):
    template_name = 'users/register.html'
    form_class = RegisterForm
    success_url = reverse_lazy('users:register_done')

    def form_valid(self, form):
        user = form.save()

        if hasattr(user, 'is_active'):
            # Деактивированным вход закрыт, но аккаунт активен
            user.is_active = True
            user.save(update_fields=['is_active'])
        send_activation_email(self.request, user)
        return super().form_valid(form)
    

class RegisterDoneView(TemplateView):
    template_name = 'users/register_done.html'


class ActivateEmailView(View):
    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError):
            user = None
        
        if user and email_activation_token.check_token(user, token):
            if hasattr(user, 'is_verified'):
                if not user.is_verified:
                    user.is_verified = True
                    user.save(update_fields=['is_verified'])
            messages.success(request, 'E-mail подтверждён. Добро пожаловать!')
            login(request, user)
            return redirect('users:profile')
        return redirect("users:activation_invalid")


class ActivationInvalidView(TemplateView):
    template_name = 'users/activation_invalid.html'


class MyProfileView(LoginRequiredMixin, DetailView):
    template_name = 'users/my_profile.html'
    context_object_name = 'profile'
    model = UserProfile

    def get_object(self, queryset=None):
        return get_object_or_404(
            UserProfile.objects.select_related('user'),
            user=self.request.user
        )


class UserProfileDetailView(DetailView):
    template_name = 'users/profile_detail.html'
    context_object_name = 'profile'
    model = UserProfile

    def get_object(self, queryset=None):
        profile = get_object_or_404(
            UserProfile.objects.select_related('user'),
            user__pk=self.kwargs['pk']
        )

        return profile


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    template_name = 'users/profile_update.html'
    form_class = ProfileForm
    model = UserProfile
    success_url = reverse_lazy('users:my_profile')

    def get_object(self, queryset=None):
        return get_object_or_404(UserProfile, user=self.request.user)


class ResendActivationView(LoginRequiredMixin, View):
    def post(self, request):
        user = request.user
        if getattr(user, 'is_verified', False):
            messages.info(request, 'E-mail уже подтверждён.')
            return redirect('users:my_profile')
        send_activation_email(request, user)
        messages.success(request, 'Письмо с подтверждением отправлено повторно.')
        return redirect('users:my_profile')
