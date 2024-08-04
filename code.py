import time
import os
import random
import board
import pwmio
import audiocore
import audiobusio
from adafruit_debouncer import Button
from digitalio import DigitalInOut, Direction, Pull
import neopixel
import adafruit_lis3dh
import simpleio

# https://learn.adafruit.com/circuitpython-led-animations
from adafruit_led_animation.animation.blink import Blink
from adafruit_led_animation.animation.chase import Chase
from adafruit_led_animation.animation.colorcycle import ColorCycle
from adafruit_led_animation.animation.comet import Comet
from adafruit_led_animation.animation.pulse import Pulse
from adafruit_led_animation.sequence import AnimationSequence
from adafruit_led_animation.color import AMBER, BLACK, BLUE, GREEN, ORANGE, RED, WHITE, YELLOW

# enable external power pin
# provides power to the external components
external_power = DigitalInOut(board.EXTERNAL_POWER)
external_power.direction = Direction.OUTPUT
external_power.value = True

#################
# Neopixels
#################

# Cyclotron Cover, pin: D6
cyclotron_cover_num_pixels = 39
cyclotron_cover_rgb = neopixel.NeoPixel(board.D5, cyclotron_cover_num_pixels, auto_write=True)
cyclotron_cover_rgb.brightness = 1

# Power Cell, pin: D6
powercell_num_pixels = 14
powercell_rgb = neopixel.NeoPixel(board.D6, powercell_num_pixels, auto_write=True)
powercell_rgb.brightness = .25

# Synchronous Generator, pin: D9
syncGen_num_pixels = 23
syncGen_rgb = neopixel.NeoPixel(board.D9, syncGen_num_pixels, auto_write=True)
syncGen_rgb.brightness = .5

# Switchboard, pin: D10
switchboard_num_pixels = 8
switchboard_rgb = neopixel.NeoPixel(board.D10, switchboard_num_pixels, auto_write=True)
switchboard_rgb.brightness = .5

#################
# Sound Effects
#################
wavs = []
for filename in os.listdir('/sounds'):
    if filename.lower().endswith('.wav') and not filename.startswith('.'):
        wavs.append("/sounds/"+filename)
wavs.sort()
print(len(wavs), ' sound file(s) found')
print(wavs)

audio = audiobusio.I2SOut(board.I2S_BIT_CLOCK, board.I2S_WORD_SELECT, board.I2S_DATA)

#################
# Functions
#################

def play_wav(num, loop=False):
    try:
        print('Playing', wavs[num])
        n = wavs[num]
        wave_file = open(n, "rb")
        wave = audiocore.WaveFile(wave_file)
        audio.play(wave, loop=loop)
    except:  # pylint: disable=bare-except
        return
    
def switchboardMode(on=True):
    if on == True:
        # The switch board is static until the overheat state
        switchboard_rgb[2] = RED
        switchboard_rgb[3] = RED
        switchboard_rgb[1] = YELLOW
        switchboard_rgb[4] = YELLOW
        switchboard_rgb[0] = GREEN
        switchboard_rgb[5] = GREEN
        switchboard_rgb[6] = BLUE
        switchboard_rgb[7] = YELLOW
    else:
        switchboard_rgb.fill(BLACK)
    
    switchboard_rgb.show()
    
def overheat_sequence():
    print('Overheat sequence')
    play_wav(3, loop=False)
    cyclotronOverheat.animate()
    powercellOverheat.animate()
    time.sleep(overheatCooldownDurationSeconds)

#################
# Toggle Switch
#################
toggleSwitch = DigitalInOut(board.D4)
toggleSwitch.direction = Direction.INPUT
toggleSwitch.pull = Pull.UP

#################
# Wand Fire Butt
#################
fireButton = DigitalInOut(board.D11)
fireButton.direction = Direction.INPUT
fireButton.pull = Pull.UP

################
# Animations
################
cyclotronSpeed = .075
cyclotronMaxSpeed = .015
cyclotronFireSpeed = .0075
cyclotronIdle = Comet(cyclotron_cover_rgb, speed=cyclotronSpeed, color=WHITE, tail_length=2, bounce=False, ring=True)
cyclotronOverheat = Blink(cyclotron_cover_rgb, speed=0.05, color=RED)

powercellIdle = Comet(powercell_rgb, speed=0.03, color=BLUE, tail_length=14, bounce=True)
powercellBootUp = Pulse(powercell_rgb, speed=0.1, color=BLUE, period=2)
powercellOverheat = Blink(cyclotron_cover_rgb, speed=0.05, color=RED)

syncGenIdle = Chase(syncGen_rgb, speed=0.05, color=WHITE, size=2, spacing=8)
syncGenBootup = Pulse(syncGen_rgb, speed=0.1, color=GREEN, period=2)

################
# Timing
################
transitionTimeSeconds = 5
timerStartTime = time.monotonic()
timerLastUpdate = None

fireButtonStartTime = None
overheatDurationSeconds = 10
overheatCooldownDurationSeconds = 5

# Prepare the BOOT UP speed range values
speedRange = cyclotronSpeed - cyclotronMaxSpeed
speedRangeStep = speedRange / transitionTimeSeconds
cyclotronBootUpSpeedValues = []

for i in range(0, transitionTimeSeconds):
    speed = cyclotronSpeed - (speedRangeStep * i)
    if speed < cyclotronMaxSpeed:
        speed = cyclotronMaxSpeed
    cyclotronBootUpSpeedValues.append(speed)

cyclotronBootUpSpeedValues.append(cyclotronMaxSpeed) # Append the final speed
cyclotronPowerDownSpeedValues = cyclotronBootUpSpeedValues[::-1] # Reverse the boot up speeds for the reverse speeds

################
# Variables
################

# Modes:
# 0: Off (Default)
# 1: Idle
mode = 0
isPoweredOn = None
isBootedUp = False
isFiring = False

def bootSequence():
    global timerLastUpdate
    global timerStartTime
    global mode
    global cyclotronIdle
    
    switchboardMode(on=True)
    syncGenBootup.animate()
    cyclotronIdle.animate()
    powercellBootUp.animate()
    
    if timerLastUpdate is None:
        timerLastUpdate = time.monotonic()
    
    elapsedTimeSeconds = round(abs(timerStartTime - timerLastUpdate))
    timerLastUpdate = time.monotonic()
    
    if elapsedTimeSeconds <= transitionTimeSeconds:
        print('Booting. Elapsed time', elapsedTimeSeconds)
        cyclotronIdle.speed = cyclotronBootUpSpeedValues[elapsedTimeSeconds]
    elif elapsedTimeSeconds > transitionTimeSeconds:
        print('Booted. Going idle.')
        mode = 1


###########################################
###########################################
while True:
    # Determine if we're powered on
    if toggleSwitch.value != isPoweredOn:
        isPoweredOn = toggleSwitch.value
        print('Powered On? ', isPoweredOn)
        print('Mode: ', mode)

        if isPoweredOn == True: # Play start up sound
            play_wav(0, loop=False)
        
    # If we're powered on, we want to know if we're booting up or not
    if isPoweredOn == True:
        if mode == 0: # Off
            
            bootSequence()
        elif mode == 1: # Idle
            cyclotronIdle.animate()
            powercellIdle.animate()
            syncGenIdle.animate()
    else:
        mode = 0
        
    time.sleep(.005) # NOTE: Overheat cyclotron speed is .0075, so this may be too low
