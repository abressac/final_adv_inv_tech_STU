#include <ESP8266WiFi.h>
#include <Adafruit_Sensor.h>
#include <DHT.h>
#include <DHT_U.h>

#define DHTPIN 5
#define DHTTYPE DHT11

DHT_Unified dht(DHTPIN, DHTTYPE);

const char* ssid = "d201";
const char* password = "MechaTronyka";

const char* serverIP = "IP_ADRESS"; //change with correct ip, i'm not putting mine on git
const int serverPort = 5000;

unsigned long captureInterval = 3000;
unsigned long previousMillis = 0;

void setup() {
  Serial.begin(115200);
  delay(10);
  dht.begin();

  Serial.println();
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("");
  Serial.println("WiFi connected");
}

void loop() {
  unsigned long currentMillis = millis();

  if (currentMillis - previousMillis >= captureInterval) {
    previousMillis = currentMillis;

    sensors_event_t event;
    float temp = 0.0;
    float hum = 0.0;

    dht.temperature().getEvent(&event);
    if (isnan(event.temperature)) {
      Serial.println("Error reading temperature!"); //mainly to check that the cable is connected to the right ping
    } else {
      temp = event.temperature;
      Serial.print("Temperature: ");
      Serial.print(temp);
      Serial.println(" C");
    }

    dht.humidity().getEvent(&event);
    if (isnan(event.relative_humidity)) {
      Serial.println("Error reading humidity!"); //same
    } else {
      hum = event.relative_humidity;
      Serial.print("Humidity: ");
      Serial.print(hum);
      Serial.println("%");
    }

    WiFiClient client;
    
    if (!client.connect(serverIP, serverPort)) {
      Serial.println("Connection to server failed");
      return;
    }

    String url = "/update?temp=" + String(temp) + "&hum=" + String(hum);

    client.print(String("GET ") + url + " HTTP/1.1\r\n" +
                 "Host: " + serverIP + "\r\n" +
                 "Connection: close\r\n\r\n");

    unsigned long timeout = millis(); //usage instead of delay to have exact interval when interval is long enougth (because of execution time)
    while (client.available() == 0) {
      if (millis() - timeout > 5000) {
        Serial.println("Client Timeout !");
        client.stop();
        return;
      }
    }

    while (client.available()) {
      String line = client.readStringUntil('\n');
      line.trim();
      if (line.indexOf("INTERVAL=") != -1) {
        int idx = line.indexOf("INTERVAL=");
        int newInterval = line.substring(idx + 9).toInt();
        if (newInterval >= 1) {
          captureInterval = (unsigned long)newInterval * 1000;
        }
      }
    }
    
    Serial.println("Data sent and interval updated");
    client.stop();
  }
}