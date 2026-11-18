/*
 * Kera 16x16 display firmware: USB serial -> WS2812B panel.
 *
 * Protocol (from display/serial_link.py):
 *   A5 5A | type 0x01 | length (2 bytes, little endian) | 768 RGB bytes | crc8(payload)
 *
 * The frame is row-major, 16x16, RGB888. Set LED_PIN / SERPENTINE below.
 * Power the panel from a separate 5 V supply; USB only powers the ESP32 and
 * carries data. Do not power 256 LEDs from a USB port.
 */

#include <Arduino.h>
#include <FastLED.h>

#define LED_PIN 16
#define MATRIX_W 16
#define MATRIX_H 16
#define LED_COUNT (MATRIX_W * MATRIX_H)
#define SERPENTINE 1
#define MAX_CURRENT_MA 5000

static const uint8_t MAGIC0 = 0xA5;
static const uint8_t MAGIC1 = 0x5A;
static const uint8_t FRAME_TYPE = 0x01;
static const uint16_t FRAME_BYTES = MATRIX_W * MATRIX_H * 3;
static const unsigned long LINK_TIMEOUT_MS = 3000;

CRGB leds[LED_COUNT];
uint8_t payload[FRAME_BYTES];
uint16_t payload_pos = 0;
uint16_t payload_len = 0;
uint8_t expected_crc = 0;
uint8_t rx_state = 0;
unsigned long last_frame_ms = 0;
bool blanked = true;

uint8_t crc8(const uint8_t *data, uint16_t length) {
  uint8_t crc = 0;
  for (uint16_t i = 0; i < length; i++) {
    crc ^= data[i];
    for (uint8_t bit = 0; bit < 8; bit++) {
      crc = (crc & 0x80) ? ((crc << 1) ^ 0x07) : (crc << 1);
    }
  }
  return crc;
}

uint16_t xy(uint8_t x, uint8_t y) {
#if SERPENTINE
  if (y & 1) {
    return y * MATRIX_W + (MATRIX_W - 1 - x);
  }
#endif
  return y * MATRIX_W + x;
}

void show_frame() {
  for (uint8_t y = 0; y < MATRIX_H; y++) {
    for (uint8_t x = 0; x < MATRIX_W; x++) {
      uint16_t src = (y * MATRIX_W + x) * 3;
      leds[xy(x, y)] = CRGB(payload[src], payload[src + 1], payload[src + 2]);
    }
  }
  FastLED.show();
  last_frame_ms = millis();
  blanked = false;
}

void handle_byte(uint8_t b) {
  switch (rx_state) {
    case 0:
      if (b == MAGIC0) rx_state = 1;
      break;
    case 1:
      rx_state = (b == MAGIC1) ? 2 : (b == MAGIC0 ? 1 : 0);
      break;
    case 2:
      rx_state = (b == FRAME_TYPE) ? 3 : 0;
      break;
    case 3:
      payload_len = b;
      rx_state = 4;
      break;
    case 4:
      payload_len |= (uint16_t)b << 8;
      if (payload_len != FRAME_BYTES) {
        rx_state = 0;
      } else {
        payload_pos = 0;
        rx_state = 5;
      }
      break;
    case 5:
      payload[payload_pos++] = b;
      if (payload_pos >= payload_len) rx_state = 6;
      break;
    case 6:
      expected_crc = b;
      rx_state = 0;
      if (crc8(payload, payload_len) == expected_crc) {
        show_frame();
      }
      break;
    default:
      rx_state = 0;
      break;
  }
}

void setup() {
  Serial.setRxBufferSize(2048);
  Serial.begin(921600);

  FastLED.addLeds<WS2812B, LED_PIN, GRB>(leds, LED_COUNT);
  FastLED.setMaxPowerInVoltsAndMilliamps(5, MAX_CURRENT_MA);
  FastLED.setBrightness(255);
  FastLED.clear(true);

  // Short power/wiring check: red, green, blue.
  fill_solid(leds, LED_COUNT, CRGB::Red);
  FastLED.show();
  delay(250);
  fill_solid(leds, LED_COUNT, CRGB::Green);
  FastLED.show();
  delay(250);
  fill_solid(leds, LED_COUNT, CRGB::Blue);
  FastLED.show();
  delay(250);
  FastLED.clear(true);

  last_frame_ms = millis();
  blanked = true;
}

void loop() {
  while (Serial.available() > 0) {
    handle_byte(static_cast<uint8_t>(Serial.read()));
  }

  if (!blanked && millis() - last_frame_ms > LINK_TIMEOUT_MS) {
    FastLED.clear(true);
    blanked = true;
  }
}
