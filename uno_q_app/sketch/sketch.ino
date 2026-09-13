#include <Arduino_RouterBridge.h>
#include <MsgPack.h>
#include <limits.h>
#include <stm32u585xx.h>
#include <zephyr/kernel.h>

#include "apan_capture.h"
#include "kx134.h"

constexpr uint8_t CS_PIN = 10;
constexpr uint8_t INT_PIN = 2;
constexpr uint8_t KX134_WHO_AM_I = 0x46;
constexpr uint32_t CPU_CLOCK_HZ = 160000000UL;
constexpr uint16_t DEFAULT_JERK_THRESHOLD = 700;
constexpr uint16_t DEFAULT_LEVEL_THRESHOLD = 200;
constexpr uint16_t DEFAULT_CONFIRMATION_THRESHOLD = 3000;
constexpr size_t EVENT_CHUNK_SAMPLES = 64;

Kx134 sensor(CS_PIN);
ApanCapture capture(DEFAULT_JERK_THRESHOLD, DEFAULT_LEVEL_THRESHOLD,
                    DEFAULT_CONFIRMATION_THRESHOLD, 16);

volatile uint32_t irqCount = 0;
uint32_t consumedIrqCount = 0;
uint32_t missedDataReady = 0;
uint32_t sampleCount = 0;
uint32_t samplePeriodCycles = 0;
uint32_t nextSampleCycle = 0;
uint32_t readBenchmarkUs = 0;
int16_t observedMinZ = INT16_MAX;
int16_t observedMaxZ = INT16_MIN;
int16_t observedPreviousZ = 0;
uint16_t observedMaxJerk = 0;
bool observedPreviousValid = false;
uint32_t eventSequence = 0;
uint32_t nextStatusAt = 0;
uint32_t lastAcceptedEventMs = 0;
uint16_t retriggerGuardMs = 120;
bool acceptedEventExists = false;
bool sensorReady = false;
bool samplingStatusReported = false;

void onDataReady() { ++irqCount; }

void setThresholds(int jerk, int level, int confirmation) {
  capture.setThresholds(
      static_cast<uint16_t>(constrain(jerk, 1, 32767)),
      static_cast<uint16_t>(constrain(level, 1, 32767)),
      static_cast<uint16_t>(constrain(confirmation, 1, 32767)));
}

void setRetriggerGuard(int milliseconds) {
  retriggerGuardMs = static_cast<uint16_t>(constrain(milliseconds, 0, 500));
  acceptedEventExists = false;
}

bool acceptEventNow() {
  const uint32_t now = millis();
  if (!acceptedEventExists || now - lastAcceptedEventMs >= retriggerGuardMs) {
    acceptedEventExists = true;
    lastAcceptedEventMs = now;
    return true;
  }
  return false;
}

void sendEvent() {
  const ApanEvent& event = capture.event();
  if (acceptEventNow()) {
    ++eventSequence;
    // Send binary little-endian chunks instead of 512 individual RPC calls.
    // At the bridge's 115200-baud transport this removes most framing overhead
    // while keeping each packet comfortably below the 1024-byte decoder limit.
    for (size_t offset = 0; offset < APAN_EVENT_SAMPLES;
         offset += EVENT_CHUNK_SAMPLES) {
      MsgPack::bin_t<uint8_t> samples;
      samples.reserve(EVENT_CHUNK_SAMPLES * sizeof(int16_t));
      for (size_t i = 0; i < EVENT_CHUNK_SAMPLES; ++i) {
        const uint16_t raw = static_cast<uint16_t>(event.samples[offset + i]);
        samples.push_back(static_cast<uint8_t>(raw & 0xff));
        samples.push_back(static_cast<uint8_t>(raw >> 8));
      }
      Bridge.notify("on_capture_chunk", static_cast<int>(eventSequence),
                    static_cast<int>(offset), samples,
                    static_cast<int>(event.triggerIndex),
                    static_cast<int>(event.peakAbs), static_cast<int>(irqCount));
    }
  }
  capture.release();
}

void setup() {
  Bridge.begin();
  Bridge.provide("set_thresholds", setThresholds);
  Bridge.provide("set_retrigger_guard", setRetriggerGuard);

  pinMode(INT_PIN, INPUT);
  sensorReady = sensor.begin();
  if (sensorReady) {
    sensor.readZ();
    const uint32_t benchmarkStarted = micros();
    for (size_t i = 0; i < 1000; ++i) sensor.readZ();
    readBenchmarkUs = micros() - benchmarkStarted;
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    samplePeriodCycles = CPU_CLOCK_HZ / APAN_SAMPLE_RATE_HZ;
  }

  Bridge.notify("on_sensor_status", sensorReady,
                static_cast<int>(sensor.whoAmI()));
  Bridge.notify("on_runtime_status", sensorReady ? "sensor" : "error",
                sensorReady);
  if (sensorReady) nextSampleCycle = DWT->CYCCNT + samplePeriodCycles;
  // The Linux app waits for the camera brick and loads the inference model and
  // SoundFont before entering App.run(). Report after that cold-start window so
  // a board power-on reliably reaches the Python subscribers. This one status
  // burst happens before performance begins and does not disturb later samples.
  nextStatusAt = millis() + 20000;
}

void loop() {
  if (!sensorReady) {
    delay(1000);
    return;
  }

  // The UNO Q Zephyr core yields for roughly 1 ms whenever loop() returns.
  // Stay in this MCU-side loop so the 39.0625 us acquisition cadence is kept.
  while (sensorReady) {
    const uint32_t nowCycle = DWT->CYCCNT;
    if (static_cast<int32_t>(nowCycle - nextSampleCycle) >= 0) {
      const uint32_t lateCycles = nowCycle - nextSampleCycle;
      if (lateCycles >= samplePeriodCycles) {
        missedDataReady += lateCycles / samplePeriodCycles;
        nextSampleCycle = nowCycle + samplePeriodCycles;
      } else {
        nextSampleCycle += samplePeriodCycles;
      }
      const int16_t rawZ = sensor.readZ();
      observedMinZ = min(observedMinZ, rawZ);
      observedMaxZ = max(observedMaxZ, rawZ);
      if (observedPreviousValid) {
        int32_t jerk = static_cast<int32_t>(rawZ) - observedPreviousZ;
        if (jerk < 0) jerk = -jerk;
        observedMaxJerk = max(observedMaxJerk,
                              static_cast<uint16_t>(min(jerk, 65535L)));
      }
      observedPreviousZ = rawZ;
      observedPreviousValid = true;
      capture.feed(rawZ);
      ++sampleCount;
      if (capture.ready()) sendEvent();
    }

    if (!samplingStatusReported && static_cast<int32_t>(millis() - nextStatusAt) >= 0) {
      samplingStatusReported = true;
      Bridge.notify("on_sensor_status", true, static_cast<int>(KX134_WHO_AM_I));
      Bridge.notify("on_runtime_status", "sensor", true);
      Bridge.notify("on_sampling_status", static_cast<int>(sampleCount),
                  static_cast<int>(missedDataReady), static_cast<int>(readBenchmarkUs),
                  static_cast<int>(CPU_CLOCK_HZ), static_cast<int>(observedMinZ),
                  static_cast<int>(observedMaxZ), static_cast<int>(observedMaxJerk));
    }
  }
}
