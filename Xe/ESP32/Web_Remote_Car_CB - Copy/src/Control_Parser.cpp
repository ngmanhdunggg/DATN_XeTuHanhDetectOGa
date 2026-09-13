#include "Control_Parser.h"
#include "Config.h"
#include "Control.h"


void handleSerialCommands() {
    if (controlIsLinkLost()) return;
    while (RPI_SERIAL.available() > 0) {
        String input = RPI_SERIAL.readStringUntil('\n');
        input.trim();
        
        if (input.startsWith("S")) {
            int aPos = input.indexOf('A');
            if (aPos != -1) {
                float dc_mps_in = input.substring(1, aPos).toFloat();
                float steer_deg_in = input.substring(aPos + 1).toFloat();
                
                // Cập nhật lệnh điều khiển
                controlOnAutoSet(dc_mps_in, steer_deg_in);
            }
        }
    }
}