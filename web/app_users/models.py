# FILE: web/app_users/models.py  (обновлено — 2026-02-15)
# PURPOSE: Добавлены 4 банковских поля в FlexxUser + добавлена информативная таблица связи Tippgeber↔Client (SET_NULL, created_at).

from __future__ import annotations

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone


class FlexxUserManager(BaseUserManager):
    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
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

    bank_account_holder = models.CharField(max_length=255, blank=True)
    bank_iban = models.CharField(max_length=34, blank=True)
    bank_name = models.CharField(max_length=255, blank=True)
    bank_bic = models.CharField(max_length=11, blank=True)

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)

    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "role"]

    objects = FlexxUserManager()

    def __str__(self) -> str:
        return self.email


class TippgeberClient(models.Model):
    """
    Информативная связь Tippgeber (agent) -> Client (client).
    У клиента максимум один Tippgeber.
    Удаления НЕ каскадят (SET_NULL).
    """

    tippgeber = models.ForeignKey(
        FlexxUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tippgeber_client_links",
    )
    client = models.OneToOneField(
        FlexxUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="client_tippgeber_link",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "tippgeber_clients"

    def __str__(self) -> str:
        return f"{self.tippgeber_id} -> {self.client_id}"
