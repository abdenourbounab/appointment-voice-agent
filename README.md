# appointment-voice-agent

Agent vocal de prise de rendez-vous basé sur LiveKit + Flask + MySQL

## Structure

```
appointment-voice-agent/
├── api/
│   ├── __init__.py
│   ├── db.py        # Instance SQLAlchemy
│   ├── models.py    # Modèle CallRecord
│   └── app.py       # Flask app — POST /end-of-call
├── agent/
│   └── agent.py     # LiveKit Agent (AgentSession v1.x)
├── .env.example
├── requirements.txt
└── README.md
```

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Copie `.env.example` en `.env` et remplis les valeurs :

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `LIVEKIT_URL` | URL WSS de ton serveur LiveKit |
| `LIVEKIT_API_KEY` | Clé API LiveKit |
| `LIVEKIT_API_SECRET` | Secret API LiveKit |
| `DATABASE_URL` | Connexion MySQL (`mysql+pymysql://user:pass@host:3306/db`) |
| `API_URL` | URL de l'API Flask (défaut : `http://localhost:5000`) |

## Lancer l'API Flask

```bash
flask --app api.app run
```

## Lancer l'agent LiveKit

```bash
python agent/agent.py dev
```

## Flow

1. L'agent rejoint la room LiveKit et demande la date de rendez-vous souhaitée
2. Le LLM (`openai/gpt-4.1-mini` via LiveKit Inference) extrait la date via function calling (`save_appointment_date`)
3. L'agent attend 10 secondes puis raccroche
4. Avant de quitter, il envoie un `POST /end-of-call` à l'API Flask
5. L'API persiste l'enregistrement en MySQL
