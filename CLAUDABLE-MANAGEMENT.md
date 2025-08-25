# Claudable Management Script

A comprehensive management tool for the Claudable development environment that handles starting, stopping, restarting, and monitoring all Claudable services.

## Quick Start

```bash
# Start Claudable services
./claudable.sh start

# Check status
./claudable.sh status

# Stop services
./claudable.sh stop
```

## Installation

The script is already included and ready to use. It's automatically executable after clone/setup.

## Usage

### Basic Commands

```bash
./claudable.sh <command> [options]
```

### Available Commands

| Command   | Description |
|-----------|-------------|
| `start`   | Start Claudable services (API & Web) |
| `stop`    | Stop all Claudable processes |
| `restart` | Restart all services |
| `status`  | Show current service status and health |
| `logs`    | Show application logs |
| `clean`   | Clean dependencies and build artifacts |
| `reset`   | Reset database and clean state |
| `backup`  | Backup database |
| `health`  | Check system health and dependencies |
| `help`    | Show help message |

### Options

| Option | Description |
|--------|-------------|
| `--port <port>` | Set custom web port (default: 8383) |
| `--api-port <port>` | Set custom API port (default: 8082) |
| `--background` | Run services in background |
| `--no-browser` | Don't auto-open browser |
| `--follow` | Follow logs in real-time |

## Examples

### Starting Services

```bash
# Start with default ports (Web: 8383, API: 8082)
./claudable.sh start

# Start with custom web port
./claudable.sh start --port 9000

# Start with both custom ports
./claudable.sh start --port 9000 --api-port 9001

# Start in background (doesn't block terminal)
./claudable.sh start --background

# Start without opening browser
./claudable.sh start --no-browser
```

### Managing Services

```bash
# Check if services are running
./claudable.sh status

# Restart services (useful after code changes)
./claudable.sh restart

# Stop all services
./claudable.sh stop

# Restart in background mode
./claudable.sh restart --background
```

### Logs and Debugging

```bash
# Show recent logs
./claudable.sh logs

# Follow logs in real-time (background mode only)
./claudable.sh logs --follow

# Check system health
./claudable.sh health
```

### Maintenance

```bash
# Clean all dependencies and build artifacts
./claudable.sh clean

# Backup database
./claudable.sh backup

# Reset database (with backup)
./claudable.sh reset
```

## NPM Integration

The management script is also available through npm commands:

```bash
npm run start       # ./claudable.sh start
npm run stop        # ./claudable.sh stop
npm run restart     # ./claudable.sh restart
npm run status      # ./claudable.sh status
npm run logs        # ./claudable.sh logs
npm run health      # ./claudable.sh health
npm run manage      # ./claudable.sh (with arguments)
```

Examples:
```bash
npm run start
npm run status
npm run restart
```

## Features

### 🔧 Process Management
- **PID Tracking**: Keeps track of all spawned processes for reliable control
- **Graceful Shutdown**: Properly terminates all child processes
- **Process Tree Cleanup**: Ensures no orphaned processes remain

### 🚦 Port Management
- **Automatic Port Detection**: Finds available ports if defaults are busy
- **Port Conflict Resolution**: Automatically resolves port conflicts
- **Custom Port Configuration**: Easy port customization via command line

### 📊 Monitoring & Status
- **Real-time Status**: Shows current state of all services
- **Health Checks**: Verifies system dependencies and service health
- **Process Information**: Detailed information about running processes

### 📝 Logging
- **Background Logging**: Logs saved to `.claudable.log` when running in background
- **Real-time Log Following**: Stream logs in real-time with `--follow`
- **Log Management**: Automatic log rotation and cleanup

### 🎨 User Experience
- **Colored Output**: Clear, color-coded status messages
- **Progress Indicators**: Visual feedback for long-running operations
- **Error Handling**: Comprehensive error messages and recovery suggestions

## File Structure

The management script uses several files for state management:

```
Claudable/
├── claudable.sh              # Main management script
├── .claudable.pid            # Process ID tracking
├── .claudable.log            # Background mode logs
├── .env                      # Port and environment configuration
└── CLAUDABLE-MANAGEMENT.md   # This documentation
```

## Service Architecture

When you run `./claudable.sh start`, it launches:

1. **Environment Setup**: Ensures `.env` and Python virtual environment
2. **API Server**: Python FastAPI server (default port: 8082)
3. **Web Server**: Next.js development server (default port: 8383)
4. **Process Tracking**: Maintains PID file for reliable process management

## Port Configuration

Ports are managed through the `.env` file:

```bash
API_PORT=8082
WEB_PORT=8383
DATABASE_URL=sqlite:///path/to/data/cc.db
```

The script will:
- Read existing port configuration from `.env`
- Check port availability before starting
- Find alternative ports if configured ports are busy
- Update `.env` with the actual ports used

## Troubleshooting

### Services Won't Start
```bash
# Check system health
./claudable.sh health

# Check for port conflicts
./claudable.sh status

# Try with different ports
./claudable.sh start --port 9000
```

### Processes Not Stopping
```bash
# Force stop all related processes
./claudable.sh stop

# If still running, check for orphaned processes
ps aux | grep -E "(claudable|cc-lovable)"
```

### Log Issues
```bash
# Check log file location
./claudable.sh status

# View recent logs
./claudable.sh logs

# Follow logs in real-time (background mode)
./claudable.sh logs --follow
```

### Clean Start
```bash
# Complete clean and restart
./claudable.sh clean
npm install
./claudable.sh start
```

## Development

The management script is designed to be:
- **Cross-platform**: Works on macOS and Linux
- **Self-contained**: No additional dependencies beyond Node.js and Python
- **Extensible**: Easy to add new commands and features
- **Reliable**: Robust error handling and process management

## Contributing

To extend the management script:

1. Add new functions for commands in `claudable.sh`
2. Update the `main()` function to handle new commands
3. Add corresponding npm scripts in `package.json`
4. Update this documentation

The script follows these conventions:
- Use colored output for user feedback
- Implement proper error handling
- Maintain PID tracking for process management
- Follow the existing command structure