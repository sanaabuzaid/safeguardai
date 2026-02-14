import json
import logging
import os
import random
import time
import uuid

import requests
from requests.auth import HTTPBasicAuth

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from twilio.rest import Client

from safety.ai_utils.agents import process_safety_query
from safety.ai_utils.tools import openai_client, transcribe_audio_file
from safety.models import Conversation, SafetyLog, User
from safety.security import run_security_checks


logger = logging.getLogger('safety')

AUDIO_EXTENSION_MAP = {
    'audio/ogg': '.ogg',
    'audio/oga': '.ogg',
    'audio/mpeg': '.mp3',
    'audio/mp4': '.m4a',
    'audio/mp3': '.mp3',
    'audio/x-m4a': '.m4a',
    'audio/wav': '.wav',
    'audio/webm': '.webm',
    'audio/opus': '.ogg',
}

_BUILTIN_RESPONSE_CACHE = {
    'hello': [
        "Hello. I'm here to help with workplace safety questions. What would you like to know?",
        "Hello. I'm your workplace safety assistant. What safety or compliance question can I help with?",
        "Hello. Ask me any safety or compliance question from your company documents.",
    ],
    'hi': [
        "Hi. How can I help you with workplace safety today?",
        "Hi. I can answer safety procedures and compliance questions. What do you need?",
        "Hi. What safety topic can I help you with?",
    ],
    'hey': [
        "Hello. What safety question can I help you with?",
        "Hi. I'm here for safety and compliance questions. How can I assist?",
    ],
    'good morning': [
        "Good morning. Stay safe today. What safety question can I help with?",
        "Good morning. How can I assist you with workplace safety this morning?",
    ],
    'good afternoon': [
        "Good afternoon. What safety question can I help with?",
        "Good afternoon. I'm here for safety and compliance. What do you need?",
    ],
    'good evening': [
        "Good evening. What safety question can I help with?",
        "Good evening. Ask me anything about workplace safety from your documents.",
    ],
    'how are you': [
        "I'm here to help with safety questions. What do you need today?",
        "Ready to assist with safety and compliance. What can I help you with?",
    ],
    'what can you do': [
        "I use your company safety documents to answer questions on procedures, PPE, hazard controls, and compliance. What would you like to know?",
        "I answer safety and compliance questions from your uploaded docs — procedures, PPE, lockout/tagout, confined space, electrical safety. What do you need?",
    ],
    'what do you do': [
        "I use your company safety documents to answer questions on procedures, PPE, hazard controls, and compliance. What would you like to know?",
        "I answer safety and compliance questions from your uploaded docs — procedures, PPE, lockout/tagout, confined space, electrical safety. What do you need?",
    ],
    'who are you': [
        "I'm SafeGuardAI, your workplace safety assistant. I answer questions using your company's safety documents. How can I help you?",
        "SafeGuardAI — I use your company documents to answer safety and compliance questions. What can I help with?",
    ],
    'what kind of things can you help with': [
        "Anything in our safety docs. Ask about a specific task — for example electrical work, PPE, or confined space — and I'll give you the details.",
        "Go ahead and ask. If it's in our procedures or PPE guides, I'll pull the answer.",
    ],
    'ready to ask': [
        "Go ahead. Ask about a procedure, PPE, or any safety topic and I'll pull the details.",
        "Yes. What do you need to know?",
    ],
    'can i ask you a specific question': [
        "Yes. Go ahead — ask about a procedure, PPE, or any safety topic and I'll pull the details.",
        "Of course. What do you need to know?",
    ],
    'thank you': [
        "You're welcome. Contact me again whenever you have another safety question.",
        "You're welcome. Stay safe, and ask anytime you need guidance.",
        "You're welcome. I'm here whenever you have more questions.",
    ],
    'thanks': [
        "You're welcome. Anything else you need, just ask.",
        "You're welcome. Stay safe. I'm here if you have further questions.",
        "You're welcome. Let me know if you need anything else.",
    ],
    'thank you so much': [
        "You're welcome. Stay safe, and reach out whenever you need assistance.",
        "You're welcome. Take care, and ask again anytime.",
    ],
    'appreciate it': [
        "You're welcome. Stay safe. I'm here if you need anything else.",
        "You're welcome. Let me know if another question comes up.",
    ],
    'great': [
        "Good to hear. If you have another safety question, just ask.",
        "Understood. Stay safe, and I'm here if you need more help.",
    ],
    'awesome': [
        "Good to hear. Stay safe. I'm here for any follow-up questions.",
        "Understood. If you need anything else, ask anytime.",
    ],
    'perfect': [
        "Understood. Stay safe. I'm here if you need anything else.",
        "Good to hear. Let me know if you have further questions.",
    ],
    'ok': [
        "Understood. Let me know if you need anything else.",
        "Understood. I'm here if you have more questions.",
    ],
    'okay': [
        "Understood. Anything else I can help with?",
        "Understood. Stay safe. Ask again whenever you need.",
    ],
    'got it': [
        "Understood. Stay safe. I'm here if you need more.",
        "Understood. Let me know if you have another question.",
    ],
    "that's all i needed, thanks": [
        "You're welcome. Stay safe, and ask anytime you need guidance.",
        "Glad I could help. Come back whenever you have another question.",
    ],
    "thanks, that was helpful": [
        "You're welcome. Stay safe. I'm here if you need anything else.",
        "Glad it helped. Ask again whenever you need.",
    ],
    'understood': [
        "Understood. Stay safe. I'm here if you need more details.",
        "Understood. Stay safe. I'm here for follow-up questions.",
    ],
    'bye': [
        "Stay safe. Come back anytime you have a safety question.",
        "Take care. I'm here whenever you need safety guidance.",
    ],
    "that's all for now, bye": [
        "Stay safe. Come back anytime you have a safety question.",
        "Take care. I'm here whenever you need safety guidance.",
    ],
    'take care': [
        "You too. Stay safe, and ask again whenever you need.",
        "Take care. I'm here whenever you need safety guidance.",
    ],
    'goodbye': [
        "Goodbye. Stay safe on the job.",
        "Goodbye. Take care, and ask again anytime.",
    ],
    'good night': [
        "Good night. Stay safe.",
        "Good night. Rest well. I'm here when you need me.",
    ],
}


_loaded_response_cache = None


def _get_response_cache():
    global _loaded_response_cache
    if _loaded_response_cache is not None:
        return _loaded_response_cache

    path = settings.SAFEGUARDAI['RESPONSE_CACHE_PATH']
    if path and os.path.isfile(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                _loaded_response_cache = json.load(f)
                return _loaded_response_cache
        except Exception as e:
            logger.warning(f"Could not load response cache from {path}: {e}")

    _loaded_response_cache = _BUILTIN_RESPONSE_CACHE
    return _loaded_response_cache


def _get_safety_keywords():
    kw = settings.SAFEGUARDAI['SAFETY_KEYWORDS']
    if kw is not None:
        return list(kw)
    return [
        'safety', 'hazard', 'procedure', 'steps', 'required', 'emergency',
        'equipment', 'inspection', 'permit', 'compliance', 'regulation',
        'ppe', 'gloves', 'voltage', 'electrical', 'lockout', 'tagout', 'loto',
        'confined space', 'arc flash', 'injury', 'testing', 'rescue',
        'atmospheric', 'boundary', 'document', 'policy', 'control',
    ]


def _get_general_keywords():
    return list(_get_response_cache().keys()) + [
        'help', 'start', 'well done', 'good job',
        'what can you help', 'how can you help',
    ]


def classify_message(message: str) -> str:
    message_lower = message.lower().strip()
    response_cache = _get_response_cache()
    safety_keywords = _get_safety_keywords()
    general_keywords = _get_general_keywords()

    if message_lower in response_cache:
        return 'cached'

    for keyword in safety_keywords:
        if keyword in message_lower:
            return 'safety'

    for keyword in general_keywords:
        if keyword in message_lower:
            return 'general'

    if len(message_lower.split()) <= 3:
        return 'general'

    return 'safety'


def handle_general_message(message: str) -> str:
    fallback = settings.SAFEGUARDAI['GENERAL_FALLBACK_MESSAGE']
    if not openai_client:
        return fallback

    max_chars = settings.SAFEGUARDAI['GENERAL_RESPONSE_MAX_CHARS']
    model = settings.SAFEGUARDAI['OPENAI_MODEL']
    system_prompt = f"""You are SafeGuardAI, a workplace safety assistant on WhatsApp.

STRICT RULES:
- Plain text only — no asterisks, no markdown, no emojis.
- Maximum {max_chars} characters total.
- One or two sentences maximum.
- Natural and human — not robotic.
- Never repeat the same phrasing twice.
- End with a brief offer to help if appropriate.

For greetings: warm, brief, invite a safety question.
For appreciation: acknowledge, offer more help.
For closings: warm safety-focused farewell.
For capability questions: briefly mention safety procedures, hazard controls, and company documents."""

    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user',   'content': message},
            ],
            temperature=0.8,
            max_tokens=80,
        )
        text = (response.choices[0].message.content or '').strip()
        if not text:
            return fallback
        if len(text) > max_chars:
            text = text[:max_chars].rsplit(' ', 1)[0]
            if not text.endswith(('.', '!', '?')):
                text += '.'
        return text
    except Exception as e:
        logger.error(f"General handler error: {e}")
        return fallback


def _init_twilio() -> Client:
    try:
        return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    except Exception as e:
        logger.error(f"Failed to initialise Twilio client: {e}")
        return None


twilio_client = _init_twilio()
twilio_number = settings.TWILIO_WHATSAPP_NUMBER


def _extension_for_media(content_type: str | None) -> str:
    if not content_type:
        return '.ogg'
    ct = content_type.split(';')[0].strip().lower()
    return AUDIO_EXTENSION_MAP.get(ct, '.ogg')


def download_twilio_media(media_url: str, content_type: str | None = None) -> str | None:
    sid = settings.TWILIO_ACCOUNT_SID
    token = settings.TWILIO_AUTH_TOKEN
    if not sid or not token:
        logger.error("download_twilio_media: Missing Twilio credentials in settings")
        return None

    ext = _extension_for_media(content_type)
    media_root = settings.MEDIA_ROOT
    voice_dir = os.path.join(media_root, 'voice')
    os.makedirs(voice_dir, exist_ok=True)
    path = os.path.join(voice_dir, f"{uuid.uuid4().hex}{ext}")

    try:
        resp = requests.get(
            media_url,
            auth=HTTPBasicAuth(sid, token),
            timeout=30,
        )
        resp.raise_for_status()
        with open(path, 'wb') as f:
            f.write(resp.content)
        logger.info(f"download_twilio_media: Saved | path={path} | size={len(resp.content)}")
        return path
    except Exception as e:
        logger.error(f"download_twilio_media: Failed | url={media_url[:60]} | error={e}")
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
        return None


def fetch_and_transcribe_voice(media_url: str, content_type: str | None = None) -> tuple[str | None, str]:
    path = download_twilio_media(media_url, content_type)
    if not path:
        return None, "Could not download voice message. Please try again or send a text message."

    try:
        transcript = transcribe_audio_file(path)
        if not transcript:
            return None, "Voice message could not be understood. Please try again or send a text message."
        return transcript, ""
    finally:
        try:
            os.remove(path)
        except OSError as e:
            logger.warning(f"fetch_and_transcribe_voice: Could not delete temp file | path={path} | error={e}")


def send_whatsapp_message(to_number: str, message: str, media_url: str | None = None) -> dict:
    if not twilio_client:
        logger.error("Cannot send — Twilio client not initialised")
        return {'status': 'failed', 'error': 'Twilio client not initialised'}

    max_len = settings.SAFEGUARDAI['MAX_WHATSAPP_MESSAGE_LENGTH']
    image_caption_fallback = settings.SAFEGUARDAI['IMAGE_CAPTION_FALLBACK']
    if len(message) > max_len:
        message = message[: max_len - 3].rsplit(' ', 1)[0]
        if not message.endswith(('.', '!', '?')):
            message += '.'
        logger.warning(f"Outgoing message truncated to {max_len} chars before send")

    if not to_number.startswith('whatsapp:'):
        to_number = f'whatsapp:{to_number}'

    kwargs = {
        'from_': twilio_number,
        'to': to_number,
        'body': message or None,
    }
    if media_url:
        kwargs['media_url'] = [media_url]
        if not message:
            kwargs['body'] = image_caption_fallback

    try:
        msg = twilio_client.messages.create(**kwargs)
        logger.info(
            f"Message sent | to={to_number} | sid={msg.sid}"
            + (" | with media" if media_url else "")
        )
        return {'status': 'sent', 'message_sid': msg.sid, 'to': to_number}
    except Exception as e:
        error_str = str(e)
        if media_url:
            logger.warning(
                f"Send with media failed (fallback to text) | to={to_number} | error={error_str[:80]}"
            )
            try:
                caption = message or image_caption_fallback
                msg = twilio_client.messages.create(
                    from_=twilio_number,
                    body=caption,
                    to=to_number,
                )
                logger.info(f"Fallback text message sent | sid={msg.sid}")
                return {'status': 'sent', 'message_sid': msg.sid, 'to': to_number}
            except Exception as e2:
                error_str = str(e2)
        if '63038' in error_str or '50 daily messages limit' in error_str or (
            'exceeded' in error_str.lower() and 'limit' in error_str.lower()
        ):
            logger.warning(
                f"Send failed — Twilio daily message limit exceeded (63038) | to={to_number}. "
                "Limit resets at midnight UTC. Upgrade at console.twilio.com for higher limits."
            )
        else:
            logger.error(f"Send failed | to={to_number} | error={error_str}")
        return {'status': 'failed', 'error': error_str, 'to': to_number}


def process_incoming_message(
    from_number: str,
    message_body: str,
    is_voice: bool = False,
    *,
    skip_rate_limit: bool = False,
) -> tuple[str, str | None]:
    start_time = time.time()
    logger.info(
        f"Processing | from={from_number} | voice={is_voice} | message='{message_body[:60]}'"
    )
    error_response = (
        "Unable to process your request at the moment.\n"
        "Please try again or contact your HSE officer directly."
    )

    try:
        t0 = time.time()
        passed, result = run_security_checks(
            from_number, message_body, skip_rate_limit=skip_rate_limit
        )
        security_time = round(time.time() - t0, 3)
        if not passed:
            logger.info(f"Security rejected | time={security_time}s")
            return (result, None)
        message_body = result

        if not message_body.strip():
            logger.info("Message empty after sanitisation — skipping save")
            return ("Please send a short safety question or greeting.", None)

        user, created = User.objects.get_or_create(
            phone_number=from_number,
            defaults={'role': User.Role.WORKER},
        )
        if created:
            logger.info(f"New user | phone={from_number}")

        t1 = time.time()
        message_type = classify_message(message_body)
        message_lower = message_body.lower().strip()
        sources = []
        image_url = None

        # Shared context lookup for general follow-up detection and safety routing
        context_minutes = settings.SAFEGUARDAI['CONVERSATION_CONTEXT_MINUTES']
        since = timezone.now() - timedelta(minutes=context_minutes)
        recent_log = (
            SafetyLog.objects.filter(user=user, timestamp__gte=since)
            .order_by('-timestamp')
            .first()
        )

        if message_type == 'cached':
            variants = _get_response_cache()[message_lower]
            response_text = random.choice(variants)
            message_type = 'general'
            handler_time = round(time.time() - t1, 3)
            logger.info(f"Served from cache | handler_time={handler_time}s")

        elif message_type == 'general':
            # Don't re-route intro/capability questions to safety even after a safety conversation
            msg_normalized = message_lower.rstrip('?').strip()
            is_general_intro = msg_normalized in _get_response_cache()
            if (
                recent_log
                and '?' in message_body
                and len(message_body.strip()) <= 120
                and not is_general_intro
            ):
                message_type = 'safety'
                logger.info(
                    f"Follow-up routed to safety | recent_sources={(recent_log.sources or '')[:50]}"
                )
            else:
                if is_general_intro:
                    response_text = random.choice(_get_response_cache()[msg_normalized])
                else:
                    response_text = handle_general_message(message_body)
                handler_time = round(time.time() - t1, 3)
                logger.info(f"General reply | handler_time={handler_time}s")

        if message_type == 'safety':
            conversation_sources = []
            if recent_log and recent_log.sources:
                conversation_sources = [s.strip() for s in recent_log.sources.split(',') if s.strip()]
            result = process_safety_query(message_body, conversation_sources=conversation_sources)
            response_text = result['answer']
            sources = result.get('sources', [])
            image_url = result.get('image_url')
            handler_time = round(time.time() - t1, 3)

            sources_str = ', '.join(sources)
            if len(sources_str) > 500:
                sources_str = sources_str[:497] + '...'

            SafetyLog.objects.create(
                user=user,
                task_description=message_body[:500],
                safety_check=f"Answered using AI agents: {sources_str[:500]}",
                sources=sources_str[:500],
            )
            logger.info(
                f"Safety log created | sources={sources} | handler_time={handler_time}s"
                + (f" | image_url={bool(image_url)}" if image_url else "")
            )

        conversation = Conversation.objects.create(
            user=user,
            message=message_body,
            response=response_text,
            message_type=Conversation.MessageType.VOICE if is_voice else Conversation.MessageType.TEXT,
            response_included_image=bool(image_url),
        )

        total_time = round(time.time() - start_time, 2)
        logger.info(
            f"Done | id={conversation.id} | type={message_type} | "
            f"total_time={total_time}s | security={security_time}s | "
            f"length={len(response_text)} chars"
        )
        return (response_text, image_url)

    except Exception:
        total_time = round(time.time() - start_time, 2)
        logger.exception("Error | from=%s | total_time=%ss", from_number, total_time)
        try:
            user = User.objects.filter(phone_number=from_number).first()
            if user:
                Conversation.objects.create(
                    user=user,
                    message=message_body[:5000] if message_body else "(error before message set)",
                    response=error_response,
                    message_type=Conversation.MessageType.TEXT,
                )
                logger.info("Saved failure conversation for audit")
        except Exception as save_err:
            logger.warning(f"Could not save failure conversation: {save_err}")
        return (error_response, None)
