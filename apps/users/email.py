from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.template.loader import render_to_string
from django.conf import settings
from .tokens import email_activation_token

def send_activation_email(request, user):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_activation_token.make_token(user)

    path = reverse("users:activate", kwargs={"uidb64": uidb64, "token": token})

    # корректно собираем URL со схемой
    scheme = "https" if request.is_secure() else "http"
    domain = get_current_site(request).domain
    activate_url = f"{scheme}://{domain}{path}"

    subject = "Подтвердите ваш e-mail"
    message = render_to_string("users/activation_email.txt", {
        "user": user,
        "activate_url": activate_url,
    })
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])

