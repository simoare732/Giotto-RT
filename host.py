import serial
import time
import img_manager
import os
import re
import threading

serial_port = '/dev/ttyACM0'
baud_rate = 9600
arduino = serial.Serial(port=serial_port, baudrate=baud_rate, timeout=0.2, write_timeout=1)
time.sleep(2)

START_MARKER = 0xFE
END_MARKER = 0xFF
MAX_PAYLOAD = 32

THRESHOLD_FULL_QUEUE = 15 # Threshold for the number of points in the queue before stopping sending new points
QUEUE_LEVEL = 0 # Current number of points in the queue, updated based on telemetry data
TELEMETRY = []


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


def read_telemetry():
    global QUEUE_LEVEL, TELEMETRY

    pattern = r'^\d+,\d+,\d+,\d+$'
    while True:
        try:

            tel = receive_data().strip()

            if re.match(pattern, tel):
                val = [int(x) for x in tel.split(',')]
                QUEUE_LEVEL = val[0]  # Update the global QUEUE_LEVEL variable with the first value from telemetry
                TELEMETRY.append(val)
            else:
                val = tel
        
        except Exception:
            pass


if __name__ == "__main__":

    filename = input("Enter the image filename (with extension): ")
    filename = "imgs_source/" + filename

    # Image is processed and contours are extracted
    binarized = img_manager.process_image(filename, (100, 100), 0.5)
    contours = img_manager.countours_extraction(binarized)

    # Optionally, create an image with only the contours and save it
    image_contours = img_manager.create_contours_only_image(binarized, contours)
    img_manager.save_opencv_image(image_contours, os.path.basename(filename))


    listener = threading.Thread(target=read_telemetry, daemon=True)
    listener.start()

    # Send the contours data to the Arduino
    for contour in contours:

        contour_str = str(contour[0][0][0]) + "," + str(contour[0][0][1]) + ",0"

        while QUEUE_LEVEL > THRESHOLD_FULL_QUEUE:
            print(f"Queue is full ({QUEUE_LEVEL}), waiting to send new points...  ")
            time.sleep(0.05)
        
        send_data(contour_str)
        print(f"Sent contour: {contour_str}")

        time.sleep(0.005)

