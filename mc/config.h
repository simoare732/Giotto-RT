/*
 * File automatically generated on 2026-07-09 12:37:51
 * WARNING: Do not modify this file manually.
 * Edit 'config.yaml' and regenerate using the Python script.
 */

#ifndef CONFIG_H
#define CONFIG_H

// --- IMAGE_CONFIG ---
#define IMAGE_WIDTH 250
#define IMAGE_HEIGHT 250
#define THRESHOLD 0.5

// --- SHEET_CONFIG ---
#define MIN_X -50
#define MAX_X 50
#define MIN_Y 27
#define MAX_Y 125

// --- GIOTTO_CONFIG ---
#define PIN_PEN 2
#define PIN_SERVO_LEFT 3
#define PIN_SERVO_RIGHT 4
#define NEUTRAL_POSITION_SERVOSX 1288
#define NEUTRAL_POSITION_SERVODX 1711
#define SERVO_DISTANCE 25.8
#define L1 60.0
#define L2 70.0
#define PEN_UP_ANGLE 80
#define PEN_DOWN_ANGLE 20
#define SKEW_SX -4.0
#define SKEW_DX 0.0

// --- GLOBAL_VARIABLES ---
#define BAUD_RATE 115200
#define ENABLE_LOG false
#define MAX_PAYLOAD_VALUE 32
#define QUEUE_SIZE 30
#define THRESHOLD_FULL_QUEUE 20
#define START_MARKER_VALUE 0xFE
#define END_MARKER_VALUE 0xFF
#define BUFFER_SIZE 32

// --- TASK_VARIABLES ---
#define PERIOD_TASK_ENGINE 20
#define PERIOD_TASK_TELEMETRY 30
#define PRIORITY_TASK_ENGINE 3
#define PRIORITY_TASK_TELEMETRY 1
#define PRIORITY_TASK_REC 2

#endif // CONFIG_H
