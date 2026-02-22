#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/adc.h"
#include "pico/time.h"


#define FIRST_PIN 26
#define SECOND_PIN 27
#define THIRD_PIN 28

#define SIDE 1

int main() {
    stdio_init_all();          // initializes any linked stdio backends :contentReference[oaicite:3]{index=3}
    sleep_ms(1500);            // helps during bring-up / first plug-in

    int thresholds[3] = {
        170,
        160,
        150
    };

    int averages[3] = {
        0,0,0
    };

    int reads[3] = {
        0,0,0
    };

    adc_init();

    adc_gpio_init(FIRST_PIN);
    adc_gpio_init(SECOND_PIN);
    adc_gpio_init(THIRD_PIN);

    uint64_t usSinceBoot = to_us_since_boot(get_absolute_time());

    int count = 0;

    while (true) {
        
        for (int i = 0; i < 3; i++) {
            adc_select_input(i);
            int read = (int)adc_read();
            averages[i] += read;
            reads[i] = read;
            if (read > thresholds[i]) {
                averages[i] += 1000;
            }
        }

        count++;

        if (to_us_since_boot(get_absolute_time()) - usSinceBoot > 100000 / 2) {
            printf("%d Values: %d, %d, %d\n", SIDE, averages[1] / count, averages[0] / count, averages[2] / count);
            usSinceBoot = to_us_since_boot(get_absolute_time());

            averages[0] = 0;
            averages[1] = 0;
            averages[2] = 0;
            count = 0;
        }

        // printf("Values: %d, %d, %d\n", reads[0], reads[1], reads[2]);

        sleep_ms(20);
    }
}

// #include <stdio.h>
// #include "pico/stdlib.h"
// // #include "hardware/uart.h"
// #include "hardware/adc.h"

// // #include "pico/cyw43_arch.h"

// void printLines(int val){
//     for(int i = 0; i*5<val;i++){
//         printf("=");
//     }
//     printf("\n");
// }

// #define SIDE 1

// #define UART_BAUD 250000

// #define FIRST_PIN 26
// #define SECOND_PIN 27
// #define THIRD_PIN 28

// const int thresholds[3] = {
//     100,
//     100,
//     100
// };

// long lastRead = 0;

// int main()
// {
//     stdio_init_all();

//     printf("test\n");
//     if (SIDE == 0) {
//         return 0;
//     }

//     // uart_set_baudrate(uart_default, UART_BAUD); // Faster UART stdio for host serial

//     // // Initialize the Wi-Fi chip (required to control its GPIO)
//     // if (!cyw43_arch_init()) {
//     //     printf("Wi-Fi init failed!");
//     //     return -1;
//     //}

//     adc_init();

//     adc_gpio_init(FIRST_PIN);
//     adc_gpio_init(SECOND_PIN);
//     adc_gpio_init(THIRD_PIN);
    
//     int i = 0;

//     int averages[3] = {
//         0,0,0
//     };

//     int count = 0;

//     // // Turn the LED on
//     // cyw43_arch_gpio_put(CYW43_WL_GPIO0, 1);
//     // printf("LED on!\n");
//     // sleep_ms(500);

//     int last_print = time_us_64();

//     while (true) {
//         int values[3] = {
//             0,0,0
//         };

//         adc_select_input(0);
//         int read = (int)adc_read();
//         averages[0] += read;
//         if (read > thresholds[0]) {
//             averages[0] += 1000;
//         }
//         // printf("%u\n",adc_read());

//         adc_select_input(1);
//         read = (int)adc_read();
//         averages[1] += read;
//         if (read > thresholds[1]) {
//             averages[1] += 1000;
//         }

//         adc_select_input(2);
//         read = (int)adc_read();
//         averages[2] += read;
//         if (read > thresholds[2]) {
//             averages[2] += 1000;
//         }

//         // adc_select_input(3);
//         // values[3] = (int)adc_read();

//         // adc_select_input(4);
//         // values[4] = (int)adc_read();

//         if (time_us_64() - last_print > 100000) {
//             printf("%d %d Values: %d, %d, %d\n", SIDE, ++i, averages[0] / count, averages[1] / count, averages[2] / count);
//             last_print = time_us_64();

//             count = 0;
//             averages[0] = 0;
//             averages[1] = 0;
//             averages[2] = 0;
//         }
//         //printLines(values[0]);

//         // int* out = constructOut(values, 3);

//         // int checksum = 0;

//         // for (int i = 0; i < 3; i++) {
//         //     checksum ^= out[i];
//         // }
        
//         // uint8_t initial = 0xFF;
        
//         // fwrite(&initial, sizeof(uint8_t), 1, stdout);
//         // fwrite(values, sizeof(int), 3, stdout);

//         // free(out);
//         sleep_ms(10);
//     }
// }