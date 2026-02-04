import sensor, image, time
from pyb import UART

# --- EINSTELLUNGEN ---
BLACK_RATIO = 0.2
MIN_LIGHT_LEVEL = 10
BALL_THRESHOLD = 5

# Zielbereich für das UNTERE Ende der Kugel
STOP_ZONE_LOW = 15
STOP_ZONE_HIGH = 20

# Geschwindigkeiten
DRIVE_SPEED = 100
TURN_SPEED_FINE = 80   # Langsamer für feine Korrekturen
BACK_SPEED_FINE = 80   # Langsamer für feine Korrekturen

uart = UART(1, 57600, timeout_char=10)

sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QQQVGA)
sensor.skip_frames(time = 2000)
sensor.set_auto_gain(False)
sensor.set_auto_whitebal(False)

clock = time.clock()
dead_pixels = set()

def get_pixel_brightness(p):
    return (p[0] + p[1] + p[2]) / 3

def send_short_pulse(command):
    """Sendet einen Befehl für eine sehr kurze Zeit und stoppt dann."""
    uart.write(command + "\n")
    time.sleep_ms(50) # Kurzer Impuls (50 Millisekunden)
    uart.write("0;0m\n") # Sofort wieder stoppen

# --- KALIBRIERUNG ---
img = sensor.snapshot()
for y in range(img.height()):
    for x in range(img.width()):
        if get_pixel_brightness(img.get_pixel(x, y)) < 15:
            dead_pixels.add((x, y))

while(True):
    clock.tick()
    img = sensor.snapshot()

    stats = img.get_statistics()
    avg_l = stats.l_mean()
    if avg_l < MIN_LIGHT_LEVEL:
        uart.write("0;0m\n")
        continue

    dynamic_threshold = (avg_l * 2.55) * BLACK_RATIO
    blocks_found = 0
    max_y = 0
    sum_x = 0

    for y in range(0, img.height()-1, 2):
        for x in range(0, img.width()-1, 2):
            if (x <= 18 and y >= 14) or (x >= 70 and y >= 14):
                continue

            is_black = []
            for dy in range(2):
                for dx in range(2):
                    px_x, px_y = x + dx, y + dy
                    if (px_x, px_y) in dead_pixels:
                        is_black.append(False)
                        continue
                    p = img.get_pixel(px_x, px_y)
                    is_black.append(get_pixel_brightness(p) < dynamic_threshold)

            if (is_black[0] and is_black[1]) or (is_black[2] and is_black[3]) or \
               (is_black[0] and is_black[2]) or (is_black[1] and is_black[3]):
                blocks_found += 1
                sum_x += x
                img.draw_rectangle(x, y, 2, 2, color=(0, 255, 0))
                if y > max_y:
                    max_y = y

    # --- MOTOR STEUERUNG ---
    if blocks_found >= BALL_THRESHOLD:
        avg_x = sum_x / blocks_found

        # 1. FEINE ZENTRIERUNG (Kurze Impulse)
        if avg_x < 28:
            send_short_pulse("-{};{}m".format(TURN_SPEED_FINE, TURN_SPEED_FINE))
        elif avg_x > 52:
            send_short_pulse("{};-{}m".format(TURN_SPEED_FINE, TURN_SPEED_FINE))

        # 2. FEINE ABSTANDSREGELUNG (Kurze Impulse)
        else:
            if max_y > STOP_ZONE_HIGH:
                # Zu nah -> Kurzer Ruck zurück
                send_short_pulse("-{};-{}m".format(BACK_SPEED_FINE, BACK_SPEED_FINE))
            elif max_y < STOP_ZONE_LOW:
                # Zu weit weg -> Kurzer Ruck vor
                send_short_pulse("{};{}m".format(DRIVE_SPEED, DRIVE_SPEED))
            else:
                # Zielbereich erreicht -> Stehen bleiben
                uart.write("0;0m\n")
    else:
        # SUCHE: Hier fährt er kontinuierlich, bis er etwas findet
        uart.write("{};{}m\n".format(DRIVE_SPEED, DRIVE_SPEED))

    # Visuelle Hilfen
    img.draw_line(28, 0, 28, 60, color=(0, 0, 255))
    img.draw_line(52, 0, 52, 60, color=(0, 0, 255))
    img.draw_line(0, STOP_ZONE_LOW, 80, STOP_ZONE_LOW, color=(255, 255, 255))
    img.draw_line(0, STOP_ZONE_HIGH, 80, STOP_ZONE_HIGH, color=(255, 255, 255))

    time.sleep_ms(1) # Schnellerer Loop für reaktivere Impulse
