#include <Servo.h>
#include <Arduino_FreeRTOS.h>
#include <queue.h>
#include <semphr.h>

// The packet from HOST will contain these information in format angleDx,angleSx,state
struct Point{
  float angleDx;
  float angleSx;
  uint8_t state;
};

Point currentPoint;  // Global variable to store the current point being processed
SemaphoreHandle_t mut;  // Semaphore to protect access to currentPoint

QueueHandle_t queue;    // Queue to hold points received from the HOST
const uint8_t QUEUE_SIZE = 30;  // Maximum number of points that can be held in the queue

// Servo objects to control the pen and the two servos
Servo pen;     
Servo servoDx;
Servo servoSx;

int pinPen = 2;
int pinServoDx = 4;
int pinServoSx = 3;

// Constants for packet markers (start and end) and maximum payload size
const byte START_MARKER = 0xFE;
const byte END_MARKER   = 0xFF;
const byte MAX_PAYLOAD  = 32;

byte payload[MAX_PAYLOAD+1];
byte payloadLen = 0;

// Enum to represent the different states of reading a packet from the serial port
enum ReadState{
  WAIT_START,
  READ_LEN,
  READ_PAYLOAD,
  READ_CHECKSUM,
  WAIT_END
};

const uint8_t T_te = 20;  // Task Engine Period
const uint8_t T_tt = 100;  // Task Telemetry Period

// Function to calculate checksum using XOR operation
byte calcChecksum(const byte* data, byte len);

// Function to read a packet from the serial port
bool readPacket(byte* data, byte& len);

// Function to send a packet over the serial port
void sendPacket(const char* msg);

// Function to control the motion of the servo based on the angles and pen state
void motionServo(int &angleStart, int angleDest, int speed);

// Task to receive packets from the serial port and put them into the queue
void TaskRec(void *pvParameters);

// Task to process points from the queue and control the servo
void TaskEngine(void *pvParameters);

// Task to send telemetry data over the serial port
void TaskTelemetry(void *pvParameters);

void setup() {
  Serial.begin(115200);

  pen.write(80);  // Initialize pen to a neutral position
  servoDx.writeMicroseconds(1711);  // Initialize servoDx to a neutral position
  servoSx.writeMicroseconds(1288);  // Initialize servoSx to a neutral position

  pen.attach(pinPen);
  servoDx.attach(pinServoDx, MIN_PULSE_WIDTH, MAX_PULSE_WIDTH);
  servoSx.attach(pinServoSx, MIN_PULSE_WIDTH, MAX_PULSE_WIDTH);

  mut = xSemaphoreCreateMutex();

  queue = xQueueCreate(QUEUE_SIZE, sizeof(Point));
      
  xTaskCreate(TaskRec, "TaskRx", 220, NULL, 2, NULL);
  xTaskCreate(TaskEngine, "TaskEngine", 220, NULL, 3, NULL);
  xTaskCreate(TaskTelemetry, "TaskTelemetry", 140, NULL, 1, NULL);

  vTaskStartScheduler();
}

void loop() {}

/*
  TaskRec: This task continuously reads data from the serial port. 
  It looks for packets that start with a specific marker, followed by a length byte, the payload, a checksum, and an end marker. 
  When a valid packet is received, it extracts the angles and state from the payload and sends them to the queue for processing by the TaskEngine.
*/
void TaskRec(void *pvParameters) {
  static ReadState state = WAIT_START;
  static byte expectedLen = 0;
  static byte idx = 0;
  static byte checksum = 0;
  
  // Local buffer of task to store payload
  byte data[MAX_PAYLOAD]; 

  for (;;) {
    if (Serial.available() > 0) {
      byte b = Serial.read();

      switch (state) {
        case WAIT_START:
          if (b == START_MARKER) state = READ_LEN;
          break;

        case READ_LEN:
          expectedLen = b;
          if (expectedLen == 0 || expectedLen > MAX_PAYLOAD) {
            state = WAIT_START;
          } else {
            idx = 0;
            checksum = expectedLen;
            state = READ_PAYLOAD;
          }
          break;

        case READ_PAYLOAD:
          data[idx++] = b;
          checksum ^= b;
          if (idx >= expectedLen) state = READ_CHECKSUM;
          break;

        case READ_CHECKSUM:
          if (b == checksum) state = WAIT_END;
          else state = WAIT_START;
          break;

        case WAIT_END:
          if (b == END_MARKER) {

            data[idx] = '\0';
            Point newP;

            // We use strtok to split the data string into tokens based on the comma delimiter
            char *tok = strtok((char*)data, ",");

            if(tok!=NULL){
              newP.angleDx = atof(tok);  // Convert the first token to float for angleDx

              tok = strtok(NULL, ","); // Get the next token for angleSx
              if(tok!=NULL){
                newP.angleSx = atof(tok);  // Convert the second token to float for angleSx

                tok = strtok(NULL, ","); // Get the next token for state
                if(tok!=NULL){
                  newP.state = atoi(tok);  // Convert the third token to int for state

                  xQueueSend(queue, &newP, portMAX_DELAY);  // Send the new point to the queue
                }
              }
            }
            

            state = WAIT_START;
          } else {
            // Reset state if END_MARKER does not correspond
            state = WAIT_START;
          }
          break;
      }
    } 
    else {
      // If there are no data, task blocks
      vTaskDelay(1);
    }
  }
}

/*
  TaskEngine: This task is responsible for controlling the servos based on the points received from the queue. 
  It checks if there is a target point to reach. If not, it tries to get a new point from the queue. 
  If a new point is received, it calculates the target pulse widths for the servos based on the angles and moves the servos towards those targets. 
  It also updates telemetry data with the current angles and pen state.
*/
void TaskEngine(void *pvParameters) {
  Point p;
  const int speedUs = 10; // Maximum speed in microseconds per cycle

  // Current positions are stored as floats to maintain precision during fractional movement calculations
  static float correnteDxUs = 1711.0;
  static float targetDxUs   = 1711.0;
  
  static float correnteSxUs = 1288.0;
  static float targetSxUs   = 1288.0;
  
  static float stepDx = 0.0;
  static float stepSx = 0.0;
  static int totalSteps = 0;
  static int currentStep = 0;

  static bool target = false;

  TickType_t xLastWakeTime = xTaskGetTickCount();
  const TickType_t xPeriod = pdMS_TO_TICKS(T_te);

  for (;;) {

    // If no movement is currently in progress, attempt to fetch a new point from the queue
    if (!target) {
      if (xQueueReceive(queue, &p, 0) == pdPASS) {
        
        // Map target angles to pulse width values for the servo motors
        targetDxUs = map(p.angleDx * 100, 0, 18000, MIN_PULSE_WIDTH, MAX_PULSE_WIDTH);
        targetSxUs = map(p.angleSx * 100, 0, 18000, MIN_PULSE_WIDTH, MAX_PULSE_WIDTH);

        // Check if pen state has changed and handle lifting/lowering
        if (p.state != currentPoint.state) {
          pen.write(p.state);
          vTaskDelay(pdMS_TO_TICKS(1));
          xLastWakeTime = xTaskGetTickCount();
        }

        // --- Linear Interpolation Calculation ---
        int distDx = targetDxUs - (int)correnteDxUs;
        int distSx = targetSxUs - (int)correnteSxUs;
        
        // Determine which motor covers the greatest distance to synchronize movement
        int maxDist = max(abs(distDx), abs(distSx));

        if (maxDist > 0) {
          // Calculate the number of cycles required based on the slowest motor
          totalSteps = maxDist / speedUs;
          if (totalSteps == 0) totalSteps = 1; // Prevent division by zero for micro-movements

          // Calculate the exact increment per cycle for each motor
          stepDx = (float)distDx / totalSteps;
          stepSx = (float)distSx / totalSteps;
          
          currentStep = 0;
          target = true;
        } else {
          // Motors are already at the target coordinates
          target = false; 
        }
      }
    }

    // Execute synchronized movement
    if (target) {
      currentStep++;
      
      correnteDxUs += stepDx;
      correnteSxUs += stepSx;

      // Finish movement when all steps are completed
      if (currentStep >= totalSteps) {
        correnteDxUs = targetDxUs; // Force final target to prevent rounding errors
        correnteSxUs = targetSxUs;
        target = false;
      }

      // Update actual servo positions
      servoDx.writeMicroseconds((int)correnteDxUs);
      servoSx.writeMicroseconds((int)correnteSxUs);

      // Update telemetry data safely using a mutex
      if (xSemaphoreTake(mut, pdMS_TO_TICKS(5)) == pdTRUE) {
        currentPoint.angleDx = map((int)correnteDxUs, MIN_PULSE_WIDTH, MAX_PULSE_WIDTH, 0, 180);
        currentPoint.angleSx = map((int)correnteSxUs, MIN_PULSE_WIDTH, MAX_PULSE_WIDTH, 0, 180);
        currentPoint.state   = p.state;

        xSemaphoreGive(mut);
      }
    }

    vTaskDelayUntil(&xLastWakeTime, xPeriod);
  }
}


/*
  TaskTelemetry: This task is responsible for sending telemetry data to the host computer.
*/
void TaskTelemetry(void *pvParameters) {
  char telBuffer[32];
  
  TickType_t xLastWakeTime = xTaskGetTickCount();
  const TickType_t xPeriod = pdMS_TO_TICKS(T_tt); 

  for (;;) {
    // Get the number of messages currently in the queue
    int nQueue = uxQueueMessagesWaiting(queue);

    if (xSemaphoreTake(mut, pdMS_TO_TICKS(5)) == pdTRUE) {
      
      sprintf(telBuffer, "%d,%d,%d,%d", nQueue, (int)currentPoint.angleDx, (int)currentPoint.angleSx, currentPoint.state);

      xSemaphoreGive(mut);
    } else {
      // If the mutex is not available, send an error message
      sprintf(telBuffer, "ERR: Mutex Timeout");
    }
    
    sendPacket(telBuffer);

    // Task blocked until the next cycle
    vTaskDelayUntil(&xLastWakeTime, xPeriod);
  }
}


/*
  calcChecksum: This function calculates the checksum of a given data array using the XOR operation. 
  It takes a pointer to the data and its length as parameters and returns the calculated checksum.
*/
byte calcChecksum(const byte* data, byte len) {
  byte cs = 0;
  for (byte i = 0; i < len; i++) 
    cs ^= data[i];
  return cs;
}


/*
  readPacket: This function reads a packet from the serial port. 
  It looks for packets that start with a specific marker, followed by a length byte, the payload, a checksum, and an end marker. 
  When a valid packet is received, it extracts the payload and its length and returns true. 
  If no valid packet is found, it returns false.
*/
bool readPacket(byte* data, byte& len) {
  static ReadState state = WAIT_START;
  static byte expectedLen = 0;
  static byte idx = 0;
  static byte checksum = 0;

  while (Serial.available() > 0) {
    byte b = Serial.read();

    switch (state) {
      case WAIT_START:
        if (b == START_MARKER) state = READ_LEN;
        break;

      case READ_LEN:
        expectedLen = b;
        if (expectedLen == 0 || expectedLen > MAX_PAYLOAD) {
          state = WAIT_START;
        } else {
          idx = 0;
          checksum = expectedLen;
          state = READ_PAYLOAD;
        }
        break;

      case READ_PAYLOAD:
        data[idx++] = b;
        checksum ^= b;
        if (idx >= expectedLen) state = READ_CHECKSUM;
        break;

      case READ_CHECKSUM:
        if (b == checksum) state = WAIT_END;
        else state = WAIT_START;
        break;

      case WAIT_END:
        if (b == END_MARKER) {
          len = expectedLen;
          state = WAIT_START;
          return true;
        }
        state = WAIT_START;
        break;
    }
  }

  return false;
}

/*
  sendPacket: This function sends a packet over the serial port. 
  It takes a pointer to the message and its length as parameters. 
  It calculates the checksum and writes the packet with the appropriate markers.
*/
void sendPacket(const char* msg) {
  byte len = strlen(msg);
  if (len > MAX_PAYLOAD) 
    len = MAX_PAYLOAD;

  byte cs = len;
  Serial.write(START_MARKER);
  Serial.write(len);

  for (byte i = 0; i < len; i++) {
    byte b = (byte)msg[i];
    cs ^= b;
    Serial.write(b);
  }

  Serial.write(cs);
  Serial.write(END_MARKER);
}


/*
  motionServo: This function controls the movement of a servo motor. 
  It takes the current angle, the destination angle, and the speed as parameters. 
  It moves the servo from the current angle towards the destination angle at the specified speed.
*/
void motionServo(int &angleStart, int angleDest, int speed) {
  // Move the angleStart towards angleDest by speed units
  if(angleStart < angleDest){
    angleStart += speed;
    if(angleStart > angleDest) angleStart = angleDest;
  } else if (angleStart > angleDest){
    angleStart -= speed;
    if(angleStart < angleDest) angleStart = angleDest;
  }

}
