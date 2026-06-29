#include <Servo.h>
#include <Arduino_FreeRTOS.h>
#include <queue.h>

// The packet from HOST will contain these information in format angleDx,angleSx,state
struct Point{
  uint8_t angleDx;
  uint8_t angleSx;
  bool state; // true = pen down, false = pen up
};

QueueHandle_t queue;

Servo pen;
int pinPen = 2;

int angleArmSx = 0;
int angleArmDx = 0;
bool PositionPen = false; // true = pen down, false = pen up

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

// Function to calculate checksum using XOR operation
byte calcChecksum(const byte* data, byte len) {
  byte cs = 0;
  for (byte i = 0; i < len; i++) 
    cs ^= data[i];
  return cs;
}

// Function to read a packet from the serial port
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

// Function to send a packet over the serial port
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
  Serial.flush();
}

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

            int tempDx = 0;
            int tempSx = 0;
            int tempState = 0;

            // Read 3 points, and put them into the queue
            int fields = sscanf((char*)data, "%d,%d,%d", &tempDx, &tempSx, &tempState);
  
            if (fields == 3) {
              newP.angleDx = tempDx;
              newP.angleSx = tempSx;
              newP.state   = (tempState != 0);

              xQueueSend(queue, &newP, portMAX_DELAY); 
              
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
      vTaskDelay(pdMS_TO_TICKS(1));
    }
  }
}


void TaskEngine(void *pvParameters){
  Point p;
  ackBuffer[32];

  for (;;) {
    if (xQueueReceive(queue, &p, portMAX_DELAY) == pdPASS) {
      pen.write(p.angleDx);
      
      sprintf(ackBuffer, "Angle set to %d", p.angleDx);
      sendPacket(ackBuffer);
    }
  }
}

void setup() {
  Serial.begin(9600);
  pen.attach(pinPen);

  queue = xQueueCreate(20, sizeof(Point));
      
  xTaskCreate(TaskRec, "TaskRx", 220, NULL, 2, NULL);
  xTaskCreate(TaskEngine, "TaskEngine", 220, NULL, 3, NULL);
  vTaskStartScheduler();
}

void loop() {
}
