# IoT2MQTT Web Interface

Beautiful, minimal web interface for IoT2MQTT - your smart home control center.

## Features

- 🎨 **Beautiful Design** - Premium SaaS-level UI with maximum minimalism
- 🌍 **Multi-language** - English, Russian, and Chinese support
- 🌓 **Dark/Light Mode** - Automatic theme switching
- 📱 **PWA Support** - Install as mobile app
- ⚡ **Real-time Updates** - WebSocket connection for instant updates
- 🐳 **Docker Management** - Create and manage containers from UI
- 🔍 **MQTT Explorer** - Browse and interact with MQTT topics
- 📊 **Device Control** - Beautiful controls for all device types

## Quick Start

### Using Docker (Recommended)

The web interface is automatically included when you run IoT2MQTT:

```bash
docker-compose up -d
```

Access the web interface at: `http://localhost:3000`

### Development

1. **Backend Setup**
```bash
cd backend
pip install -r requirements.txt
python main.py
```

2. **Frontend Setup**
```bash
cd frontend
npm install
npm run dev
```

Access development server at: `http://localhost:5173`

## First Time Setup

1. **Access Key** - On first launch, enter any key you want to use as your password
2. **MQTT Configuration** - Configure connection to your MQTT broker
3. **Add Integrations** - Start adding your IoT devices

## Architecture

### Backend (FastAPI)
- REST API for configuration and management
- WebSocket for real-time updates
- Docker SDK for container management
- File-based configuration with locking

### Frontend (React + TypeScript)
- Vite for fast development
- Tailwind CSS for styling
- Zustand for state management
- React Query for data fetching
- Socket.IO for real-time updates

## API Documentation

When running, API documentation is available at:
- Swagger UI: `http://localhost:3000/docs`
- ReDoc: `http://localhost:3000/redoc`

## Configuration

The web interface uses the same `.env` file as IoT2MQTT:

```env
# Web Interface
WEB_PORT=3000
WEB_ACCESS_KEY=<hashed_key>

# MQTT Settings
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_BASE_TOPIC=IoT2mqtt
```

## Security

- Access key is hashed with bcrypt
- JWT tokens for session management
- Docker socket mounted read-only by default
- All passwords masked in UI
- File locking for configuration changes

## Development

### Adding New Pages

1. Create page component in `frontend/src/pages/`
2. Add route in `frontend/src/App.tsx`
3. Add menu item in `frontend/src/components/Layout.tsx`
4. Add translations in `frontend/src/i18n/locales/`

### Adding New API Endpoints

1. Create endpoint in `backend/api/`
2. Add schema in `backend/models/schemas.py`
3. Register in `backend/main.py`

### Adding New Connector Support

1. Create `setup.json` in connector directory
2. Define fields and wizard steps
3. Web UI will automatically generate forms

## Troubleshooting

### Cannot connect to Docker
- Ensure Docker socket is accessible
- Check permissions on `/var/run/docker.sock`

### MQTT connection fails
- Verify MQTT broker is running
- Check firewall settings
- Ensure correct credentials

### Web interface not accessible
- Check if port 3000 is available
- Verify container is running: `docker ps`
- Check logs: `docker-compose logs web`

## License

MIT