// Fixture firmware for the paper check tests.
static const uint8_t PIN_SDA = 5;   // I2C SDA
static const uint8_t PIN_SCL = 6;   // I2C SCL
static const uint8_t PIN_BUZZER = 0;
static void hello() { Serial.print("HELLO demo-panel "); Serial.print(VERSION); Serial.println(" esp32c3"); }
