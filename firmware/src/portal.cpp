#include "portal.h"
#include "config.h"
#include "storage.h"
#include "network.h"

#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <esp_system.h>

#include "../data/portal_html.h"

// ── Portal state ────────────────────────────────────────────
bool portalActive    = false;
bool wifiConnected   = false;

static bool     wifiConnecting = false;
static String   lastWifiError  = "";
static bool     pendingRestart = false;
static unsigned long restartAtMillis = 0;

static WebServer webServer(80);
static DNSServer dnsServer;

// ── Input validation helpers ────────────────────────────────

static const int PORTAL_MAX_SSID   = 32;
static const int PORTAL_MAX_PASS   = 64;
static const int PORTAL_MAX_URL    = 200;
static const int PORTAL_MAX_CONFIG = 2048;

static String generatePairCode();

static String sanitizeInput(const String &input, int maxLen) {
    String result = input.substring(0, maxLen);
    result.trim();
    result.replace("<", "");
    result.replace(">", "");
    return result;
}

static String sanitizeTextInput(const String &input, int maxLen) {
    String result = sanitizeInput(input, maxLen);
    result.replace("\"", "");
    result.replace("'", "");
    result.replace("&", "");
    result.replace("\\", "");
    return result;
}

static String sanitizeSSID(const String &input) {
    String result = sanitizeTextInput(input, PORTAL_MAX_SSID);
    // Remove control characters (keep printable ASCII + UTF-8 multibyte)
    String cleaned;
    for (unsigned int i = 0; i < result.length(); i++) {
        char c = result.charAt(i);
        if (c >= 32 || (c & 0x80)) cleaned += c;
    }
    return cleaned;
}

static bool isValidJson(const String &s) {
    // Minimal check: starts with { and ends with }, contains "modes"
    if (s.length() < 2) return false;
    if (s.charAt(0) != '{' || s.charAt(s.length() - 1) != '}') return false;
    if (s.indexOf("\"modes\"") < 0) return false;
    return true;
}

static bool isValidUrl(const String &url) {
    return url.startsWith("http://") || url.startsWith("https://");
}

// Escape a string for safe embedding in a JSON string literal.
static String jsonEscape(const String &s) {
    String out;
    for (unsigned int i = 0; i < s.length(); i++) {
        char c = s.charAt(i);
        if (c == '"' || c == '\\') { out += '\\'; out += c; }
        else if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else if (c == '\t') out += "\\t";
        else out += c;
    }
    return out;
}

// Build {"networks":["a","b"],"max":N} from the saved WiFi list.
static String buildWiFiListJson() {
    String names[MAX_WIFI_NETWORKS];
    int count = 0;
    getWiFiSSIDList(names, count);
    String json = "{\"networks\":[";
    for (int i = 0; i < count; i++) {
        if (i > 0) json += ",";
        json += "\"" + jsonEscape(names[i]) + "\"";
    }
    json += "],\"max\":" + String(MAX_WIFI_NETWORKS) + "}";
    return json;
}

static bool findSavedWiFiPassword(const String &targetSsid, String &passOut) {
    int count = getWiFiCount();
    for (int i = 0; i < count; i++) {
        String savedSsid, savedPass;
        if (!getWiFiAt(i, savedSsid, savedPass)) continue;
        if (savedSsid == targetSsid) {
            passOut = savedPass;
            return true;
        }
    }
    return false;
}

static bool connectPortalWiFi(const String &ssid, const String &pass) {
    Serial.printf("Portal: connecting to %s\n", ssid.c_str());
    wifiConnecting = true;
    lastWifiError  = "";

    WiFi.mode(WIFI_AP_STA);
    WiFi.begin(ssid.c_str(), pass.c_str());

    unsigned long t0 = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t0 < (unsigned long)WIFI_TIMEOUT) {
        delay(300);
        Serial.print(".");
    }
    Serial.println();

    wifiConnecting = false;

    if (WiFi.status() == WL_CONNECTED) {
        wifiConnected = true;
        lastWifiError = "";
        Serial.printf("WiFi OK  IP=%s\n", WiFi.localIP().toString().c_str());
        return true;
    }

    uint8_t reason = WiFi.status();
    Serial.printf("WiFi connection failed, status code: %d\n", reason);
    if (reason == WL_NO_SSID_AVAIL) {
        lastWifiError = "NO_SSID";
    } else if (reason == WL_CONNECT_FAILED) {
        lastWifiError = "AUTH_FAIL";
    } else {
        lastWifiError = "TIMEOUT";
    }
    WiFi.disconnect();
    WiFi.mode(WIFI_AP_STA);
    return false;
}

static void sendPortalConnectSuccess() {
    String pairCode = generatePairCode();
    savePendingPairCode(pairCode);
    Serial.printf("[PAIR] local pair code: %s\n", pairCode.c_str());
    String response = String("{\"ok\":true,\"pair_code\":\"") + pairCode +
                      "\",\"list\":" + buildWiFiListJson() + "}";
    Serial.printf("Sending response: %s\n", response.c_str());
    webServer.send(200, "application/json", response);

    pendingRestart  = true;
    restartAtMillis = millis() + 15000;
    Serial.println("Restart scheduled in 15s (or earlier via /restart)");
}

static String generatePairCode() {
    char buf[7];
    snprintf(buf, sizeof(buf), "%06u", (unsigned)(esp_random() % 1000000));
    return String(buf);
}

static void resetPortalProvisioningState() {
    pendingRestart = false;
    restartAtMillis = 0;
    wifiConnected = false;
    wifiConnecting = false;
    lastWifiError = "";
    clearPendingPairCode();
    WiFi.disconnect();
    WiFi.mode(WIFI_AP_STA);
}

// ── Start captive portal ────────────────────────────────────

void startCaptivePortal() {
    String mac = WiFi.macAddress();
    String apName = "InkSight-" + mac.substring(mac.length() - 5);
    apName.replace(":", "");

    WiFi.mode(WIFI_AP_STA);
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

        // Deduplicate by SSID, keeping the strongest signal
        struct NetInfo { String ssid; int rssi; bool secure; };
        NetInfo best[32];
        int count = 0;
        for (int i = 0; i < n; i++) {
            String ssid = WiFi.SSID(i);
            if (ssid.length() == 0) continue;
            int rssi = WiFi.RSSI(i);
            bool secure = (WiFi.encryptionType(i) != WIFI_AUTH_OPEN);
            int found = -1;
            for (int j = 0; j < count; j++) {
                if (best[j].ssid == ssid) { found = j; break; }
            }
            if (found >= 0) {
                if (rssi > best[found].rssi) {
                    best[found].rssi = rssi;
                    best[found].secure = secure;
                }
            } else if (count < 32) {
                best[count++] = { ssid, rssi, secure };
            }
        }

        // Sort by signal strength (strongest first)
        for (int i = 0; i < count - 1; i++)
            for (int j = i + 1; j < count; j++)
                if (best[j].rssi > best[i].rssi) {
                    NetInfo tmp = best[i]; best[i] = best[j]; best[j] = tmp;
                }

        String json = "{\"networks\":[";
        for (int i = 0; i < count; i++) {
            if (i > 0) json += ",";
            json += "{\"ssid\":\"" + best[i].ssid + "\",";
            json += "\"rssi\":" + String(best[i].rssi) + ",";
            json += "\"secure\":" + String(best[i].secure ? "true" : "false") + "}";
        }
        json += "]}";

        webServer.sendHeader("Access-Control-Allow-Origin", "*");
        webServer.send(200, "application/json", json);
        Serial.printf("Scan response sent (%d unique networks)\n", count);
    });

    // ── Route: Device info ──────────────────────────────────
    webServer.on("/info", HTTP_GET, []() {
        float v = readBatteryVoltage();
        String json = "{\"mac\":\"" + WiFi.macAddress() + "\",";
        json += "\"battery\":\"" + String(v, 2) + "V\",";
        json += "\"server_url\":\"" + cfgServer + "\"}";
        webServer.send(200, "application/json", json);
    });

    // ── Route: WiFi connection status ──────────────────────────
    webServer.on("/status", HTTP_GET, []() {
        String json = "{\"state\":\"";
        if (WiFi.status() == WL_CONNECTED) {
            json += "connected\",\"ip\":\"" + WiFi.localIP().toString() + "\"";
        } else if (wifiConnecting) {
            json += "connecting\"";
        } else if (lastWifiError.length() > 0) {
            json += "failed\",\"error\":\"" + lastWifiError + "\"";
        } else {
            json += "idle\"";
        }
        json += "}";
        webServer.sendHeader("Access-Control-Allow-Origin", "*");
        webServer.send(200, "application/json", json);
    });

    // ── Route: Save WiFi credentials (async with polling) ────
    webServer.on("/save_wifi", HTTP_POST, []() {
        String ssid = sanitizeSSID(webServer.arg("ssid"));
        String pass = sanitizeTextInput(webServer.arg("pass"), PORTAL_MAX_PASS);
        String serverUrl = sanitizeInput(webServer.arg("server"), PORTAL_MAX_URL);

        Serial.printf("\n--- /save_wifi Request ---\n");
        Serial.printf("SSID: %s\n", ssid.c_str());
        Serial.printf("Server: %s\n", serverUrl.c_str());

        if (ssid.length() == 0) {
            Serial.println("Error: SSID empty");
            webServer.send(200, "application/json", "{\"ok\":false,\"msg\":\"SSID empty\"}");
            return;
        }

        if (serverUrl.length() > 0) {
            if (!isValidUrl(serverUrl)) {
                webServer.send(200, "application/json",
                               "{\"ok\":false,\"msg\":\"服务器地址必须以 http:// 或 https:// 开头\"}");
                return;
            }
            // Remove trailing slash
            while (serverUrl.endsWith("/")) {
                serverUrl = serverUrl.substring(0, serverUrl.length() - 1);
            }
            saveServerUrl(serverUrl);
            Serial.printf("Server URL saved: %s\n", serverUrl.c_str());
        }

        if (connectPortalWiFi(ssid, pass)) {
            saveWiFiConfig(ssid, pass);
            sendPortalConnectSuccess();
        } else {
            String msg;
            if (lastWifiError == "NO_SSID")    msg = "找不到该网络";
            else if (lastWifiError == "AUTH_FAIL") msg = "密码错误";
            else                                   msg = "连接超时，请重试";
            
            Serial.printf("Sending error response: %s\n", msg.c_str());
            webServer.send(200, "application/json",
                           "{\"ok\":false,\"msg\":\"" + msg + "\"}");
        }
    });

    // ── Route: Connect using a saved network password ───────
    webServer.on("/connect_saved", HTTP_POST, []() {
        String ssid = sanitizeSSID(webServer.arg("ssid"));
        String serverUrl = sanitizeInput(webServer.arg("server"), PORTAL_MAX_URL);
        webServer.sendHeader("Access-Control-Allow-Origin", "*");

        Serial.printf("\n--- /connect_saved Request ---\n");
        Serial.printf("SSID: %s\n", ssid.c_str());
        Serial.printf("Server: %s\n", serverUrl.c_str());

        if (ssid.length() == 0) {
            webServer.send(200, "application/json", "{\"ok\":false,\"msg\":\"SSID empty\"}");
            return;
        }

        String pass;
        if (!findSavedWiFiPassword(ssid, pass)) {
            webServer.send(200, "application/json",
                           "{\"ok\":false,\"msg\":\"NOT_FOUND\",\"list\":" + buildWiFiListJson() + "}");
            return;
        }

        if (serverUrl.length() > 0) {
            if (!isValidUrl(serverUrl)) {
                webServer.send(200, "application/json",
                               "{\"ok\":false,\"msg\":\"服务器地址必须以 http:// 或 https:// 开头\"}");
                return;
            }
            while (serverUrl.endsWith("/")) {
                serverUrl = serverUrl.substring(0, serverUrl.length() - 1);
            }
            saveServerUrl(serverUrl);
            Serial.printf("Server URL saved: %s\n", serverUrl.c_str());
        }

        if (connectPortalWiFi(ssid, pass)) {
            // Re-saving an existing SSID promotes it to slot 0.
            addWiFiConfig(ssid, pass);
            sendPortalConnectSuccess();
        } else {
            Serial.println("[PORTAL] Saved network connect failed");
            webServer.send(200, "application/json",
                           "{\"ok\":false,\"msg\":\"SAVED_CONNECT_FAILED\",\"list\":" + buildWiFiListJson() + "}");
        }
    });

    // ── Route: Save user config ─────────────────────────────
    webServer.on("/save_config", HTTP_POST, []() {
        String config = sanitizeInput(webServer.arg("config"), PORTAL_MAX_CONFIG);
        if (config.length() == 0) {
            webServer.send(200, "application/json", "{\"ok\":false,\"msg\":\"Config empty\"}");
            return;
        }
        if (!isValidJson(config)) {
            webServer.send(200, "application/json", "{\"ok\":false,\"msg\":\"Invalid config format\"}");
            return;
        }
        saveUserConfig(config);
        Serial.println("Config saved to NVS");
        webServer.send(200, "application/json", "{\"ok\":true}");

        // Post config to backend if connected
        if (wifiConnected) {
            delay(500);
            postConfigToBackend();
        }

        // Schedule a deferred restart (30s) — front-end can call /restart sooner
        pendingRestart  = true;
        restartAtMillis = millis() + 30000;
        Serial.println("Restart scheduled in 30 seconds (or earlier via /restart)");
    });

    // ── Route: List saved WiFi networks (names only) ────────
    webServer.on("/wifi_list", HTTP_GET, []() {
        webServer.sendHeader("Access-Control-Allow-Origin", "*");
        webServer.send(200, "application/json", buildWiFiListJson());
    });

    // ── Route: Add a network to the saved list (no connect) ──
    // Used to pre-register secondary networks (office / phone hotspot) that
    // are not reachable from the current location. No restart is triggered.
    webServer.on("/add_wifi", HTTP_POST, []() {
        String ssid = sanitizeSSID(webServer.arg("ssid"));
        String pass = sanitizeTextInput(webServer.arg("pass"), PORTAL_MAX_PASS);
        webServer.sendHeader("Access-Control-Allow-Origin", "*");
        if (ssid.length() == 0) {
            webServer.send(200, "application/json", "{\"ok\":false,\"msg\":\"SSID empty\"}");
            return;
        }
        if (addWiFiConfig(ssid, pass)) {
            Serial.printf("[PORTAL] Added saved network: %s\n", ssid.c_str());
            webServer.send(200, "application/json",
                           "{\"ok\":true,\"list\":" + buildWiFiListJson() + "}");
        } else {
            webServer.send(200, "application/json",
                           "{\"ok\":false,\"msg\":\"FULL\"}");
        }
    });

    // ── Route: Delete a saved network by SSID ───────────────
    webServer.on("/delete_wifi", HTTP_POST, []() {
        String ssid = sanitizeSSID(webServer.arg("ssid"));
        bool ok = deleteWiFiBySSID(ssid);
        Serial.printf("[PORTAL] Delete network '%s' -> %s\n", ssid.c_str(), ok ? "ok" : "not found");
        webServer.sendHeader("Access-Control-Allow-Origin", "*");
        webServer.send(200, "application/json",
                       String("{\"ok\":") + (ok ? "true" : "false") +
                       ",\"list\":" + buildWiFiListJson() + "}");
    });

    // ── Route: Manual restart ───────────────────────────────
    webServer.on("/restart", HTTP_POST, []() {
        Serial.println("\n--- /restart Request Received ---");
        webServer.send(200, "application/json", "{\"ok\":true}");
        Serial.println("Manual restart requested, restarting in 1 second...");
        delay(1000);
        ESP.restart();
    });

    webServer.on("/reset_portal", HTTP_POST, []() {
        Serial.println("\n--- /reset_portal Request Received ---");
        resetPortalProvisioningState();
        webServer.send(200, "application/json", "{\"ok\":true}");
        Serial.println("Portal reset requested, staying in provisioning mode");
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

    // Deferred restart after config save
    if (pendingRestart && millis() >= restartAtMillis) {
        Serial.println("Deferred restart triggered");
        delay(200);
        ESP.restart();
    }
}
