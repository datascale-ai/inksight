#ifndef INKSIGHT_OTA_H
#define INKSIGHT_OTA_H

#include <Arduino.h>

// Global OTA parameters set by network.cpp when parsing state JSON
extern String g_pending_ota_url;
extern String g_pending_ota_version;

// Check and perform OTA if a pending update is set.
// Called from handleLiveMode() after hasPendingRemoteAction() returns true.
// Returns true if OTA was executed (success or failure),
// false if no OTA was pending.
bool checkAndPerformOTA();

#endif  // INKSIGHT_OTA_H
