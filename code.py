from bbq10keyboard import BBQ10Keyboard, STATE_PRESS, STATE_RELEASE, STATE_LONG_PRESS
from adafruit_display_text.label import Label
from adafruit_display_shapes.rect import Rect
import adafruit_ili9341
import terminalio
import displayio
import neopixel
import board
import busio
import time
import gc

import adafruit_sdcard
import digitalio
import storage
import os
import rtc


# ui dimensions
header = 32
margin = 8
border = 1

# Release any resources currently in use for the displays
displayio.release_displays()

spi = board.SPI()
# remapped for Argon
tft_cs = board.D4 #D9
tft_dc = board.D5 #D10

neopix_pin = board.D6 #D11

sd_cs = board.D2 #D5


display_bus = displayio.FourWire(spi, command=tft_dc, chip_select=tft_cs)
display = adafruit_ili9341.ILI9341(display_bus, width=320, height=240)

uart = busio.UART(board.TX, board.RX, baudrate=115200, receiver_buffer_size=128)

i2c = board.I2C()
kbd = BBQ10Keyboard(i2c)

splash = displayio.Group(max_size=25)
display.show(splash)


# stop blinding me with the Neopixel!
pixels = neopixel.NeoPixel(neopix_pin, 1)
pixels[0] = 0x0000FF
time.sleep(0.3)
pixels.brightness = 0.1

# background
color_bitmap = displayio.Bitmap(display.width, 240, 1)
color_palette = displayio.Palette(1)
color_palette[0] = 0x0000F9
bg_sprite = displayio.TileGrid(color_bitmap, x=0, y=0, pixel_shader=color_palette)
splash.append(bg_sprite)

# output rect
output_rect = Rect(margin, margin, display.width-margin*2, display.height-margin*2-header-margin, fill=0x000000, outline=0x00FFFF)
splash.append(output_rect)

# output header
header_rect = Rect(margin + border, margin+border, display.width-(margin+border)*2, header, fill=0x00FFFF)
splash.append(header_rect)

header_text = Label(terminalio.FONT, text="ZORDmicro", x=margin*2+border, y=int(margin+border+header/2), color=0x000000)
splash.append(header_text)

# output text
p = displayio.Palette(2)
p.make_transparent(0)
p[1] = 0xFFFFFF

w, h = terminalio.FONT.get_bounding_box()
tilegrid = displayio.TileGrid(terminalio.FONT.bitmap, pixel_shader=p, x=margin*2+border, y=int(margin+border+header+margin/2), width=48, height=10, tile_width=w, tile_height=h)
term = terminalio.Terminal(tilegrid, terminalio.FONT)
splash.append(tilegrid)

# input textarea
input_rect = Rect(margin, display.height-margin-header, display.width-margin*2, header, fill=0x000000, outline=0x00FFFF)
splash.append(input_rect)

# input text
input_text = Label(terminalio.FONT, text='', x=margin*2+border, y=int(display.height-margin-border-header*0.7), color=0xFFFFFF, max_glyphs=50)
splash.append(input_text)

# carret
carret = Rect(input_text.x + input_text.bounding_box[2] + 1, int(display.height-margin-header/2-header/4), 1, header//2, fill=0xFFFFFF)
splash.append(carret)

carret_blink_time = time.monotonic()
carret_blink_state = True



def dir_command():
    sdcard = adafruit_sdcard.SDCard(spi, digitalio.DigitalInOut(sd_cs))
    vfs = storage.VfsFat(sdcard)
    storage.mount(vfs, '/sd')
    return "{}\n\r".format(os.listdir('/sd/'))

def mem_command():
    return "{} BYTES FREE\n\r".format(gc.mem_free())

def uname_command():
    sys = os.uname()
    return "{}\n\r{}\n\r".format(sys.machine, sys.version)

def time_command():
    dt = rtc.RTC().datetime
    return "{:02d}:{:02d}\n\r".format(dt.tm_hour, dt.tm_min)


def run_command(command):
    # already contains \n
    term.write("{}\r".format(command))

    mapp = {
        "dir\n": dir_command,
        "ls\n": dir_command,
        "mem\n": mem_command,
        "uname\n": uname_command,
        "time\n": time_command
    }
    #term.write("c:{} s:{}\n\r".format(command, mapp.keys()))
    func = mapp.get(str(command), lambda: "Invalid command\n\r")
    term.write(func())

term.write("ZORDmicro v1\n\r")
term.write(mem_command())


while True:
    # Carret blink animation
    if time.monotonic() - carret_blink_time >= 0.5:
        if carret_blink_state:
            splash.remove(carret)
        else:
            splash.append(carret)

        carret_blink_state = not carret_blink_state
        carret_blink_time = time.monotonic()


    # Process keyboard
    if kbd.key_count > 0:
        k = kbd.key
        if k[0] == STATE_RELEASE:
            if k[1] == '\x08': # Backspace
                if len(input_text.text) > 0:
                    input_text.text = input_text.text[:-1]
            elif k[1] == '\n': # Enter, send over UART
                text =  input_text.text + '\n'
                run_command(text)

                input_text.text = ''
            else: # Anything else, we add to the text field
                input_text.text += k[1]

            carret.x = input_text.x + input_text.bounding_box[2] + 1
