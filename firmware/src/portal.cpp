#include "portal.h"
#include "config.h"
#include "storage.h"
#include "network.h"

#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>

#include "../data/portal_html.h"

// ── Portal state ────────────────────────────────────────────
bool portalActive  = false;
bool wifiConnected = false;

static WebServer webServer(80);
static DNSServer dnsServer;

// ── Input validation helpers ────────────────────────────────

static const int PORTAL_MAX_SSID   = 32;
static const int PORTAL_MAX_PASS   = 64;
static const int PORTAL_MAX_URL    = 200;
static const int PORTAL_MAX_CONFIG = 2048;

static String sanitizeInput(const String &input, int maxLen) {
    String result = input.substring(0, maxLen);
    result.trim();
    return result;
}

static bool isValidUrl(const String &url) {
    return url.startsWith("http://") || url.startsWith("https://");
}

// ── Start captive portal ────────────────────────────────────

void startCaptivePortal() {
    String mac = WiFi.macAddress();
    String apName = "InkSight-" + mac.substring(mac.length() - 5);
    apName.replace(":", "");

    WiFi.mode(WIFI_AP);
    WiFi.softAP(apName.c_str());
    delay(100);

    Serial.printf("AP started: %s  IP: %s\n",
                  apName.c_str(), WiFi.softAPIP().toString().c_str());

    dnsServer.start(53, "*", WiFi.softAPIP());

    // ── Route: Portal home page ─────────────────────────────
    webServer.on("/", HTTP_GET, []() {
        webServer.send(200, "text/html", PORTAL_HTML);
    });

    // ── Route: WiFi network scan ────────────────────────────
    webServer.on("/scan", HTTP_GET, []() {
        Serial.println("Scanning WiFi networks...");
        int n = WiFi.scanNetworks();
        Serial.printf("Found %d networks\n", n);

        String json = "{\"networks\":[";
        for (int i = 0; i < n; i++) {
            if (i > 0) json += ",";
            json += "{\"ssid\":\"" + WiFi.SSID(i) + "\",";
            json += "\"rssi\":" + String(WiFi.RSSI(i)) + ",";
            json += "\"secure\":" + String(WiFi.encryptionType(i) != WIFI_AUTH_OPEN ? "true" : "false") + "}";
        }
        json += "]}";

        webServer.sendHeader("Access-Control-Allow-Origin", "*");
        webServer.send(200, "application/json", json);
        Serial.println("Scan response sent");
    });

    // ── Route: Device info ──────────────────────────────────
    webServer.on("/info", HTTP_GET, []() {
        float v = readBatteryVoltage();
        String json = "{\"mac\":\"" + WiFi.macAddress() + "\",";
        json += "\"battery\":\"" + String(v, 2) + "V\",";
        json += "\"server_url\":\"" + cfgServer + "\"}";
        webServer.send(200, "application/json", json);
    });

    // ── Route: Save WiFi credentials ────────────────────────
    webServer.on("/save_wifi", HTTP_POST, []() {
        String ssid = sanitizeInput(webServer.arg("ssid"), PORTAL_MAX_SSID);
        String pass = sanitizeInput(webServer.arg("pass"), PORTAL_MAX_PASS);

        if (ssid.length() == 0) {
            webServer.send(200, "application/json", "{\"ok\":false,\"msg\":\"SSID empty\"}");
            return;
        }

        Serial.printf("Portal: connecting to %s\n", ssid.c_str());

        WiFi.mode(WIFI_AP_STA);
        WiFi.begin(ssid.c_str(), pass.c_str());

        unsigned long t0 = millis();
        while (WiFi.status() != WL_CONNECTED && millis() - t0 < (unsigned long)WIFI_TIMEOUT) {
            delay(300);
        }

        if (WiFi.status() == WL_CONNECTED) {
            saveWiFiConfig(ssid, pass);
            wifiConnected = true;
            Serial.printf("WiFi OK  IP=%s\n", WiFi.localIP().toString().c_str());
            webServer.send(200, "application/json", "{\"ok\":true}");
        } else {
            WiFi.disconnect();
            WiFi.mode(WIFI_AP);
            webServer.send(200, "application/json",
                           "{\"ok\":false,\"msg\":\"连接失败，请检查密码\"}");
        }
    });

    // ── Route: Save user config ─────────────────────────────
    webServer.on("/save_config", HTTP_POST, []() {
        String config = sanitizeInput(webServer.arg("config"), PORTAL_MAX_CONFIG);
        if (config.length() == 0) {
            webServer.send(200, "application/json", "{\"ok\":false,\"msg\":\"Config empty\"}");
            return;
        }
        saveUserConfig(config);
        Serial.println("Config saved to NVS");
        webServer.send(200, "application/json", "{\"ok\":true}");

        // Post config to backend if connected
        delay(500);
        if (wifiConnected) {
            postConfigToBackend();
        }

        // Keep serving requests for 35 seconds before restart
        Serial.println("Scheduling restart in 35 seconds...");
        unsigned long restartTime = millis() + 35000;
        while (millis() < restartTime) {
            dnsServer.processNextRequest();
            webServer.handleClient();
            delay(10);
        }

        Serial.println("Restarting now...");
        ESP.restart();
    });

    // ── Route: Manual restart ───────────────────────────────
    webServer.on("/restart", HTTP_POST, []() {
        webServer.send(200, "application/json", "{\"ok\":true}");
        Serial.println("Manual restart requested, restarting in 1 second...");
        delay(1000);
        ESP.restart();
    });

    // ── Captive portal redirect for all other requests ──────
    webServer.onNotFound([]() {
        String path = webServer.uri();

        // Silently handle captive portal detection URLs
        if (path == "/generate_204" || path == "/gen_204" ||
            path == "/hotspot-detect.html" || path == "/canonical.html" ||
            path == "/success.txt" || path == "/ncsi.txt") {
            webServer.send(204);
            return;
        }

        // Ignore common resource requests
        if (path.endsWith(".ico") || path.endsWith(".png") || path.endsWith(".jpg")) {
            webServer.send(404);
            return;
        }

        // Redirect everything else to portal
        webServer.sendHeader("Location", "http://" + WiFi.softAPIP().toString());
        webServer.send(302, "text/plain", "");
    });

    webServer.begin();
    portalActive = true;
    Serial.println("Captive portal started");
}

// ── Handle pending requests ─────────────────────────────────

void handlePortalClients() {
    dnsServer.processNextRequest();
    webServer.handleClient();
}
