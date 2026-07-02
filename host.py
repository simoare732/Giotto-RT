import queue
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename

import serial
import time
import img_manager
import os
import re
import threading
import yaml

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# --- CONFIGURAZIONE SERVER WEB ---
app = Flask(__name__)
# Evita un avviso di sicurezza su Flask
app.config['SECRET_KEY'] = 'segreto_super_sicuro' 
# Inizializza SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

serial_port = '/dev/ttyACM0'
baud_rate = 115200
arduino = serial.Serial(port=serial_port, baudrate=baud_rate, timeout=0.2, write_timeout=1)
time.sleep(2)

START_MARKER = 0xFE
END_MARKER = 0xFF
MAX_PAYLOAD = 32

THRESHOLD_FULL_QUEUE = 15 # Threshold for the number of points in the queue before stopping sending new points
QUEUE_LEVEL = 0 # Current number of points in the queue, updated based on telemetry data
TELEMETRY = []

is_drawing = False  # Global flag to indicate if the drawing process is active
UPLOAD_FOLDER = 'imgs_source'  # Directory where uploaded images will be saved


def calc_checksum(data):
    """
    Compute the checksum of the given data using XOR operation.
    """
    cs = len(data)  
    for b in data:
        cs ^= b
    return cs & 0xFF

def send_data(msg_str):
    """
    Send a message to the Arduino over the serial connection, with a specific packet structure.
    The packet structure is as follows:
    - Start marker (1 byte): 0xFE
    - Length of the payload (1 byte)
    - Payload (up to 32 bytes)
    - Checksum (1 byte): XOR of the length and all payload bytes
    - End marker (1 byte): 0xFF
    The payload is truncated to a maximum of 32 bytes if it exceeds that length.
    """

    payload = msg_str.encode('utf-8')[:MAX_PAYLOAD]

    packet = bytes([START_MARKER, len(payload)]) + payload + bytes([calc_checksum(payload), END_MARKER])
    arduino.write(packet)
    arduino.flush()

def receive_data(timeout_s=2.0):
    """
    Receive a message from the Arduino over the serial connection, with a specific packet structure.
    The function waits for a valid packet to be received within the specified timeout.
    The packet structure is as follows:
    - Start marker (1 byte): 0xFE
    - Length of the payload (1 byte)
    - Payload (up to 32 bytes)
    - Checksum (1 byte): XOR of the length and all payload bytes
    - End marker (1 byte): 0xFF
    If a valid packet is received, the payload is returned as a string. If no valid packet is received within the timeout, a TimeoutError is raised.
    """

    deadline = time.time() + timeout_s

    while time.time() < deadline:
        b = arduino.read(1)
        if not b:
            continue
        if b[0] != START_MARKER:
            continue

        length_b = arduino.read(1)
        if not length_b:
            continue
        length = length_b[0]
        if length == 0 or length > MAX_PAYLOAD:
            continue

        payload = arduino.read(length)
        checksum_b = arduino.read(1)
        end_b = arduino.read(1)

        if len(payload) != length or not checksum_b or not end_b:
            continue
        if end_b[0] != END_MARKER:
            continue

        expected = calc_checksum(payload)
        if checksum_b[0] != expected:
            continue

        return payload.decode('utf-8', errors='ignore')

    raise TimeoutError("Nessuna risposta valida dall'Arduino")


def read_telemetry(queue_tel):
    """
    Continuously read telemetry data from the Arduino and update the global QUEUE_LEVEL and TELEMETRY variables.
    """
    global QUEUE_LEVEL, TELEMETRY

    pattern = r'^\d+,\d+,\d+,\d+$'
    while True:
        try:

            tel = receive_data().strip()

            if re.match(pattern, tel):
                val = [int(x) for x in tel.split(',')]
                val[3] = 1 if val[3] == config["giotto_config"]["pen_down_angle"] else 0  # Convert pen angle to binary state
                QUEUE_LEVEL = val[0]  # Update the global QUEUE_LEVEL variable with the first value from telemetry
                TELEMETRY.append(val)

                socketio.emit("Update telemetry", val)  # Send the telemetry data to the web client via SocketIO
            else:
                val = tel
        
        except Exception:
            pass


def send_contours(filename, queue_points):
    """
    Process the given image file to extract contours and send them to the Arduino, while also updating the GUI with the points.
    The function processes the image, extracts contours, and sends each contour point to the Arduino.
    """
    global QUEUE_LEVEL, is_drawing

    is_drawing = True  # Set the drawing flag to True when starting the drawing process

    socketio.emit("Clear canvas")  # Notify the web client to clear the canvas

    # Image is processed and contours are extracted
    target_x, target_y = config["image_config"]["image_width"], config["image_config"]["image_height"]
    thres = config["image_config"]["threshold"]
    binarized = img_manager.process_image(filename, (target_x, target_y), thres)
    contours = img_manager.countours_extraction(binarized)

    # Optionally, create an image with only the contours and save it
    image_contours = img_manager.create_contours_only_image(binarized, contours)
    img_manager.save_opencv_image(image_contours, os.path.basename(filename))

    # Create the path (in pixels) from the contours
    path_pixel = img_manager.draw_contours(contours)

    path_mm = img_manager.convert_pixels_to_millimeters(path_pixel, target_x, target_y)

     # Send the contours data to the Arduino
    for p in path_mm:
        x = int(p["x"])
        y = int(p["y"])
        state = p["state"]  # True for pen down, False for pen up

        if state:
            z = config["giotto_config"]["pen_down_angle"]  # Use the configured pen down angle
        else:
            z = config["giotto_config"]["pen_up_angle"]  # Use the configured pen up angle

        ang_Rx, ang_Sx = img_manager.compute_kinematics(x, y)

        if ang_Sx is None or ang_Rx is None:
            print(f"Point ({x}, {y}) is unreachable. Skipping...")
            continue  # Skip this point if it's unreachable

        contour_str = f"{ang_Rx},{ang_Sx},{z}"

        while QUEUE_LEVEL > THRESHOLD_FULL_QUEUE:
            print(f"Queue is full ({QUEUE_LEVEL}), waiting to send new points...  ")
            time.sleep(0.05)
        
        send_data(contour_str)
        print(f"Sent contour: {contour_str}")

        socketio.emit("Update points", {'x': x, 'y': y, 'state': state})  # Send the point to the web client via SocketIO

        time.sleep(0.01)  # Small delay to avoid overwhelming the Arduino
        
    
    is_drawing = False  # Set the drawing flag to False when the drawing process is complete
    socketio.emit("Drawing complete")  # Notify the web client that the drawing process is complete

    time.sleep(1)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    global is_drawing
    
    if is_drawing:
        return jsonify({'error': 'La macchina sta già disegnando. Attendi la fine.'}), 400

    if 'file' not in request.files:
        return jsonify({'error': 'Nessun file ricevuto.'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'Nessun file selezionato.'}), 400
    
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # Usiamo ancora queue_points per mantenere intatta la firma della tua funzione
        queue_points = queue.Queue()

        # Avvia il processo in background
        thread_invio = threading.Thread(target=send_contours, args=(filepath, queue_points), daemon=True)
        thread_invio.start()

        return jsonify({'message': 'File salvato e processo di disegno avviato.'}), 200


if __name__ == "__main__":

    #filename = input("Enter the image filename (with extension): ")
    #filename = "imgs_source/" + filename

    queue_tel = queue.Queue()

    listener = threading.Thread(target=read_telemetry, args=(queue_tel,), daemon=True)
    listener.start()

    print("Server is running. Access the web interface at http://localhost:5000")

    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)

