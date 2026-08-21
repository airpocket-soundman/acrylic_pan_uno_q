#include <Arduino_RouterBridge.h>

// Keep this enabled until the KX134 adapter is connected and electrically checked.
#define APAN_DUMMY_MODE 1

#if APAN_DUMMY_MODE

constexpr uint32_t DUMMY_CASE_INTERVAL_MS = 1000;
constexpr uint32_t BRIDGE_WARMUP_MS = 10000;
uint32_t nextDummyCaseAt = 0;
uint8_t dummyCase = 0;

void setup() {
  Bridge.begin();
  nextDummyCaseAt = millis() + BRIDGE_WARMUP_MS;
}

void loop() {
  const uint32_t now = millis();
  if (static_cast<int32_t>(now - nextDummyCaseAt) >= 0) {
    Bridge.notify("on_dummy_case", static_cast<int>(dummyCase));
    dummyCase = (dummyCase + 1U) % 8U;
    nextDummyCaseAt = now + DUMMY_CASE_INTERVAL_MS;
  }
  delay(1);
}

#else

#include <vector>

#include "apan_capture.h"
#include "kx134.h"

constexpr uint8_t KX134_CS_PIN = 10;
constexpr uint8_t KX134_INT1_PIN = 2;
constexpr uint8_t KX134_INT2_PIN = 3;
constexpr uint32_t SAMPLE_PERIOD_US = 1000000UL / APAN_SAMPLE_RATE_HZ;
constexpr uint32_t SAMPLE_PERIOD_REMAINDER = 1000000UL % APAN_SAMPLE_RATE_HZ;
constexpr size_t BRIDGE_CHUNK_SAMPLES = 64;

Kx134 sensor(KX134_CS_PIN);
ApanCapture capture(120, 80);
uint32_t nextSampleAt = 0;
uint32_t samplePhase = 0;
uint32_t eventSequence = 0;
bool sensorReady = false;

void setThresholds(int jerkThreshold, int levelThreshold) {
  capture.setThresholds(constrain(jerkThreshold, 0, 65535),
                        constrain(levelThreshold, 0, 65535));
}

void sendEvent() {
  const ApanEvent& event = capture.event();
  ++eventSequence;
  for (size_t offset = 0; offset < APAN_EVENT_SAMPLES; offset += BRIDGE_CHUNK_SAMPLES) {
    std::vector<int> chunk;
    chunk.reserve(BRIDGE_CHUNK_SAMPLES);
    const size_t end = min(offset + BRIDGE_CHUNK_SAMPLES, APAN_EVENT_SAMPLES);
    for (size_t i = offset; i < end; ++i) chunk.push_back(event.samples[i]);
    Bridge.notify("on_capture_chunk", static_cast<int>(eventSequence),
                  static_cast<int>(offset), chunk,
                  static_cast<int>(event.triggerIndex), static_cast<int>(event.peakAbs));
  }
  capture.release();
}

void setup() {
  Bridge.begin();
  Bridge.provide("set_thresholds", setThresholds);
  pinMode(KX134_INT1_PIN, INPUT_PULLUP);
  pinMode(KX134_INT2_PIN, INPUT_PULLUP);

  sensorReady = sensor.begin();
  if (!sensorReady) {
    Bridge.notify("on_sensor_status", false, static_cast<int>(sensor.whoAmI()));
    return;
  }

  Bridge.notify("on_runtime_status", "sensor", true);
  Bridge.notify("on_sensor_status", true, static_cast<int>(sensor.whoAmI()));
  nextSampleAt = micros();
}

void loop() {
  if (!sensorReady) {
    delay(1000);
    return;
  }
  if (capture.ready()) {
    sendEvent();
    nextSampleAt = micros();
    samplePhase = 0;
    return;
  }

  const uint32_t now = micros();
  if (static_cast<int32_t>(now - nextSampleAt) >= 0) {
    nextSampleAt += SAMPLE_PERIOD_US;
    samplePhase += SAMPLE_PERIOD_REMAINDER;
    if (samplePhase >= APAN_SAMPLE_RATE_HZ) {
      ++nextSampleAt;
      samplePhase -= APAN_SAMPLE_RATE_HZ;
    }
    capture.feed(sensor.readZ());
  }
}

#endif
