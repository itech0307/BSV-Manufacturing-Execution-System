from django import forms
from common.models import Profile
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import re

class UserRegistrationForm(forms.ModelForm):
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not re.match(r'^[a-z][a-z0-9_-]{3,19}$', username):
            raise ValidationError(
                "Username must be 4-20 characters long, start with a letter, "
                "and may only contain lowercase letters, numbers, hyphens, and underscores."
            )
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email.endswith('@baiksan.co.kr'):
            raise ValidationError("Only email addresses from baiksan.co.kr domain are allowed.")
        
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email address already exists.")
        
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['language']
        labels = {
            'language': 'language',
        }