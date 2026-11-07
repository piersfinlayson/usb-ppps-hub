// USB PPPS Hub EEPROM programmer for a Raspberry Pi Pico or Pico 2.
//
// Writes the EEPROM image in a request that program.py has loaded into flash,
// then reboots into BOOTSEL. If there isn't a valid request it reboots into
// BOOTSEL and doesn't drive any pin. The request is erased before programming
// starts so it is never run twice. The result is written to flash at
// RESULT_OFFSET for program.py to read.

#include <string.h>
#include "pico/stdlib.h"
#include "pico/bootrom.h"
#include "hardware/i2c.h"
#include "hardware/flash.h"
#include "hardware/sync.h"

#define SDA_PIN 4
#define SCL_PIN 5
#define RST_PIN 6
#define EEPROM 0x50
#define REQUEST_OFFSET (1024 * 1024)
#define RESULT_OFFSET (REQUEST_OFFSET + FLASH_SECTOR_SIZE)
#define REQUEST_MAGIC 0x51504545
#define RESULT_MAGIC 0x57504545
#define TIMEOUT_US 10000

// program.py's copy of these values must match
enum {
    OK,
    RESET_LOW,
    LINES_LOW,
    NO_ACK,
    WRITE_FAILED,
    WRITE_TIMEOUT,
    READ_FAILED,
    MISMATCH,
};

typedef struct {
    uint32_t magic;
    uint32_t id;
    uint32_t crc;           // CRC-32 of image
    uint8_t image[256];
} request_t;

typedef struct {
    uint32_t magic;
    uint32_t id;            // the request's id
    uint32_t status;
    uint32_t address;       // address of a failed write
    uint32_t rst;           // RESET_N level before the Pico drives it low
    uint32_t sda;
    uint32_t scl;
    uint32_t clocks;        // SCL pulses needed to release a stuck SDA
    uint8_t before[256];
    uint8_t after[256];
} result_t;

static request_t req;

static union {
    result_t r;
    uint8_t raw[1024];
} out;

static uint32_t crc32(const uint8_t *p, size_t n) {
    uint32_t crc = 0xFFFFFFFF;
    while (n--) {
        crc ^= *p++;
        for (int i = 0; i < 8; i++)
            crc = (crc >> 1) ^ (0xEDB88320 & -(crc & 1));
    }
    return ~crc;
}

static void erase(uint32_t offset) {
    uint32_t irq = save_and_disable_interrupts();
    flash_range_erase(offset, FLASH_SECTOR_SIZE);
    restore_interrupts(irq);
}

static bool read_all(uint8_t *buf) {
    uint8_t a = 0;
    if (i2c_write_timeout_us(i2c0, EEPROM, &a, 1, true, TIMEOUT_US) != 1)
        return false;
    return i2c_read_timeout_us(i2c0, EEPROM, buf, 256, false, 100000) == 256;
}

static uint32_t write_byte(uint8_t a, uint8_t v) {
    uint8_t b[2] = {a, v};
    if (i2c_write_timeout_us(i2c0, EEPROM, b, 2, false, TIMEOUT_US) != 2)
        return WRITE_FAILED;
    absolute_time_t end = make_timeout_time_ms(20);
    while (!time_reached(end))
        if (i2c_write_timeout_us(i2c0, EEPROM, &a, 1, false, TIMEOUT_US) == 1)
            return OK;
    return WRITE_TIMEOUT;
}

static uint32_t sample(uint pin) {
    gpio_init(pin);
    gpio_pull_down(pin);
    sleep_ms(1);
    uint32_t level = gpio_get(pin);
    gpio_disable_pulls(pin);
    return level;
}

// SCL is released rather than driven high so the board's pull-up raises it.
static void scl_level(bool high) {
    gpio_set_dir(SCL_PIN, high ? GPIO_IN : GPIO_OUT);
    sleep_us(50);
}

// A slave left mid-transfer holds SDA low until it is clocked out of its byte.
static void recover(result_t *r) {
    gpio_put(SCL_PIN, 0);
    gpio_put(SDA_PIN, 0);
    gpio_pull_down(SDA_PIN);
    while (r->clocks < 9 && !gpio_get(SDA_PIN)) {
        scl_level(false);
        scl_level(true);
        r->clocks++;
    }
    // STOP: SDA rises while SCL is high
    scl_level(false);
    gpio_set_dir(SDA_PIN, GPIO_OUT);
    sleep_us(50);
    scl_level(true);
    gpio_set_dir(SDA_PIN, GPIO_IN);
    sleep_us(50);
    r->sda = gpio_get(SDA_PIN);
    gpio_disable_pulls(SDA_PIN);
}

static uint32_t program(result_t *r) {
    if (!r->sda && r->scl)
        recover(r);
    if (!r->sda || !r->scl)
        return LINES_LOW;
    i2c_init(i2c0, 100 * 1000);
    gpio_set_function(SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(SCL_PIN, GPIO_FUNC_I2C);
    if (!read_all(r->before))
        return NO_ACK;
    for (uint a = 0; a < 256; a++) {
        uint32_t e = write_byte(a, req.image[a]);
        if (e != OK) {
            r->address = a;
            return e;
        }
    }
    if (!read_all(r->after))
        return READ_FAILED;
    return memcmp(r->after, req.image, 256) ? MISMATCH : OK;
}

int main(void) {
    memcpy(&req, (const void *)(XIP_BASE + REQUEST_OFFSET), sizeof req);
    if (req.magic != REQUEST_MAGIC || req.crc != crc32(req.image, sizeof req.image))
        reset_usb_boot(0, 0);
    erase(REQUEST_OFFSET);
    erase(RESULT_OFFSET);

    result_t *r = &out.r;
    r->magic = RESULT_MAGIC;
    r->id = req.id;

    r->rst = sample(RST_PIN);
    if (r->rst) {
        gpio_put(RST_PIN, 0);
        gpio_set_dir(RST_PIN, GPIO_OUT);
        sleep_ms(10);
        r->sda = sample(SDA_PIN);
        r->scl = sample(SCL_PIN);
        r->status = program(r);
        gpio_set_dir(RST_PIN, GPIO_IN);
    } else {
        r->status = RESET_LOW;
    }

    uint32_t irq = save_and_disable_interrupts();
    flash_range_program(RESULT_OFFSET, out.raw, sizeof out.raw);
    restore_interrupts(irq);

    reset_usb_boot(0, 0);
}
