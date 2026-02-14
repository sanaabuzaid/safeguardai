from pathlib import Path

from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',')
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'safety.apps.SafetyConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'dashboard'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': config('DB_ENGINE', default='django.db.backends.postgresql'),
        'NAME': config('DB_NAME', default='safeguardai_db'),
        'USER': config('DB_USER', default='safeguardai_user'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'dashboard' / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'safety.pagination.DashboardPageNumberPagination',
    'PAGE_SIZE': 20,
}

OPENAI_API_KEY = config('OPENAI_API_KEY')

TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_NUMBER = config('TWILIO_WHATSAPP_NUMBER')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'safety': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}

SAFEGUARDAI = {
    'MAX_WHATSAPP_MESSAGE_LENGTH': 1400,
    'RAG_NUM_RESULTS': 5,
    'OPENAI_MODEL': 'gpt-4o-mini',
    'CHROMA_PERSIST_DIR': str(BASE_DIR / 'data' / 'chroma'),
    'CHROMA_COLLECTION_NAME': 'safety_documents',
    'RAG_CHUNK_SIZE': 500,
    'RAG_CHUNK_OVERLAP': 50,
    'RAG_EMBEDDING_MODEL': 'text-embedding-3-small',
    'RAG_RELEVANCE_DISTANCE_THRESHOLD': 0.45,
    'CONVERSATION_CONTEXT_MINUTES': 10,
    'DALLE_MODEL': 'dall-e-3',
    'DALLE_SIZE': '1024x1024',
    'DALLE_QUALITY': 'standard',
    'NOT_IN_DOCUMENTS_MESSAGE': (
        "This isn't in our safety documents. Please contact your HSE officer or check company communications."
    ),
    'TOPIC_REQUIRED_SOURCE_HINTS': (),
    'IMAGE_TRIGGER_PHRASES': (
        'show me', 'draw', 'picture', 'visual', 'illustrate',
        'image of', 'image for', 'figure of', 'photo',
    ),
    'IMAGE_DESCRIPTION_MAX_LENGTH': 120,
    'IMAGE_DESCRIPTION_FALLBACK': 'workplace safety equipment and procedures',
    'IMAGE_CAPTION_FALLBACK': 'Safety image (see image above).',
    'COMPLEXITY_SIMPLE_TARGET': (400, 600),
    'COMPLEXITY_MEDIUM_TARGET': (700, 900),
    'COMPLEXITY_COMPLEX_TARGET': (1000, 1250),
    'COMPLEXITY_MEDIUM_THRESHOLD': 2,
    'COMPLEXITY_COMPLEX_THRESHOLD': 5,
    'RESPONSE_CACHE_PATH': None,
    'SAFETY_KEYWORDS': None,
    'GENERAL_RESPONSE_MAX_CHARS': 200,
    'GENERAL_FALLBACK_MESSAGE': "SafeGuardAI here. Ask me any workplace safety question.",
}
