#!/usr/bin/env bash

# IoT2MQTT Proxmox LXC Installer
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/eduard256/IoT2mqtt/main/install_proxmox.sh)
#
# This script creates an Ubuntu LXC container on Proxmox and installs IoT2MQTT inside it.
# Supports Proxmox VE 7.x, 8.x, and 9.x

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

REPO_URL="https://raw.githubusercontent.com/eduard256/IoT2mqtt/main"
INSTALL_SCRIPT_URL="${REPO_URL}/install.sh"
LOG_FILE="/tmp/iot2mqtt-proxmox-install-$$.log"

# Default LXC parameters
DEFAULT_DISK_SIZE="10"          # GB
DEFAULT_RAM="4096"               # MB
DEFAULT_SWAP="512"               # MB
DEFAULT_CORES="0"                # 0 = unlimited
DEFAULT_BRIDGE="vmbr0"
UBUNTU_VERSION="22.04"           # Ubuntu LTS version

# ============================================================================
# Colors & Styling
# ============================================================================

if [ -t 1 ] && command -v tput >/dev/null 2>&1; then
  BOLD=$(tput bold)
  DIM=$(tput dim)
  RESET=$(tput sgr0)
  CYAN=$(tput setaf 6)
  GREEN=$(tput setaf 2)
  YELLOW=$(tput setaf 3)
  RED=$(tput setaf 1)
  BLUE=$(tput setaf 4)
  MAGENTA=$(tput setaf 5)
else
  BOLD="" DIM="" RESET="" CYAN="" GREEN="" YELLOW="" RED="" BLUE="" MAGENTA=""
fi

# ============================================================================
# Helper Functions
# ============================================================================

log() {
  local prefix="${CYAN}▸${RESET}"
  echo -e "${prefix} $*" | tee -a "$LOG_FILE"
}

success() {
  local prefix="${GREEN}✓${RESET}"
  echo -e "${prefix} ${GREEN}$*${RESET}" | tee -a "$LOG_FILE"
}

error() {
  local prefix="${RED}✗${RESET}"
  echo -e "${prefix} ${RED}$*${RESET}" | tee -a "$LOG_FILE"
}

warning() {
  local prefix="${YELLOW}⚠${RESET}"
  echo -e "${prefix} ${YELLOW}$*${RESET}" | tee -a "$LOG_FILE"
}

step() {
  echo ""
  echo -e "${BOLD}${BLUE}━━━ $* ━━━${RESET}" | tee -a "$LOG_FILE"
}

show_header() {
  clear
  cat <<'EOF'

  ██████╗ ██████╗  ██████╗ ██╗  ██╗███╗   ███╗ ██████╗ ██╗  ██╗
  ██╔══██╗██╔══██╗██╔═══██╗╚██╗██╔╝████╗ ████║██╔═══██╗╚██╗██╔╝
  ██████╔╝██████╔╝██║   ██║ ╚███╔╝ ██╔████╔██║██║   ██║ ╚███╔╝
  ██╔═══╝ ██╔══██╗██║   ██║ ██╔██╗ ██║╚██╔╝██║██║   ██║ ██╔██╗
  ██║     ██║  ██║╚██████╔╝██╔╝ ██╗██║ ╚═╝ ██║╚██████╔╝██╔╝ ██╗
  ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝

           ██╗ ██████╗ ████████╗██████╗ ███╗   ███╗ ██████╗ ████████╗████████╗
           ██║██╔═══██╗╚══██╔══╝╚════██╗████╗ ████║██╔═══██╗╚══██╔══╝╚══██╔══╝
           ██║██║   ██║   ██║    █████╔╝██╔████╔██║██║   ██║   ██║      ██║
           ██║██║   ██║   ██║   ██╔═══╝ ██║╚██╔╝██║██║▄▄ ██║   ██║      ██║
           ██║╚██████╔╝   ██║   ███████╗██║ ╚═╝ ██║╚██████╔╝   ██║      ██║
           ╚═╝ ╚═════╝    ╚═╝   ╚══════╝╚═╝     ╚═╝ ╚══▀▀═╝    ╚═╝      ╚═╝

EOF
  echo -e "                  ${DIM}LXC Container Installer for Proxmox VE${RESET}"
  echo ""
}

# ============================================================================
# System Checks
# ============================================================================

check_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    error "This script must be run as root"
    echo "  Please run: sudo bash $0"
    exit 1
  fi
}

check_proxmox() {
  if ! command -v pveversion >/dev/null 2>&1; then
    error "This script must be run on a Proxmox VE host"
    exit 1
  fi
}

get_proxmox_version() {
  pveversion | grep -oP 'pve-manager/\K[0-9]+' || echo "0"
}

check_dependencies() {
  local missing=()

  for cmd in pct qm pvesm pveam curl; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      missing+=("$cmd")
    fi
  done

  if [ ${#missing[@]} -gt 0 ]; then
    error "Missing required commands: ${missing[*]}"
    exit 1
  fi

  # Check for whiptail or dialog
  if ! command -v whiptail >/dev/null 2>&1; then
    if ! command -v dialog >/dev/null 2>&1; then
      log "Installing whiptail for interactive menus..."
      apt-get update -qq && apt-get install -y whiptail >/dev/null 2>&1 || {
        error "Failed to install whiptail"
        exit 1
      }
    fi
  fi
}

# ============================================================================
# Container ID Management
# ============================================================================

get_next_free_ctid() {
  local ctid=100
  log "Scanning for available container ID..."

  while true; do
    # Check if ID exists in VMs
    if qm list 2>/dev/null | awk 'NR>1 {print $1}' | grep -q "^${ctid}$"; then
      ctid=$((ctid + 1))
      continue
    fi

    # Check if ID exists in containers
    if pct list 2>/dev/null | awk 'NR>1 {print $1}' | grep -q "^${ctid}$"; then
      ctid=$((ctid + 1))
      continue
    fi

    # ID is free
    echo "$ctid"
    break
  done
}

validate_ctid() {
  local ctid="$1"

  # Check if numeric
  if ! [[ "$ctid" =~ ^[0-9]+$ ]]; then
    return 1
  fi

  # Check if in valid range (100-999999)
  if [ "$ctid" -lt 100 ] || [ "$ctid" -gt 999999 ]; then
    return 1
  fi

  # Check if already in use
  if qm status "$ctid" >/dev/null 2>&1 || pct status "$ctid" >/dev/null 2>&1; then
    return 1
  fi

  return 0
}

# ============================================================================
# Template Management
# ============================================================================

get_storage_list() {
  pvesm status -content vztmpl 2>/dev/null | awk 'NR>1 {print $1}' | head -1
}

find_ubuntu_template() {
  local storage="$1"
  local template

  # Try to find Ubuntu 22.04 template
  template=$(pveam available -section system 2>/dev/null | grep -i "ubuntu-${UBUNTU_VERSION}" | grep "standard" | head -1 | awk '{print $2}')

  if [ -z "$template" ]; then
    # Try 20.04
    template=$(pveam available -section system 2>/dev/null | grep -i "ubuntu-20.04" | grep "standard" | head -1 | awk '{print $2}')
  fi

  if [ -z "$template" ]; then
    # Try 24.04
    template=$(pveam available -section system 2>/dev/null | grep -i "ubuntu-24.04" | grep "standard" | head -1 | awk '{print $2}')
  fi

  echo "$template"
}

download_template() {
  local storage="$1"
  local template="$2"

  step "Downloading Ubuntu LXC Template"

  log "Updating template list..."
  pveam update >>"$LOG_FILE" 2>&1

  log "Downloading $template..."
  log "This may take a few minutes depending on your connection..."

  if pveam download "$storage" "$template" 2>&1 | tee -a "$LOG_FILE" | grep -q "download of.*finished"; then
    success "Template downloaded successfully"
    return 0
  else
    return 1
  fi
}

ensure_template() {
  local storage="$1"

  # Check if any Ubuntu template already exists
  if pvesm list "$storage" 2>/dev/null | grep -q "ubuntu.*standard"; then
    local existing=$(pvesm list "$storage" 2>/dev/null | grep "ubuntu.*standard" | head -1 | awk '{print $1}')
    success "Found existing template: $existing"
    echo "$existing"
    return 0
  fi

  # Need to download
  local template=$(find_ubuntu_template "$storage")

  if [ -z "$template" ]; then
    error "Could not find Ubuntu template"
    return 1
  fi

  log "Template not found, will download: $template"

  if download_template "$storage" "$template"; then
    echo "$storage:vztmpl/$template"
    return 0
  else
    error "Failed to download template"
    return 1
  fi
}

# ============================================================================
# Resource Checks
# ============================================================================

get_available_ram() {
  free -m | awk 'NR==2 {print $7}'
}

get_max_safe_ram() {
  local available=$(get_available_ram)
  local max_alloc=$((available - 2048))  # Leave 2GB for host

  if [ "$max_alloc" -lt 1024 ]; then
    echo "1024"  # Minimum 1GB
  elif [ "$max_alloc" -gt "$DEFAULT_RAM" ]; then
    echo "$DEFAULT_RAM"
  else
    echo "$max_alloc"
  fi
}

# ============================================================================
# Whiptail Menu Functions
# ============================================================================

show_main_menu() {
  local choice

  choice=$(whiptail --clear --backtitle "IoT2MQTT Proxmox Installer" \
    --title "Installation Mode" \
    --menu "Choose installation mode:" 15 70 2 \
    "1" "Automatic Installation (Recommended)" \
    "2" "Advanced Installation (Custom Settings)" \
    3>&1 1>&2 2>&3)

  echo "$choice"
}

show_advanced_menu() {
  local ctid ip gateway disk ram cores privileged storage

  # Get default free CTID
  local default_ctid=$(get_next_free_ctid)

  # CTID Input
  while true; do
    ctid=$(whiptail --inputbox "Enter Container ID:" 10 60 "$default_ctid" 3>&1 1>&2 2>&3)
    if [ $? -ne 0 ]; then
      return 1  # User cancelled
    fi

    if validate_ctid "$ctid"; then
      break
    else
      whiptail --msgbox "Invalid or already used Container ID. Please try another." 10 60
    fi
  done

  # Network configuration
  if whiptail --yesno "Use DHCP for network configuration?" 10 60; then
    ip="dhcp"
    gateway=""
  else
    ip=$(whiptail --inputbox "Enter IP address (with CIDR, e.g., 192.168.1.100/24):" 10 60 "192.168.1.100/24" 3>&1 1>&2 2>&3)
    if [ $? -ne 0 ]; then return 1; fi

    gateway=$(whiptail --inputbox "Enter Gateway:" 10 60 "192.168.1.1" 3>&1 1>&2 2>&3)
    if [ $? -ne 0 ]; then return 1; fi
  fi

  # Storage selection
  local storage_options=()
  while IFS= read -r stor; do
    storage_options+=("$stor" "")
  done < <(pvesm status -content vztmpl 2>/dev/null | awk 'NR>1 {print $1}')

  if [ ${#storage_options[@]} -eq 0 ]; then
    error "No storage available for containers"
    return 1
  fi

  storage=$(whiptail --menu "Select storage:" 15 60 5 "${storage_options[@]}" 3>&1 1>&2 2>&3)
  if [ $? -ne 0 ]; then return 1; fi

  # Disk size
  disk=$(whiptail --inputbox "Enter disk size (GB):" 10 60 "$DEFAULT_DISK_SIZE" 3>&1 1>&2 2>&3)
  if [ $? -ne 0 ]; then return 1; fi

  # RAM
  local max_ram=$(get_max_safe_ram)
  ram=$(whiptail --inputbox "Enter RAM (MB):\n\nAvailable: ${max_ram}MB" 12 60 "$max_ram" 3>&1 1>&2 2>&3)
  if [ $? -ne 0 ]; then return 1; fi

  # CPU Cores
  local max_cores=$(nproc)
  cores=$(whiptail --inputbox "Enter CPU cores (0 = unlimited):\n\nAvailable: ${max_cores}" 12 60 "$DEFAULT_CORES" 3>&1 1>&2 2>&3)
  if [ $? -ne 0 ]; then return 1; fi

  # Privileged/Unprivileged
  if whiptail --yesno "Create as unprivileged container?\n\n(Recommended for security)" 10 60; then
    privileged="0"
  else
    privileged="1"
  fi

  # Export all settings
  echo "CTID=$ctid"
  echo "IP=$ip"
  echo "GATEWAY=$gateway"
  echo "STORAGE=$storage"
  echo "DISK=$disk"
  echo "RAM=$ram"
  echo "CORES=$cores"
  echo "PRIVILEGED=$privileged"
}

# ============================================================================
# Container Creation
# ============================================================================

create_container() {
  local ctid="$1"
  local storage="$2"
  local template="$3"
  local disk="$4"
  local ram="$5"
  local cores="$6"
  local privileged="$7"
  local ip="$8"
  local gateway="$9"

  step "Creating LXC Container"

  log "Container ID: $ctid"
  log "Template: $template"
  log "Storage: $storage"
  log "Disk: ${disk}GB"
  log "RAM: ${ram}MB"
  log "Cores: $cores"
  log "Privileged: $privileged"
  log "Network: $ip"

  # Build pct create command
  local pct_cmd="pct create $ctid $template"
  pct_cmd+=" --storage $storage"
  pct_cmd+=" --rootfs $storage:$disk"
  pct_cmd+=" --memory $ram"
  pct_cmd+=" --swap $DEFAULT_SWAP"
  pct_cmd+=" --cores $cores"
  pct_cmd+=" --hostname iot2mqtt"
  pct_cmd+=" --unprivileged $((1 - privileged))"
  pct_cmd+=" --features nesting=1"
  pct_cmd+=" --onboot 1"
  pct_cmd+=" --start 0"

  # Network configuration
  if [ "$ip" = "dhcp" ]; then
    pct_cmd+=" --net0 name=eth0,bridge=$DEFAULT_BRIDGE,ip=dhcp"
  else
    pct_cmd+=" --net0 name=eth0,bridge=$DEFAULT_BRIDGE,ip=$ip"
    if [ -n "$gateway" ]; then
      pct_cmd+=" --nameserver 8.8.8.8"
      pct_cmd+=" --searchdomain local"
    fi
  fi

  log "Executing: $pct_cmd"

  if eval "$pct_cmd" >>"$LOG_FILE" 2>&1; then
    success "Container created successfully"

    # Set gateway if static IP
    if [ "$ip" != "dhcp" ] && [ -n "$gateway" ]; then
      pct set "$ctid" -nameserver 8.8.8.8 >>"$LOG_FILE" 2>&1 || true
    fi

    return 0
  else
    error "Failed to create container"
    return 1
  fi
}

start_container() {
  local ctid="$1"

  log "Starting container..."

  if pct start "$ctid" >>"$LOG_FILE" 2>&1; then
    success "Container started"

    # Wait for container to be ready
    log "Waiting for container to initialize..."
    sleep 5

    # Wait for network
    for i in {1..30}; do
      if pct exec "$ctid" -- ip addr show eth0 2>/dev/null | grep -q "inet "; then
        success "Network is ready"
        return 0
      fi
      sleep 2
    done

    warning "Container started but network might not be ready"
    return 0
  else
    error "Failed to start container"
    return 1
  fi
}

# ============================================================================
# IoT2MQTT Installation
# ============================================================================

install_iot2mqtt() {
  local ctid="$1"

  step "Installing IoT2MQTT"

  log "Preparing container environment..."

  # Update package lists
  pct exec "$ctid" -- bash -c "apt-get update -qq" >>"$LOG_FILE" 2>&1 || true

  # Install curl if not present
  pct exec "$ctid" -- bash -c "command -v curl >/dev/null || apt-get install -y curl" >>"$LOG_FILE" 2>&1

  log "Downloading and running IoT2MQTT installer..."
  log "This may take several minutes..."
  echo ""

  # Run install script and capture output
  if pct exec "$ctid" -- bash -c "curl -fsSL $INSTALL_SCRIPT_URL | bash" 2>&1 | tee -a "$LOG_FILE" | while IFS= read -r line; do
    # Check for completion marker
    if echo "$line" | grep -q "IOT2MQTT_INSTALL_COMPLETE"; then
      echo "INSTALL_COMPLETE" > "/tmp/iot2mqtt-status-$$"
    fi

    # Forward output with some filtering
    if [[ "$line" =~ ^[[:space:]]*$ ]]; then
      continue
    fi
    echo "$line"
  done; then
    echo ""
    success "IoT2MQTT installation completed"
    return 0
  else
    echo ""
    warning "Installation script finished (check output above for any issues)"
    return 0
  fi
}

get_container_ip() {
  local ctid="$1"
  local ip

  # Try to get IP from container
  ip=$(pct exec "$ctid" -- ip -4 addr show eth0 2>/dev/null | grep -oP 'inet \K[\d.]+' | head -1)

  if [ -z "$ip" ]; then
    # Try alternative method
    ip=$(pct exec "$ctid" -- hostname -I 2>/dev/null | awk '{print $1}')
  fi

  echo "$ip"
}

# ============================================================================
# Main Installation Flow
# ============================================================================

run_automatic_installation() {
  local ctid storage template_path ram

  # Get next free CTID
  ctid=$(get_next_free_ctid)
  success "Selected Container ID: $ctid"

  # Get storage
  storage=$(get_storage_list)
  if [ -z "$storage" ]; then
    error "No storage found for container templates"
    exit 1
  fi
  success "Using storage: $storage"

  # Ensure template exists
  template_path=$(ensure_template "$storage")
  if [ -z "$template_path" ]; then
    error "Failed to get Ubuntu template"
    exit 1
  fi

  # Calculate RAM
  ram=$(get_max_safe_ram)
  success "Allocating RAM: ${ram}MB"

  # Create container
  if ! create_container "$ctid" "$storage" "$template_path" "$DEFAULT_DISK_SIZE" "$ram" "$DEFAULT_CORES" "0" "dhcp" ""; then
    error "Failed to create container"
    exit 1
  fi

  # Start container
  if ! start_container "$ctid"; then
    error "Failed to start container"
    exit 1
  fi

  # Install IoT2MQTT
  if ! install_iot2mqtt "$ctid"; then
    error "Failed to install IoT2MQTT"
    exit 1
  fi

  # Success message
  show_success_message "$ctid"
}

run_advanced_installation() {
  local settings

  settings=$(show_advanced_menu)

  if [ $? -ne 0 ] || [ -z "$settings" ]; then
    error "Installation cancelled"
    exit 1
  fi

  # Parse settings
  eval "$settings"

  # Ensure template exists
  local template_path
  template_path=$(ensure_template "$STORAGE")
  if [ -z "$template_path" ]; then
    error "Failed to get Ubuntu template"
    exit 1
  fi

  # Create container
  if ! create_container "$CTID" "$STORAGE" "$template_path" "$DISK" "$RAM" "$CORES" "$PRIVILEGED" "$IP" "$GATEWAY"; then
    error "Failed to create container"
    exit 1
  fi

  # Start container
  if ! start_container "$CTID"; then
    error "Failed to start container"
    exit 1
  fi

  # Install IoT2MQTT
  if ! install_iot2mqtt "$CTID"; then
    error "Failed to install IoT2MQTT"
    exit 1
  fi

  # Success message
  show_success_message "$CTID"
}

show_success_message() {
  local ctid="$1"
  local ip

  ip=$(get_container_ip "$ctid")

  echo ""
  echo ""
  echo -e "${GREEN}${BOLD}╔════════════════════════════════════════════════════════════════╗${RESET}"
  echo -e "${GREEN}${BOLD}║                                                                ║${RESET}"
  echo -e "${GREEN}${BOLD}║         🎉  IoT2MQTT Container is Ready!  🎉                  ║${RESET}"
  echo -e "${GREEN}${BOLD}║                                                                ║${RESET}"
  echo -e "${GREEN}${BOLD}╚════════════════════════════════════════════════════════════════╝${RESET}"
  echo ""
  echo -e "  ${BOLD}Container ID:${RESET} ${CYAN}${ctid}${RESET}"

  if [ -n "$ip" ] && [ "$ip" != "127.0.0.1" ]; then
    echo -e "  ${BOLD}IP Address:${RESET} ${CYAN}${ip}${RESET}"
    echo -e "  ${BOLD}Web Interface:${RESET} ${CYAN}${BOLD}http://${ip}:8765${RESET}"
  else
    echo -e "  ${YELLOW}Note: Unable to detect container IP automatically${RESET}"
    echo -e "  ${DIM}Check container network configuration with: pct exec $ctid ip addr${RESET}"
  fi

  echo ""
  echo -e "  ${DIM}• Container will auto-start on boot${RESET}"
  echo -e "  ${DIM}• Access container: pct enter $ctid${RESET}"
  echo -e "  ${DIM}• View logs: pct exec $ctid docker logs -f iot2mqtt_web${RESET}"
  echo -e "  ${DIM}• Stop container: pct stop $ctid${RESET}"
  echo ""
  echo -e "${DIM}Installation log: ${LOG_FILE}${RESET}"
  echo ""
}

# ============================================================================
# Main
# ============================================================================

main() {
  show_header

  # Initialize log
  echo "Proxmox IoT2MQTT Installation started at $(date)" > "$LOG_FILE"

  # System checks
  step "System Checks"

  check_root
  success "Running as root"

  check_proxmox
  local pve_version=$(get_proxmox_version)
  success "Proxmox VE ${pve_version}.x detected"

  check_dependencies
  success "All dependencies available"

  echo ""

  # Show menu
  local choice
  choice=$(show_main_menu)

  if [ $? -ne 0 ] || [ -z "$choice" ]; then
    error "Installation cancelled"
    exit 0
  fi

  case "$choice" in
    1)
      run_automatic_installation
      ;;
    2)
      run_advanced_installation
      ;;
    *)
      error "Invalid choice"
      exit 1
      ;;
  esac
}

# ============================================================================
# Run
# ============================================================================

main "$@"
