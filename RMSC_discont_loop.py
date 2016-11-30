#!/usr/bin/env python3
##########################################################################################
# This code pulls weather data from weather underground (Park Ave station, Rochester, NY)#
# and calculates hourly runoff from green infrastructure implemented at the RMSC campus  #
##########################################################################################

## TO DO:
#   update cumulative runoff so (1) it works and (2) can reset itself if the code goes down (maybe have it pull from sparkfun?)

########################################################################
# runoff_phant.py
#
# Calculate the runoff difference between new and old landscape at the RMSC
# Created by Matthew Hoffman in 2016
#
# Uses code from the Raspberry Pi Phant Example
# created by Jim Lindblom @ SparkFun Electronics
# July 7, 2014
#
########################################################################
import time # time used for delays
import http
import urllib
import urllib.request
import json

#################
## Phant Stuff ##
#################
server     = "data.sparkfun.com" # base URL of your feed
publicKey  = "1n1b4lW1pMI95AJ4MWzJ" # public key, everyone can see this
privateKey = "0mqobDpqB5IPDpmdZ5km"  # private key, only you should know
fields     = ["rain", "runoff", "cumulative_runoff"] # Your feed's data fields

##################################
# Coefficients for Runoff Model ##
##################################
S_pervious             = 10.40816327 # pervious S value
S_impervious           = 0.309278351 # impervious S value
S_pervious_pavement    = 12.22222222 # pervious pavement S value

area_pervious          = 39203 # area of pervious surface (ft^2)
area_impervious        = 28023 # area of impervious surface (ft^2)
area_pervious_pavement = 24111 # area of pervious pavement (ft^2)
area_impervious_pre    = 48579 # area of impervios surface prior to renovation (ft^2)
area_pervious_pre      = 42938 # area of pervious surface prior to renvation (ft^2)

def update_rainfall(rain_prev):
    print("Updating rainfall!")
    # Our first job is to create the data set. This is pulled from wunderground

    # with _ as _: handles closing automatically
    with urllib.request.urlopen('http://api.wunderground.com/api/03a091e5dab21b0f/conditions/1/q/pws:KNYROCHE40.json') as f:
        parsed_json = json.loads(f.read().decode('utf-8'))
    obs_time = parsed_json['current_observation']['observation_time']
    #location = parsed_json['location']['city']

    rain_current = float(parsed_json['current_observation']['precip_1hr_in'])

    # determine if it was previously raining. If it was, add the current rainfall
    if rain_prev > 0:
        storm = storm + rain_current
    else:
        storm = rain_current

    print(obs_time)
    print("Current hourly rainfall is: %s inches" % (rain_prev))
    print("This storm event has resulted in: %s inches" % (storm))

    return storm, rain_current

def post_data(data):
    # Next, we need to encode that data into a url format:
    params = urllib.parse.urlencode(dict(zip(fields, data))) # [a,b,c] [1,2,3] -> [(a,1), (b,2), (c,3)] -> {a:1, b:2, c:3}

    # Now we need to set up our headers:
    # These are static, should be there every time:
    headers = {"Content-Type"      : "application/x-www-form-urlencoded",
               "Connection"        : "close",
               "Content-Length"    : len(params), # length of data
               "Phant-Private-Key" : privateKey} # private key header

    # Now we initiate a connection, and post the data
    c = http.client.HTTPConnection(server)
    # Here's the magic, our reqeust format is POST, we want
    # to send the data to data.sparkfun.com/input/PUBLIC_KEY.txt
    # and include both our data (params) and headers
    c.request("POST", "/input/" + publicKey + ".txt", params, headers)
    try:
        r = c.getresponse() # Get the server's response and print it
        print (str(r.status) + " " + str(r.reason))
    except:
        pass

def compute_runoff(storm, cumulative_runoff_saved):
    # Compute Runoff
    runoff_impervious_inc = 0
    runoff_pervious_inc = 0
    runoff_pervious_pavement_inc = 0
    if storm > 0.2 * S_impervious:
        runoff_impervious_inc = curve_number_eq(storm, S_impervious)
    if storm > 0.2 * S_pervious:
        runoff_pervious_inc = curve_number_eq(storm, S_pervious)
    if storm > 0.2 * S_pervious_pavement:
        runoff_pervious_pavement_inc = curve_number_eq(storm, S_pervious_pavement)

    runoff = (runoff_impervious_inc * area_impervious + \
              runoff_pervious_inc * area_pervious + \
              runoff_pervious_pavement_inc * area_pervious_pavement) / 12 # calculate runoff after GI
    runoff_pre_gi = (runoff_impervious_inc * area_impervious_pre + \
                     runoff_pervious_inc * area_pervious_pre) / 12 # calculate runoff before GI
    
    # average over one hour to add incrementally each minute
    cumulative_runoff_saved += (runoff_pre_gi - runoff) / 60

    print ("The current runoff value with new GI is: %s feet^3." % (runoff))
    print ("The runoff value before any GI was added was: %s feet^3." % (runoff_pre_gi))
    print ("The amount of runoff saved was: %s feet^3." % (runoff_pre_gi - runoff))
    print ("The total cumulative rain saved as of October 1, 2016 is " + str(cumulative_runoff_saved * 7.48052) + " gallons!") #conversion from ft^3 to gallons

    return runoff, cumulative_runoff_saved

def curve_number_eq(P, S):
    return ((P - 0.2 * S)**2 / (P + 0.8 * S))

def main():
    minutes = 60

    cumulative_runoff_saved = 0

    rain_prev = 0
    storm = 0

    # Load previous cumulative data from the data site
    with urllib.request.urlopen("http://" + server + "/output/" + publicKey + ".json") as r:
        cumulative_runoff_saved = float(json.loads(r.read().decode('utf-8'))[0]["cumulative_runoff"])

    print(cumulative_runoff_saved)

    print("Here we go! Press CTRL+C to exit")
    # Loop until CTRL+C is pressed
    while 1:
        # send data every hour
        if minutes == 60:
            storm, rain_prev = update_rainfall(rain_prev)
            minutes = 0
        else:
            runoff, cumulative_runoff_saved = compute_runoff(storm, cumulative_runoff_saved)

            # Field 0 to total rain from storm event
            # Field 1 is the runoff increment:
            # Field 2 is cumulative runoff
            post_data([storm, runoff, cumulative_runoff_saved])

            time.sleep(60) # delay for one minute
            minutes += 1
            print (minutes)

# If run as a file, run the main() function
if __name__ == '__main__':
    main()
