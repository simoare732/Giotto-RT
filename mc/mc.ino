#include <Servo.h>

Servo pen;
int pinPen = 2;

const byte START_MARKER = 0xFE;
const byte END_MARKER = 0xFF;
const byte BUFFER_SIZE = 32;
byte receivedData[BUFFER_SIZE];
byte bytesRecvd = 0;
boolean dataReady = false;

void setup() {
  Serial.begin(9600);
  pen.attach(pinPen);
  delay(2000);
  // Segnala al Python che il setup è completato
  Serial.println("Arduino ready!");
}

void loop() {
  recvWithStartEndMarkers();

  // Elabora i dati solo se un pacchetto completo è stato ricevuto
  if (dataReady == true) {
    processData();
  }
}

void recvWithStartEndMarkers() {
  static boolean recvInProgress = false;
  byte rc;

  while (Serial.available() > 0 && dataReady == false) {
    rc = Serial.read();

    if (recvInProgress == false) {
      if (rc == START_MARKER) {
        recvInProgress = true;
        bytesRecvd = 0;
      }
    } else {
      if (rc == END_MARKER) {
        recvInProgress = false;
        dataReady = true;
      } else {
        if (bytesRecvd < BUFFER_SIZE - 1) { // -1 per lasciare spazio al terminatore nullo
          receivedData[bytesRecvd] = rc;
          bytesRecvd++;
        }
      }
    }
  }
}

void processData() {
  receivedData[bytesRecvd] = 0;  // Null terminator per convertire l'array in stringa
  String message = String((char*)receivedData);
  
  Serial.print("Received: ");
  Serial.println(message);
  
  // Converti il messaggio in numero
  int angle = message.toInt();
  
  if (angle >= 0 && angle <= 180) {
    pen.write(angle);
    Serial.print("Servo moved to: ");
    Serial.println(angle);
  } else {
    Serial.println("Invalid angle");
  }

  // Resetta lo stato per permettere la ricezione del pacchetto successivo
  dataReady = false;
}
