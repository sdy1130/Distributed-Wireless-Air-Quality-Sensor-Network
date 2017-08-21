#---------------------------------#
# filename: sensorSDS021.py       #
# author: SeungDoo (Charlie) Yang #
#---------------------------------#

import os
import sys
import time
import serial
import numpy as np

class SDS021Reader:

    def __init__(self, inport):
        
        #open port
        self.serial = serial.Serial(port=inport,baudrate=9600)

    def readValue(self):
        """function:
            Read and return a frame with length of 8 from the serial port
        """
        
        step = 0
        
        while True:
            
            while self.serial.inWaiting() != 0:
                
                #read serial input of ASCII characters as an integer
                v = ord(self.serial.read()) 
        
                #total of 10 bit but only focus on 3rd to 6th DATA bits
                if step == 0:
                    #first bit is always 170
                    if v == 170:
                        values = [0,0,0,0,0,0,0]
                        step = 1
                
                elif step == 1:
                    #second bit is always 192
                    if v == 192:
                        step = 2
                    else:
                        step = 0

                elif step > 8:
                    step = 0
                    #low and high*265 byte / 10... according to documentation
                    pm25 = (values[0] + values[1]*256)/10
                    pm10 = (values[2] + values[3]*256)/10
                    
                    return [pm25,pm10]
                
                #start DATA bit acquisition
                elif step >= 2:
                    if v == 170: #on 4th measurement 170, 192 repeats
                        step = 1
                        continue
                    values[step-2] = v 
                    step += 1
                
    def read(self, duration, file_name, debug):
        """function:
            Read the frames for a given duration and return PM 2.5 and PM 10 concentrations'
            average, standard deviation, min, and max
        """

        #initialization
        start = os.times()[4] 
        count = 0
        species = [[],[]]
        result = []

        while os.times()[4]<start+duration:
            try:
                values = self.readValue()
                
                #pm2.5
                species[0].append(values[0])
                #pm10
                species[1].append(values[1])
                
                #elasped time
                dt = os.times()[4] - start
                
                time.sleep(1)
                count += 1
            except KeyboardInterrupt:
                sys.exit()
            except:
                e = sys.exc_info()[0]

        #create debug file
        if debug:
            file_name = "debug_" + file_name
            f = open(file_name,"w")
            for pm in range(2):
                for value in species[pm]:
                    f.write(str(value) + "\n")
                f.write("-------------\n")
            f.close()

        #average, standard deviation, min and max computing
        for i in range(len(species)):
            result.append(np.average(species[i]))
            result.append(np.std(species[i]))
            result.append(min(species[i]))
            result.append(max(species[i]))
            
        return result
