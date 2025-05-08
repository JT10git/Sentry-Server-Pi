# Simple Shell with API Control

This is a simplified implementation of a remote shell system with an API interface. It uses a more reliable approach with JSON-based communication between the client and server.

## Components

1. **Simple Shell Server** (`simple_shell_server.py`): 
   - Listens for incoming connections on port 7878
   - Provides a REST API on port 8080 for sending commands and retrieving outputs
   - Includes a web interface for controlling the shell

2. **Simple Shell Client** (`simple_shell_client.py`):
   - Connects to the server and waits for commands
   - Executes commands using subprocess and returns the output
   - Uses JSON for structured communication

## Key Features

- **Simplified Architecture**: Uses a direct command execution model instead of a persistent shell
- **JSON Communication**: Structured message format for reliable data exchange
- **Improved Error Handling**: Better error detection and reporting
- **Automatic Reconnection**: Client automatically reconnects if the connection is lost
- **Web Interface**: User-friendly control panel for sending commands and viewing outputs

## Setup and Usage

### Prerequisites

- Python 3.6+
- Required packages: `flask`, `flask-cors`

### Installation

1. Install the required packages:
   ```
   pip install flask flask-cors
   ```

### Running the Server

1. Start the server:
   ```
   start_simple_server.bat
   ```
   or
   ```
   python simple_shell_server.py
   ```

2. Access the web interface at:
   ```
   http://localhost:8080
   ```

### Running the Client

1. On the target machine, run the client:
   ```
   start_simple_client.bat
   ```
   or
   ```
   python simple_shell_client.py <server_ip> 7878
   ```
   Replace `<server_ip>` with the IP address of the server.

## How It Works

1. The server listens for incoming connections on port 7878.
2. The client connects to the server and identifies itself.
3. The server provides a web interface on port 8080 for controlling the shell.
4. Commands are sent from the web interface to the server via the API.
5. The server forwards commands to the connected client.
6. The client executes the commands and returns the output.
7. The output is displayed in the web interface.

## API Endpoints

- `GET /status`: Check the connection status
- `POST /command`: Send a command to the shell
- `GET /output`: Retrieve command outputs
- `POST /clear`: Clear the command and output queues
- `POST /disconnect`: Disconnect the current client

## Troubleshooting

### Connection Issues
- If the client cannot connect, check firewall settings and ensure the server is running
- If the connection is unstable, try using a different network or check for firewall restrictions

### Command Execution Issues
- If commands are not executing, check the connection status and try reconnecting
- Verify that the command is valid for the client's operating system
- Check the client console for any error messages

### JSON Parsing Issues
- If you see JSON parsing errors in the client console, check the format of the messages
- Run the `test_json_parsing.py` script to verify JSON parsing:
  ```
  python test_json_parsing.py '{"type": "command", "data": "echo hello"}'
  ```
- Make sure both the server and client are using the same encoding (UTF-8)

### API Issues
- For API issues, check the server console for error messages
- Verify that the Flask server is running and accessible
- Try accessing the API endpoints directly using tools like curl or Postman

## Security Considerations

This tool is intended for educational purposes or legitimate system administration tasks. Please use responsibly:

- Always obtain proper authorization before using on any system
- Use secure communication channels when possible
- Be aware of legal implications in your jurisdiction