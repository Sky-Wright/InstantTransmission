import socket
import threading
import tkinter as tk
from PIL import Image, ImageTk
import zlib
import mss
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController
import json
import struct
import logging

# Basic logger setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RemoteDesktopClient:
    """The client window that displays the remote screen and sends input."""
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.root = None
        self.canvas = None
        self.sock = None
        self._is_running = False

    def start(self):
        """Starts the client UI and network connection."""
        self._is_running = True
        self.root = tk.Tk()
        self.root.title(f"Remote Desktop - {self.host}")
        
        # The canvas will display the screen from the host
        self.canvas = tk.Canvas(self.root)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind input events
        self.root.bind('<KeyPress>', self._key_press)
        self.root.bind('<KeyRelease>', self._key_release)
        self.canvas.bind('<ButtonPress-1>', self._mouse_press)
        self.canvas.bind('<ButtonRelease-1>', self._mouse_release)
        self.canvas.bind('<Motion>', self._mouse_motion)

        self.root.protocol("WM_DELETE_WINDOW", self.stop)

        # Start network threads
        threading.Thread(target=self._receive_frames, daemon=True).start()
        
        self.root.mainloop()

    def stop(self):
        """Stops the client."""
        logging.info("Stopping client...")
        self._is_running = False
        if self.sock:
            self.sock.close()
        if self.root:
            self.root.destroy()

    def _send_input(self, data):
        """Sends input data to the host."""
        if self.sock and self._is_running:
            try:
                serialized_data = json.dumps(data).encode('utf-8')
                self.sock.sendall(struct.pack('>I', len(serialized_data)) + serialized_data)
            except (ConnectionResetError, BrokenPipeError):
                logging.error("Connection to host lost.")
                self.stop()

    # --- Event Handlers ---
    def _key_press(self, event):
        self._send_input({'type': 'key_press', 'key': event.keysym})

    def _key_release(self, event):
        self._send_input({'type': 'key_release', 'key': event.keysym})

    def _mouse_press(self, event):
        self._send_input({'type': 'mouse_press', 'x': event.x, 'y': event.y, 'button': 'left'})

    def _mouse_release(self, event):
        self._send_input({'type': 'mouse_release', 'x': event.x, 'y': event.y, 'button': 'left'})

    def _mouse_motion(self, event):
        self._send_input({'type': 'mouse_move', 'x': event.x, 'y': event.y})

    def _receive_frames(self):
        """Receives and displays screen frames from the host."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.host, self.port))
            logging.info(f"Connected to host {self.host}:{self.port}")
        except Exception as e:
            logging.error(f"Failed to connect to host: {e}")
            self.stop()
            return

        while self._is_running:
            try:
                # Read message length
                packed_msg_size = self.sock.recv(4)
                if not packed_msg_size: break
                msg_size = struct.unpack('>I', packed_msg_size)[0]
                
                # Read the frame data
                frame_data = b""
                while len(frame_data) < msg_size:
                    chunk = self.sock.recv(msg_size - len(frame_data))
                    if not chunk: break
                    frame_data += chunk
                
                # Decompress and display
                frame = Image.frombytes("RGB", (1920, 1080), zlib.decompress(frame_data), "raw", "RGB") # Placeholder size
                
                if self.root and self.canvas:
                    img = ImageTk.PhotoImage(image=frame)
                    self.canvas.create_image(0, 0, anchor=tk.NW, image=img)
                    self.canvas.image = img # Keep a reference!
                    if self.root.winfo_width() != img.width() or self.root.winfo_height() != img.height():
                        self.root.geometry(f"{img.width()}x{img.height()}")

            except (ConnectionResetError, struct.error):
                logging.error("Connection lost while receiving frames.")
                break
            except Exception as e:
                logging.error(f"An error occurred while receiving frames: {e}")
                break
        self.stop()


class RemoteDesktopServer:
    """The server that runs on the host machine, streaming its screen and accepting input."""
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.server_socket = None
        self.client_socket = None
        self._is_running = False
        self.mouse = MouseController()
        self.keyboard = KeyboardController()

    def start(self):
        """Starts the server and listens for a client."""
        self._is_running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        logging.info(f"Remote Desktop Server listening on {self.host}:{self.port}")

        try:
            self.client_socket, addr = self.server_socket.accept()
            logging.info(f"Client connected from {addr}")
            
            # Start threads for sending screen and receiving input
            threading.Thread(target=self._stream_screen, daemon=True).start()
            threading.Thread(target=self._receive_input, daemon=True).start()

        except OSError:
            logging.warning("Server socket was closed.")
        except Exception as e:
            logging.error(f"Error accepting client connection: {e}")
            self.stop()

    def stop(self):
        """Stops the server."""
        logging.info("Stopping server...")
        self._is_running = False
        if self.client_socket:
            self.client_socket.close()
        if self.server_socket:
            self.server_socket.close()

    def _stream_screen(self):
        """Captures and streams the screen to the client."""
        with mss.mss() as sct:
            monitor = sct.monitors[1] # Capture the primary monitor
            while self._is_running:
                try:
                    img = sct.grab(monitor)
                    img_bytes = zlib.compress(img.rgb)
                    
                    # Pack the message with its size
                    message = struct.pack('>I', len(img_bytes)) + img_bytes
                    self.client_socket.sendall(message)
                except (ConnectionResetError, BrokenPipeError):
                    logging.warning("Client disconnected.")
                    break
                except Exception as e:
                    logging.error(f"Error streaming screen: {e}")
                    break
        self.stop()

    def _receive_input(self):
        """Receives and processes input events from the client."""
        while self._is_running:
            try:
                # Read message length
                packed_msg_size = self.client_socket.recv(4)
                if not packed_msg_size: break
                msg_size = struct.unpack('>I', packed_msg_size)[0]

                # Read the data
                data = self.client_socket.recv(msg_size).decode('utf-8')
                event = json.loads(data)
                self._handle_input_event(event)

            except (ConnectionResetError, struct.error):
                logging.warning("Client disconnected.")
                break
            except Exception as e:
                logging.error(f"Error receiving input: {e}")
                break
        self.stop()

    def _handle_input_event(self, event):
        """Uses pynput to execute the received input event."""
        event_type = event.get('type')
        # Note: This does not handle scaling between client/host resolutions.
        # For a real app, you'd need to translate coordinates.
        if event_type == 'mouse_move':
            self.mouse.position = (event['x'], event['y'])
        elif event_type == 'mouse_press':
            self.mouse.press(Button.left)
        elif event_type == 'mouse_release':
            self.mouse.release(Button.left)
        elif event_type == 'key_press':
            self.keyboard.press(Key[event['key']] if event['key'] in Key.__members__ else event['key'])
        elif event_type == 'key_release':
            self.keyboard.release(Key[event['key']] if event['key'] in Key.__members__ else event['key'])
