from machine import Pin, I2C
import time

i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=100000)

while True:
    devices = i2c.scan()
    print("scan:", [hex(d) for d in devices])
    time.sleep(1)
