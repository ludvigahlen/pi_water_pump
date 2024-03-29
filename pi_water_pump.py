import signal
import sys
import time
import spidev
import RPi.GPIO as GPIO
from MySQLdb import _mysql


# db
db_ip = "" # ip of your mysql/mariadb
db_username = "" # username
db_password = "" # password
db_database = "" # database

# gpio 22
LED1 = 15
# gpio 23
LED2 = 16

# gpio 18
PUMP = 12

spi_ch = 0

# Enable SPI
spi = spidev.SpiDev(0, spi_ch)
spi.max_speed_hz = 1200000

# to use Raspberry Pi board pin numbers
GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

# set up GPIO output channel
GPIO.setup(LED1, GPIO.OUT)
GPIO.setup(LED2, GPIO.OUT)
GPIO.setup(PUMP, GPIO.OUT)




def close(signal, frame):
    GPIO.output(LED1, 0)
    GPIO.output(LED2, 0)
    GPIO.output(PUMP, 0)
    sys.exit(0)

signal.signal(signal.SIGINT, close)

def valmap(value, istart, istop, ostart, ostop):
    value = ostart + (ostop - ostart) * ((value - istart) / (istop - istart))
    if value > ostop:
       value = ostop
    return value

def get_adc(channel):

    # Make sure ADC channel is 0 or 1
    if channel != 0:
        channel = 1

    # Construct SPI message
    #  First bit (Start): Logic high (1)
    #  Second bit (SGL/DIFF): 1 to select single mode
    #  Third bit (ODD/SIGN): Select channel (0 or 1)
    #  Fourth bit (MSFB): 0 for LSB first
    #  Next 12 bits: 0 (don't care)
    msg = 0b11
    msg = ((msg << 1) + channel) << 5
    msg = [msg, 0b00000000]
    reply = spi.xfer2(msg)

    # Construct single integer out of the reply (2 bytes)
    adc = 0
    for n in reply:
        adc = (adc << 8) + n

    # Last bit (0) is not part of ADC value, shift to remove it
    adc = adc >> 1

    # Calculate voltage form ADC value
    # considering the soil moisture sensor is working at 5V
    voltage = (5 * adc) / 1024

    return voltage

if __name__ == '__main__':
    # Report the channel 0 and channel 1 voltages to the terminal
    try:
        high_0 = 3.4277
        low_0 = 1.5625
        high_1 = 3.3203
        low_1 = 1.3671
        while True:
            db = _mysql.connect(db_ip, db_username, db_password, db_database)

            adc_0 = get_adc(0)
            adc_1 = get_adc(1)
  
            if adc_0 < low_0:
             low_0 = adc_0
            if adc_0 > high_0:
             high_0 = adc_0
            if adc_1 < low_1:
             low_1 = adc_1
            if adc_1 > high_1:
             high_1 = adc_1            


            
            moist1 = ((adc_0 - low_0) / (high_0 - low_0)) * 100
            moist2 = ((adc_1 - low_1) / (high_1 - low_1))* 100
            moist1 = moist1 * -1
            moist1 = moist1 + 100
            if moist1 < 0:
             moist1 = 0
            if moist1 > 100:
             moist1 = 100
            moist2 = moist2 * -1
            moist2 = moist2 + 100
            if moist2 < 0:
             moist2 = 0
            if moist2 > 100:
             moist2 = 100

            db.query("delete from STUFF where name = 'pi02_moisture'")
            db.query("insert into STUFF(name, value) values('pi02_moisture_1', {})".format(moist1))
            db.query("insert into STUFF(name, value) values('pi02_moisture_2', {})".format(moist2))

            GPIO.output(PUMP,0)
            db.query("select value from STUFF where name = 'pump_action'")
            r = db.store_result()
            row = r.fetch_row(1, how=0)
            if 'pump_water' in str(row[0]):
             print("PUMP IS ON!!")
             db.query("update STUFF set value = 'pump_idle' where name = 'pump_action'")
             GPIO.output(PUMP,1)
             time.sleep(5)
             GPIO.output(PUMP,0)
  #          print("fetch: ",row[0])
            db.close()
            time.sleep(5)
    finally:
        GPIO.cleanup()
