from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.tokens import PasswordResetTokenGenerator

class EmailActivationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        base = f'{user.pk}{timestamp}{getattr(user, 'is_verified', False)}{user.is_active}'
        return base
    

email_activation_token = EmailActivationTokenGenerator()
