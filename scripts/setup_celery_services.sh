#!/bin/bash

# Celery Services Setup Script for Email & Document Ingestion System
# This script installs and configures Celery worker and beat services

set -e

# Configuration
PROJECT_DIR="/app"
SERVICE_USER="celery"
SERVICE_GROUP="celery"
CELERY_DATA_DIR="/var/lib/celery"
CELERY_LOG_DIR="/var/log/celery"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "Please run this script as root or with sudo"
        exit 1
    fi
}

# Create celery user if it doesn't exist
create_celery_user() {
    log_info "Creating celery user and group..."

    if ! id -u $SERVICE_USER >/dev/null 2>&1; then
        useradd --system --shell /bin/false $SERVICE_USER
        log_info "Created user: $SERVICE_USER"
    else
        log_info "User $SERVICE_USER already exists"
    fi

    if ! getent group $SERVICE_GROUP >/dev/null 2>&1; then
        groupadd --system $SERVICE_GROUP
        log_info "Created group: $SERVICE_GROUP"
    else
        log_info "Group $SERVICE_GROUP already exists"
    fi

    # Ensure user is in the correct group
    usermod -a -G $SERVICE_GROUP $SERVICE_USER
}

# Create directories and set permissions
setup_directories() {
    log_info "Setting up directories and permissions..."

    # Create directories
    mkdir -p $CELERY_DATA_DIR
    mkdir -p $CELERY_LOG_DIR

    # Set ownership
    chown -R $SERVICE_USER:$SERVICE_GROUP $CELERY_DATA_DIR
    chown -R $SERVICE_USER:$SERVICE_GROUP $CELERY_LOG_DIR

    # Set permissions
    chmod 755 $CELERY_DATA_DIR
    chmod 755 $CELERY_LOG_DIR

    log_info "Directories created and permissions set."
}

# Copy service files
install_service_files() {
    log_info "Installing systemd service files..."

    # Get the script's directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

    # Copy service files to systemd directory
    cp "$SCRIPT_DIR/celery-worker.service" /etc/systemd/system/
    cp "$SCRIPT_DIR/celery-beat.service" /etc/systemd/system/

    # Set correct permissions
    chmod 644 /etc/systemd/system/celery-worker.service
    chmod 644 /etc/systemd/system/celery-beat.service

    log_info "Service files installed."
}

# Configure log rotation
setup_log_rotation() {
    log_info "Setting up log rotation..."

    cat > /etc/logrotate.d/celery << EOF
$CELERY_LOG_DIR/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 0644 $SERVICE_USER $SERVICE_GROUP
    postrotate
        systemctl reload celery-worker.service
        systemctl reload celery-beat.service
    endscript
}
EOF

    log_info "Log rotation configured."
}

# Test services
test_services() {
    log_info "Testing service configuration..."

    # Reload systemd
    systemctl daemon-reload

    # Check service files
    if systemctl list-unit-files | grep -q celery-worker.service; then
        log_info "Celery worker service file is valid"
    else
        log_error "Celery worker service file is not valid"
        exit 1
    fi

    if systemctl list-unit-files | grep -q celery-beat.service; then
        log_info "Celery beat service file is valid"
    else
        log_error "Celery beat service file is not valid"
        exit 1
    fi

    log_info "Service configuration is valid."
}

# Start services
start_services() {
    log_info "Starting Celery services..."

    # Enable services
    systemctl enable celery-worker.service
    systemctl enable celery-beat.service

    # Start services
    systemctl start celery-worker.service
    systemctl start celery-beat.service

    # Wait a moment and check status
    sleep 2

    if systemctl is-active --quiet celery-worker.service; then
        log_info "Celery worker service started successfully"
    else
        log_warn "Celery worker service failed to start. Check logs with: journalctl -u celery-worker"
    fi

    if systemctl is-active --quiet celery-beat.service; then
        log_info "Celery beat service started successfully"
    else
        log_warn "Celery beat service failed to start. Check logs with: journalctl -u celery-beat"
    fi
}

# Print service management commands
print_usage() {
    log_info "Celery services setup completed!"
    echo ""
    log_info "Service management commands:"
    echo "  Start services:    systemctl start celery-worker celery-beat"
    echo "  Stop services:     systemctl stop celery-worker celery-beat"
    echo "  Restart services:  systemctl restart celery-worker celery-beat"
    echo "  Check status:      systemctl status celery-worker celery-beat"
    echo "  View logs:         journalctl -u celery-worker"
    echo "                    journalctl -u celery-beat"
    echo "  Follow logs:       journalctl -u celery-worker -f"
    echo ""
    log_info "Manual testing commands:"
    echo "  Test worker:       python -m celery -A workers.celery_app worker --help"
    echo "  Test beat:         python -m celery -A workers.celery_app beat --help"
    echo "  List queues:       python -m celery -A workers.celery_app inspect registered"
}

# Main setup function
main() {
    log_info "Starting Celery services setup for Email & Document Ingestion System..."

    check_root
    create_celery_user
    setup_directories
    install_service_files
    setup_log_rotation
    test_services
    start_services
    print_usage
}

# Run main function with error handling
trap 'log_error "Setup failed. Check the logs for details."' ERR
main "$@"
