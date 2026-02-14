from collections import Counter
from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from safety.ai_utils.rag_system import get_rag
from safety.models import Conversation, Document, SafetyLog
from safety.serializers import (
    ConversationSerializer,
    DocumentSerializer,
    SafetyLogSerializer,
)


def _apply_date_filters(queryset, request, date_field):
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    if start_date:
        queryset = queryset.filter(**{f'{date_field}__gte': start_date})
    if end_date:
        queryset = queryset.filter(**{f'{date_field}__lte': end_date})
    return queryset


class ConversationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Conversation.objects.all().select_related('user').order_by('-created_at')
    serializer_class = ConversationSerializer

    def get_queryset(self):
        queryset = _apply_date_filters(super().get_queryset(), self.request, 'created_at')
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(message__icontains=search) | Q(response__icontains=search)
            )
        message_type = self.request.query_params.get('message_type')
        if message_type == 'image':
            queryset = queryset.filter(response_included_image=True)
        elif message_type:
            queryset = queryset.filter(message_type=message_type)
        return queryset


class SafetyLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SafetyLog.objects.all().select_related('user').order_by('-timestamp')
    serializer_class = SafetyLogSerializer

    def get_queryset(self):
        queryset = _apply_date_filters(super().get_queryset(), self.request, 'timestamp')
        source = self.request.query_params.get('source')
        if source:
            queryset = queryset.filter(sources__icontains=source)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(task_description__icontains=search)
        return queryset


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all().order_by('-uploaded_at')
    serializer_class = DocumentSerializer
    parser_classes = (MultiPartParser, FormParser)

    @action(detail=False, methods=['post'])
    def upload(self, request):
        title = request.data.get('title')
        uploaded_file = request.FILES.get('file')
        if not title or not uploaded_file:
            return Response(
                {'error': 'Both title and file are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not uploaded_file.name.endswith('.txt'):
            return Response(
                {'error': 'Only .txt files are supported'},
                status=status.HTTP_400_BAD_REQUEST
            )
        document = None
        try:
            document = Document.objects.create(
                title=title,
                file=uploaded_file,
            )
            rag = get_rag()
            stats_before = rag.get_stats()
            chunks_before = stats_before.get('total_chunks', 0)
            rag.add_document(document.file.path, document.title)
            stats_after = rag.get_stats()
            chunks_after = stats_after.get('total_chunks', 0)
            in_sources = document.title in (stats_after.get('indexed_sources') or [])
            if not (chunks_after > chunks_before or in_sources):
                document.delete()
                return Response(
                    {
                        'error': (
                            'Document was saved but no chunks were indexed. '
                            'Check that OPENAI_API_KEY is set correctly in .env (no quotes, no spaces) '
                            'and that the key has access to the embeddings API. '
                            'See server logs for "Failed to index chunk" or "Embedding generation failed" for the exact error.'
                        )
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            return Response(
                {
                    'message': 'Document uploaded and indexed successfully',
                    'document': DocumentSerializer(document).data
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            if document is not None:
                try:
                    document.delete()
                except Exception:
                    pass
            return Response(
                {'error': f'Failed to upload document: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def reindex(self, request, pk=None):
        document = self.get_object()
        if not document.file:
            return Response(
                {'error': 'Document has no file attached'},
                status=status.HTTP_404_NOT_FOUND
            )
        try:
            file_path = document.file.path
            if not file_path or not document.file.storage.exists(document.file.name):
                return Response(
                    {'error': 'Document file not found on disk'},
                    status=status.HTTP_404_NOT_FOUND
                )
            rag = get_rag()
            rag.add_document(file_path, document.title, force=True)
            stats = rag.get_stats()
            if document.title not in (stats.get('indexed_sources') or []):
                return Response(
                    {
                        'error': (
                            'Re-indexing ran but no chunks were added. '
                            'Check OPENAI_API_KEY and that the embedding API is reachable.'
                        )
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            return Response(
                {'message': f'Document "{document.title}" re-indexed successfully'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to re-index document: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AnalyticsViewSet(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def summary(self, request):
        now = timezone.now()
        seven_days_ago = now - timedelta(days=7)

        total_conversations = Conversation.objects.count()
        total_safety_queries = SafetyLog.objects.count()
        active_users = Conversation.objects.values('user').distinct().count()
        conversations_7d = Conversation.objects.filter(created_at__gte=seven_days_ago).count()
        active_users_7d = Conversation.objects.filter(created_at__gte=seven_days_ago).values('user').distinct().count()

        top_topics = (
            SafetyLog.objects
            .values('sources')
            .annotate(count=Count('id'))
            .order_by('-count')[:8]
        )

        daily_counts = dict(
            Conversation.objects
            .filter(created_at__gte=seven_days_ago)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(count=Count('id'))
            .values_list('date', 'count')
        )
        conversations_by_day = [
            {
                'date': (seven_days_ago + timedelta(days=i)).strftime('%Y-%m-%d'),
                'count': daily_counts.get((seven_days_ago + timedelta(days=i)).date(), 0),
            }
            for i in range(8)
        ]

        all_docs = list(Document.objects.values('id', 'title', 'uploaded_at'))
        all_sources = list(
            SafetyLog.objects
            .exclude(sources='')
            .values_list('sources', flat=True)
        )
        source_counts = Counter()
        for src_str in all_sources:
            for s in src_str.split(','):
                s = s.strip()
                if s:
                    source_counts[s] += 1
        documents = []
        for doc in all_docs:
            documents.append({
                'id': doc['id'],
                'title': doc['title'],
                'usage_count': source_counts.get(doc['title'], 0),
                'uploaded_at': doc['uploaded_at'],
            })

        return Response({
            'total_conversations': total_conversations,
            'conversations_7d': conversations_7d,
            'total_safety_queries': total_safety_queries,
            'active_users': active_users,
            'active_users_7d': active_users_7d,
            'top_topics': list(top_topics),
            'conversations_by_day': conversations_by_day,
            'documents': documents,
        })
