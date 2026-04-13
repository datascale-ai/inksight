#ifndef INKSIGHT_OTA_H
#define INKSIGHT_OTA_H

#include <Arduino.h>

// Global OTA parameters set by network.cpp when parsing state JSON
extern String g_pending_ota_url;
extern String g_pending_ota_version;

// Check and execute OTA if a pending update is set.
// This launches an independent FreeRTOS task (12KB stack) to avoid
// stack overflow in loopTask when the ESP32-C3 performs HTTPS/TLS
// OTA downloads.
// Returns true if an OTA task was started, false if no OTA was pending.
// Note: on success the device reboots; on failure the task clears the
// pending globals internally. The caller should NOT clear them.
bool checkAndPerformOTA();

// Returns true if an OTA task is currently running.
bool isOtaTaskRunning();

#endif  // INKSIGHT_OTA_H
