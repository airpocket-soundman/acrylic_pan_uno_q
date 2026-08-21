#pragma once

#include <Arduino.h>

constexpr size_t APAN_EVENT_SAMPLES = 512;
constexpr size_t APAN_PRETRIGGER_SAMPLES = 128;
constexpr uint32_t APAN_SAMPLE_RATE_HZ = 25600;

struct ApanEvent {
  int16_t samples[APAN_EVENT_SAMPLES];
  uint16_t triggerIndex;
  uint16_t peakAbs;
};

class ApanCapture {
 public:
  ApanCapture(uint16_t jerkThreshold, uint16_t levelThreshold);

  void feed(int16_t sample);
  bool ready() const;
  const ApanEvent& event() const;
  void release();
  void setThresholds(uint16_t jerkThreshold, uint16_t levelThreshold);

 private:
  static uint16_t magnitude(int16_t value);
  void pushHistory(int16_t sample);
  void beginEvent(int16_t triggerSample);

  int16_t history_[APAN_PRETRIGGER_SAMPLES] = {};
  uint16_t historyWrite_ = 0;
  uint16_t historyCount_ = 0;
  int16_t previousSample_ = 0;
  bool hasPreviousSample_ = false;
  bool collecting_ = false;
  bool ready_ = false;
  uint16_t eventWrite_ = 0;
  uint16_t jerkThreshold_;
  uint16_t levelThreshold_;
  ApanEvent event_ = {};
};
