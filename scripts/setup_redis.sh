#!/bin/bash

# Redis Setup Script for Email & Document Ingestion System
# This script installs and configures Redis with optimized settings

set -e

# Configuration
REDIS_VERSION="7.2"
REDIS_CONF_DIR="/etc/redis"
REDIS_LOG_DIR="/var/log/redis"
REDIS_DATA_DIR="/var/lib/redis"
REDIS_USER="redis"
REDIS_GROUP="redis"

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

# Detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    elif type lsb_release >/dev/null 2>&1; then
        OS=$(lsb_release -si)
        VER=$(lsb_release -sr)
    elif [ -f /etc/lsb-release ]; then
        . /etc/lsb-release
        OS=$DISTRIB_ID
        VER=$DISTRIB_RELEASE
    else
        OS=$(uname -s)
        VER=$(uname -r)
    fi
}

# Install Redis based on OS
install_redis() {
    log_info "Installing Redis..."

    case $OS in
        "Ubuntu"|"Debian GNU/Linux")
            apt-get update
            apt-get install -y redis-server redis-tools
            ;;
        "CentOS Linux"|"Red Hat Enterprise Linux"|"Fedora")
            if [ "$OS" = "CentOS Linux" ] || [ "$OS" = "Red Hat Enterprise Linux" ]; then
                yum install -y epel-release
                yum install -y redis
            else
                dnf install -y redis
            fi
            ;;
        "Darwin")
            if command -v brew >/dev/null 2>&1; then
                brew install redis
            else
                log_error "Homebrew not found. Please install Redis manually."
                exit 1
            fi
            ;;
        *)
            log_error "Unsupported OS: $OS"
            log_info "Please install Redis manually for your operating system."
            exit 1
            ;;
    esac

    log_info "Redis installation completed."
}

# Create Redis user and directories
setup_directories() {
    log_info "Setting up Redis directories and permissions..."

    # Create Redis user if it doesn't exist
    if ! id -u $REDIS_USER >/dev/null 2>&1; then
        useradd --system --shell /bin/false $REDIS_USER
    fi

    # Create directories
    mkdir -p $REDIS_CONF_DIR
    mkdir -p $REDIS_LOG_DIR
    mkdir -p $REDIS_DATA_DIR

    # Set permissions
    chown $REDIS_USER:$REDIS_GROUP $REDIS_LOG_DIR
    chown $REDIS_USER:$REDIS_GROUP $REDIS_DATA_DIR
    chmod 755 $REDIS_CONF_DIR
    chmod 755 $REDIS_LOG_DIR
    chmod 750 $REDIS_DATA_DIR

    log_info "Directories created and permissions set."
}

# Copy configuration files
copy_configs() {
    log_info "Copying Redis configuration files..."

    # Get the script's directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

    # Copy base configuration
    if [ -f "$PROJECT_ROOT/config/redis.conf" ]; then
        cp "$PROJECT_ROOT/config/redis.conf" "$REDIS_CONF_DIR/redis.conf"
        chown $REDIS_USER:$REDIS_GROUP "$REDIS_CONF_DIR/redis.conf"
        chmod 644 "$REDIS_CONF_DIR/redis.conf"
    else
        log_warn "Base Redis configuration not found at $PROJECT_ROOT/config/redis.conf"
    fi

    # Copy environment-specific configuration
    ENV="${ENVIRONMENT:-development}"
    ENV_CONFIG="$PROJECT_ROOT/config/environments/redis.$ENV.conf"

    if [ -f "$ENV_CONFIG" ]; then
        cp "$ENV_CONFIG" "$REDIS_CONF_DIR/redis.$ENV.conf"
        chown $REDIS_USER:$REDIS_GROUP "$REDIS_CONF_DIR/redis.$ENV.conf"
        chmod 644 "$REDIS_CONF_DIR/redis.$ENV.conf"
    else
        log_warn "Environment-specific Redis configuration not found at $ENV_CONFIG"
    fi

    log_info "Configuration files copied."
}

# Configure systemd service (for Linux)
setup_systemd() {
    if [ "$OS" = "Darwin" ]; then
        log_info "Skipping systemd setup on macOS."
        return
    fi

    log_info "Setting up systemd service..."

    cat > /etc/systemd/system/redis-server.service << EOF
[Unit]
Description=Redis In-Memory Data Store
After=network.target
Documentation=http://redis.io/documentation

[Service]
Type=notify
User=$REDIS_USER
Group=$REDIS_GROUP
ExecStart=/usr/bin/redis-server $REDIS_CONF_DIR/redis.conf
ExecStop=/usr/bin/redis-cli shutdown
Restart=always
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    systemctl daemon-reload

    # Enable and start Redis service
    systemctl enable redis-server
    systemctl start redis-server

    log_info "Systemd service configured and started."
}

# Configure launchd service (for macOS)
setup_launchd() {
    if [ "$OS" != "Darwin" ]; then
        return
    fi

    log_info "Setting up launchd service for macOS..."

    cat > ~/Library/LaunchAgents/homebrew.mxcl.redis.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>homebrew.mxcl.redis</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/opt/redis/bin/redis-server</string>
        <string>/usr/local/etc/redis.conf</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>/usr/local</string>
</dict>
</plist>
EOF

    # Load the service
    launchctl load ~/Library/LaunchAgents/homebrew.mxcl.redis.plist

    log_info "launchd service configured and started."
}

# Test Redis installation
test_redis() {
    log_info "Testing Redis installation..."

    # Wait a moment for Redis to start
    sleep 2

    # Test connection
    if redis-cli ping >/dev/null 2>&1; then
        log_info "Redis is running and responding to ping."
    else
        log_error "Redis is not responding to ping. Check the logs."
        exit 1
    fi

    # Test basic operations
    if redis-cli set test_key "test_value" >/dev/null 2>&1; then
        if [ "$(redis-cli get test_key)" = "test_value" ]; then
            log_info "Redis basic operations are working correctly."
            redis-cli del test_key >/dev/null
        else
            log_error "Redis set/get operations failed."
            exit 1
        fi
    else
        log_error "Could not set test key in Redis."
        exit 1
    fi
}

# Main setup function
main() {
    log_info "Starting Redis setup for Email & Document Ingestion System..."

    detect_os
    log_info "Detected OS: $OS"

    # Check if Redis is already installed
    if command -v redis-server >/dev/null 2>&1; then
        log_info "Redis is already installed. Skipping installation."
    else
        install_redis
    fi

    setup_directories
    copy_configs

    if [ "$OS" = "Darwin" ]; then
        setup_launchd
    else
        setup_systemd
    fi

    test_redis

    log_info "Redis setup completed successfully!"
    log_info "Redis is running and ready to use."
    log_info ""
    log_info "Next steps:"
    log_info "1. Update your environment variables in .env file:"
    log_info "   REDIS_HOST=localhost"
    log_info "   REDIS_PORT=6379"
    log_info "   REDIS_PASSWORD=your_secure_password"
    log_info "   REDIS_DB=0"
    log_info ""
    log_info "2. Test your application with Redis"
    log_info "3. Monitor Redis logs at $REDIS_LOG_DIR/redis-server.log"
}

# Run main function with error handling
trap 'log_error "Setup failed. Check the logs for details."' ERR
main "$@"
