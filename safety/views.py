import json
import logging
import threading

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from twilio.request_validator import RequestValidator

from safety.whatsapp_integration import (
    fetch_and_transcribe_voice,
    process_incoming_message,
    send_whatsapp_message,
)

logger = logging.getLogger('safety')


def _is_audio_content_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    return content_type.strip().lower().startswith('audio/')


def verify_twilio_signature(request) -> bool:
    if settings.DEBUG:
        return True
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    signature = request.META.get('HTTP_X_TWILIO_SIGNATURE', '')
    url = request.build_absolute_uri()
    post_data = request.POST
    return validator.validate(url, post_data, signature)


def process_and_send(
    from_number: str,
    message_body: str | None = None,
    media_url: str | None = None,
    media_content_type: str | None = None,
) -> None:
    try:
        logger.info(
            f"Background processing started | from={from_number} | voice={bool(media_url)}"
        )
        is_voice = False
        if media_url and _is_audio_content_type(media_content_type):
            transcript, err = fetch_and_transcribe_voice(media_url, media_content_type)
            if err:
                send_whatsapp_message(from_number, err)
                logger.warning(f"Voice transcription failed | from={from_number}")
                return
            message_body = transcript
            is_voice = True

        if not message_body or not message_body.strip():
            logger.warning("No message body after voice transcript — skipping")
            return

        response_text, image_url = process_incoming_message(
            from_number, message_body, is_voice=is_voice
        )
        logger.info(
            f"Response ready | to={from_number} | length={len(response_text)} chars"
            + (" | with image" if image_url else "")
        )
        result = send_whatsapp_message(
            from_number, response_text, media_url=image_url
        )
        if result['status'] == 'sent':
            logger.info(f"Message delivered | sid={result.get('message_sid')}")
        else:
            logger.error(f"Message delivery failed | error={result.get('error')}")

    except Exception:
        logger.exception("Error in background processing | from=%s", from_number)


@csrf_exempt
@require_http_methods(["POST"])
def whatsapp_webhook(request):
    if not verify_twilio_signature(request):
        logger.warning("Rejected request with invalid Twilio signature")
        return HttpResponse(status=403)

    from_number = request.POST.get('From', '').strip()
    message_body = request.POST.get('Body', '').strip()
    num_media = int(request.POST.get('NumMedia', '0') or '0')
    media_url0 = request.POST.get('MediaUrl0', '').strip()
    media_content_type0 = request.POST.get('MediaContentType0', '').strip() or None

    if not from_number:
        logger.warning("Webhook received with missing 'From' field")
        return HttpResponse(status=400)

    kwargs = {}
    if message_body:
        kwargs['message_body'] = message_body
        logger.info(f"Webhook received | from={from_number} | text='{message_body[:50]}'")
    elif num_media >= 1 and media_url0 and _is_audio_content_type(media_content_type0):
        kwargs['media_url'] = media_url0
        kwargs['media_content_type'] = media_content_type0
        logger.info(f"Webhook received | from={from_number} | voice media")
    else:
        logger.info(f"Empty or non-voice message from {from_number} — ignoring")
        return HttpResponse(status=200)

    threading.Thread(
        target=process_and_send,
        args=(from_number,),
        kwargs=kwargs,
        daemon=True,
    ).start()
    logger.info("Responded 200 OK to Twilio — processing in background")
    return HttpResponse(status=200)


@csrf_exempt
@require_http_methods(["POST"])
def test_message(request):
    """DEBUG only: run the same pipeline as WhatsApp webhook and return response in JSON (no Twilio send). Use curl to test when WhatsApp is out of service."""
    if not settings.DEBUG:
        return HttpResponse(status=404)
    try:
        if request.content_type and 'application/json' in request.content_type:
            data = json.loads(request.body)
        else:
            data = request.POST
        from_number = (data.get('from') or data.get('From') or '').strip()
        message_body = (data.get('message') or data.get('Body') or '').strip()
        is_voice = str(data.get('is_voice', 'false')).lower() in ('true', '1', 'yes')
    except Exception as e:
        logger.warning(f"test_message: bad request | error={e}")
        return JsonResponse({'error': 'Invalid request. Send JSON: {"from": "whatsapp:+123...", "message": "..."}'}, status=400)
    if not from_number or not message_body:
        return JsonResponse({'error': 'Missing "from" and "message"'}, status=400)
    if not from_number.startswith('whatsapp:'):
        from_number = f'whatsapp:{from_number}'
    try:
        response_text, image_url = process_incoming_message(
            from_number,
            message_body,
            is_voice=is_voice,
            skip_rate_limit=settings.DEBUG,
        )
        return JsonResponse({
            'response': response_text,
            'image_url': image_url,
        })
    except Exception as e:
        logger.exception("test_message: processing failed")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def webhook_status(request):
    try:
        from safety.models import Conversation
        db_status = 'ok'
        total_conversations = Conversation.objects.count()
    except Exception:
        db_status = 'error'
        total_conversations = 0

    try:
        from safety.ai_utils.rag_system import get_rag
        rag = get_rag()
        stats = rag.get_stats()
        rag_status = 'ok'
        rag_chunks = stats.get('total_chunks', 0)
        indexed_sources = stats.get('indexed_sources', [])
    except Exception:
        rag_status = 'error'
        rag_chunks = 0
        indexed_sources = []

    return JsonResponse({
        'status': 'online',
        'message': 'SafeGuardAI WhatsApp webhook is running',
        'system': {
            'database': db_status,
            'rag': rag_status,
            'total_chunks': rag_chunks,
            'indexed_sources': indexed_sources,
            'total_conversations': total_conversations,
            'debug_mode': settings.DEBUG,
        },
        'endpoints': {
            'whatsapp_webhook': reverse('safety:whatsapp_webhook'),
            'status': reverse('safety:webhook_status'),
            **({'test_message': reverse('safety:test_message')} if settings.DEBUG else {}),
        },
    })


def dashboard_view(request):
    response = render(request, 'index.html')
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    return response
