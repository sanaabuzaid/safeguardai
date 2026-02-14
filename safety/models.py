import logging

from django.db import models
from django.contrib.auth.models import User as DjangoUser
from django.core.validators import RegexValidator
from django.db.models.signals import pre_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


PHONE_VALIDATOR = RegexValidator(
    regex=r'^whatsapp:\+\d{10,15}$',
    message="Phone must be in Twilio WhatsApp format: whatsapp:+XXXXXXXXXXXX",
)


class User(models.Model):
    class Role(models.TextChoices):
        WORKER = 'worker', 'Worker'
        HSE_OFFICER = 'hse_officer', 'HSE Officer'

    phone_number = models.CharField(
        max_length=100,
        unique=True,
        validators=[PHONE_VALIDATOR],
        help_text="WhatsApp number in Twilio format: whatsapp:+XXXXXXXXXXXX",
    )
    role = models.CharField(
        max_length=50,
        choices=Role.choices,
        default=Role.WORKER,
        help_text="User role determines access level and logging behaviour"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        db_table = 'safeguardai_user'

    def __str__(self):
        return f"{self.phone_number} ({self.get_role_display()})"


class Document(models.Model):
    title = models.CharField(max_length=200)
    file = models.FileField(
        upload_to='documents/safety_manuals/',
        help_text="Uploaded safety manual or procedure document"
    )
    uploaded_by = models.ForeignKey(
        DjangoUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_documents'
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive documents are excluded from RAG search results"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
        db_table = 'safeguardai_document'
        indexes = [
            models.Index(fields=['-uploaded_at']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.title



@receiver(pre_delete, sender=Document)
def delete_document_file(sender, instance, **kwargs):
    if instance.file and instance.file.name:
        try:
            instance.file.delete(save=False)
        except Exception:
            logger.warning("Failed to delete file %s for document %s", instance.file.name, instance.pk)


class Conversation(models.Model):
    class MessageType(models.TextChoices):
        TEXT = 'text', 'Text'
        VOICE = 'voice', 'Voice'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='conversations'
    )
    message = models.TextField(
        help_text="Original message from the worker"
    )
    response = models.TextField(
        help_text="AI-generated response sent back to the worker"
    )
    message_type = models.CharField(
        max_length=10,
        choices=MessageType.choices,
        default=MessageType.TEXT,
        help_text="Whether the worker sent a text or voice message"
    )
    response_included_image = models.BooleanField(
        default=False,
        help_text="True if the AI response included a generated image (e.g. DALL·E)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'
        db_table = 'safeguardai_conversation'
        indexes = [models.Index(fields=['-created_at'])]

    def __str__(self):
        msg = (self.message or '')[:50]
        return f"{self.user.phone_number}: {msg}"


class SafetyLog(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='safety_logs'
    )
    task_description = models.TextField(
        help_text="The safety question or task the worker asked about"
    )
    safety_check = models.TextField(
        help_text="Summary of the safety guidance provided"
    )
    sources = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text="Comma-separated list of documents used to generate the answer"
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Safety Log'
        verbose_name_plural = 'Safety Logs'
        db_table = 'safeguardai_safetylog'
        indexes = [models.Index(fields=['-timestamp'])]

    def __str__(self):
        task = (self.task_description or '')[:50]
        return f"{self.user.phone_number}: {task}"
