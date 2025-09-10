# IoT2MQTT 🚀

**Revolutionary Smart Home System - 100% Containerized**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![MQTT](https://img.shields.io/badge/MQTT-Protocol-purple)](https://mqtt.org/)

IoT2MQTT is a revolutionary smart home integration system that runs entirely in Docker containers. Zero host dependencies - just Docker. The system uses Docker-in-Docker architecture where the main web container orchestrates all connector containers.

## ✨ Key Highlights

- 🐳 **100% Containerized** - No Python, Node.js or any dependencies on host
- 🚀 **One Command Launch** - Just run `./run.sh` and you're done
- 🎨 **Beautiful Web Interface** - Premium SaaS-level UI at `http://localhost:8765`
- ⚡ **Minimal Latency** - Direct MQTT connection without intermediate layers
- 🌍 **Multi-language** - English, Russian, and Chinese support
- 📱 **PWA Support** - Install as mobile app

## 🎯 Why IoT2MQTT?

Traditional smart home systems require complex installations with multiple dependencies on your host system. IoT2MQTT changes this:

**Before (Traditional Systems):**
- Install Python, Node.js, and dozens of packages
- Manage virtual environments
- Deal with version conflicts
- Complex update procedures
- System-specific issues

**Now (IoT2MQTT):**
- Install Docker (once)
- Run `./run.sh`
- Everything works
- Updates are seamless
- Works identically on any system

## 🚀 Quick Start

### Prerequisites

Only Docker and Docker Compose are required. Nothing else.

```bash
# Check if Docker is installed
docker --version
docker compose version
```

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/eduard256/IoT2mqtt.git
cd IoT2mqtt
```

2. **Run the system**
```bash
./run.sh
```

That's it! The script will:
- Check Docker installation
- Build all containers
- Start the web interface
- Show you the URL to access

3. **Open Web Interface**

Navigate to `http://localhost:8765` in your browser.

### First Time Setup

1. **Create Access Key** - Your password for the web interface
2. **Configure MQTT** - Connect to your MQTT broker
3. **Add Integrations** - Start adding IoT devices through the web UI

## 🏗️ Architecture

### Docker-in-Docker Design

```
Your Host System
    └── Docker Engine
         └── iot2mqtt_web (Main Container)
              ├── Web Interface (React + FastAPI)
              ├── Docker Socket Mounted (/var/run/docker.sock)
              └── Container Manager
                   ├── Creates connector containers
                   ├── Manages lifecycle
                   ├── Collects logs
                   └── Monitors health
                   
         └── iot2mqtt_connector_1
         └── iot2mqtt_connector_2
         └── ... (one container per instance)
```

### How It Works

1. **Main Web Container** runs the web interface and API
2. **Docker Socket** is mounted to allow container management
3. **Connector Containers** are created dynamically for each integration
4. **MQTT Communication** happens directly from each container
5. **Shared Network** allows inter-container communication

## 🎨 Web Interface Features

- **Dashboard** - Overview of all devices and their status
- **Integrations** - Add and manage IoT connectors
- **Devices** - Control and monitor all devices
- **MQTT Explorer** - Browse and debug MQTT topics
- **Container Management** - Start/stop/restart containers
- **Logs Viewer** - Real-time colored logs from all containers
- **Settings** - Configure MQTT, access keys, and more

## 📦 Supported Integrations

Current connectors:
- **Yeelight** - Smart bulbs and LED strips
- **Xiaomi** - Mi Home devices (coming soon)
- **Tuya** - Smart Life devices (coming soon)
- **ESPHome** - DIY ESP devices (coming soon)

Each connector:
- Runs in isolated container
- Has zero dependencies on host
- Can be updated independently
- Supports multiple instances

## 🔧 Configuration

### Environment Variables

The system uses a `.env` file (created automatically):

```env
# Web Interface
WEB_PORT=8765           # Change web interface port

# MQTT Settings (configured via web UI)
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_BASE_TOPIC=IoT2mqtt

# System
LOG_LEVEL=INFO
TZ=UTC
```

### Custom Port

To use a different port:

```bash
WEB_PORT=9000 ./run.sh
```

## 🐳 Docker Management

### Basic Commands

```bash
# View logs
docker compose logs -f

# Stop system
docker compose down

# Restart system
docker compose restart

# Update system
git pull && ./run.sh

# Remove everything (including data)
docker compose down -v
```

### Container Management

All container management should be done through the web interface. The web container has full Docker access and can:
- Create new containers for connectors
- Start/stop containers
- View real-time logs
- Monitor resource usage
- Auto-restart failed containers

## 🔒 Security Considerations

### Docker Socket Access

The web container has access to Docker socket (`/var/run/docker.sock`). This is required for container management but grants significant privileges. 

**Security measures:**
- Web interface requires authentication
- Access keys are bcrypt hashed
- JWT tokens for sessions
- Containers are isolated in network
- Read-only mounts where possible

### Best Practices

1. **Use strong access key** for web interface
2. **Secure your MQTT broker** with authentication
3. **Run on trusted network** or use VPN
4. **Keep Docker updated** for security patches
5. **Regular backups** of configuration

## 🛠️ Development

### Adding New Connectors

1. Web interface → Integrations → Add Custom
2. Implement connector logic
3. Container is built automatically
4. No host system changes needed

### Project Structure

```
IoT2mqtt/
├── run.sh                 # One-command launcher
├── docker-compose.yml     # Main orchestration
├── web/                   # Web interface container
│   ├── frontend/         # React UI
│   ├── backend/          # FastAPI backend
│   └── Dockerfile
├── connectors/           # Connector definitions
│   └── {name}/
│       ├── connector.py
│       ├── requirements.txt
│       └── Dockerfile
└── shared/              # Shared libraries
```

## 📊 Monitoring

The web interface provides comprehensive monitoring:
- Container status and health
- Real-time logs with color coding
- MQTT message flow
- Device state changes
- Error tracking
- Performance metrics

## 🆘 Troubleshooting

### Web Interface Not Accessible

```bash
# Check if container is running
docker ps | grep iot2mqtt_web

# Check logs
docker compose logs web

# Check port availability
lsof -i :8765
```

### Container Creation Failed

- Check Docker daemon is running
- Ensure sufficient disk space
- Verify Docker socket permissions
- Check web container logs

### MQTT Connection Issues

- Verify broker is running
- Check firewall rules
- Confirm credentials in web UI
- Test with MQTT client

## 🤝 Contributing

We welcome contributions! Since everything runs in containers:
1. No need to set up development environment
2. Changes are tested in isolated containers
3. Easy to test without affecting host system

### How to Contribute

1. Fork the repository
2. Create feature branch
3. Make changes
4. Test with `./run.sh`
5. Submit pull request

## 📝 License

MIT License - see [LICENSE](LICENSE) file

## 🙏 Acknowledgments

- Docker team for amazing container technology
- MQTT protocol developers
- All IoT device manufacturers
- Open source community

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/eduard256/IoT2mqtt/issues)
- **Discussions**: [GitHub Discussions](https://github.com/eduard256/IoT2mqtt/discussions)
- **Documentation**: [Wiki](https://github.com/eduard256/IoT2mqtt/wiki)

---

**Made with ❤️ for the Smart Home Community**

*No more dependency hell. Just Docker and go!*