#!/usr/bin/env bash

# IoT2MQTT Proxmox LXC Installer
# This script creates an Ubuntu LXC container and installs IoT2MQTT inside it
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/eduard256/IoT2mqtt/main/scripts/install_proxmox.sh)

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Container configuration (fixed)
DISK_SIZE="8"
RAM_SIZE="2048"
CORES="2"
OS_TEMPLATE="ubuntu-22.04-standard"
BRIDGE="vmbr0"
GATEWAY=""
HOSTNAME="iot2mqtt"
USE_DHCP=false

# Functions
error() {
    echo -e "${RED}✗ Error: $*${NC}" >&2
    exit 1
}

success() {
    echo -e "${GREEN}✓ $*${NC}"
}

info() {
    echo -e "${CYAN}ℹ $*${NC}"
}

warning() {
    echo -e "${YELLOW}⚠ $*${NC}"
}

header() {
    clear
    cat <<"EOF"
  ██╗ ██████╗ ████████╗██████╗ ███╗   ███╗ ██████╗ ████████╗████████╗
  ██║██╔═══██╗╚══██╔══╝╚════██╗████╗ ████║██╔═══██╗╚══██╔══╝╚══██╔══╗
  ██║██║   ██║   ██║    █████╔╝██╔████╔██║██║   ██║   ██║      ██║
  ██║██║   ██║   ██║   ██╔═══╝ ██║╚██╔╝██║██║▄▄ ██║   ██║      ██║
  ██║╚██████╔╝   ██║   ███████╗██║ ╚═╝ ██║╚██████╔╝   ██║      ██║
  ╚═╝ ╚═════╝    ╚═╝   ╚══════╝╚═╝     ╚═╝ ╚══▀▀═╝    ╚═╝      ╚═╝

EOF
    echo -e "  ${BLUE}Proxmox LXC Installer${NC}"
    echo
}

check_proxmox() {
    if ! command -v pct &> /dev/null; then
        error "This script must be run on a Proxmox host"
    fi

    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root"
    fi
}

get_gateway() {
    local ip_cidr="$1"
    local ip="${ip_cidr%/*}"

    # Extract network part and set gateway as .1
    IFS='.' read -r i1 i2 i3 i4 <<< "$ip"
    echo "${i1}.${i2}.${i3}.1"
}

get_next_free_ctid() {
    # Find first available container ID starting from 100
    local ctid=100
    while pct status "$ctid" &>/dev/null; do
        ctid=$((ctid + 1))
    done
    echo "$ctid"
}

download_template() {
    local template="$1"

    info "Checking for Ubuntu 22.04 template..."

    # Check if template exists
    if pveam list local | grep -q "$template"; then
        success "Template already downloaded"
        return 0
    fi

    info "Downloading Ubuntu 22.04 template..."
    pveam download local "$template" || error "Failed to download template"
    success "Template downloaded"
}

create_container() {
    local ctid="$1"
    local ip="$2"
    local template_path="local:vztmpl/${OS_TEMPLATE}_amd64.tar.zst"

    info "Creating LXC container $ctid..."

    # Network configuration
    local net_config
    if [ "$USE_DHCP" = true ]; then
        net_config="name=eth0,bridge=${BRIDGE},ip=dhcp"
    else
        # Detect gateway from IP
        GATEWAY=$(get_gateway "$ip")
        net_config="name=eth0,bridge=${BRIDGE},ip=${ip},gw=${GATEWAY}"
    fi

    pct create "$ctid" "$template_path" \
        --hostname "$HOSTNAME" \
        --cores "$CORES" \
        --memory "$RAM_SIZE" \
        --swap 512 \
        --rootfs local-lvm:${DISK_SIZE} \
        --net0 "$net_config" \
        --features nesting=1 \
        --unprivileged 1 \
        --onboot 1 \
        --start 1 \
        || error "Failed to create container"

    success "Container $ctid created"
}

wait_for_container() {
    local ctid="$1"
    local max_wait=60
    local count=0

    info "Waiting for container to start..."

    while [ $count -lt $max_wait ]; do
        if pct status "$ctid" | grep -q "running"; then
            # Wait additional time for network
            sleep 5
            success "Container is running"
            return 0
        fi
        sleep 2
        count=$((count + 2))
    done

    error "Container failed to start"
}

install_iot2mqtt() {
    local ctid="$1"

    info "Installing IoT2MQTT inside container..."
    echo

    # Run our install script inside the container
    pct exec "$ctid" -- bash -c "curl -fsSL https://raw.githubusercontent.com/eduard256/IoT2mqtt/main/install.sh | bash" \
        || error "Failed to install IoT2MQTT"

    echo
    success "IoT2MQTT installed successfully"
}

get_container_ip() {
    local ctid="$1"
    pct exec "$ctid" -- hostname -I 2>/dev/null | awk '{print $1}' || echo "unknown"
}

# Main script
main() {
    header
    check_proxmox

    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo
    echo -e "${CYAN}Выберите режим установки:${NC}"
    echo
    echo "  1) Автоматическая установка (DHCP, автоматический ID и имя)"
    echo "  2) Дополнительная установка (ручная настройка параметров)"
    echo

    while true; do
        read -p "Введите номер режима (1 или 2): " mode

        case $mode in
            1)
                info "Выбран режим: Автоматическая установка"
                USE_DHCP=true
                CTID=$(get_next_free_ctid)
                HOSTNAME="iot2mqtt"
                IP_ADDR="dhcp"
                break
                ;;
            2)
                info "Выбран режим: Дополнительная установка"
                USE_DHCP=false

                # Get hostname
                read -p "Введите имя контейнера (по умолчанию: iot2mqtt): " input_hostname
                HOSTNAME="${input_hostname:-iot2mqtt}"

                # Get container ID
                while true; do
                    read -p "Введите ID контейнера (например, 100): " CTID

                    if [[ ! "$CTID" =~ ^[0-9]+$ ]]; then
                        warning "ID контейнера должен быть числом"
                        continue
                    fi

                    if pct status "$CTID" &>/dev/null; then
                        warning "Контейнер $CTID уже существует"
                        read -p "Продолжить в любом случае? (yes/no): " confirm
                        if [[ "$confirm" != "yes" ]]; then
                            continue
                        fi
                    fi

                    break
                done

                # Get IP address
                while true; do
                    read -p "Введите IP адрес с CIDR (например, 192.168.1.50/24): " IP_ADDR

                    if [[ ! "$IP_ADDR" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/[0-9]{1,2}$ ]]; then
                        warning "Неверный формат IP. Используйте формат: 192.168.1.50/24"
                        continue
                    fi

                    break
                done

                # Get gateway (optional)
                local default_gw=$(get_gateway "$IP_ADDR")
                read -p "Введите шлюз (по умолчанию: $default_gw): " input_gateway
                GATEWAY="${input_gateway:-$default_gw}"

                # Get bridge (optional)
                read -p "Введите сетевой мост (по умолчанию: vmbr0): " input_bridge
                BRIDGE="${input_bridge:-vmbr0}"

                # Get disk size (optional)
                read -p "Введите размер диска в GB (по умолчанию: 8): " input_disk
                DISK_SIZE="${input_disk:-8}"

                # Get RAM size (optional)
                read -p "Введите размер RAM в MB (по умолчанию: 2048): " input_ram
                RAM_SIZE="${input_ram:-2048}"

                # Get CPU cores (optional)
                read -p "Введите количество CPU ядер (по умолчанию: 2): " input_cores
                CORES="${input_cores:-2}"

                break
                ;;
            *)
                warning "Неверный выбор. Введите 1 или 2"
                ;;
        esac
    done

    echo
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo
    info "Конфигурация:"
    echo "  Имя контейнера: $HOSTNAME"
    echo "  ID контейнера:  $CTID"
    if [ "$USE_DHCP" = true ]; then
        echo "  IP адрес:       DHCP (автоматически)"
    else
        echo "  IP адрес:       $IP_ADDR"
        echo "  Шлюз:           $GATEWAY"
        echo "  Мост:           $BRIDGE"
    fi
    echo "  Диск:           ${DISK_SIZE}GB"
    echo "  RAM:            ${RAM_SIZE}MB"
    echo "  CPU ядер:       $CORES"
    echo "  ОС:             Ubuntu 22.04"
    echo

    read -p "Продолжить установку? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        info "Установка отменена"
        exit 0
    fi

    echo
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    # Download template
    download_template "${OS_TEMPLATE}_amd64.tar.zst"

    # Create container
    create_container "$CTID" "$IP_ADDR"

    # Wait for container to be ready
    wait_for_container "$CTID"

    # Install IoT2MQTT
    install_iot2mqtt "$CTID"

    # Get container IP (actual)
    CONTAINER_IP=$(get_container_ip "$CTID")

    # Final message
    echo
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo
    echo -e "${GREEN}${BOLD}✓ Установка завершена!${NC}"
    echo
    echo -e "  ${CYAN}Веб-интерфейс:${NC} http://${CONTAINER_IP}:8765"
    echo -e "  ${CYAN}ID контейнера:${NC}  $CTID"
    echo -e "  ${CYAN}Имя контейнера:${NC} $HOSTNAME"
    echo
    echo -e "  ${YELLOW}Полезные команды:${NC}"
    echo -e "    pct enter $CTID          # Войти в контейнер"
    echo -e "    pct stop $CTID           # Остановить контейнер"
    echo -e "    pct start $CTID          # Запустить контейнер"
    echo -e "    pct status $CTID         # Проверить статус"
    echo
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo
}

# Run main
main "$@"
