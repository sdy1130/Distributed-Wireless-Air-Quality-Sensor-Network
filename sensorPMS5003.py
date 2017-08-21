#---------------------------------#
# filename: sensorPMS5003.py      #
# author: SeungDoo (Charlie) Yang #
#---------------------------------#

import os
import sys
import time
import serial
import numpy as np

DATA_FRAME_LENGTH = 28

class PMS5003Reader:

    def __init__(self, inport):
        
        #open port
        self.serial = serial.Serial(port=inport,baudrate=9600)

    def readValue(self):
        """function:
            Read and return a frame with length of 28 from the serial port
        """
        
        while True:

            data = []
            
            #two start bytes
            start1 = self.serial.read()
            if start1 == b'\x42':
                start2 = self.serial.read()
                if start2 == b'\x4d':
                    
                    #check if the frame length is correct
                    frame_high = ord(self.serial.read())
                    frame_low =  ord(self.serial.read())
                    frame_length = frame_high*256 + frame_low
                    if frame_length == DATA_FRAME_LENGTH:
                        
                        #data acquisition
                        for i in range(frame_length):
                            data.append(ord(self.serial.read()))

                        #verify the data with checksum (last two bytes)
                        checksum_expected = data[len(data)-2]*256 + data[len(data)-1]
                        checksum_received = 0
                        for i in range(len(data) - 2):
                            checksum_received += data[i]
                        checksum_received += frame_high + frame_low + ord(start1) + ord(start2)

                        if checksum_expected == checksum_received:
                            return data
                        else:
                            print "checksum error\n"
                            print "expected: {0}, received: {1} bytes".format(checksum_expected, checksum_received)
                            return None

                    else: 
                        print "unexpected frame length"
                        return None
        
    def read(self, duration, file_name, debug):
        
        """function:
            Read the frames for a given duration and return PM 2.5 and PM 10 concentrations'
            average, standard deviation, min, and max
            
            The frame also consists of 10 other data, such as a number of particles larger than PM 2.5
            But at this moment, only focusing on PM 2.5 and PM 10 concentrations
        """

        #initialization
        start = os.times()[4] 
        count = 0
        species = [[] for i in range(12)]
        result = []

        while os.times()[4]<start+duration:
            try:
                values = self.readValue()
                
                #convert each data to an integer value
                for i in range(len(species)):
                    species[i].append(values[i*2]*256 + values[i*2 + 1])

                #elasped time
                dt = os.times()[4] - start
                
                time.sleep(1)
                count += 1
            except KeyboardInterrupt:
                print "keyboard interrupt"
                sys.exit()
            except:
                e = sys.exc_info()[0]
                print ("ERROR: " + str(e))

        #create debug file
        if debug:
            file_name = "debug_" + file_name
            f = open(file_name,"w")
            for pm in range(len(species)):
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

        #only return concentration of pm2.5 and pm10 (for the current purpose)
        return result[12:20]
