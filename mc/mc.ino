#include <Servo.h>
#include <Arduino_FreeRTOS.h>
#include <queue.h>
#include <semphr.h>


// The packet from HOST will contain these information in format angleDx,angleSx,state
struct Point{
  uint8_t angleDx;
  uint8_t angleSx;
  uint8_t state;
};
Point currentPoint;  // Global variable to store the current point being processed
SemaphoreHandle_t mut;  // Semaphore to protect access to currentPoint

QueueHandle_t queue;
const uint8_t QUEUE_SIZE = 20;

Servo pen;
Servo servoDx;
Servo servoSx;

int pinPen = 3;
int pinServoDx = 2;
int pinServoSx = 4;

const byte START_MARKER = 0xFE;
const byte END_MARKER   = 0xFF;
const byte MAX_PAYLOAD  = 32;

byte payload[MAX_PAYLOAD+1];
byte payloadLen = 0;

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

  pen.write(90);  // Initialize pen to a neutral position
  servoDx.writeMicroseconds(1500);  // Initialize servoDx to a neutral position
  servoSx.writeMicroseconds(1500);  // Initialize servoSx to a neutral position

  pen.attach(pinPen);
  servoDx.attach(pinServoDx);
  servoSx.attach(pinServoSx);

  mut = xSemaphoreCreateMutex();

  queue = xQueueCreate(QUEUE_SIZE, sizeof(Point));
      
  xTaskCreate(TaskRec, "TaskRx", 220, NULL, 2, NULL);
  xTaskCreate(TaskEngine, "TaskEngine", 220, NULL, 3, NULL);
  xTaskCreate(TaskTelemetry, "TaskTelemetry", 140, NULL, 1, NULL);

  vTaskStartScheduler();
}

void loop() {}


void TaskRec(void *pvParameters) {
  static ReadState state = WAIT_START;
  static byte expectedLen = 0;
  static byte idx = 0;
  static byte checksum = 0;


  unsigned long tempoInizio;
  unsigned long tempoFine;
  unsigned long tempoEsecuzione;
  
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

            //tempoInizio = micros();
            
            data[idx] = '\0';
            Point newP;

            int tempDx = 0;
            int tempSx = 0;
            int tempState = 0;

            // Read 3 points, and put them into the queue
            int fields = sscanf((char*)data, "%d,%d,%d", &tempDx, &tempSx, &tempState);
  
            if (fields == 3) {
              newP.angleDx = tempDx;
              newP.angleSx = tempSx;
              newP.state   = tempState;

              xQueueSend(queue, &newP, portMAX_DELAY); 
              
            }

            //tempoFine = micros();
            //tempoEsecuzione = tempoFine - tempoInizio;
            
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


void TaskEngine(void *pvParameters){
  Point p;

  const int MIN_PULSE = 500;
  const int MAX_PULSE = 2500;
  
  // Speed of drawing 
  const int stepUs = 10; 

  // Variables for the current and target pulse widths for the servos
  static int correnteDxUs = 1500;
  static int targetDxUs   = 1500;
  
  static int correnteSxUs = 1500;
  static int targetSxUs   = 1500;

  static bool target = false;  // Flag to indicate if there is already a target to reach

  unsigned long tempoInizio;
  unsigned long tempoFine;
  unsigned long tempoEsecuzione;

  // The time of last wake up
  TickType_t xLastWakeTime = xTaskGetTickCount();
  const TickType_t xPeriod = pdMS_TO_TICKS(T_te); // Period of task in ticks

  for (;;) {

    // If there is no target, try to get a new point from the queue
    if(!target){
      if (xQueueReceive(queue, &p, 0) == pdPASS){
        targetDxUs = map(p.angleDx, 0, 180, MIN_PULSE, MAX_PULSE);
        targetSxUs = map(p.angleSx, 0, 180, MIN_PULSE, MAX_PULSE);

        if(p.state != currentPoint.state){
          pen.write(p.state);

          // Wait for 150ms to allow the pen to move up or down before continuing
          vTaskDelay(pdMS_TO_TICKS(150)); 
          
          // The period of the task start over from now 
          xLastWakeTime = xTaskGetTickCount();
        }

        target = true;
      }
    }

    // If there is a target, move the servos towards the target angles
    if(target){

      // Compute the new pulse width for the right servo
      motionServo(correnteDxUs, targetDxUs, stepUs);

      // Compute the new pulse width for the left servo
      motionServo(correnteSxUs, targetSxUs, stepUs);

      servoDx.writeMicroseconds(correnteDxUs);
      servoSx.writeMicroseconds(correnteSxUs);

      // Update telemetry with the current angles
      if (xSemaphoreTake(mut, pdMS_TO_TICKS(5)) == pdTRUE){
        currentPoint.angleDx = map(correnteDxUs, MIN_PULSE, MAX_PULSE, 0, 180);
        currentPoint.angleSx = map(correnteSxUs, MIN_PULSE, MAX_PULSE, 0, 180);
        currentPoint.state   = p.state;

        xSemaphoreGive(mut);
      }

      if(correnteDxUs == targetDxUs && correnteSxUs == targetSxUs){
        target = false;  // Target reached, reset the flag
      }
    }

    vTaskDelayUntil(&xLastWakeTime, xPeriod); // Wait for the next cycle
  }
}


void TaskTelemetry(void *pvParameters) {
  char telBuffer[32];
  
  TickType_t xLastWakeTime = xTaskGetTickCount();
  const TickType_t xPeriod = pdMS_TO_TICKS(T_tt); 

  for (;;) {
    // Get the number of messages currently in the queue
    int nQueue = uxQueueMessagesWaiting(queue);

    if (xSemaphoreTake(mut, pdMS_TO_TICKS(5)) == pdTRUE) {
      
      sprintf(telBuffer, "%d,%d,%d,%d", nQueue, currentPoint.angleDx, currentPoint.angleSx, currentPoint.state);

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



byte calcChecksum(const byte* data, byte len) {
  byte cs = 0;
  for (byte i = 0; i < len; i++) 
    cs ^= data[i];
  return cs;
}


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