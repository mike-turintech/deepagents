#!/bin/bash
#
# Cron Setup Script for Natura Parga Article Generator
# 
# This script helps you set up automatic article generation on macOS/Linux
# using cron. It will detect your Python environment and configure a
# crontab entry to run the article generator every 2 days.
#
# Usage:
#   ./scripts/setup_cron.sh          # Install cron job
#   ./scripts/setup_cron.sh install  # Install cron job
#   ./scripts/setup_cron.sh remove   # Remove cron job
#   ./scripts/setup_cron.sh status   # Check if cron job is installed
#

set -e

# ============================================================
# Configuration
# ============================================================

# Unique identifier for our cron job (used to find/remove it)
CRON_MARKER="# NATURA_PARGA_ARTICLE_GENERATOR"

# Schedule: Run at a morning hour (8-11 AM) every 2 days
# Using hour 9 as default, can be customized
CRON_HOUR="${CRON_HOUR:-9}"
CRON_MINUTE="${CRON_MINUTE:-0}"

# ============================================================
# Color Output
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================================
# Path Detection
# ============================================================

detect_project_dir() {
    # Get the directory where this script is located
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    
    # Project root is one directory up from scripts/
    PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
    
    # Verify run_article.py exists
    if [[ ! -f "$PROJECT_DIR/run_article.py" ]]; then
        error "Cannot find run_article.py in $PROJECT_DIR"
        error "Make sure this script is in the scripts/ directory of the project"
        exit 1
    fi
    
    info "Project directory: $PROJECT_DIR"
}

detect_python() {
    # Check for virtual environment in order of preference
    if [[ -f "$PROJECT_DIR/venv/bin/python" ]]; then
        PYTHON_PATH="$PROJECT_DIR/venv/bin/python"
        info "Found virtual environment: $PYTHON_PATH"
    elif [[ -f "$PROJECT_DIR/.venv/bin/python" ]]; then
        PYTHON_PATH="$PROJECT_DIR/.venv/bin/python"
        info "Found virtual environment: $PYTHON_PATH"
    elif command -v python3 &> /dev/null; then
        PYTHON_PATH="$(which python3)"
        warn "Using system Python: $PYTHON_PATH"
        warn "Consider using a virtual environment for isolation"
    elif command -v python &> /dev/null; then
        PYTHON_PATH="$(which python)"
        warn "Using system Python: $PYTHON_PATH"
        warn "Consider using a virtual environment for isolation"
    else
        error "Could not find Python installation"
        error "Please install Python 3.11+ or create a virtual environment"
        exit 1
    fi
    
    # Verify Python version
    PYTHON_VERSION=$("$PYTHON_PATH" --version 2>&1 | cut -d' ' -f2)
    info "Python version: $PYTHON_VERSION"
}

# ============================================================
# Cron Management
# ============================================================

get_cron_entry() {
    # Build the cron entry
    # Schedule: minute hour */2 * * (every 2 days)
    local log_file="$PROJECT_DIR/logs/scheduled_runs.log"
    
    echo "$CRON_MINUTE $CRON_HOUR */2 * * cd \"$PROJECT_DIR\" && \"$PYTHON_PATH\" run_article.py >> \"$log_file\" 2>&1 $CRON_MARKER"
}

check_cron_installed() {
    if crontab -l 2>/dev/null | grep -q "$CRON_MARKER"; then
        return 0
    else
        return 1
    fi
}

install_cron() {
    detect_project_dir
    detect_python
    
    # Create logs directory if it doesn't exist
    mkdir -p "$PROJECT_DIR/logs"
    
    if check_cron_installed; then
        warn "Cron job already installed!"
        echo ""
        echo "Current cron entry:"
        crontab -l 2>/dev/null | grep "$CRON_MARKER"
        echo ""
        read -p "Do you want to reinstall it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Keeping existing cron job"
            exit 0
        fi
        # Remove existing entry before adding new one
        remove_cron_quiet
    fi
    
    # Generate new cron entry
    local cron_entry
    cron_entry=$(get_cron_entry)
    
    echo ""
    echo "The following cron entry will be added:"
    echo ""
    echo -e "${YELLOW}$cron_entry${NC}"
    echo ""
    echo "This will run the article generator every 2 days at ${CRON_HOUR}:$(printf '%02d' $CRON_MINUTE) AM"
    echo "Output will be logged to: $PROJECT_DIR/logs/scheduled_runs.log"
    echo ""
    
    read -p "Install this cron job? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Add to crontab
        (crontab -l 2>/dev/null || true; echo "$cron_entry") | crontab -
        
        if check_cron_installed; then
            success "Cron job installed successfully!"
            echo ""
            echo "To verify the installation, run:"
            echo "  crontab -l"
            echo ""
            echo "To test the script manually, run:"
            echo "  cd $PROJECT_DIR && python run_article.py --dry-run"
            echo ""
            echo "To view logs:"
            echo "  tail -f $PROJECT_DIR/logs/scheduled_runs.log"
        else
            error "Failed to install cron job"
            exit 1
        fi
    else
        info "Installation cancelled"
    fi
}

remove_cron_quiet() {
    # Remove without prompts (internal use)
    crontab -l 2>/dev/null | grep -v "$CRON_MARKER" | crontab - 2>/dev/null || true
}

remove_cron() {
    detect_project_dir
    
    if ! check_cron_installed; then
        info "No Natura Parga cron job found"
        exit 0
    fi
    
    echo "The following cron entry will be removed:"
    echo ""
    crontab -l 2>/dev/null | grep "$CRON_MARKER"
    echo ""
    
    read -p "Remove this cron job? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        remove_cron_quiet
        
        if ! check_cron_installed; then
            success "Cron job removed successfully!"
        else
            error "Failed to remove cron job"
            exit 1
        fi
    else
        info "Removal cancelled"
    fi
}

show_status() {
    detect_project_dir
    
    echo ""
    echo "Natura Parga Article Generator - Cron Status"
    echo "============================================="
    echo ""
    
    if check_cron_installed; then
        success "Cron job is INSTALLED"
        echo ""
        echo "Current entry:"
        crontab -l 2>/dev/null | grep "$CRON_MARKER"
        echo ""
        
        # Check if log file exists
        local log_file="$PROJECT_DIR/logs/scheduled_runs.log"
        if [[ -f "$log_file" ]]; then
            echo "Log file exists: $log_file"
            echo "Last 5 lines of log:"
            echo "---"
            tail -5 "$log_file" 2>/dev/null || echo "(empty)"
            echo "---"
        else
            echo "Log file: $log_file (not yet created - will be created on first run)"
        fi
    else
        warn "Cron job is NOT installed"
        echo ""
        echo "To install, run:"
        echo "  ./scripts/setup_cron.sh install"
    fi
    echo ""
}

# ============================================================
# Help
# ============================================================

show_help() {
    echo "Natura Parga Article Generator - Cron Setup Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  install   Install the cron job (default if no command given)"
    echo "  remove    Remove the cron job"
    echo "  status    Check if cron job is installed"
    echo "  help      Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  CRON_HOUR     Hour to run (0-23, default: 9)"
    echo "  CRON_MINUTE   Minute to run (0-59, default: 0)"
    echo ""
    echo "Examples:"
    echo "  # Install with default schedule (9:00 AM every 2 days)"
    echo "  ./scripts/setup_cron.sh"
    echo ""
    echo "  # Install with custom time (10:30 AM every 2 days)"
    echo "  CRON_HOUR=10 CRON_MINUTE=30 ./scripts/setup_cron.sh"
    echo ""
    echo "  # Remove the cron job"
    echo "  ./scripts/setup_cron.sh remove"
}

# ============================================================
# Main
# ============================================================

main() {
    local command="${1:-install}"
    
    case "$command" in
        install)
            install_cron
            ;;
        remove|uninstall)
            remove_cron
            ;;
        status)
            show_status
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            error "Unknown command: $command"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
