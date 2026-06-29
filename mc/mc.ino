#include <Servo.h>

Servo pen;
int pinPen = 2;

const byte START_MARKER = 0xFE;
const byte END_MARKER   = 0xFF;
const byte MAX_PAYLOAD  = 32;

byte payload[MAX_PAYLOAD];
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
  ReadState state = WAIT_START;
  byte expectedLen = 0;
  byte idx = 0;
  byte checksum = 0;

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
void sendPacket(const String& msg) {
  byte len = msg.length();
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

void setup() {
  Serial.begin(9600);
  pen.attach(pinPen);
  delay(2000);
}

void loop() {
  if (readPacket(payload, payloadLen)) {
    payload[payloadLen] = 0;
    String message = String((char*)payload);

    int anglePen = message.toInt();
    if (anglePen >= 0 && anglePen <= 180) {
      pen.write(anglePen);
      sendPacket("Confirmation: Angle set to " + String(anglePen));
    } else {
      sendPacket("ERR: Invalid angle");
    }
  }
}