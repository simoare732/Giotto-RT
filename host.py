import serial
import time
import os

serial_port = '/dev/ttyACM0'
baud_rate = 9600
arduino = serial.Serial(port=serial_port, baudrate=baud_rate, timeout=1)

# Attende che Arduino completi il riavvio e il setup() iniziale
time.sleep(3)

def send_data(msg_str):
    # Converte la stringa in byte
    payload_bytes = msg_str.encode('utf-8')

    start_marker = b'\xFE'
    # Utilizza i byte convertiti invece di un valore fisso
    end_marker = b'\xFF'

    packet = start_marker + payload_bytes + end_marker
    print(f"Invio pacchetto: {packet}")

    try:
        arduino.write(packet)
        arduino.flush()  # Assicura che i dati vengano inviati
    except Exception as e:
        print(f"Errore durante l'invio: {e}")

# Invia il comando per muovere il servo a 90 gradi
send_data('90')

# Attende la risposta da Arduino prima di chiudere
time.sleep(0.5) 
while arduino.in_waiting > 0:
    risposta = arduino.readline().decode('utf-8', errors='ignore').strip()
    print(f"Risposta da Arduino: {risposta}")

# Invia il comando per muovere il servo a 90 gradi
send_data('0')

# Attende la risposta da Arduino prima di chiudere
time.sleep(0.5) 
while arduino.in_waiting > 0:
    risposta = arduino.readline().decode('utf-8', errors='ignore').strip()
    print(f"Risposta da Arduino: {risposta}")

arduino.close() 