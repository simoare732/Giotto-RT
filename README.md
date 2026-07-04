# Giotto: SCARA Drawer Robot

University project of a 2D Drawing Robot based on a Five-Bar Linkage SCARA architecture.

## Description
Giotto is a robotic arm equipped with a pen. By uploading an image through the provided web interface, the robot will automatically trace and draw the image on a physical sheet of paper.

*Note: The uploaded image is automatically binarized and downsampled by the software to correctly fit the physical drawing area (Workspace).*

## Requirements

### Hardware Required
* Microcontroller (Arduino Mega 2560 / Arduino Uno / ESP32 or similar)
* 3x SG90 Servomotors (2 for the arms, 1 for the pen lifting mechanism)
* Jumpers and connecting wires
* 3D printed mechanical structure. This project is physically based on the excellent design: [SCARA 2D Drawing Robot - Five Bar Link](https://makerworld.com/en/models/978425-scara-2d-drawing-robot-esp32-five-bar-link).

### Software Required
* Python 3.11 or higher
* Arduino IDE (for firmware upload)

## ⚙️ Installation

1. Clone the repository:
```bash 
git clone https://github.com/simoare732/Giotto-RT.git
cd Giotto-RT
```

2. *(Optional but Recommended)* Create and activate a virtual environment:
```bash
python -m venv venv
# On Windows: venv\Scripts\activate
# On Linux/Mac: source venv/bin/activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. **Arduino Side:**
   * Open the Arduino IDE and install the `Servo.h` and `FreeRTOS` libraries (search for `FreeRTOS` in the Library Manager).
   * Verify the pin assignments for the 3 Servos in the `.ino` sketch.
   * Connect the microcontroller via USB and upload the sketch at **115200 baud**.

5. **Configuration:** Open the `config.yaml` file to modify the physical parameters of the robot and the workspace (e.g., sheet dimensions, arm lengths L1 and L2).

## Running the System

To start the web server, run:
```bash
python host.py
```
Then, open your web browser and go to `http://localhost:5000`. You will be able to monitor the telemetry and upload the image you want the robot to draw.

## Implementation Details (RTOS & Control Loop)

The firmware is built on top of **FreeRTOS** and adheres to real-time engineering principles:

* **Scheduling:** FreeRTOS natively adopts Priority Scheduling. In this project, task priorities are assigned following the **Rate Monotonic (RM) algorithm** (shorter period = higher priority).
  * `TaskEngine` (Priority 3 - High, Period 20ms): Manages synchronous interpolation and servo actuation.
  * `TaskRec` (Priority 2 - Medium, Aperiodic): Asynchronously listens to the serial port for incoming coordinates.
  * `TaskTelemetry` (Priority 1 - Low, Period 100ms): Sends real-time state feedback to the host.
* **High-Resolution Actuation:** To avoid mechanical vibrations, the `TaskEngine` bypasses integer degree control (`servo.write()`) and uses **microsecond pulse width control** (`writeMicroseconds()`), splitting the 180° range into 2000 ultra-fine steps for extremely fluid movements.
* **Flow Control (Feedback Loop):** A custom telemetry protocol communicates the current queue level back to Python. If the Arduino queue exceeds a safe threshold (`THRESHOLD_FULL_QUEUE = 15`), Python automatically pauses the transmission, preventing buffer overflows and loss of packets.
* **Concurrency & Safety:** Shared resources (like variables storing the current point for telemetry) are protected using the `semphr.h` library, specifically through **Mutexes** with priority inheritance. Communication between `TaskRec` and `TaskEngine` is entirely thread-safe, utilizing a native FreeRTOS **Queue**.

## Screenshots  
![Screenshot of application running](https://github.com/simoare732/Giotto-RT/blob/master/screenshots/website.png?raw=true)

## Made By
**simoare732** *Date: July 2026*

## Credits
Special thanks to the author of the original 3D mechanical model **SCARA 2D Drawing Robot**.

Links to the original project:  
* [MakerWorld 3D Models](https://makerworld.com/en/models/978425-scara-2d-drawing-robot-esp32-five-bar-link)  
* [GitHub Repository](https://github.com/MatixYo/ESP32-Drawing-Robot)