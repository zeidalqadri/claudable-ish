#!/bin/bash

# Claudable Management Script
# Comprehensive tool for managing Claudable development environment

set -euo pipefail

# Configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PID_FILE="$SCRIPT_DIR/.claudable.pid"
readonly LOG_DIR="$SCRIPT_DIR/logs"
readonly API_LOG_FILE="$LOG_DIR/api.log"
readonly WEB_LOG_FILE="$LOG_DIR/web.log"
readonly MAIN_LOG_FILE="$LOG_DIR/claudable.log"
readonly ENV_FILE="$SCRIPT_DIR/.env"
readonly PROJECTS_DIR="$SCRIPT_DIR/data/projects"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[0;33m'
readonly BLUE='\033[0;34m'
readonly MAGENTA='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly WHITE='\033[0;37m'
readonly BOLD='\033[1m'
readonly NC='\033[0m' # No Color

# Default values
DEFAULT_WEB_PORT=8383
DEFAULT_API_PORT=8082

# Print colored output
print_colored() {
    local color=$1
    shift
    echo -e "${color}$*${NC}"
}

# Print banner
print_banner() {
    print_colored "$MAGENTA" "
██████╗██╗      █████╗ ██╗   ██╗██████╗  █████╗ ██████╗ ██╗     ███████╗
██╔════╝██║     ██╔══██╗██║   ██║██╔══██╗██╔══██╗██╔══██╗██║     ██╔════╝
██║     ██║     ███████║██║   ██║██║  ██║███████║██████╔╝██║     █████╗  
██║     ██║     ██╔══██║██║   ██║██║  ██║██╔══██║██╔══██╗██║     ██╔══╝  
╚██████╗███████╗██║  ██║╚██████╔╝██████╔╝██║  ██║██████╔╝███████╗███████╗
 ╚═════╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝╚══════╝
"
    print_colored "$CYAN" "    Management Script - Build what you want. Deploy instantly."
    echo
}

# Show usage information
show_usage() {
    print_colored "$WHITE" "${BOLD}USAGE:${NC}"
    echo "  $0 <command> [options]"
    echo
    print_colored "$WHITE" "${BOLD}COMMANDS:${NC}"
    echo "  start     Start Claudable services"
    echo "  stop      Stop all Claudable processes"
    echo "  restart   Restart all services"
    echo "  status    Show current service status"
    echo "  logs      Show logs (--follow for real-time)"
    echo "  clean     Clean dependencies and build artifacts"
    echo "  reset     Reset database and clean state"
    echo "  backup    Backup database"
    echo "  health    Check service health"
    echo "  watch     Monitor services and auto-restart"
    echo "  projects  List and manage projects"
    echo "  rebuild   Clean and rebuild everything"
    echo "  debug     Start in debug mode with verbose logging"
    echo "  doctor    Comprehensive health check and fixes"
    echo "  help      Show this help message"
    echo
    print_colored "$WHITE" "${BOLD}OPTIONS:${NC}"
    echo "  --port <port>     Set custom web port (default: $DEFAULT_WEB_PORT)"
    echo "  --api-port <port> Set custom API port (default: $DEFAULT_API_PORT)"
    echo "  --follow          Follow logs in real-time"
    echo "  --background      Run services in background"
    echo "  --no-browser      Don't auto-open browser"
    echo
    print_colored "$WHITE" "${BOLD}EXAMPLES:${NC}"
    echo "  $0 start                    # Start with default ports"
    echo "  $0 start --port 9000        # Start with custom web port"
    echo "  $0 restart --background     # Restart in background"
    echo "  $0 logs --follow            # Follow logs in real-time"
    echo "  $0 status                   # Check service status"
}

# Check if port is available
is_port_available() {
    local port=$1
    ! lsof -i :$port > /dev/null 2>&1
}

# Find available port starting from given port
find_available_port() {
    local start_port=$1
    local port=$start_port
    
    while ! is_port_available $port; do
        ((port++))
    done
    
    echo $port
}

# Get PIDs from file
get_pids() {
    if [[ -f "$PID_FILE" ]]; then
        cat "$PID_FILE" | grep -v "^$" || true
    fi
}

# Save PID to file
save_pid() {
    echo "$1" >> "$PID_FILE"
}

# Clean PID file
clean_pids() {
    > "$PID_FILE"
}

# Check if process is running
is_process_running() {
    local pid=$1
    kill -0 "$pid" 2>/dev/null
}

# Get process info
get_process_info() {
    local pid=$1
    if is_process_running "$pid"; then
        ps -p "$pid" -o pid,ppid,cmd --no-headers 2>/dev/null | head -1
    fi
}

# Kill process tree
kill_process_tree() {
    local pid=$1
    local signal=${2:-TERM}
    
    if is_process_running "$pid"; then
        # Get all child processes
        local children=$(pgrep -P "$pid" 2>/dev/null || true)
        
        # Kill children first
        for child in $children; do
            kill_process_tree "$child" "$signal"
        done
        
        # Kill the parent
        print_colored "$YELLOW" "Killing process $pid..."
        kill -$signal "$pid" 2>/dev/null || true
        
        # Wait a bit for graceful shutdown
        if [[ "$signal" == "TERM" ]]; then
            sleep 2
            if is_process_running "$pid"; then
                print_colored "$RED" "Force killing process $pid..."
                kill -KILL "$pid" 2>/dev/null || true
            fi
        fi
    fi
}

# Log rotation helper
rotate_log() {
    local log_file=$1
    local max_size=${2:-10485760}  # 10MB default
    
    if [[ -f "$log_file" ]] && [[ $(stat -f%z "$log_file" 2>/dev/null || stat -c%s "$log_file" 2>/dev/null || echo 0) -gt $max_size ]]; then
        mv "$log_file" "${log_file}.old"
        touch "$log_file"
        print_colored "$YELLOW" "Rotated log file: $log_file"
    fi
}

# Write timestamped log entry
write_log() {
    local message="$1"
    local log_file="${2:-$MAIN_LOG_FILE}"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    rotate_log "$log_file"
    echo "[$timestamp] $message" >> "$log_file"
}

# Check if service is responsive
check_service_health() {
    local port=$1
    local service_name=$2
    local timeout=${3:-5}
    
    if timeout "$timeout" curl -s "http://localhost:$port" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Get memory usage for PID
get_memory_usage() {
    local pid=$1
    if is_process_running "$pid"; then
        ps -p "$pid" -o rss= 2>/dev/null | awk '{print int($1/1024)"MB"}'
    else
        echo "N/A"
    fi
}

# Get CPU usage for PID
get_cpu_usage() {
    local pid=$1
    if is_process_running "$pid"; then
        ps -p "$pid" -o %cpu= 2>/dev/null | awk '{print $1"%"}'
    else
        echo "N/A"
    fi
}

# Get current ports from .env file
get_current_ports() {
    local web_port=$DEFAULT_WEB_PORT
    local api_port=$DEFAULT_API_PORT
    
    if [[ -f "$ENV_FILE" ]]; then
        if grep -q "WEB_PORT=" "$ENV_FILE"; then
            web_port=$(grep "WEB_PORT=" "$ENV_FILE" | cut -d'=' -f2)
        fi
        if grep -q "API_PORT=" "$ENV_FILE"; then
            api_port=$(grep "API_PORT=" "$ENV_FILE" | cut -d'=' -f2)
        fi
    fi
    
    echo "$web_port $api_port"
}

# Start Claudable services
start_claudable() {
    local web_port=$DEFAULT_WEB_PORT
    local api_port=$DEFAULT_API_PORT
    local background=false
    local no_browser=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --port)
                web_port="$2"
                shift 2
                ;;
            --api-port)
                api_port="$2"
                shift 2
                ;;
            --background)
                background=true
                shift
                ;;
            --no-browser)
                no_browser=true
                shift
                ;;
            *)
                shift
                ;;
        esac
    done
    
    print_colored "$GREEN" "${BOLD}Starting Claudable...${NC}"
    
    # Check if already running
    local pids=$(get_pids)
    if [[ -n "$pids" ]]; then
        local running_pids=""
        for pid in $pids; do
            if is_process_running "$pid"; then
                running_pids="$running_pids $pid"
            fi
        done
        
        if [[ -n "$running_pids" ]]; then
            print_colored "$YELLOW" "Claudable is already running (PIDs:$running_pids)"
            print_colored "$CYAN" "Use '$0 stop' to stop, or '$0 restart' to restart"
            return 1
        else
            clean_pids
        fi
    fi
    
    # Find available ports if needed
    if ! is_port_available "$web_port"; then
        local new_port=$(find_available_port "$web_port")
        print_colored "$YELLOW" "Port $web_port is busy, using $new_port for web"
        web_port=$new_port
    fi
    
    if ! is_port_available "$api_port"; then
        local new_port=$(find_available_port "$api_port")
        print_colored "$YELLOW" "Port $api_port is busy, using $new_port for API"
        api_port=$new_port
    fi
    
    # Update .env file with ports
    if [[ -f "$ENV_FILE" ]]; then
        sed -i.bak "s/WEB_PORT=.*/WEB_PORT=$web_port/" "$ENV_FILE"
        sed -i.bak "s/API_PORT=.*/API_PORT=$api_port/" "$ENV_FILE"
    fi
    
    # Set browser environment variable
    if [[ "$no_browser" == true ]]; then
        export BROWSER=false
    fi
    
    # Start services
    cd "$SCRIPT_DIR"
    
    if [[ "$background" == true ]]; then
        print_colored "$BLUE" "Starting services in background..."
        write_log "Starting Claudable services (Web: $web_port, API: $api_port)"
        nohup npm run dev > "$MAIN_LOG_FILE" 2>&1 &
        local main_pid=$!
        save_pid "$main_pid"
        
        # Wait a bit for services to start
        sleep 5
        
        print_colored "$GREEN" "✅ Claudable started in background"
        print_colored "$CYAN" "   Web: http://localhost:$web_port"
        print_colored "$CYAN" "   API: http://localhost:$api_port"
        print_colored "$YELLOW" "   Logs: tail -f $MAIN_LOG_FILE"
        write_log "Services started successfully"
    else
        print_colored "$BLUE" "Starting services (press Ctrl+C to stop)..."
        print_colored "$CYAN" "   Web: http://localhost:$web_port"
        print_colored "$CYAN" "   API: http://localhost:$api_port"
        echo
        
        # Run in foreground and capture PID
        npm run dev &
        local main_pid=$!
        save_pid "$main_pid"
        
        # Wait for the process
        wait "$main_pid"
    fi
}

# Stop Claudable services
stop_claudable() {
    print_colored "$RED" "${BOLD}Stopping Claudable...${NC}"
    
    local pids=$(get_pids)
    if [[ -z "$pids" ]]; then
        print_colored "$YELLOW" "No Claudable processes found"
        return 0
    fi
    
    local stopped_any=false
    for pid in $pids; do
        if is_process_running "$pid"; then
            local info=$(get_process_info "$pid")
            print_colored "$YELLOW" "Stopping: $info"
            kill_process_tree "$pid" "TERM"
            stopped_any=true
        fi
    done
    
    # Clean up any remaining npm/node processes related to Claudable
    print_colored "$YELLOW" "Cleaning up remaining processes..."
    pkill -f "claudable\|cc-lovable" 2>/dev/null || true
    
    # Clean PID file
    clean_pids
    
    if [[ "$stopped_any" == true ]]; then
        print_colored "$GREEN" "✅ Claudable stopped"
    else
        print_colored "$YELLOW" "No running processes found"
    fi
}

# Restart Claudable services
restart_claudable() {
    print_colored "$BLUE" "${BOLD}Restarting Claudable...${NC}"
    
    stop_claudable
    sleep 2
    start_claudable "$@"
}

# Show service status
show_status() {
    print_colored "$BLUE" "${BOLD}Claudable Status:${NC}"
    echo
    
    local ports=$(get_current_ports)
    local web_port=$(echo $ports | cut -d' ' -f1)
    local api_port=$(echo $ports | cut -d' ' -f2)
    
    print_colored "$WHITE" "Configuration:"
    print_colored "$CYAN" "  Web Port: $web_port"
    print_colored "$CYAN" "  API Port: $api_port"
    print_colored "$CYAN" "  Log Dir: $LOG_DIR"
    echo
    
    local pids=$(get_pids)
    if [[ -z "$pids" ]]; then
        print_colored "$RED" "Status: Not Running"
        return 0
    fi
    
    print_colored "$WHITE" "Running Processes:"
    local running_count=0
    for pid in $pids; do
        if is_process_running "$pid"; then
            local info=$(get_process_info "$pid")
            local memory=$(get_memory_usage "$pid")
            local cpu=$(get_cpu_usage "$pid")
            print_colored "$GREEN" "  ✓ PID: $pid, Memory: $memory, CPU: $cpu"
            print_colored "$WHITE" "    $(echo "$info" | awk '{$1=$2=""; print substr($0,3)}')"
            ((running_count++))
        else
            print_colored "$RED" "  ✗ Dead process: $pid"
        fi
    done
    
    if [[ $running_count -gt 0 ]]; then
        print_colored "$GREEN" "Status: Running ($running_count processes)"
        
        # Check if ports are responding
        print_colored "$WHITE" "Service Health:"
        if curl -s "http://localhost:$api_port/docs" > /dev/null; then
            print_colored "$GREEN" "  ✓ API responding on port $api_port"
        else
            print_colored "$RED" "  ✗ API not responding on port $api_port"
        fi
        
        if curl -s "http://localhost:$web_port" > /dev/null; then
            print_colored "$GREEN" "  ✓ Web responding on port $web_port"
        else
            print_colored "$RED" "  ✗ Web not responding on port $web_port"
        fi
    else
        print_colored "$RED" "Status: Not Running (stale PID file)"
        clean_pids
    fi
}

# Show logs
show_logs() {
    local follow=false
    local service="all"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --follow|-f)
                follow=true
                shift
                ;;
            --service|-s)
                service="$2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done
    
    local log_files=()
    case $service in
        "api")
            log_files=("$API_LOG_FILE")
            ;;
        "web")
            log_files=("$WEB_LOG_FILE")
            ;;
        "main"|"claudable")
            log_files=("$MAIN_LOG_FILE")
            ;;
        *)
            log_files=("$MAIN_LOG_FILE" "$API_LOG_FILE" "$WEB_LOG_FILE")
            ;;
    esac
    
    # Check if any log files exist
    local existing_files=()
    for log_file in "${log_files[@]}"; do
        if [[ -f "$log_file" ]]; then
            existing_files+=("$log_file")
        fi
    done
    
    if [[ ${#existing_files[@]} -eq 0 ]]; then
        print_colored "$YELLOW" "No log files found"
        print_colored "$CYAN" "Logs are only available when running in background mode"
        return 0
    fi
    
    if [[ "$follow" == true ]]; then
        print_colored "$BLUE" "Following logs (press Ctrl+C to stop):"
        if [[ ${#existing_files[@]} -eq 1 ]]; then
            tail -f "${existing_files[0]}"
        else
            tail -f "${existing_files[@]}"
        fi
    else
        print_colored "$BLUE" "Recent logs:"
        for log_file in "${existing_files[@]}"; do
            if [[ ${#existing_files[@]} -gt 1 ]]; then
                print_colored "$CYAN" "\n=== $(basename "$log_file") ==="
            fi
            tail -50 "$log_file"
        done
    fi
}

# Clean project
clean_project() {
    print_colored "$YELLOW" "${BOLD}Cleaning Claudable...${NC}"
    
    # Stop services first
    stop_claudable
    
    # Run the clean script
    cd "$SCRIPT_DIR"
    npm run clean
    
    # Clean additional files
    print_colored "$YELLOW" "Cleaning additional files..."
    rm -f "$PID_FILE" .env.bak
    if [[ -d "$LOG_DIR" ]]; then
        rm -rf "$LOG_DIR"
        mkdir -p "$LOG_DIR"
    fi
    
    print_colored "$GREEN" "✅ Clean complete!"
}

# Reset database and state
reset_claudable() {
    print_colored "$YELLOW" "${BOLD}Resetting Claudable...${NC}"
    
    print_colored "$RED" "This will delete all data and reset the database."
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_colored "$CYAN" "Reset cancelled"
        return 0
    fi
    
    # Stop services
    stop_claudable
    
    # Backup first
    backup_database
    
    # Run reset
    cd "$SCRIPT_DIR"
    npm run db:reset
    
    print_colored "$GREEN" "✅ Reset complete!"
}

# Backup database
backup_database() {
    print_colored "$BLUE" "${BOLD}Backing up database...${NC}"
    
    cd "$SCRIPT_DIR"
    npm run db:backup
    
    print_colored "$GREEN" "✅ Backup complete!"
}

# Health check
health_check() {
    print_colored "$BLUE" "${BOLD}Health Check:${NC}"
    echo
    
    # Check Node.js version
    if command -v node >/dev/null 2>&1; then
        local node_version=$(node --version)
        print_colored "$GREEN" "✓ Node.js: $node_version"
    else
        print_colored "$RED" "✗ Node.js not found"
    fi
    
    # Check npm version
    if command -v npm >/dev/null 2>&1; then
        local npm_version=$(npm --version)
        print_colored "$GREEN" "✓ npm: v$npm_version"
    else
        print_colored "$RED" "✗ npm not found"
    fi
    
    # Check Python version
    if command -v python3 >/dev/null 2>&1; then
        local python_version=$(python3 --version)
        print_colored "$GREEN" "✓ Python: $python_version"
    else
        print_colored "$RED" "✗ Python3 not found"
    fi
    
    # Check project structure
    if [[ -f "$SCRIPT_DIR/package.json" ]]; then
        print_colored "$GREEN" "✓ Project structure"
    else
        print_colored "$RED" "✗ Invalid project structure"
    fi
    
    # Check dependencies
    if [[ -d "$SCRIPT_DIR/node_modules" ]]; then
        print_colored "$GREEN" "✓ Node dependencies installed"
    else
        print_colored "$YELLOW" "⚠ Node dependencies not installed (run: npm install)"
    fi
    
    if [[ -d "$SCRIPT_DIR/apps/api/.venv" ]]; then
        print_colored "$GREEN" "✓ Python virtual environment"
    else
        print_colored "$YELLOW" "⚠ Python virtual environment not found"
    fi
    
    # Check ports
    local ports=$(get_current_ports)
    local web_port=$(echo $ports | cut -d' ' -f1)
    local api_port=$(echo $ports | cut -d' ' -f2)
    
    if is_port_available "$web_port"; then
        print_colored "$GREEN" "✓ Web port $web_port available"
    else
        print_colored "$YELLOW" "⚠ Web port $web_port in use"
    fi
    
    if is_port_available "$api_port"; then
        print_colored "$GREEN" "✓ API port $api_port available"
    else
        print_colored "$YELLOW" "⚠ API port $api_port in use"
    fi
}

# Watch and monitor services
watch_services() {
    local interval=30
    local auto_restart=true
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --interval|-i)
                interval="$2"
                shift 2
                ;;
            --no-restart)
                auto_restart=false
                shift
                ;;
            *)
                shift
                ;;
        esac
    done
    
    print_colored "$BLUE" "${BOLD}Monitoring Claudable services...${NC}"
    print_colored "$CYAN" "Check interval: ${interval}s, Auto-restart: $auto_restart"
    print_colored "$YELLOW" "Press Ctrl+C to stop monitoring"
    echo
    
    while true; do
        local pids=$(get_pids)
        local restart_needed=false
        
        if [[ -z "$pids" ]]; then
            print_colored "$RED" "$(date): No services running"
            restart_needed=true
        else
            local running_count=0
            for pid in $pids; do
                if is_process_running "$pid"; then
                    ((running_count++))
                else
                    print_colored "$RED" "$(date): Dead process detected: $pid"
                    restart_needed=true
                fi
            done
            
            if [[ $running_count -gt 0 ]]; then
                print_colored "$GREEN" "$(date): $running_count processes running"
                
                # Check service health
                local ports=$(get_current_ports)
                local web_port=$(echo $ports | cut -d' ' -f1)
                local api_port=$(echo $ports | cut -d' ' -f2)
                
                if ! check_service_health "$web_port" "Web"; then
                    print_colored "$RED" "$(date): Web service not responding on port $web_port"
                    restart_needed=true
                fi
                
                if ! check_service_health "$api_port" "API"; then
                    print_colored "$RED" "$(date): API service not responding on port $api_port"
                    restart_needed=true
                fi
            fi
        fi
        
        if [[ "$restart_needed" == true && "$auto_restart" == true ]]; then
            print_colored "$YELLOW" "$(date): Restarting services..."
            write_log "Auto-restarting services due to health check failure"
            restart_claudable --background
            sleep 10  # Give extra time for restart
        fi
        
        sleep "$interval"
    done
}

# List and manage projects
manage_projects() {
    local action="${1:-list}"
    shift 2>/dev/null || true
    
    case $action in
        "list"|"ls")
            print_colored "$BLUE" "${BOLD}Claudable Projects:${NC}"
            echo
            
            if [[ ! -d "$PROJECTS_DIR" ]]; then
                print_colored "$YELLOW" "No projects directory found"
                return 0
            fi
            
            local count=0
            for project_dir in "$PROJECTS_DIR"/*/; do
                if [[ -d "$project_dir" ]]; then
                    local project_name=$(basename "$project_dir")
                    local repo_dir="$project_dir/repo"
                    
                    print_colored "$CYAN" "📁 $project_name"
                    
                    if [[ -f "$repo_dir/package.json" ]]; then
                        local project_info=$(grep -E '"name"|"version"' "$repo_dir/package.json" | head -2)
                        echo "   $project_info" | sed 's/[",]//g' | awk '{print "   " $0}'
                    fi
                    
                    if [[ -d "$repo_dir" ]]; then
                        local size=$(du -sh "$repo_dir" 2>/dev/null | cut -f1)
                        print_colored "$WHITE" "   Size: $size"
                    fi
                    
                    echo
                    ((count++))
                fi
            done
            
            print_colored "$WHITE" "Total projects: $count"
            ;;
            
        "clean")
            local project_id="$1"
            if [[ -z "$project_id" ]]; then
                print_colored "$RED" "Usage: $0 projects clean <project_id>"
                return 1
            fi
            
            local project_dir="$PROJECTS_DIR/$project_id"
            if [[ ! -d "$project_dir" ]]; then
                print_colored "$RED" "Project not found: $project_id"
                return 1
            fi
            
            print_colored "$YELLOW" "Cleaning project: $project_id"
            cd "$project_dir/repo" 2>/dev/null || return 1
            
            if [[ -f "package.json" ]]; then
                rm -rf node_modules package-lock.json
                npm cache clean --force 2>/dev/null || true
                print_colored "$GREEN" "✓ Cleaned Node.js dependencies"
            fi
            
            rm -rf .next dist build
            print_colored "$GREEN" "✓ Cleaned build artifacts"
            ;;
            
        *)
            print_colored "$WHITE" "Available project actions:"
            echo "  list (ls)    List all projects"
            echo "  clean <id>   Clean project dependencies"
            ;;
    esac
}

# Rebuild everything
rebuild_claudable() {
    print_colored "$BLUE" "${BOLD}Rebuilding Claudable...${NC}"
    
    # Stop services
    stop_claudable
    
    # Clean everything
    clean_project
    
    # Reinstall dependencies
    print_colored "$YELLOW" "Reinstalling dependencies..."
    cd "$SCRIPT_DIR"
    npm install
    
    # Setup environment
    if [[ -f "scripts/setup-env.js" ]]; then
        node scripts/setup-env.js
    fi
    
    # Setup Python environment
    if [[ -f "scripts/setup-venv.js" ]]; then
        node scripts/setup-venv.js
    fi
    
    print_colored "$GREEN" "✅ Rebuild complete!"
    print_colored "$CYAN" "You can now start Claudable with: $0 start"
}

# Debug mode
debug_mode() {
    print_colored "$BLUE" "${BOLD}Starting Claudable in Debug Mode...${NC}"
    
    export DEBUG=1
    export NODE_ENV=development
    export VERBOSE=1
    
    print_colored "$YELLOW" "Debug flags enabled:"
    print_colored "$CYAN" "  DEBUG=1"
    print_colored "$CYAN" "  NODE_ENV=development"
    print_colored "$CYAN" "  VERBOSE=1"
    echo
    
    # Start with verbose logging
    start_claudable --no-browser "$@"
}

# Comprehensive health check and fixes
doctor_check() {
    print_colored "$BLUE" "${BOLD}Claudable Doctor - Comprehensive Health Check${NC}"
    echo
    
    local issues_found=0
    local fixes_applied=0
    
    # Check and fix Node.js
    if ! command -v node >/dev/null 2>&1; then
        print_colored "$RED" "✗ Node.js not found"
        print_colored "$YELLOW" "  Please install Node.js from https://nodejs.org/"
        ((issues_found++))
    else
        local node_version=$(node --version)
        local major_version=$(echo "$node_version" | cut -d'.' -f1 | sed 's/v//')
        if [[ $major_version -lt 18 ]]; then
            print_colored "$YELLOW" "⚠ Node.js $node_version (recommend v18+)"
            ((issues_found++))
        else
            print_colored "$GREEN" "✓ Node.js: $node_version"
        fi
    fi
    
    # Check npm
    if ! command -v npm >/dev/null 2>&1; then
        print_colored "$RED" "✗ npm not found"
        ((issues_found++))
    else
        print_colored "$GREEN" "✓ npm: v$(npm --version)"
    fi
    
    # Check project structure
    local required_files=("package.json" "apps/web/package.json" "apps/api/requirements.txt")
    for file in "${required_files[@]}"; do
        if [[ -f "$SCRIPT_DIR/$file" ]]; then
            print_colored "$GREEN" "✓ $file exists"
        else
            print_colored "$RED" "✗ Missing: $file"
            ((issues_found++))
        fi
    done
    
    # Check and fix dependencies
    if [[ ! -d "$SCRIPT_DIR/node_modules" ]]; then
        print_colored "$YELLOW" "⚠ Node dependencies not installed"
        print_colored "$CYAN" "  Running npm install..."
        cd "$SCRIPT_DIR" && npm install
        ((fixes_applied++))
        print_colored "$GREEN" "✓ Dependencies installed"
    else
        print_colored "$GREEN" "✓ Node dependencies installed"
    fi
    
    # Check Python environment
    if [[ ! -d "$SCRIPT_DIR/apps/api/.venv" ]]; then
        print_colored "$YELLOW" "⚠ Python virtual environment missing"
        if command -v python3 >/dev/null 2>&1; then
            print_colored "$CYAN" "  Creating virtual environment..."
            cd "$SCRIPT_DIR/apps/api" && python3 -m venv .venv
            source .venv/bin/activate && pip install -r requirements.txt
            ((fixes_applied++))
            print_colored "$GREEN" "✓ Python environment created"
        else
            print_colored "$RED" "✗ Python3 not found - cannot create virtual environment"
            ((issues_found++))
        fi
    else
        print_colored "$GREEN" "✓ Python virtual environment exists"
    fi
    
    # Check ports
    local ports=$(get_current_ports)
    local web_port=$(echo $ports | cut -d' ' -f1)
    local api_port=$(echo $ports | cut -d' ' -f2)
    
    if is_port_available "$web_port"; then
        print_colored "$GREEN" "✓ Web port $web_port available"
    else
        print_colored "$YELLOW" "⚠ Web port $web_port in use"
        local new_port=$(find_available_port $((web_port + 1)))
        print_colored "$CYAN" "  Suggested alternative: $new_port"
    fi
    
    if is_port_available "$api_port"; then
        print_colored "$GREEN" "✓ API port $api_port available"
    else
        print_colored "$YELLOW" "⚠ API port $api_port in use"
        local new_port=$(find_available_port $((api_port + 1)))
        print_colored "$CYAN" "  Suggested alternative: $new_port"
    fi
    
    # Clean up stale processes
    local stale_processes=$(ps aux | grep -E "claudable|cc-lovable" | grep -v grep | grep -v "$0" | wc -l)
    if [[ $stale_processes -gt 0 ]]; then
        print_colored "$YELLOW" "⚠ Found $stale_processes stale processes"
        print_colored "$CYAN" "  Cleaning up..."
        pkill -f "claudable|cc-lovable" 2>/dev/null || true
        clean_pids
        ((fixes_applied++))
        print_colored "$GREEN" "✓ Stale processes cleaned"
    else
        print_colored "$GREEN" "✓ No stale processes found"
    fi
    
    # Summary
    echo
    print_colored "$WHITE" "${BOLD}Health Check Summary:${NC}"
    if [[ $issues_found -eq 0 ]]; then
        print_colored "$GREEN" "🎉 All systems healthy!"
    else
        print_colored "$YELLOW" "⚠ Found $issues_found issues"
    fi
    
    if [[ $fixes_applied -gt 0 ]]; then
        print_colored "$BLUE" "🔧 Applied $fixes_applied fixes"
    fi
    
    print_colored "$CYAN" "Run '$0 start' to launch Claudable"
}

# Main function
main() {
    # Handle Ctrl+C gracefully
    trap 'print_colored "$YELLOW" "\nShutting down..."; stop_claudable; exit 0' INT TERM
    
    if [[ $# -eq 0 ]]; then
        print_banner
        show_usage
        exit 1
    fi
    
    local command=$1
    shift
    
    case $command in
        start)
            print_banner
            start_claudable "$@"
            ;;
        stop)
            stop_claudable
            ;;
        restart)
            restart_claudable "$@"
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs "$@"
            ;;
        clean)
            clean_project
            ;;
        reset)
            reset_claudable
            ;;
        backup)
            backup_database
            ;;
        health)
            health_check
            ;;
        watch)
            watch_services "$@"
            ;;
        projects)
            manage_projects "$@"
            ;;
        rebuild)
            rebuild_claudable
            ;;
        debug)
            debug_mode "$@"
            ;;
        doctor)
            doctor_check
            ;;
        help|--help|-h)
            print_banner
            show_usage
            ;;
        *)
            print_colored "$RED" "Unknown command: $command"
            echo
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"