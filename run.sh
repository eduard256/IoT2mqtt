#!/bin/bash

# IoT2MQTT - Beautiful launcher script
# Direct IoT to MQTT bridge for minimal latency

set -e

# Colors for beautiful output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Default port (can be overridden with environment variable)
WEB_PORT=${WEB_PORT:-8765}

# Spinner animation
spin() {
    local pid=$1
    local delay=0.1
    local spinstr='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    printf " "
    while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

# Clear screen for fresh start
clear

# Display beautiful ASCII art logo
echo -e "${CYAN}"
cat << "EOF"
    ╔═══════════════════════════════════════════════════════════════════╗
    ║                                                                   ║
    ║     ██╗ ██████╗ ████████╗    ██████╗     ███╗   ███╗ ██████╗    ║
    ║     ██║██╔═══██╗╚══██╔══╝    ╚════██╗    ████╗ ████║██╔═══██╗   ║
    ║     ██║██║   ██║   ██║        █████╔╝    ██╔████╔██║██║   ██║   ║
    ║     ██║██║   ██║   ██║       ██╔═══╝     ██║╚██╔╝██║██║▄▄ ██║   ║
    ║     ██║╚██████╔╝   ██║       ███████╗    ██║ ╚═╝ ██║╚██████╔╝   ║
    ║     ╚═╝ ╚═════╝    ╚═╝       ╚══════╝    ╚═╝     ╚═╝ ╚══▀▀═╝    ║
    ║                                                                   ║
    ║            🚀 Direct IoT to MQTT Bridge System 🚀                ║
    ║                                                                   ║
    ╚═══════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo -e "${BOLD}${WHITE}    Revolutionary Smart Home Integration Platform${NC}"
echo -e "${CYAN}    ═══════════════════════════════════════════════${NC}"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to get Docker version
get_docker_version() {
    docker --version 2>/dev/null | awk '{print $3}' | sed 's/,$//'
}

# Function to get Docker Compose version
get_compose_version() {
    if command_exists docker-compose; then
        docker-compose --version 2>/dev/null | awk '{print $3}' | sed 's/,$//'
    elif docker compose version >/dev/null 2>&1; then
        docker compose version --short 2>/dev/null
    else
        echo "not found"
    fi
}

# Check Docker installation
echo -e "${YELLOW}▶ Checking system requirements...${NC}"
echo ""

# Check Docker
if ! command_exists docker; then
    echo -e "${RED}✗ Docker is not installed!${NC}"
    echo -e "${WHITE}  Please install Docker from: ${CYAN}https://docs.docker.com/get-docker/${NC}"
    exit 1
else
    DOCKER_VERSION=$(get_docker_version)
    echo -e "${GREEN}✓${NC} Docker ${BOLD}${DOCKER_VERSION}${NC} detected"
fi

# Check Docker Compose
COMPOSE_VERSION=$(get_compose_version)
if [ "$COMPOSE_VERSION" = "not found" ]; then
    echo -e "${RED}✗ Docker Compose is not installed!${NC}"
    echo -e "${WHITE}  Please install Docker Compose from: ${CYAN}https://docs.docker.com/compose/install/${NC}"
    exit 1
else
    echo -e "${GREEN}✓${NC} Docker Compose ${BOLD}${COMPOSE_VERSION}${NC} detected"
fi

# Check if Docker daemon is running
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}✗ Docker daemon is not running!${NC}"
    echo -e "${WHITE}  Please start Docker and try again.${NC}"
    exit 1
else
    echo -e "${GREEN}✓${NC} Docker daemon is ${BOLD}running${NC}"
fi

# Check if port is available
echo ""
echo -e "${YELLOW}▶ Checking port availability...${NC}"
if lsof -Pi :$WEB_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}✗ Port ${WEB_PORT} is already in use!${NC}"
    echo -e "${WHITE}  You can set a different port with: ${CYAN}WEB_PORT=8080 ./run.sh${NC}"
    exit 1
else
    echo -e "${GREEN}✓${NC} Port ${BOLD}${WEB_PORT}${NC} is available"
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo -e "${YELLOW}▶ Creating environment configuration...${NC}"
    cat > .env << EOL
# IoT2MQTT Configuration
# Generated on $(date)

# Web Interface
WEB_PORT=${WEB_PORT}

# MQTT Settings (will be configured via web interface)
MQTT_HOST=
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_BASE_TOPIC=IoT2mqtt

# System Settings
LOG_LEVEL=INFO
TZ=$(cat /etc/timezone 2>/dev/null || echo "UTC")
EOL
    echo -e "${GREEN}✓${NC} Created ${BOLD}.env${NC} configuration file"
fi

# Create necessary directories
echo ""
echo -e "${YELLOW}▶ Preparing directory structure...${NC}"
mkdir -p secrets/instances connectors shared
echo -e "${GREEN}✓${NC} Directory structure ready"

# Pull or build images
echo ""
echo -e "${YELLOW}▶ Building Docker images...${NC}"
echo -e "${CYAN}  This may take a few minutes on first run...${NC}"
echo ""

# Use docker compose or docker-compose based on availability
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Build images with progress
$COMPOSE_CMD build --progress=plain 2>&1 | while IFS= read -r line; do
    if [[ $line == *"Step"* ]]; then
        echo -e "${CYAN}  ▪ ${line}${NC}"
    elif [[ $line == *"Successfully"* ]]; then
        echo -e "${GREEN}  ✓ ${line}${NC}"
    elif [[ $line == *"ERROR"* ]] || [[ $line == *"error"* ]]; then
        echo -e "${RED}  ✗ ${line}${NC}"
    fi
done

# Start containers
echo ""
echo -e "${YELLOW}▶ Starting IoT2MQTT containers...${NC}"
echo ""

# Start in detached mode
$COMPOSE_CMD up -d 2>&1 | while IFS= read -r line; do
    if [[ $line == *"Creating"* ]]; then
        echo -e "${CYAN}  ▪ ${line}${NC}"
    elif [[ $line == *"Started"* ]] || [[ $line == *"done"* ]]; then
        echo -e "${GREEN}  ✓ ${line}${NC}"
    elif [[ $line == *"ERROR"* ]] || [[ $line == *"error"* ]]; then
        echo -e "${RED}  ✗ ${line}${NC}"
    fi
done

# Wait for services to be healthy
echo ""
echo -e "${YELLOW}▶ Waiting for services to be ready...${NC}"

MAX_WAIT=60
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if curl -s -f http://localhost:${WEB_PORT}/api/health >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Web interface is ${BOLD}ready${NC}"
        break
    fi
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    printf "  Waiting... [${WAIT_COUNT}/${MAX_WAIT}s]\r"
done

if [ $WAIT_COUNT -eq $MAX_WAIT ]; then
    echo -e "${RED}✗ Web interface failed to start!${NC}"
    echo -e "${WHITE}  Check logs with: ${CYAN}docker compose logs web${NC}"
    exit 1
fi

# Display success message
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}       🎉 IoT2MQTT is successfully running! 🎉${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${WHITE}${BOLD}Access the web interface at:${NC}"
echo ""
echo -e "    ${CYAN}${BOLD}http://localhost:${WEB_PORT}${NC}"
echo ""
echo -e "${WHITE}${BOLD}Quick commands:${NC}"
echo -e "  ${CYAN}View logs:${NC}        docker compose logs -f"
echo -e "  ${CYAN}Stop system:${NC}      docker compose down"
echo -e "  ${CYAN}Restart system:${NC}   docker compose restart"
echo -e "  ${CYAN}Update system:${NC}    git pull && ./run.sh"
echo ""
echo -e "${YELLOW}${BOLD}First time setup:${NC}"
echo -e "  1. Open ${CYAN}http://localhost:${WEB_PORT}${NC} in your browser"
echo -e "  2. Create an access key (your password)"
echo -e "  3. Configure MQTT connection"
echo -e "  4. Start adding IoT integrations!"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${MAGENTA}${BOLD}Thank you for using IoT2MQTT!${NC}"
echo -e "${WHITE}Documentation: ${CYAN}https://github.com/eduard256/IoT2mqtt${NC}"
echo ""

# Optional: Open browser automatically
if command_exists xdg-open; then
    read -p "$(echo -e ${YELLOW}Would you like to open the web interface now? [Y/n]: ${NC})" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        xdg-open "http://localhost:${WEB_PORT}" 2>/dev/null &
    fi
elif command_exists open; then
    read -p "$(echo -e ${YELLOW}Would you like to open the web interface now? [Y/n]: ${NC})" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        open "http://localhost:${WEB_PORT}" 2>/dev/null &
    fi
fi