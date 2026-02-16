# SafeGuardAI

> An AI-powered workplace safety assistant for WhatsApp. Workers send safety questions via text or voice, and the system searches company documents to provide accurate, source-attributed answers with optional visual guides.

---

## Features

- **Document-Based Answers** - RAG searches uploaded safety manuals to ensure responses come from approved documentation
- **Multi-Modal Input** - Text messages and voice notes (auto-transcribed with Whisper)
- **Visual Safety Guides** - DALL-E 3 generates photorealistic safety images on request
- **Adaptive Responses** - Answer length adjusts based on query complexity (400-1250 characters)
- **HSE Dashboard** - Document management, analytics, and conversation monitoring
- **WhatsApp Integration** - No app installation required for workers

---

## Prerequisites

- Python 3.10+
- PostgreSQL 12+
- Node.js 16+ (for CrewAI tools)
- Twilio account with WhatsApp sandbox
- OpenAI API key

---

## Quick Start

```bash
git clone https://github.com/sanaabuzaid/safeguardai.git
cd safeguardai
python -m venv safeguardai-env
source safeguardai-env/bin/activate  # Windows: safeguardai-env\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                  # Add your API keys
```

**Set up PostgreSQL database:**
```bash
# Create user with password
createuser -P safeguardai_user  # Enter password when prompted

# Create database owned by user
createdb -O safeguardai_user safeguardai_db
```

**Run migrations and create admin:**
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://localhost:8000/api/dashboard/`

---

## Running the Application

### 1. Start the Django Server

**Development server:**
```bash
python manage.py runserver
```

The server will start at:
- **Dashboard:** `http://localhost:8000/api/dashboard/`
- **Django Admin:** `http://localhost:8000/admin/`
- **API Health Check:** `http://localhost:8000/api/webhook/status/`

**Production server (Gunicorn):**
```bash
gunicorn backend.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

### 2. Access the Dashboard

1. Open browser: `http://localhost:8000/api/dashboard/`
2. Login with your superuser credentials (created in Quick Start)
3. Upload safety documents (.txt files only)
4. View conversations, analytics, and logs

### 3. Upload Your First Safety Document

**Before testing WhatsApp, you MUST upload at least one document:**

1. Click "Upload Document" button in dashboard
2. Enter a clear title (e.g., "Welding Safety Procedures")
3. Select a .txt file (UTF-8 encoded, plain text only)
4. Click "Upload" and wait for confirmation
5. Verify in dashboard: "X chunks" should be greater than 0
6. Check "Safety guides" table shows your document

**Document requirements:**
- **Format:** Plain text (.txt) only - no PDF, DOCX, or scanned images
- **Encoding:** UTF-8 (avoid special characters or smart quotes)
- **Structure:** Use headings and numbered lists for best results
- **Size:** Keep procedures focused (one topic per document recommended)

**Example good document format:**
```
# Welding Safety Procedure

## Required PPE
- Welding helmet with shade 10-13 lens
- Leather gloves and apron
- Safety boots with metatarsal protection

## Pre-welding Inspection
1. Check equipment for damage
2. Ensure adequate ventilation
3. Clear combustible materials within 35 feet
```

---

## Setting Up WhatsApp Integration

To receive WhatsApp messages during development, expose your local server using ngrok:

### Step 1: Install ngrok

**Download and install ngrok:**

```bash
# macOS
brew install ngrok

# Linux
sudo snap install ngrok

# Windows (Chocolatey)
choco install ngrok

# Or download directly from: https://ngrok.com/download
```

### Step 2: Start Your Django Server

In your **first terminal**, make sure Django is running:

```bash
python manage.py runserver
```

Keep this terminal open.

### Step 3: Start ngrok

In a **second terminal**, start ngrok:

```bash
ngrok http 8000
```

You'll see output like:
```
Forwarding   https://abc123-def456.ngrok.io -> http://localhost:8000
```

**Copy the HTTPS URL** (e.g., `https://abc123-def456.ngrok.io`)

### Step 4: Configure Twilio Webhook

1. Go to Twilio Console: https://console.twilio.com/
2. Navigate to: **Messaging** → **Try it out** → **Send a WhatsApp message**
3. Scroll to **Sandbox settings**
4. In the "When a message comes in" field, paste:
   ```
   https://abc123-def456.ngrok.io/api/webhook/whatsapp/
   ```
   (Replace `abc123-def456` with your actual ngrok URL)
5. Click **Save**

### Step 5: Test WhatsApp Integration

1. **Join the sandbox:** Send the join code to your Twilio WhatsApp number
   - Example: Send `join safety-test` to `+1 415 523 8886`
2. **Ask a safety question:**
   - Send: "What PPE do I need for welding?"
3. **Check your terminals:**
   - Django terminal: See webhook received
   - ngrok terminal: See HTTP POST request
4. **Receive response** via WhatsApp with safety guidance

### Step 6: Test Without WhatsApp (Optional)

**DEBUG mode only** - test the system without Twilio:

```bash
curl -X POST http://localhost:8000/api/webhook/test/ \
  -H "Content-Type: application/json" \
  -d '{"from": "whatsapp:+1234567890", "message": "What PPE for welding?"}'
```

Response will be returned as JSON instead of sent via WhatsApp.

### ngrok Tips

- **Keep both terminals open** - Django server AND ngrok must run simultaneously
- **URL changes on restart** - ngrok generates a new URL each time (update Twilio webhook)
- **View requests:** ngrok dashboard at `http://localhost:4040` shows all traffic
- **Paid account:** Get permanent URLs with ngrok paid plan

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Django secret key | Yes |
| `DEBUG` | Debug mode (False in production) | Yes |
| `ALLOWED_HOSTS` | Comma-separated hostnames | Yes |
| `DB_ENGINE` | Database backend | Yes |
| `DB_NAME` | PostgreSQL database name | Yes |
| `DB_USER` | Database username | Yes |
| `DB_PASSWORD` | Database password | Yes |
| `DB_HOST` | Database host (localhost) | Yes |
| `DB_PORT` | Database port (5432) | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `TWILIO_ACCOUNT_SID` | Twilio account ID | Yes |
| `TWILIO_AUTH_TOKEN` | Twilio auth token | Yes |
| `TWILIO_WHATSAPP_NUMBER` | Twilio WhatsApp number | Yes |

**Example .env file:**
```bash
SECRET_KEY=django-insecure-your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_ENGINE=django.db.backends.postgresql
DB_NAME=safeguardai_db
DB_USER=safeguardai_user
DB_PASSWORD=your-secure-password
DB_HOST=localhost
DB_PORT=5432
OPENAI_API_KEY=sk-proj-your-openai-key-here
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

**Important notes:**
- Do NOT use quotes around values in .env file
- Keep .env file secure and never commit to Git
- OpenAI API key must have access to GPT-4, Whisper, DALL-E 3, and Embeddings

---

## Data Storage

SafeGuardAI stores data in multiple locations:

| Data Type | Location | Persistent | Notes |
|-----------|----------|------------|-------|
| Conversations | PostgreSQL | Yes | Full audit trail |
| Safety logs | PostgreSQL | Yes | Query tracking |
| Documents | `media/documents/safety_manuals/` | Yes | Original .txt files |
| Vector embeddings | `data/chroma/` | Yes | ChromaDB vector store |
| Voice files | `media/voice/` | No | Auto-deleted after transcription |
| Generated images | External URLs | No | DALL-E URLs expire ~2 hours |

**Backup strategy:**
- PostgreSQL: Use `pg_dump` for conversation/log backups
- ChromaDB: Include `data/chroma/` directory in backups
- Documents: Include `media/documents/` in backups

---

## Project Structure

```
safeguardai/
├── backend/              # Django settings and configuration
│   ├── settings.py       # Main settings with SAFEGUARDAI config
│   ├── urls.py           # Root URL configuration
│   ├── wsgi.py           # WSGI entry point
│   └── asgi.py           # ASGI entry point
├── safety/               # Main application
│   ├── models.py         # User, Document, Conversation, SafetyLog
│   ├── views.py          # WhatsApp webhook handlers
│   ├── viewsets.py       # REST API endpoints
│   ├── serializers.py    # DRF serializers
│   ├── security.py       # Rate limiting and validation
│   ├── whatsapp_integration.py  # Message processing
│   └── ai_utils/         # AI components
│       ├── agents.py     # CrewAI agents (Researcher + Formatter)
│       ├── rag_system.py # ChromaDB vector search
│       └── tools.py      # Whisper, DALL-E tools
├── dashboard/            # HSE web interface
│   ├── static/           # CSS and JavaScript
│   └── index.html        # Dashboard template
├── data/                 # Created at runtime
│   └── chroma/           # ChromaDB vector store
├── media/                # Created at runtime
│   ├── documents/        # Uploaded safety documents
│   └── voice/            # Temporary voice files
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variables template
└── manage.py             # Django management script
```

---

## API Endpoints

### Webhook Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/webhook/whatsapp/` | POST | Twilio webhook for incoming WhatsApp messages |
| `/api/webhook/test/` | POST | Test endpoint (DEBUG only, bypasses Twilio) |
| `/api/webhook/status/` | GET | System health check (DB, RAG, chunks count) |

### Dashboard & Analytics

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboard/` | GET | Dashboard web interface (HTML) |
| `/api/analytics/summary/` | GET | Dashboard stats (conversations, users, documents) |

### Conversations (Read-Only)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/conversations/` | GET | List all conversations (paginated, filterable) |
| `/api/conversations/{id}/` | GET | Retrieve single conversation by ID |

**Query parameters:**
- `?search=query` - Search in message/response text
- `?message_type=text|voice|image` - Filter by type
- `?start_date=YYYY-MM-DD` - Filter by date range
- `?end_date=YYYY-MM-DD` - Filter by date range
- `?page_size=N` - Results per page (max 200)

### Safety Logs (Read-Only)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/safety-logs/` | GET | List all safety query logs (paginated, filterable) |
| `/api/safety-logs/{id}/` | GET | Retrieve single safety log by ID |

**Query parameters:**
- `?search=query` - Search in task description
- `?source=document_title` - Filter by source document
- `?start_date=YYYY-MM-DD` - Filter by date range
- `?end_date=YYYY-MM-DD` - Filter by date range
- `?page_size=N` - Results per page (max 200)

### Documents (Full CRUD)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/documents/` | GET | List all documents |
| `/api/documents/{id}/` | GET | Retrieve single document by ID |
| `/api/documents/` | POST | Create document (use `/upload/` instead) |
| `/api/documents/{id}/` | PUT | Update document metadata |
| `/api/documents/{id}/` | PATCH | Partially update document |
| `/api/documents/{id}/` | DELETE | Delete document and file |
| `/api/documents/upload/` | POST | Upload .txt file and auto-index in RAG |
| `/api/documents/{id}/reindex/` | POST | Re-index document after editing file |

**Upload request format (multipart/form-data):**
```
title: "PPE Guidelines"
file: safety_ppe.txt
```

### Admin Panel

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/` | GET | Django admin interface (superuser only) |

---

**Authentication:**
- **Webhook endpoints:** Twilio signature validation (disabled in DEBUG mode)
- **Dashboard/API endpoints:** Django session authentication (login required)
- **Admin panel:** Django superuser authentication

---

## Tech Stack

**Why These Technologies?**

### Backend Framework
- **Django 6.0.2** - Robust web framework with built-in security, ORM, and admin interface for rapid development
- **Django REST Framework 3.16.1** - Professional API development with serialization, pagination, and viewsets
- **PostgreSQL** - Reliable relational database for audit trails, user management, and transactional data

### Vector Search & RAG
- **ChromaDB 1.1.1** - Lightweight vector database with HNSW indexing for fast semantic search
  - *Why:* No separate server needed, persists to disk, perfect for document-based RAG
  - *Alternative considered:* Pinecone (requires paid cloud service)

### AI Models (OpenAI)
- **GPT-4o-mini** - Fast, cost-effective model for chat completions
  - *Why:* 128K context window, good reasoning, 60% cheaper than GPT-4
  - *Use case:* Generating safety responses (simple queries ~3-5s, complex ~10-15s)

- **text-embedding-3-small** - Compact embedding model (1536 dimensions)
  - *Why:* 5x cheaper than text-embedding-3-large with minimal quality loss
  - *Use case:* Indexing safety document chunks for semantic search

- **Whisper-1** - Speech-to-text model
  - *Why:* Supports 8 audio formats, robust to accents and background noise
  - *Use case:* Transcribing worker voice notes for hands-free operation

- **DALL-E 3** - Image generation model
  - *Why:* Photorealistic outputs, safety instruction visualization
  - *Use case:* Generating visual safety guides when workers request images

### Multi-Agent Framework
- **CrewAI 1.9.3** - Orchestrates specialized AI agents
  - *Why:* Sequential task pipeline (Research → Format) produces better structured responses
  - *Agent 1 (Researcher):* Extracts facts from documents, validates completeness
  - *Agent 2 (Formatter):* Formats for WhatsApp, enforces length limits, handles images
  - *Alternative considered:* LangChain (more complex, overkill for 2-agent system)

### Communication
- **Twilio WhatsApp API** - Enterprise-grade messaging platform
  - *Why:* No worker app installation, familiar interface, 2 billion+ WhatsApp users
  - *Features:* Voice note support, media delivery, webhook reliability

### Frontend
- **Vanilla JavaScript** - No framework overhead for simple dashboard
  - *Why:* Fast loading, no build process, adequate for admin-only interface
- **Tabler UI 1.4.0** - Clean, professional admin template
- **Chart.js 4.4.0** - Simple charts for usage analytics

### Infrastructure
- **Python 3.10+** - Modern Python with type hints and performance improvements
- **Node.js 16+** - Required by CrewAI tools for JavaScript-based utilities

---

## Troubleshooting

### "This isn't in our safety documents" Response

**Cause:** Document not uploaded, not indexed, or doesn't contain relevant information.

**Fix:**
1. Check dashboard shows document in "Safety guides" table
2. Verify "chunks" count is greater than 0
3. Check `/api/webhook/status/` shows document in `indexed_sources`
4. Ensure question matches document content (system only searches uploaded docs)
5. Try re-uploading with "Update in system" button if file was edited

---

### No RAG Results / Empty Search

**Cause:** ChromaDB not initialized or embeddings failed.

**Fix:**
1. Check `OPENAI_API_KEY` in .env (no quotes, no extra spaces)
2. Verify OpenAI API has sufficient credits
3. Check Django logs for "Embedding generation failed" errors
4. Delete `data/chroma/` and re-upload documents to rebuild index
5. Confirm `data/chroma/` directory exists and has write permissions

---

### Voice Notes Not Transcribing

**Cause:** Unsupported format or Twilio media download failed.

**Fix:**
1. Supported formats: MP3, M4A, OGG, WAV, WEBM
2. Check Django logs for "transcribe_audio_file" errors
3. Verify Twilio credentials in .env are correct
4. Check `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` match console
5. Ensure server can reach Twilio's media URLs (check firewall)

**Note:** Voice files are automatically deleted after transcription (not stored long-term).

---

### Images Not Generating

**Cause:** Missing trigger phrase or DALL-E API error.

**Fix:**
1. Use explicit trigger phrases: "show me", "picture", "photo", "image of", "draw", "illustrate"
2. Example: "Show me a picture of PPE for welding"
3. Check OpenAI API has DALL-E 3 access enabled
4. Check Django logs for "SafetyImageTool" errors
5. Image URLs expire after ~2 hours (temporary links only)

---

### "Message Limit Exceeded" Error

**Cause:** Rate limiting (20 messages per hour per worker).

**Fix:**
1. Wait 60 minutes for rate limit to reset
2. For urgent queries, contact HSE officer directly
3. Adjust limit in `safety/security.py` if needed:
   ```python
   MAX_REQUESTS_PER_HOUR = 20  # Change this value
   ```

---

### Webhook Not Receiving Messages

**Cause:** ngrok not running, wrong URL, or Twilio misconfiguration.

**Fix:**
1. Verify ngrok is running in separate terminal
2. Check ngrok dashboard: `http://localhost:4040` for incoming requests
3. Confirm Twilio webhook URL matches current ngrok URL (changes on restart)
4. Check Django server logs for webhook POST requests
5. Verify Twilio sandbox is active and join code was sent
6. Test with `/api/webhook/test/` endpoint to isolate Twilio issues

---

### Documents Not Indexing

**Cause:** Wrong file format, encoding issues, or OpenAI API error.

**Fix:**
1. Only .txt files supported (no PDF, DOCX, or scanned images)
2. Ensure file is UTF-8 encoded (not UTF-16, ASCII, or other)
3. Remove special characters, smart quotes, or non-printable characters
4. Check dashboard for "chunks added" confirmation after upload
5. Check Django logs for "Failed to index chunk" or "Embedding generation failed"
6. Verify `OPENAI_API_KEY` has embeddings API access

---

### Slow Response Times

**Expected response times:**
- Simple queries: 5-10 seconds
- Medium queries: 10-15 seconds  
- Complex queries: 15-25 seconds
- With image generation: Add 5-10 seconds

**If slower than expected:**
1. Check OpenAI API status: https://status.openai.com
2. Verify server has good internet connection
3. Check ChromaDB index size (very large = slower searches)
4. Consider upgrading to faster OpenAI models in settings

---

### Database Connection Errors

**Cause:** PostgreSQL not running or wrong credentials.

**Fix:**
1. Verify PostgreSQL is running: `pg_isready`
2. Check database exists: `psql -l | grep safeguardai_db`
3. Test credentials: `psql -U safeguardai_user -d safeguardai_db`
4. Verify .env values match PostgreSQL setup
5. Check PostgreSQL logs for connection errors

---

## Production Deployment

**Before deploying to production:**

### 1. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

Static files will be collected to `staticfiles/` directory.

### 2. Configure Environment Variables

```bash
# Critical production settings
export DEBUG=False
export SECRET_KEY='your-strong-random-secret-key-here'
export ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

### 3. Use Production WSGI Server

```bash
# Install Gunicorn
pip install gunicorn

# Run with multiple workers
gunicorn backend.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

### 4. Security Checklist

- [ ] Set `DEBUG=False` in production
- [ ] Use strong, randomly generated `SECRET_KEY`
- [ ] Configure HTTPS (required for Twilio webhooks in production)
- [ ] Set proper `ALLOWED_HOSTS` (no wildcards)
- [ ] Use environment variables for all secrets (never hardcode)
- [ ] Enable PostgreSQL authentication and SSL
- [ ] Configure firewall rules (allow only port 443/80)
- [ ] Set up regular database backups
- [ ] Back up `data/chroma/` directory regularly
- [ ] Monitor error logs and set up alerts
- [ ] Rate limit at nginx/load balancer level
- [ ] Use process manager (systemd, supervisor) to keep Gunicorn running

### 5. Twilio Webhook Configuration

**Production webhook URL must use HTTPS:**
```
https://yourdomain.com/api/webhook/whatsapp/
```

Twilio requires valid SSL certificate (ngrok not suitable for production).

### 6. Recommended Production Setup

```
Internet → Nginx (HTTPS, static files) → Gunicorn (Django) → PostgreSQL
                                       ↘ ChromaDB (local)
```

**Nginx configuration example:**
```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /static/ {
        alias /path/to/safeguardai/staticfiles/;
    }

    location /media/ {
        alias /path/to/safeguardai/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## License

MIT License - See LICENSE file for details.

---

## Author

**Sana Abu Zaid**

GitHub: [@sanaabuzaid](https://github.com/sanaabuzaid)
Email: sanaabuzaid02@gmail.com

---

## Acknowledgments

Built with Django, OpenAI, CrewAI, Twilio, and ChromaDB.

---

<div align="center">

© 2026 Sana Abu Zaid. All rights reserved.

</div>
