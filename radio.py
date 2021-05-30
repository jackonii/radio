#!/usr/bin/env python
# The wiring for the LCD is as follows:
    # LCD |Description          | MCP Pin      | Notes
    # 1 : GND
    # 2 : 5V
    # 3 : Contrast (0-5V)                   2K TRIMPOT
    # 4 : RS (Register Select)   1 (B0)      
    # 5 : R/W (Read Write)                   GROUND THIS PIN
    # 6 : Enable or Strobe      2 (B1)
    # 7 : Data Bit 0                         NOT USED
    # 8 : Data Bit 1                         NOT USED
    # 9 : Data Bit 2                         NOT USED
    # 10: Data Bit 3                         NOT USED
    # 11: Data Bit 4         5 (B4)
    # 12: Data Bit 5         6 (B5)
    # 13: Data Bit 6         7 (B6)
    # 14: Data Bit 7         8 (B7)
    # 15: LCD Backlight +5V
    # 16: LCD Backlight GND                VIA collector of PN2222 Transistor and 5 OHM RESISTOR

    #Connections to the RPi are as follows:
    # RPi |Description          | MCP Pins      | Notes
    # 2 : 5V                9 & 18          Its OK to use this at 5V as the i2c bus is a pull down bus - the MCP chip only pulls the two data lines to GND to communicate, and the pis internal pull ups set the high as 3.3 on the SCL and SDA lines. Use buffers if unsure for 100% saftey.
    # 3 : I2C SDA             13
    # 5 : I2C SCL             12
    # 6 : GND                10
    #18 : Lirc reciever TSOP4838

    #Connections of buttons
    #MCP PIN	|	Button
    # A0		start/stop
    # A1		next
    # A2		previous

    #Connection for LCD LED control
    # MCP PIN	|	element
    # A4		Base of PN2222 transistor VIA 2K Resistor



import time
from time import sleep, strftime
from subprocess import *
from datetime import datetime, timedelta
import smbus
import os

# i2c bank A Setup. Bank B is for LCD purpose
i2c_addr = 0x20 			# i2c device address

bus=smbus.SMBus(1) 			# change to 0 for rev 1 raspberries
bus.write_byte_data(i2c_addr,0x00,0x07) # register IODIRA - set A7-A3 as Output Pins and A2-A0 as Input
bus.write_byte_data(i2c_addr,0x12,0x00) # register GPIOA - set bank A GPIOs value to 00000000
bus.write_byte_data(i2c_addr,0x0C,0x07) # register GPPUA - set pull-up resistor for A0,A1,A2
bus.write_byte_data(i2c_addr,0x02,0x07) # register IPOLA - revers polarity for A0,A1,A2
bus.write_byte_data(i2c_addr,0x04,0x07) # register GPINTENA - enables Interupts-On-Change for A0,A1,A2
bus.write_byte_data(i2c_addr,0x08,0x00) # register INTCONA - enables Interupt-On-Change compare to previous pin value - not FROM REGISTER DEFAULT - DEFVALB
bus.write_byte_data(i2c_addr,0x06,0x00) # register DEFVALA - sets default value of pins  A0,A1,A2 to '0'

# sets commands
mpc_station = "mpc -f %name% current | tr -d '[]'"
mpc_song = "mpc -f %title% current"
mpc_artist = "mpc -f %artist% current"
mpc_next = "mpc next"
mpc_prev = "mpc prev"
mpc_toggle = "mpc toggle"
mpc_repeat = "mpc repeat on"
mpc_status = "mpc | grep 0:00 | cut -d[ -f2 | cut -d] -f1" #Gets the Play/Pause status
mpc_play = "mpc play"
mpc_stop = "mpc stop"
radioon = "irsend SEND_ONCE denon KEY_DVD && mpc play"
radiooff = "irsend SEND_ONCE denon KEY_POWER2 && mpc stop"

def run_cmd(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE)
    output = p.communicate()[0]
    return output

class LCD_23017(object):
    # Timing constants
    E_PULSE = 0.00005
    E_DELAY = 0.00005
    def __init__(self, bus, addr, port, rs, en):
        self.bus = bus
        self.addr = addr
        self.rs = rs
        self.en = en
        self.DIRECTION = 0x00 if port == 'A' else 0x01
        self.DATA = 0x12 if port == 'A' else 0x13

        self.bus.write_byte_data(addr, self.DIRECTION, 0x00)

    def lcd_byte(self, data, rs):
        rs <<= self.rs
        en = 1 << self.en
        for nybble in (data&0xf0, data<<4):
            self.bus.write_byte_data(self.addr, self.DATA, nybble | rs)
            time.sleep(self.E_DELAY)
            self.bus.write_byte_data(self.addr, self.DATA, nybble | rs | en)
            time.sleep(self.E_PULSE)
            self.bus.write_byte_data(self.addr, self.DATA, nybble | rs)
class HD47780(object):
    LCD_CHR = True
    LCD_CMD = False
    # Base addresses for lines on a 20x4 display
    LCD_BASE = 0x80, 0xC0, 0x94, 0xD4
    def __init__(self, driver, rows=2, width=24):
        self.rows = rows
        self.width = width
        self.driver = driver
        self.lcd_init()
    def lcd_init(self):
        # Initialise display
        lcd_byte = self.driver.lcd_byte
        for i in 0x33, 0x32, 0x28, 0x0C, 0x06, 0x01:
            lcd_byte(i, self.LCD_CMD)

    def lcd_string(self, message, line, style):
        # Send string to display
        lcd_byte = self.driver.lcd_byte
        lcd_byte(self.LCD_BASE[line], self.LCD_CMD)
        if style==1:
            message = message.ljust(self.width," ") 
        elif style==2:
            message = message.center(self.width," ")
        elif style==3:
            message = message.rjust(self.width," ")
           
        for i in bytearray(message):
            lcd_byte(i, self.LCD_CHR)


def test_i2c():
    driver1 = LCD_23017(bus=smbus.SMBus(1), addr=0x20, port='B', rs=0, en=1)
    lcd1 = HD47780(driver=driver1, rows=2, width=24)
    k = 0
    scrolltime = datetime.now()
    radiotime = datetime.now()
    run_cmd(mpc_repeat)
    int = 0
    inp = 0
    while True:
        while True:
            int = bus.read_byte_data(i2c_addr,0x0E)
            
            if int != 0:
                inp = bus.read_byte_data(i2c_addr,0x10)
                if inp == 0x01: #00000001 - turn off with buttom
                    run_cmd(radioon)
                    break
                    
            else:
                inp = bus.read_byte_data(i2c_addr,0x12)
                if inp == 208:
                    bus.write_byte_data(i2c_addr,0x12,0x00)
                if inp == 160: #10100000 - turn off with remote
                    bus.write_byte_data(i2c_addr,0x12,0x00)
                    break
                    
            sleep(0.5)

        bus.write_byte_data(i2c_addr,0x12,0x10)
        lcd1.lcd_string("Welcome to",0,2)
        lcd1.lcd_string("RaspPi WebRadio",1,2)
        run_cmd(mpc_play)
        sleep(3)
        lcd1.lcd_string(" ",0,1)
        lcd1.lcd_string(" ",1,1)

        while True:

            int = bus.read_byte_data(i2c_addr,0x0E)
            if int != 0:
                inp = bus.read_byte_data(i2c_addr,0x10)
                if inp == 0x11: # 00010001
                    countdown = 4 # turn off with buttom - sets countdown to turn amplifier off
                    sleep(0.5)
                    break
                if inp == 0x12: # 00010010
                    run_cmd(mpc_next)
                    sleep (0.25)
                if inp == 0x14: # 00010100
                    run_cmd(mpc_prev)
                    sleep (0.25)
            else:    
                inp = bus.read_byte_data(i2c_addr,0x12)
                if inp == 160:
                    bus.write_byte_data(i2c_addr,0x12,0x10)
                if inp == 208: # 11010000
                    countdown = 0 # remote turn off, bypass countdown
                    sleep(0.5)
                    break

            timenow = datetime.now()
            radiodelta = timenow - radiotime
            if radiodelta > timedelta(seconds=1):
                f=os.popen("mpc -f @=@[%name%]@=@[%artist%]@=@[%title%]@=@ current | tr -d '[]'")
                current = str(f.readlines())
            if radiodelta > timedelta(seconds=1):
                if current != "[]":
                    station = current.split("@=@")[1][:25]
                    song = current.split("@=@")[3]

                    if station == "":
                        artist = current.split("@=@")[2]
                        lcd1.lcd_string(artist,0,2)
                    else: 
                        lcd1.lcd_string(station,0,2)
                else:
                    lcd1.lcd_string("Stopped or",0,2)
                    lcd1.lcd_string("playlist empty ",1,2)
                radiotime = datetime.now()
            if current != "[]":
                timenow = datetime.now()
                scrolldelta = timenow - scrolltime
                if scrolldelta > timedelta(seconds=0.4):
                    if len(song) > 25:
                        lcd_text = song[k:(k+24)]
                        lcd1.lcd_string(lcd_text,1,1)
                        k=k+1
                        if k > len(song):
                            k=0
                    else:
                        lcd1.lcd_string(song,1,2)
                    scrolltime = datetime.now()
                
                
            sleep(0.3)

        if countdown == 4:
            lcd1.lcd_string("Shutdown sequence",0,2)
            lcd1.lcd_string("Denon down in: ",1,2)
            counttime = datetime.now()
            while True:
                inp = 0
                inp = bus.read_byte_data(i2c_addr,0x12)
                if inp == 0x11: # option to break amplifier turn off countdown with power on/off buttom
                    lcd1.lcd_string("Interrupted",1,2)
                    sleep(1)
                    break
                    sleep(1)
                timenow=datetime.now()
                countdelta=timenow - counttime
                if countdelta > timedelta(seconds=0.95):
                    countdown = countdown - 1
                    lcd1.lcd_string(" Denon down in: " + str(countdown),1,2)
                    counttime = datetime.now()
                if countdown == 0:
                    run_cmd(radiooff)
                    break
        lcd1.lcd_string("Goodbye",0,2)
        lcd1.lcd_string(" ",1,1)
        run_cmd(mpc_stop)
        sleep(3)
        lcd1.lcd_string(" ",0,1)
        bus.write_byte_data(i2c_addr,0x12,0x00)
def main():
    test_i2c()

if __name__ == "__main__":
    main()
