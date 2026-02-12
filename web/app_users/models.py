# FILE: web/app_users/models.py  (обновлено — 2026-02-12)
# PURPOSE: Переименование модели User → FlexxUser (кастомный пользователь web, username=email, роли client/admin/agent).

from __future__ import annotations

from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)
from django.utils import timezone


class FlexxUserManager(BaseUserManager):
    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class FlexxUser(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        CLIENT = "client", "Client"
        ADMIN = "admin", "Admin"
        AGENT = "agent", "Agent"

    email = models.EmailField(unique=True)

    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    birth_date = models.DateField(null=True, blank=True)

    street = models.CharField(max_length=255, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=150, blank=True)

    phone = models.CharField(max_length=50, blank=True)
    fax = models.CharField(max_length=50, blank=True)

    company = models.CharField(max_length=255, blank=True)
    handelsregister = models.CharField(max_length=255, blank=True)
    handelsregister_number = models.CharField(max_length=100, blank=True)
    contact_person = models.CharField(max_length=255, blank=True)

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CLIENT,
    )

    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "role"]

    objects = FlexxUserManager()

    def __str__(self) -> str:
        return self.email
