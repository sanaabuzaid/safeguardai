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
# Create database and user
createdb safeguardai_db
createuser safeguardai_user

# Grant privileges (run in psql)
psql -c "GRANT ALL PRIVILEGES ON DATABASE safeguardai_db TO safeguardai_user;"
```

**Run migrations and create admin:**
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://localhost:8000/dashboard/`

---

## Running the Application

### 1. Start the Django Server

**Development server:**
```bash
python manage.py runserver
```

The server will start at:
- **Dashboard:** `http://localhost:8000/dashboard/`
- **Django Admin:** `http://localhost:8000/admin/`
- **API Health Check:** `http://localhost:8000/api/webhook/status/`

**Production server (Gunicorn):**
```bash
gunicorn backend.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

### 2. Access the Dashboard

1. Open browser: `http://localhost:8000/dashboard/`
2. Login with your superuser credentials (created in Quick Start)
3. Upload safety documents (.txt files only)
4. View conversations, analytics, and logs

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
SECRET_KEY=django-insecure-your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_ENGINE=django.db.backends.postgresql
DB_NAME=safeguardai_db
DB_USER=safeguardai_user
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432
OPENAI_API_KEY=sk-proj-your-key
TWILIO_ACCOUNT_SID=ACxxxxxxxx
TWILIO_AUTH_TOKEN=your-token
TWILIO_WHATSAPP_NUMBER=whatsapp:+1234567890
```

---

## Project Structure

```
safeguardai/
├── backend/              # Django settings and configuration
├── safety/               # Main application
│   ├── models.py         # User, Document, Conversation, SafetyLog
│   ├── views.py          # WhatsApp webhook handlers
│   ├── viewsets.py       # REST API endpoints
│   ├── security.py       # Rate limiting and validation
│   ├── whatsapp_integration.py  # Message processing
│   └── ai_utils/         # AI components
│       ├── agents.py     # CrewAI agents (Researcher + Formatter)
│       ├── rag_system.py # ChromaDB vector search
│       └── tools.py      # Whisper, DALL-E tools
├── dashboard/            # HSE web interface
└── requirements.txt      # Dependencies
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/webhook/whatsapp/` | POST | Twilio webhook |
| `/api/webhook/test/` | POST | Test endpoint (DEBUG only) |
| `/api/conversations/` | GET | List conversations |
| `/api/safety-logs/` | GET | List safety queries |
| `/api/documents/` | GET | List documents |
| `/api/documents/upload/` | POST | Upload document |
| `/api/analytics/summary/` | GET | Dashboard stats |

---

## Tech Stack

- Django 6.0.2 + Django REST Framework
- PostgreSQL (database)
- ChromaDB (vector search)
- OpenAI GPT-4o-mini (responses)
- CrewAI (multi-agent orchestration)
- DALL-E 3 (image generation)
- Whisper (voice transcription)
- Twilio WhatsApp API
- Tabler + Chart.js (dashboard)

---

## Troubleshooting

**No RAG results:**
- Verify documents uploaded via dashboard
- Check `OPENAI_API_KEY` in .env

**Voice not transcribing:**
- Supported: mp3, m4a, ogg, wav, webm

**Images not generating:**
- Use trigger phrases: "show me", "picture", "photo"

---

## License

MIT License - See LICENSE file for details.

---

## Author

**Sana Abu Zaid**

GitHub: [@sanaabuzaid](https://github.com/sanaabuzaid)

---

## Acknowledgments

Built with Django, OpenAI, CrewAI, Twilio, and ChromaDB.

---

<div align="center">

© 2026 Sana Abu Zaid. All rights reserved.

</div>
