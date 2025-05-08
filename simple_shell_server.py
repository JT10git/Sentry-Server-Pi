import socket
import threading
import queue
import time
import json
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS

# Create Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Queues for communication
command_queue = queue.Queue()
output_queue = queue.Queue()

# Connection state
client_connected = False
client_info = None
server_running = True
client_lock = threading.Lock()

# Socket server
server_socket = None
client_socket = None

def socket_server():
    """Run the socket server that accepts client connections."""
    global server_socket, client_socket, client_connected, client_info, server_running
    
    try:
        # Create server socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', 7878))
        server_socket.listen(1)
        server_socket.settimeout(1)  # 1 second timeout for accept()
        
        print("[Server] Socket server started on 0.0.0.0:7878")
        output_queue.put("Server started and waiting for connections...\n")
        
        while server_running:
            try:
                # Accept connection (with timeout)
                conn, addr = server_socket.accept()
                
                with client_lock:
                    # Close any existing connection
                    if client_socket:
                        try:
                            client_socket.close()
                        except:
                            pass
                    
                    # Set new connection
                    client_socket = conn
                    client_connected = True
                    client_info = f"{addr[0]}:{addr[1]}"
                
                print(f"[Server] Client connected from {addr}")
                output_queue.put(f"Client connected from {addr}\n")
                
                # Start client handler thread
                client_thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
                client_thread.start()
                
            except socket.timeout:
                # This is expected due to the timeout we set
                continue
            except Exception as e:
                print(f"[Server] Error accepting connection: {e}")
                time.sleep(1)
    
    except Exception as e:
        print(f"[Server] Socket server error: {e}")
    finally:
        # Clean up server socket
        if server_socket:
            try:
                server_socket.close()
            except:
                pass
        print("[Server] Socket server stopped")

def handle_client(conn, addr):
    """Handle communication with a connected client."""
    global client_connected, client_info
    
    try:
        # Send initial message with proper formatting
        welcome_obj = {"type": "info", "data": "Connected to server"}
        welcome_msg = json.dumps(welcome_obj, ensure_ascii=False) + "\n"
        conn.sendall(welcome_msg.encode('utf-8'))
        print(f"[Server] Sent welcome message: {welcome_msg.strip()}")
        
        # Set socket timeout for recv
        conn.settimeout(0.5)
        
        while True:
            # Check for commands to send
            if not command_queue.empty():
                cmd = command_queue.get()
                try:
                    # Format command as JSON with proper formatting
                    cmd_obj = {"type": "command", "data": cmd}
                    cmd_json = json.dumps(cmd_obj, ensure_ascii=False) + "\n"
                    conn.sendall(cmd_json.encode('utf-8'))
                    print(f"[Server] Sent command: {cmd}")
                    print(f"[Server] JSON sent: {cmd_json.strip()}")
                except Exception as e:
                    print(f"[Server] Error sending command: {e}")
                    output_queue.put(f"Error sending command: {e}\n")
                    break
            
            # Check for client output
            try:
                data = conn.recv(4096)
                if not data:  # Connection closed
                    break
                
                # Try to parse as JSON
                try:
                    messages = data.decode('utf-8', errors='replace').split('\n')
                    for msg in messages:
                        if not msg.strip():
                            continue
                        
                        response = json.loads(msg)
                        if response.get("type") == "output":
                            output_queue.put(response.get("data", "") + "\n")
                        elif response.get("type") == "error":
                            output_queue.put(f"Error: {response.get('data', '')}\n")
                        elif response.get("type") == "info":
                            output_queue.put(f"Info: {response.get('data', '')}\n")
                except json.JSONDecodeError:
                    # If not valid JSON, treat as raw output
                    output_queue.put(data.decode('utf-8', errors='replace'))
                except Exception as e:
                    print(f"[Server] Error processing client data: {e}")
            
            except socket.timeout:
                # This is expected due to the timeout we set
                continue
            except Exception as e:
                print(f"[Server] Error receiving data: {e}")
                break
            
            # Small delay to prevent CPU hogging
            time.sleep(0.01)
    
    except Exception as e:
        print(f"[Server] Client handler error: {e}")
    finally:
        # Clean up
        try:
            conn.close()
        except:
            pass
        
        with client_lock:
            if client_socket == conn:
                client_socket = None
                client_connected = False
                client_info = None
        
        print(f"[Server] Client disconnected from {addr}")
        output_queue.put(f"Client disconnected from {addr}\n")

# API Routes
@app.route('/status', methods=['GET'])
def get_status():
    """Get the current server status."""
    with client_lock:
        return jsonify({
            "connected": client_connected,
            "client": client_info,
            "pending_commands": command_queue.qsize(),
            "pending_outputs": output_queue.qsize()
        })

@app.route('/command', methods=['POST'])
def send_command():
    """Send a command to the connected client."""
    with client_lock:
        if not client_connected:
            return jsonify({"error": "No client connected"}), 503
    
    data = request.get_json()
    if not data or 'command' not in data:
        return jsonify({"error": "Missing 'command' field"}), 400
    
    command = data['command']
    command_queue.put(command)
    
    return jsonify({
        "status": "success",
        "message": f"Command '{command}' sent to the shell"
    })

@app.route('/output', methods=['GET'])
def get_output():
    """Get any pending output from the client."""
    outputs = []
    
    # Get all available outputs (non-blocking)
    while not output_queue.empty():
        outputs.append(output_queue.get())
    
    return jsonify({
        "status": "success",
        "outputs": outputs
    })

@app.route('/clear', methods=['POST'])
def clear_queues():
    """Clear the command and output queues."""
    # Clear both queues
    while not command_queue.empty():
        command_queue.get()
    
    while not output_queue.empty():
        output_queue.get()
    
    return jsonify({
        "status": "success",
        "message": "All queues cleared"
    })

@app.route('/disconnect', methods=['POST'])
def disconnect_client():
    """Disconnect the current client."""
    global client_socket
    
    with client_lock:
        if client_socket:
            try:
                client_socket.close()
                return jsonify({"status": "success", "message": "Client disconnected"})
            except Exception as e:
                return jsonify({"error": f"Error disconnecting client: {e}"}), 500
        else:
            return jsonify({"error": "No client connected"}), 503

@app.route('/')
def index():
    """Serve the web interface."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Simple Shell Control Panel</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .status {
            display: flex;
            justify-content: space-between;
            margin-bottom: 20px;
            padding: 10px;
            background-color: #f0f0f0;
            border-radius: 5px;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 5px;
        }
        .connected { background-color: #4CAF50; }
        .disconnected { background-color: #F44336; }
        
        .terminal {
            background-color: #2b2b2b;
            color: #f0f0f0;
            padding: 15px;
            border-radius: 5px;
            height: 400px;
            overflow-y: auto;
            font-family: monospace;
            margin-bottom: 20px;
            white-space: pre-wrap;
        }
        .command-input {
            display: flex;
            margin-bottom: 20px;
        }
        input[type="text"] {
            flex-grow: 1;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px 0 0 5px;
            font-family: monospace;
        }
        button {
            padding: 10px 15px;
            background-color: #4CAF50;
            color: white;
            border: none;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        button:hover {
            background-color: #45a049;
        }
        .send-btn {
            border-radius: 0 5px 5px 0;
        }
        .clear-btn {
            border-radius: 5px;
            margin-left: 10px;
            background-color: #f44336;
        }
        .clear-btn:hover {
            background-color: #d32f2f;
        }
        .action-btn {
            border-radius: 5px;
            margin-left: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Simple Shell Control Panel</h1>
        
        <div class="status">
            <div>
                <span class="status-indicator disconnected" id="status-light"></span>
                <span id="status-text">Disconnected</span>
            </div>
            <div>
                <button id="refresh-status" class="action-btn">Refresh</button>
                <button id="disconnect-client" class="action-btn" style="background-color: #f44336;">Disconnect</button>
            </div>
        </div>
        
        <div class="terminal" id="terminal"></div>
        
        <div class="command-input">
            <input type="text" id="command" placeholder="Enter command..." autocomplete="off">
            <button class="send-btn" id="send-command">Send</button>
            <button class="clear-btn" id="clear-terminal">Clear</button>
        </div>
    </div>

    <script>
        const API_URL = window.location.origin;
        let isConnected = false;
        let outputPollingInterval = null;
        
        // DOM elements
        const statusLight = document.getElementById('status-light');
        const statusText = document.getElementById('status-text');
        const terminal = document.getElementById('terminal');
        const commandInput = document.getElementById('command');
        const sendButton = document.getElementById('send-command');
        const clearButton = document.getElementById('clear-terminal');
        const refreshStatusButton = document.getElementById('refresh-status');
        const disconnectButton = document.getElementById('disconnect-client');
        
        // Update the connection status
        async function updateStatus() {
            try {
                const response = await fetch(`${API_URL}/status`);
                const data = await response.json();
                
                isConnected = data.connected;
                
                if (isConnected) {
                    statusLight.classList.remove('disconnected');
                    statusLight.classList.add('connected');
                    statusText.textContent = `Connected to ${data.client}`;
                    disconnectButton.disabled = false;
                    
                    // Start polling for output if not already doing so
                    if (!outputPollingInterval) {
                        outputPollingInterval = setInterval(fetchOutput, 1000);
                    }
                } else {
                    statusLight.classList.remove('connected');
                    statusLight.classList.add('disconnected');
                    statusText.textContent = 'Disconnected';
                    disconnectButton.disabled = true;
                    
                    // Stop polling if disconnected
                    if (outputPollingInterval) {
                        clearInterval(outputPollingInterval);
                        outputPollingInterval = null;
                    }
                }
            } catch (error) {
                console.error('Error fetching status:', error);
                statusText.textContent = 'API Error';
            }
        }
        
        // Send a command to the server
        async function sendCommand() {
            const command = commandInput.value.trim();
            if (!command) return;
            
            try {
                const response = await fetch(`${API_URL}/command`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ command })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    // Add the command to the terminal with a prompt
                    appendToTerminal(`$ ${command}\n`);
                    commandInput.value = '';
                } else {
                    appendToTerminal(`Error: ${data.error}\n`);
                }
            } catch (error) {
                console.error('Error sending command:', error);
                appendToTerminal('Error: Could not send command to the server\n');
            }
        }
        
        // Fetch output from the server
        async function fetchOutput() {
            try {
                const response = await fetch(`${API_URL}/output`);
                const data = await response.json();
                
                if (response.ok && data.outputs && data.outputs.length > 0) {
                    data.outputs.forEach(output => {
                        appendToTerminal(output);
                    });
                }
            } catch (error) {
                console.error('Error fetching output:', error);
            }
        }
        
        // Clear the terminal
        async function clearTerminal() {
            terminal.textContent = '';
            
            // Also clear the server-side queues
            try {
                await fetch(`${API_URL}/clear`, { method: 'POST' });
            } catch (error) {
                console.error('Error clearing queues:', error);
            }
        }
        
        // Disconnect the client
        async function disconnectClient() {
            try {
                const response = await fetch(`${API_URL}/disconnect`, { method: 'POST' });
                const data = await response.json();
                
                if (response.ok) {
                    appendToTerminal(`System: ${data.message}\n`);
                } else {
                    appendToTerminal(`Error: ${data.error}\n`);
                }
            } catch (error) {
                console.error('Error disconnecting client:', error);
                appendToTerminal('Error: Could not disconnect client\n');
            }
        }
        
        // Append text to the terminal and scroll to bottom
        function appendToTerminal(text) {
            terminal.textContent += text;
            terminal.scrollTop = terminal.scrollHeight;
        }
        
        // Event listeners
        sendButton.addEventListener('click', sendCommand);
        clearButton.addEventListener('click', clearTerminal);
        refreshStatusButton.addEventListener('click', updateStatus);
        disconnectButton.addEventListener('click', disconnectClient);
        
        commandInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendCommand();
            }
        });
        
        // Initial status check
        updateStatus();
        
        // Check status periodically
        setInterval(updateStatus, 5000);
    </script>
</body>
</html>"""
    return html_content
    return html_content

if __name__ == '__main__':
    # Start the socket server in a separate thread
    server_thread = threading.Thread(target=socket_server, daemon=True)
    server_thread.start()
    
    try:
        # Start the Flask API
        print("[Server] Starting Flask API on port 8080...")
        app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
    finally:
        # Signal the server to stop
        server_running = False
        print("[Server] Shutting down...")