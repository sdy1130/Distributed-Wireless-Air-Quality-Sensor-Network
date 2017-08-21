#---------------------------------#
# filename: AQstation_mainCode.py #
# author: SeungDoo (Charlie) Yang #
#---------------------------------#

import subprocess
import datetime
import os
import sys
import time
import MySQLdb as mysql
import sensorSDS021
import sensorPMS5003

DURATION = 300 #5 min
DEBUG = False #True to also create a debug file

#credentials
HOST = "agTechELlqs.ag.technion.ac.il"
USER = "AirSeung"
PASSWORD = "AirSeung"
DATABASE = "AirSeung"

#hardware id
SELECTED_HARDWARE = 2 #1 for SDS021, 2 for PMS5003

def doMeasurement(duration, debug):

    """function:
        This function calls one of the two sensor
        reader classes according to which station 
        was selected. It receives average, max and min values 
        of the PM 2.5 and PM 10 concentration after 
        a measurement of a set duration of time.
        
        Then it creates a new log file and stores the data.
        It return the file name of the newly created log file.
    """

    print "START MEASUREMENT"
    count = 0

    #open a log file for current time
    file_name = str(datetime.datetime.now()).split(".")[0]

    #measurements
    if SELECTED_HARDWARE == 1:
        USBPORT  = "/dev/ttyUSB0"
        results = sensorSDS021.SDS021Reader(USBPORT).read(duration, file_name, debug)
    elif SELECTED_HARDWARE == 2:
        USBPORT  = "/dev/ttyS0"
        results = sensorPMS5003.PMS5003Reader(USBPORT).read(duration, file_name, debug)

    file_name = "log_" + file_name
    f = open(file_name,"w")
    
    #if nothing is measured
    if len(results) == 0:
        for i in range(8):
            f.write("-1\n")
    
    #append results at the end of the log file
    else:
        for i in range(8):
            f.write(str(results[i]) + "\n")
                    
    f.write("---END OF MEASUREMENTS---\n") 
    f.close()
    return file_name

def detectDevices(file_name, duration):
    
    """function:
        This function detects nearby Wi-Fi enabled devices
        and saves their MAC address in the log file from
        doMeasurement function.
    """

    print "START DETECTION"

    #initialization
    splited_line = [] 
    mac_list = []
    start_append = 0 
    
    #append mode
    f = open(file_name,"a")
    
    #command line configuration
    #only display source, and destinaiton of the packet
    cmd = ("tshark -i mon0 -o column.format:"+'"src","%uhs","dst","%uhd"').split()

    #execute the command
    process = subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
    start_time = time.time()

    #for every output line
    for line in iter(process.stdout.readline, ""):

        #acquire data for set duration of time    
        if time.time()-start_time > duration:
            process.terminate()
            break

        #start writing to the file when a MAC address is read    
        if start_append == 0:
            if "Capturing on" in str(line):
                start_append = 1
                continue
            
        splited_line = line.split(" ")
        
        for mac in splited_line:

            if "\n" not in mac:
                mac = mac + "\n"
            
            #check if it is a valid MAC address
            if ("ff:ff:ff:ff:ff:ff" not in mac) and (len(mac) == 18):

                #write the address to file if it was not detected before
                if mac not in mac_list: 
                    mac_list.append(mac)
                    f.write(mac_list[len(mac_list)-1])
    f.write("---END OF MAC ADDRESSES---")        
    f.close()
    return

def uploadToDatabase(file_name, selected_hardware, host, user, password, database):
    
    """function:
        This function uploads the data in the log file to the database.
        It only uploads the data if the log file is complete.
        After uploading, it moves the log file to "uploaded_logs" folder
        to indicated that the log file has been uploaded.
    """

    print "START UPLOADING"

    #upload to AQMeasurement if 0, to log if 1
    switch_table = 0
    
    results = []
    
    #open data base connection
    db = mysql.connect(host, user, password, database)
    #prepare cursor object
    curs = db.cursor()

    f = open(file_name,"r")
    lines = f.readlines()

    #if a log file is incomplete
    if "---END OF MAC ADDRESSES---" not in lines:
        incomplete_file = "'" + file_name + "'"
        cmd = "sudo rm /home/pi/logs/{0}/{1}".format(str(selected_hardware), incomplete_file)
        os.system(cmd)
        f.close()
        return
    
    for line in lines:

        #end of file
        if line == "---END OF MAC ADDRESSES---":
            continue

        if "\n" in line:
            line = line[:len(line)-1]
            
        if switch_table == 0:
            
            #switch to uploading to AQMeasurement
            if line == "---END OF MEASUREMENTS---":
                switch_table = 1
                continue
            results.append(line)
            
        else:
            #upload to log table
            try:
                curs.execute("""insert into log(date, mac_address, hardware_id) values(%s, %s, %s)""",
                             (file_name[4:], line, selected_hardware)) #file_name[4:] to take out "log_"
                db.commit()
            except:
                db.rollback()

    #upload to AQMeasurement table
    try:
        curs.execute("""insert into AQmeasurement(date, hardware_id, avg_pm25, avg_pm10, std_pm25, std_pm10, min_pm25, max_pm25, min_pm10, max_pm10) values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                     (file_name[4:], selected_hardware, results[0], results[4], results[1], results[5], results[2], results[3], results[6], results[7]))
        db.commit()
    except:
        db.rollback()

    #move the file to uploaded logs
    file_name = "'" + file_name + "'"
    cmd = "sudo mv {0} /home/pi/logs/{1}/uploaded_logs/".format(file_name, str(SELECTED_HARDWARE))
    os.system(cmd)

    print "END"
    f.close()
    db.close()
    return

def checkInternetConnection(host):
    
    """function:
        This function checks if there is an internet connection
        to the database and uploading is possible. It returns True if yes.
    """
    
    count = 0
    
    #check if pinging goes through
    cmd = ("timeout 10 ping {0}".format(host)).split()

    process = subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)

    for line in iter(process.stdout.readline, ""):

        count += 1

    #there is only one line of output if database cannot be reached
    if count > 1:
        process.terminate()
        return True
    
    process.terminate()
    return False

#--------------------------#
# Execute Data Acquisition #
#--------------------------#

#wait for pi to boot up
time.sleep(60)

#check if there is a log folder; if not, create a new one
cmd = "/home/pi"
files = os.listdir(cmd)
if "logs" not in files:
    cmd = "sudo mkdir logs"
    os.system(cmd)

#check if there is a folder for a selected hardware; if not, create a new one
cmd = "/home/pi/logs"
files = os.listdir(cmd)
if str(SELECTED_HARDWARE) not in files:
    cmd = "sudo mkdir -p logs/{0}/uploaded_logs".format(str(SELECTED_HARDWARE))
    os.system(cmd)

#set working directory
cmd = "/home/pi/logs/{0}".format(str(SELECTED_HARDWARE))
os.chdir(cmd)
    
while True:

    #upload any not uploaded log
    if checkInternetConnection(HOST):
        cmd = "/home/pi/logs/{0}".format(str(SELECTED_HARDWARE))
        files = os.listdir(cmd)
        for file in files:
            if "log_" in file:
                try: uploadToDatabase(file, SELECTED_HARDWARE, HOST, USER, PASSWORD, DATABASE)
                except: continue

    while True:

        #measurement
        upload_info = doMeasurement(DURATION, DEBUG)

        #device detection
        detectDevices(upload_info, DURATION)

        #time interval
        time.sleep(1000)

        if checkInternetConnection(HOST):
            break
