from rest_framework import serializers
from safety.models import Conversation, SafetyLog, Document


class ConversationSerializer(serializers.ModelSerializer):
    user_phone = serializers.CharField(source='user.phone_number', read_only=True)
    user_role = serializers.CharField(source='user.get_role_display', read_only=True)

    class Meta:
        model = Conversation
        fields = [
            'id',
            'user',
            'user_phone',
            'user_role',
            'message',
            'response',
            'message_type',
            'response_included_image',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class SafetyLogSerializer(serializers.ModelSerializer):
    user_phone = serializers.CharField(source='user.phone_number', read_only=True)

    class Meta:
        model = SafetyLog
        fields = [
            'id',
            'user',
            'user_phone',
            'task_description',
            'safety_check',
            'sources',
            'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            'id',
            'title',
            'file',
            'is_active',
            'uploaded_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'uploaded_at', 'updated_at']
