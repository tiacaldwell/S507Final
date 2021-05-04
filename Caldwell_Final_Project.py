##############
#Tia Caldwell
#SI 507
##############

from requests_oauthlib import OAuth2Session
import json
import requests
import re
import sqlite3 
import plotly.graph_objs as go 
import plotly.express as px 
import datetime
import time
import pandas as pd

from sklearn import datasets #pip install 
import statsmodels.formula.api as smf
from stargazer.stargazer import Stargazer #pip instal 
import webbrowser
import os

CACHE_STRAVA = "strava_activities.json"
CACHE_TOKENS = "strava_tokens.json"
CACHE_CITIES = "place_lat_lng.json"
CACHE_WEATHER = "weather.json"
CACHE_FINAL = "run_data.json"


#####################################################################################################################
#Strava  API#
#####################################################################################################################


'''This info needs to be put in by hand for the user. If you sign up for an API you can find it here: https://www.strava.com/settings/api"  '''

STRAVA_CLIENT_ID = '64159'
STRAVA_CLIENT_SECRET = 'def06feddcf3370c9cb472efe0aeb80746125c9d'
STRAVA_ACCESS_TOKEN = 'afb8b8caa47749bc314404ba852e9e0494b9578d'

def save_cache(cache_dict, CACHE_FILENAME):
    ''' Saves the current state of the cache to disk
    
    Parameters
    ----------
    cache_dict: dict
        The dictionary to save

    CACHE_FILENAME: str
        Name of cache 

    Returns
    -------
    None
    '''
    dumped_json_cache = json.dumps(cache_dict)
    fw = open(CACHE_FILENAME,"w")
    fw.write(dumped_json_cache)
    fw.close() 

def open_cache(CACHE_FILENANE):
    ''' Opens the cache file if it exists and loads the JSON into
    the CACHE_DICT dictionary.
    if the cache file doesn't exist, creates a new cache dictionary
    
    Parameters
    ----------
    None
    
    Returns
    -------
    The opened cache: dict
    '''
    try:
        cache_file = open(CACHE_FILENANE, 'r')
        cache_contents = cache_file.read()
        cache_dict = json.loads(cache_contents)
        cache_file.close()
    except:
        cache_dict = {}
    return cache_dict

def get_one_time_code(): #Go through the OATH 2 PROCESS TO GET TOKENS  

    #Go to website to authorize by clicking on the website 
    authorization_url = 'https://www.strava.com/oauth/authorize?client_id=' + STRAVA_CLIENT_ID + '&response_type=code&redirect_uri=http://localhost/exchange_token&approval_prompt=force&scope=profile:read_all,activity:read_all' 
    oauth = OAuth2Session(authorization_url)
    print('\n Please go to %s and click "Authorize" to authorize access.' % authorization_url)
    authorization_response = input('\nEnter the full callback URL')

    STRAVA_CODE = (re.split('=|&', authorization_response))[3] #parse the URL to get the secrete code 

    return STRAVA_CODE

def update_strava_tokens(): 

    tokens_json = open_cache(CACHE_TOKENS)

    #If the tokens don't exit, run the one-time code and populate the cache
    if not tokens_json: 

        STRAVA_CODE = get_one_time_code()

        strava_response = requests.post(
                            url = 'https://www.strava.com/oauth/token',
                            data = {
                                    'client_id': STRAVA_CLIENT_ID ,
                                    'client_secret': STRAVA_CLIENT_SECRET,
                                    'code': STRAVA_CODE,
                                    'grant_type': 'authorization_code'
                                    }
                        )
        #return json response
        print(strava_response.json())
        save_cache(strava_response.json(), CACHE_TOKENS)

    #If the code is expired 
    elif tokens_json['expires_at'] < time.time():
        strava_response = requests.post(
                        url = 'https://www.strava.com/oauth/token',
                        data = {
                                'client_id': STRAVA_CLIENT_ID,
                                'client_secret': STRAVA_CLIENT_SECRET,
                                'grant_type': 'refresh_token',
                                'refresh_token': tokens_json['refresh_token']
                                }
                    )
        save_cache(strava_response.json(), CACHE_TOKENS)
    
    #otherwise the saved cache is good to go 
    else: 
        pass


def scrape_strava_activities(number_pages): 
    base_url = "https://www.strava.com/api/v3/activities"

    #get access token 
    update_strava_tokens()
    tokens_json = (open_cache(CACHE_TOKENS))
    access_token = tokens_json['access_token']

    # Get pages of activities from Strava
    cache_strava = open_cache(CACHE_STRAVA)

    #for i in range(number_pages): ##### FIX LOOP! 
    for i in range(1,2):
        page = i +1 
        cache_id = base_url + '&per_page=200&' + str(page)
        url = base_url + '?access_token=' + access_token + '&per_page=200&' + str(page)

        if cache_id in cache_strava and cache_strava[cache_id][0].get('message') is None: #make sure didnt just get a message error
            print("Using cache")
            response = cache_strava[cache_id]

        else: 
            print("Pinging Strava's API")
            r = requests.get(url)
            response = r.json()
            cache_strava[cache_id] = response
            save_cache(cache_strava, CACHE_STRAVA)

def open_strava_cache_by_page(page_number):
    cache_dict = open_cache(CACHE_STRAVA)
    base_url = "https://www.strava.com/api/v3/activities"
    cache_id = base_url + '&per_page=200&'+ str(page_number)
    response = cache_dict[cache_id]
    return response

def add_strava_to_activities(json_response, activity_dict):
    for activity_num in range(len(json_response)):
        id =  json_response[activity_num]['id']
        activity_dict[id] = {}
        date_str = json_response[activity_num]['start_date'][:-10]
        activity_dict[id]['date_time'] = json_response[activity_num]['start_date']
        activity_dict[id]['date'] = date_str
        activity_dict[id]['name'] = json_response[activity_num]['name']
        activity_dict[id]['distance'] = json_response[activity_num]['distance']
        activity_dict[id]['pace'] = json_response[activity_num]['average_speed']
        activity_dict[id]['elevation'] = json_response[activity_num]['total_elevation_gain']
        activity_dict[id]['lat'] = json_response[activity_num]['start_latitude']
        activity_dict[id]['lon'] = json_response[activity_num]['start_longitude']
        activity_dict[id]['partner'] =  json_response[activity_num]['athlete_count']
        activity_dict[id]['time_zone'] =  json_response[activity_num]['timezone']
        activity_dict[id]['city'] =  json_response[activity_num]['location_city']

def clean_data(dict_activities): 

    for activity in dict_activities:

        #convert meteres per second into minute miles, storing one string and one time object 
        temp_pace = dict_activities[activity]['pace'] 
        answer = (26.8224/temp_pace)
        mins = int(26.8224/temp_pace)
        seconds = int(((26.8224/temp_pace) - mins)*60)
        time_object = datetime.time(minute= mins, second = seconds)
        time_string = time_object.strftime("%M:%S")

        #dict_activities[activity]['minmiles_obj'] = time_object
        dict_activities[activity]['minmiles'] = time_string
        dict_activities[activity]['minmiles1'] = round(answer,2)
       
        if  dict_activities[activity]['minmiles1'] > 10: 
            #dict_activities[activity]['minmiles_obj'] = datetime.time(minute= 10)
            dict_activities[activity]['minmiles'] = "10:00"
            dict_activities[activity]['minmiles1'] = 10

        else:
            dict_activities[activity]['minmiles'] = time_string[1:]
        
        #convert km to miles
        dict_activities[activity]['miles'] = round(dict_activities[activity]['distance'] *0.000621371,2) 


#####################################################################################################################
#Location API#
#####################################################################################################################

#The API has pretty tough limits so I need to get the city first through another API 
#https://opencagedata.com/dashboard#api-keys
#https://api.opencagedata.com/geocode/v1/json?key=692162e49460425ba7839f886d6bc431&q=51.952659%2C+7.632473&pretty=1&no_annotations=1
#for some reason that does not work https://pypi.org/project/opencage/

def get_location_json(lat, lon):

    lat1 = ("{0:.3f}".format(float(lat)))
    lon1 = ("{0:.3f}".format(float(lon)))

    city_dic_key = lat1 + "," + lon1

    city_dict = open_cache(CACHE_CITIES)

    if city_dic_key in city_dict:  
        print("Using city cache")
        response = city_dict[city_dic_key]

    else: 
        print("Pinging opencage's API")

        key = '692162e49460425ba7839f886d6bc431'
        geocoder = OpenCageGeocode(key)
        response = geocoder.reverse_geocode(lat1, lon1, no_annotations=1)
        city_dict[city_dic_key] = response
        save_cache(city_dict, CACHE_CITIES)
    
    return(response)
#print(get_location_json('27.089547', '-82.453588'))

def add_location_to_activity(activities, json_response, activity_key):
    
    activities[activity_key]['country'] = json_response[0]['components']['country']
    activities[activity_key]['state'] = json_response[0]['components']['state']
    activities[activity_key]['county'] = json_response[0]['components']['county']

    try: 
        activities[activity_key]['municipality'] = json_response[0]['components']['municipality']
    except KeyError: 
        try:
            activities[activity_key]['municipality'] = json_response[0]['components']['city']
        except:
            activities[activity_key]['municipality'] = json_response[0]['components']['town']

    try:
        activities[activity_key]['village'] = json_response[0]['components']['village']
    except: 
         activities[activity_key]['village'] = "" 

    activities[activity_key]['address'] = json_response[0]['formatted']

def add_location_to_activities(dict_activities):
    for activity in dict_activities: 
        if dict_activities[activity]['lat'] != None:  
            response = get_location_json(dict_activities[activity]['lat'], dict_activities[activity]['lon'])
            add_location_to_activity(dict_activities,response, activity)
        else: 
            dict_activities[activity]['country'] = ""
            dict_activities[activity]['state'] = ""
            dict_activities[activity]['county'] = ""
            dict_activities[activity]['municipality'] = ""
            dict_activities[activity]['village'] = ""
            dict_activities[activity]['address'] = ""


#####################################################################################################################
#Weather API#
#####################################################################################################################


def get_weather_json(activity_dict): 

    date_time = activity_dict['date_time'][:-1]
    weather_dic_key = date_time + ':' + str(activity_dict['lat'])+ "," + str(activity_dict['lon'])

    weather_dict = open_cache(CACHE_WEATHER)

    if weather_dic_key in weather_dict:  
        print("Using weather cache")
        response = weather_dict[weather_dic_key]

    else: 
        print("Pinging crossing weather's API")

        url = "https://visual-crossing-weather.p.rapidapi.com/history"

        querystring = {"startDateTime": date_time,
                        "aggregateHours":"1",
                        "location": str(activity_dict['lat'])+ "," + str(activity_dict['lon']),
                        "endDateTime": date_time,
                        "unitGroup":"us",
                        "contentType":"json",
                        "shortColumnNames":"0", 
                        "timezone" : "Z"}

        headers = {
            'x-rapidapi-key': "20bdcc2682msh87b18467617b824p1c1c05jsnc20fbb90351d",
            'x-rapidapi-host': "visual-crossing-weather.p.rapidapi.com"
            }

        r = requests.request("GET", url, headers=headers, params=querystring)
        response = r.json()
        weather_dict[weather_dic_key] = response
        save_cache(weather_dict, CACHE_WEATHER)

    return response 

def add_weather_to_activity(activities, json_response, activity_key):
    
    location_str = str(activities[activity_key]['lat']) + "," + str(activities[activity_key]['lon'])

    activities[activity_key]['temperature'] = json_response['locations'][location_str]['values'][0]['temp']
    activities[activity_key]['windspeed'] = json_response['locations'][location_str]['values'][0]['wspd']
    activities[activity_key]['precipitation'] = json_response['locations'][location_str]['values'][0]['precip']
    activities[activity_key]['snowdepth'] = json_response['locations'][location_str]['values'][0]['snowdepth']
    activities[activity_key]['snow'] = json_response['locations'][location_str]['values'][0]['snow']
    activities[activity_key]['humidity'] = json_response['locations'][location_str]['values'][0]['humidity']
    activities[activity_key]['conditions'] = json_response['locations'][location_str]['values'][0]['conditions']
    activities[activity_key]['weathertype'] = json_response['locations'][location_str]['values'][0]['weathertype']

def add_weather_to_activities(dict_activities):

    for activity in dict_activities: 
        if dict_activities[activity]['lat'] != None:  
            response = get_weather_json(dict_activities[activity])
            add_weather_to_activity(dict_activities, response, activity)
        else: 
            dict_activities[activity]['temperature'] = ""
            dict_activities[activity]['windspeed'] = ""
            dict_activities[activity]['precipitation'] = ""
            dict_activities[activity]['snowdepth'] = ""
            dict_activities[activity]['snow'] = ""
            dict_activities[activity]['humidity'] = ""
            dict_activities[activity]['conditions'] = ""
            dict_activities[activity]['weathertype'] = ""


#####################################################################################################################
# Store data in SQL tablea #
#####################################################################################################################

def make_sql_table():
    conn = sqlite3.connect("activities.sqlite")
    handle = conn.cursor()

    drop_table = '''
        DROP TABLE IF EXISTS "strava_runs"; 
    '''

    create_table = '''
        CREATE TABLE "strava_runs"(
            "id"   INTEGER PRIMARY KEY  UNIQUE,
            "date_time" TEXT NOT NULL,
            "date" TEXT NOT NULL,
            "name" TEXT NOT NULL,
            "miles" TEXT NOT NULL,
            "minmiles" TEXT NOT NULL,
            "minmiles1" TEXT NOT NULL, 
            "distance" REAL NOT NULL, 
            "pace" REAL NOT NULL,
            "elevation" REAL NOT NULL,
            "lat" REAL, 
            "lon" REAL, 
            "partner" NUMERIC, 
            "time_zone" TEXT NOT NULL, 
            "city" TEXT,
            "country" TEXT,
            "state" TEXT,
            "county" TEXT,
            "municipality" TEXT, 
            "location_cat" TEXT,
            "village" TEXT,
            "address" TEXT, 
            "temperature" TEXT, 
            "windspeed" TEXT, 
            "percipitation" TEXT,
            "smowdepth" TEXT, 
            "snow" TEXT, 
            "humidity" TEXT, 
            "conditions" TEXT, 
            "weathertype" TEXT 
        ); 
    '''
    handle.execute(drop_table)
    handle.execute(create_table)
    conn.commit()


def populate_sql_table(dict_activities): 

    conn = sqlite3.connect("activities.sqlite")
    handle = conn.cursor()


    insert_runs = ''' 
        INSERT INTO strava_runs 
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    '''

    for activity in dict_activities:

        new_entry = [activity, dict_activities[activity]['date_time'], dict_activities[activity]['date'], 
        dict_activities[activity]['name'], dict_activities[activity]['miles'], dict_activities[activity]['minmiles'],
        dict_activities[activity]['minmiles1'], dict_activities[activity]['distance'], dict_activities[activity]['pace'],
        dict_activities[activity]['elevation'], dict_activities[activity]['lat'], dict_activities[activity]['lon'], 
        dict_activities[activity]['partner'], dict_activities[activity]['time_zone'], dict_activities[activity]['city'],     
        dict_activities[activity]['country'], dict_activities[activity]['state'], dict_activities[activity]['county'], 
        dict_activities[activity]['municipality'], dict_activities[activity]['municipality'], dict_activities[activity]['village'], dict_activities[activity]['address'],
        dict_activities[activity]['temperature'], dict_activities[activity]['windspeed'], dict_activities[activity]['precipitation'],
        dict_activities[activity]['snowdepth'], dict_activities[activity]['snow'], dict_activities[activity]['humidity'],
        dict_activities[activity]['conditions'], dict_activities[activity]['weathertype']]
        
        handle.execute(insert_runs, new_entry)
        conn.commit()

def find_min_date(activities): 
    run_ids = activities.keys()
    list_dates = [datetime.datetime.strptime(activities[x]['date'],"%Y-%m-%d") for x in run_ids]
    return min(list_dates)

def find_max_date(activities):
    run_ids = activities.keys()
    list_dates = [datetime.datetime.strptime(activities[x]['date'],"%Y-%m-%d") for x in run_ids]
    return max(list_dates)
 
def make_list_of_dates(start_date, end_date): 
    list_of_days = []
    delta = end_date - start_date
    for i in range(delta.days+1):
        date_object = start_date + datetime.timedelta(days=i)
        date_str = date_object.strftime("%Y-%m-%d")
        list_of_day = []
        list_of_day.append(date_str)
        list_of_days.append(list_of_day)

    return list_of_days


def make_sql_table_days():
    conn = sqlite3.connect("activities.sqlite")
    handle = conn.cursor()

    drop_table = '''
        DROP TABLE IF EXISTS "days"; 
    '''

    create_table = '''
        CREATE TABLE "days"(
            "date"   TEXT KEY  UNIQUE
            
        ); 
    '''
    handle.execute(drop_table)
    handle.execute(create_table)
    conn.commit()



def populate_sql_table_days(list_of_days): 

    conn = sqlite3.connect("activities.sqlite")
    handle = conn.cursor()


    insert_runs_by_day = ''' 
        INSERT INTO days
        VALUES (?)
    '''
    for  list_of_day in list_of_days:
        handle.execute(insert_runs_by_day, list_of_day)
        conn.commit()

 
def make_sql_run_by_day(): 

    conn = sqlite3.connect("activities.sqlite")
    handle = conn.cursor()

    drop_table = '''  DROP TABLE IF EXISTS "runs_by_day"; '''

    #this just takes the first run if there were multiple
    make_table = '''
        CREATE TABLE runs_by_day AS
        SELECT * FROM days  LEFT JOIN strava_runs ON strava_runs.date = days.date
		GROUP BY days.date 
		 '''
    clean_table_miles = '''
        UPDATE  runs_by_day
        SET miles = 0
        WHERE id IS NULL; '''

    clean_table_pace = '''
        UPDATE  runs_by_day
        SET minmiles = 0
        WHERE id IS NULL;
    '''
    handle.execute(drop_table)
    handle.execute(make_table)
    handle.execute(clean_table_miles)
    handle.execute(clean_table_pace)
    conn.commit()


#pull places more than ten runs: 
def find_run_locations():
    conn = sqlite3.connect("activities.sqlite")
    handle = conn.cursor()
    query = '''
    SELECT  municipality, count(municipality) 
    FROM strava_runs
    GROUP BY municipality
    HAVING count(municipality) > 9 
    ORDER BY count(municipality) DESC
     ;  
    '''
    handle.execute(query)
    return handle.fetchall()
    conn.close()

def make_sql_location_cat(): 

    tuples_location = find_run_locations()

    list_location = [tuple[0] for tuple in tuples_location]
    str_location = str(list_location)
    str_location =  str_location.replace("[","(")
    str_location = str_location.replace("]",")")

    conn = sqlite3.connect("activities.sqlite")
    handle = conn.cursor()

    copy_data = '''
    UPDATE strava_runs
    SET location_cat = municipality; 
    '''
    update_data = "UPDATE strava_runs SET location_cat = 'Other' WHERE location_cat NOT IN " + str_location + ";"

    handle.execute(copy_data)
    handle.execute(update_data)

    conn.commit()    

def find_runs_per_day():
    conn = sqlite3.connect("activities.sqlite")
    handle = conn.cursor()

    query = '''
    SELECT date, miles, minmiles, minmiles1, municipality, name FROM runs_by_day;
    '''
    handle.execute(query)
    results= handle.fetchall()
    df =  pd.DataFrame(results, columns =['Date', 'Distance', 'Pace_label', 'Pace_value', 'Location', 'Name'])
    df = df.astype({'Distance': float, 'Pace_value': float})
    return df 
    conn.close()



#####################################################################################################################
# Make tables #
#####################################################################################################################
#print(find_runs_per_day())

def bar_chart(data_frame): 
    barchart = px.bar( 
        data_frame = data_frame,
        x = "Date",
        y = "Distance",
        color = "Pace_value",
        color_continuous_midpoint = 8,
        #color_continuous_scale= px.colors.diverging.balance,
        color_continuous_scale= px.colors.sequential.thermal_r,
        #color_continuous_scale= ["limegreen", "plum", "indigo"],
        hover_name = "Name", 
        hover_data={'Pace_label' : True, 'Pace_value': False}, 
        labels = {'Pace_label': 'Pace'}
    )

    barchart.update_layout(coloraxis_colorbar=dict(
    title="Pace color scale",
    tickvals = [7,7.5,8,8.5,9,9.5,10],
    ticktext= ['7:00', '7:30', '8:00', '8:30', '9:00', '9:30', ''],
    lenmode="pixels", len=300,
    ))

    barchart.update_layout = {
        'bargap':0 }

    barchart.show()

def scatter_plot_default(): 

    conn = sqlite3.connect("activities.sqlite")
    handle = conn.cursor()

    query = '''
    SELECT date, miles, minmiles, minmiles1, name, municipality, location_cat, temperature FROM strava_runs;
    '''
    handle.execute(query)
    results= handle.fetchall()
    df =  pd.DataFrame(results, columns =['Date', 'Distance', 'Pace_label', 'Pace_value', 'Name', 'Location', 'Location_category', 'Temperature'])
    df = df.astype({'Distance': float, 'Pace_value': float})
    conn.close()

    scatterplot = px.scatter(
        data_frame = df,
        x = 'Distance',
        y = 'Pace_value',
        color = 'Location_category',
        color_discrete_map = {'Other': 'grey'},
        opacity = 0.75, 
        hover_name  = 'Date',
        hover_data={'Pace_label' : True, 'Pace_value': False, 'Location_category': False, 'Location':True}, 
        labels = {'Pace_label': 'Pace', 'Pace_value':'Pace (min miles)', 'Location_category':'Location', 'Distance': 'Miles'},
        title = "Pace and Distance by Location", 
        category_orders = {"Location_category" : ['Other'] }

    )

    scatterplot.show()

def scatter_plot(string_value): 

    conn = sqlite3.connect("activities.sqlite")
    handle = conn.cursor()

    list_commands = string_value.split(",")
    x_value = list_commands[0].strip().title()
    y_value = list_commands[1].strip().title()
    color_value = list_commands[2].strip().title()

    query = '''
    SELECT date, miles, minmiles1, name, municipality, location_cat, temperature, elevation, partner, windspeed, percipitation, humidity, conditions FROM strava_runs WHERE windspeed IS NOT ""; 
    '''
    handle.execute(query)
    results= handle.fetchall()
    df =  pd.DataFrame(results, columns =['Date', 'Miles', 'Pace', 'Name', 'Location', 'Location Category', 'Temperature', 'Elevation', 'Partner', 'Windspeed', 'Percipitation', 'Humidity', 'Weather Conditions'])
    df = df.astype({'Miles':float, 'Pace':float, 'Temperature':float, 'Elevation':float, 'Partner':float, 'Windspeed':float, 'Percipitation':float, 'Humidity':float})
    conn.close()

    scatterplot = px.scatter(
        data_frame = df,
        x = x_value,
        y =  y_value,
        color = color_value,
        opacity = 0.75, 
        hover_name  = 'Date', 
        labels = {'Pace_label': 'Pace', 'Pace_value':'Pace (min miles)', 'Location_category':'Location', 'Distance': 'Miles'},
        title = x_value + " and " +  y_value + " by " + color_value 

    )

    scatterplot.show()

def regress(formula_string):

    conn = sqlite3.connect("activities.sqlite")
    handle = conn.cursor()

    query = '''
    SELECT miles, minmiles1, elevation, partner, temperature, windspeed, percipitation, humidity, conditions, location_cat FROM strava_runs WHERE windspeed IS NOT ""; 
    '''
    handle.execute(query)
    results= handle.fetchall()
    conn.close()

    df =  pd.DataFrame(results, columns =['minmiles', 'miles', 'elevation', 'partner', 'temperature', 'windspeed', 'percipitation', 'humidity', 'conditions', 'location'])
    df = df.astype({'minmiles':float , 'miles':float , 'elevation':float , 'partner':float , 'temperature':float , 'windspeed':float , 'percipitation':float , 'humidity':float })
   # print(df['minmiles'])
   # print(df[['miles', 'elevation', 'partner', 'temperature', 'windspeed', 'percipitation', 'humidity', 'conditions', 'location']])

    mod = smf.ols(formula = formula_string, data=df)
    #minmiles ~ miles + elevation + temperature + location
    est = mod.fit()
    print(est.summary())
    return  mod.fit()


  #regress("minmiles ~ miles + elevation + temperature + location")


#####################################################################################################################
# Run it All #
#####################################################################################################################
def run(): 

    print("Welcome! If you have your own strava account and a strava developer page, this will scrape your data. Let's get started.")

    ##THIS GETS ALLL THE DATA INTO A DICT###

    def get_data_from_python():
        activities = {}
        scrape_strava_activities(2) 
        strava_data = open_strava_cache_by_page(2)
        add_strava_to_activities(open_strava_cache_by_page(2), activities)
        add_location_to_activities(activities)
        add_weather_to_activities(activities)
        clean_data(activities)
        save_cache(activities, CACHE_FINAL)


        print("Your runs were scrapped and matched with location and weather data")

    get_data_from_python()
    activities = open_cache(CACHE_FINAL)

    ##THIS GETS ALLL THE DATA INTO TWO SEQUEL TABLES###
    def get_data_into_sql():
        make_sql_table()
        populate_sql_table(activities)
        make_sql_table_days()
        list_of_days = (make_list_of_dates(find_min_date(activities), find_max_date(activities)))
        populate_sql_table_days(list_of_days)
        make_sql_run_by_day()
        make_sql_location_cat()

        print("A  SQL database 'activites' was created or updated on your computer")
    
    get_data_into_sql()

    #activities = open_cache(CACHE_FINAL)

    #This is the user input to choose out put 
    break_main_loop = 0
    while True: 

        if break_main_loop == 1: 
            break

        commmand = input("\n How would you like to see your data? Type 'scatter plot' or 'bar chart' or 'regresion'. You can also always type 'exit' or 'back': ") 

        if commmand == 'scatter plot': 
            scatter_plot_default()

            while True: 

                if break_main_loop == 1: 
                    break

            
                
                print('''
                That was my favorite scatter plot! You can make your own  by entering in "X Variable, Y Variable, Grouping Variable".
                For Example, "Miles, Pace, Location Category".

                X-AXIS, Y-AXIS, AND GROUP VARIABLE OPTIONS:
                        - Date 
                        - Miles
                        - Pace 
                        - Temperature
                        - Elevation
                        - Windspeed
                        - Percipitation
                        - Humidity
                        - Partner (number of people ran with)

                OPTIONS ONLY FOR GROUP VARIABLES 
                        - Location Category
                        - Weather Conditions

                        ''')

                scatter_command = input("Type your command here: ")

                if scatter_command.strip().lower() == "exit":
                    break_main_loop == 1
                    break

                if scatter_command.strip().lower() == "back":
                    break

                try:
                    scatter_plot(scatter_command)

                except: 
                    print("Error - only enter allowable words, and don't enter the same paramter in two spots. \n")

                again = input("Would you like to make another scatter plot? Type 'yes' or 'no' or 'exit': ")
                again = again.title().strip()
                if again == "yes": pass 
                elif again == "no": break
                elif again == "exit": 
                    break_main_loop = 1
                    break

        if commmand == 'bar chart': 
            print("Use the zoom function to see smaller time periods.")
            bar_chart((find_runs_per_day()))

        if commmand == 'regression': 
            print('''
            
            You can build your own OLS regression. 
            Regression commands are progressed in the form of  'Y ~ X1, X2, X3'. 
            For example, "minmiles ~ miles + elevation + temperature + location" 
            ''') 
            
            while True: 
                string_formula =  input("\nEnter a regression command formula, or type 'exit' or 'back': ") 

                if string_formula.lower().strip() == "exit": 
                    break 
                    break_main_loop = 1 

                elif string_formula.lower().strip() == "back":
                    break
                else:
                    try: 
                        stargazer = regress(string_formula)
                    except: 
                        print("The command was not accepted. Check out the allowed inputs again.")

        if commmand == 'exit': 
            break
        if break_main_loop == 1: 
            break

run()

            


                    