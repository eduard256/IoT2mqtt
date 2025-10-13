# IoT2MQTT 🚀

**Revolutionary Smart Home System - 100% Containerized**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![MQTT](https://img.shields.io/badge/MQTT-Protocol-purple)](https://mqtt.org/)

IoT2MQTT is a revolutionary smart home integration system that runs entirely in Docker containers. Zero host dependencies - just Docker. The system uses Docker-in-Docker architecture where the main web container orchestrates all connector containers.

## ✨ Key Highlights

- 🐳 **100% Containerized** - No Python, Node.js or any dependencies on host
- 🚀 **One Command Launch** - Just run `./scripts/run.sh` and you're done
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
- Run `./scripts/run.sh`
- Everything works
- Updates are seamless
- Works identically on any system

## 🚀 Quick Start

### One‑Line Install (any Linux)

Runs a beautiful CLI with a live progress bar and snake mini‑game while installing everything (Docker, Compose, app, and services). When done, it prints your LAN URL.

```bash
curl -fsSL https://raw.githubusercontent.com/eduard256/IoT2mqtt/main/install.sh | bash
```

Notes:
- Run as root or with passwordless sudo for a fully non‑interactive setup.
- The installer supports most Linux distros (Debian/Ubuntu, RHEL/CentOS/Fedora, openSUSE, Arch, Alpine). It uses Docker's convenience script or native packages.
- On completion, you'll see the URL like `http://<your_lan_ip>:8765`.

### Proxmox LXC Install

Install IoT2MQTT in a Proxmox LXC container with a beautiful interactive installer:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/eduard256/IoT2mqtt/main/install_proxmox.sh)
```

**Features:**
- 🎨 Beautiful CLI with interactive navigation menu
- 🚀 Automatic mode: zero configuration needed
- ⚙️ Advanced mode: full control over all parameters
- ✅ Supports Proxmox VE 7.x, 8.x, and 9.x
- 🐳 Pre-configured for Docker (nested containers enabled)

**The installer will:**
1. Show interactive menu to choose installation mode
2. Auto-detect free container ID (or let you choose)
3. Download Ubuntu 22.04 LXC template if needed
4. Create unprivileged container with Docker support
5. Run IoT2MQTT installation inside
6. Display the access URL when complete

**Default configuration (Automatic mode):**
- Ubuntu 22.04 LXC (unprivileged)
- 10GB disk, 4GB RAM, all CPU cores
- DHCP networking (auto-configured)
- Docker-ready (nesting enabled)

**Advanced mode allows you to customize:**
- Container ID
- Network configuration (DHCP or static IP)
- Storage selection
- Disk size, RAM, and CPU allocation
- Privileged/unprivileged mode

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
./scripts/run.sh
```

That's it! The script will:
- Check Docker installation
- Build all containers
- Start the web interface
- Show you the URL to access

3. **Open Web Interface**

Navigate to `http://localhost:8765` in your browser.

Or, if you used the one‑liner installer above, open the LAN URL it prints (for example, `http://192.168.1.50:8765`).

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

### Declarative Setup Flows

Every integration describes its onboarding wizard in
`connectors/<name>/setup.json`. The backend validates this schema and the
frontend renders it dynamically (forms, tool execution, OAuth, summaries, etc.).
Documentation for the full schema lives in
[`docs/setup-flows.md`](docs/setup-flows.md).

Key benefits:

- No custom UI code per connector – add new steps by editing `setup.json`.
- Tool scripts run in isolation via the test-runner container
  (`connectors/<name>/actions/`).
- OAuth, discovery, and manual flows share the same infrastructure.
- Instance files are stored under `instances/<connector>/<id>.json`, while
  secrets are encrypted automatically.

### Environment variables

- `IOT2MQTT_PATH` — overrides the project root auto-detected by backend
  services.
- `IOT2MQTT_SECRETS_PATH` — custom directory for encrypted secrets and the
  master key (`.master.key`). Useful for running tests or deploying in
  environments with restricted filesystem access.
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
WEB_PORT=9000 ./scripts/run.sh
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
git pull && ./scripts/run.sh

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
├── scripts/              # Utility scripts
│   ├── run.sh           # One-command launcher
│   ├── install.sh       # Installation script
│   └── ...
├── tests/               # Test files
├── docs/                # Documentation
│   ├── features/       # Feature documentation
│   └── archived/       # Archived docs
├── docker-compose.yml   # Main orchestration
├── web/                 # Web interface container
│   ├── frontend/       # React UI
│   ├── backend/        # FastAPI backend
│   └── Dockerfile
├── connectors/         # Connector definitions
│   └── {name}/
│       ├── connector.py
│       ├── requirements.txt
│       └── Dockerfile
└── shared/            # Shared libraries
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
4. Test with `./scripts/run.sh`
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
- **Runtime paths & storage**: [docs/runtime-storage.md](docs/runtime-storage.md)
- **Backend services**: [docs/backend-services.md](docs/backend-services.md)
- **REST API reference**: [docs/api-reference.md](docs/api-reference.md)
- **Connector guide**: [docs/connectors.md](docs/connectors.md)

---

**Made with ❤️ for the Smart Home Community**

*No more dependency hell. Just Docker and go!*
