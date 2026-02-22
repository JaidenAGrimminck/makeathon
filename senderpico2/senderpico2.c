#include <stdlib.h>
#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/adc.h"

int* constructOut(int values[]) {
    int* out = (int*)malloc(10 * sizeof(int));
    for (int i = 0; i < 10; i++) {
        out[i] = values[i];
    }
    return out;
}
 

#define THUMB_PIN 26
#define INDEX_PIN 27
#define MIDDLE_PIN 28
#define RING_PIN 29
#define PINKY_PIN 26


int main()
{
    stdio_init_all();
    adc_init();

    adc_gpio_init(THUMB_PIN);
    adc_gpio_init(INDEX_PIN);
    adc_gpio_init(MIDDLE_PIN);
    adc_gpio_init(RING_PIN);
    adc_gpio_init(PINKY_PIN);

    while (true) {
        int values[5] = {
            0,0,0,0,0
        };

        adc_select_input(0);
        values[0] = (int)adc_read();

        adc_select_input(1);
        values[1] = (int)adc_read();

        adc_select_input(2);
        values[2] = (int)adc_read();

        adc_select_input(3);
        values[3] = (int)adc_read();

        adc_select_input(4);
        values[4] = (int)adc_read();

        int* out = constructOut(values);

        int checksum = 0;

        for (int i = 0; i < 10; i++) {
            checksum ^= out[i];
        }
        
        int initial = 0xDEADBEEF;
        
        fwrite(&initial, sizeof(int), 1, stdout);
        fwrite(out, sizeof(int), 10, stdout);
        fwrite(&checksum, sizeof(int), 1, stdout);

        free(out);

        sleep_ms(1000);
    }
}