# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
from datetime import datetime,timedelta
import os

#Input values
param_dict = {
    "fleet_size" : [50000,10000,1000],
    "mean_dvmt" : [45,35,25],
    "temp_c" : [40,30,20,10,0,-10,-20],
    "pev_type" : ['PHEV20','PHEV50','BEV100','BEV250'],
    "pev_dist" : ['BEV','PHEV','EQUAL'],
    "class_dist" : ['Sedan','SUV','Equal'],
    "home_access_dist" : ['HA100','HA75','HA50',],
    "home_power_dist" : ['MostL1','MostL2','Equal'],
    "work_power_dist" : ['MostL1','MostL2','Equal'],
    "pref_dist" : ['Home60','Home80','Home100'],  
    "res_charging" : ['min_delay','max_delay','midnight_charge'],
    "work_charging" : ['min_delay','max_delay']
}

#Kicks off the run either for just individual scenarios or for scenarios for aggregated temperature profiles (if temp_path is included)
#By default, saves weekend/weekday plots for each scenario in the folder this is run from

def run(scenario_path, temp_path="", api_key = "DEMO_KEY"):

    #Ensure scenario_path is valid
    try:
        pd.read_csv(scenario_path)
    except:
        scenario_path = input('Enter full file path to scenario csv file: ')
    scenario_csv = pd.read_csv(scenario_path)
    
    if temp_path=="":
        print("Running API without user-defined temperatures...")
        final_result = csv_run(scenario_csv,api_key)
        for scenario in final_result.keys():
            dow_dict = {}
            dow_dict = dow_dict.fromkeys(['weekday_load_profile','weekend_load_profile'])
            for dow in dow_dict.keys():
                dow_dict[dow] = pd.DataFrame(final_result[scenario][dow].to_list(),index = final_result[scenario].index) 
                dow_dict[dow].T.to_csv(os.path.join(os.getcwd(),'OutputData','scen'+str(scenario)+"_"+dow.split("_")[0].capitalize()+"_gridLoad.csv"))
            final_result[scenario] = dow_dict

    #If we have a temperature csv, read it and pass it to function
    else:
        temp_csv= pd.read_csv(temp_path)
        print("Using input csv for temperatures to run the API...")
        temp_csv['date'] = pd.to_datetime(temp_csv['date'])
        temp_csv['date'] = temp_csv['date'].dt.date
    # Saturday and Sunday are 5 and 6, Monday is 0. <5 is weekday
        temp_csv['weekday'] = temp_csv['date'].apply(lambda x: x.weekday())#<5)
        temp_csv['temp_c'] = temp_csv['temperature']
        temp_csv.drop('temperature',axis = 1,inplace=True)
        final_result = temp_run(scenario_csv,temp_csv,api_key)

#Plotting and Save CSVs with data
    for scenario,row in scenario_csv.iterrows():
        if temp_path == "":
            for dow in final_result[scenario]:
                notemp_loadPlotting(final_result[scenario][dow],scenario,dow)
        else:
            loadPlotting(final_result,scenario)
            final_result[scenario].to_csv(os.path.join(os.path.curdir,'OutputData','scen'+str(scenario)+"_temp_gridLoad.csv"))
 


#Applies API_Run to every row in temp_csv. This is only run if using a csv with temperature data
#Sends in a row based on a single scenario and a set of temperatures (each representing one day or time interval to be averaged)
def temp_run(scenario_csv,temp_csv,api_key,smoothing=1):
    output_dict = {}
    
    for scenario_id, scenario_row in scenario_csv.iterrows(): #Each row here represents a particular scenario defined by the user. row index is used as scenario identifier
        input_temps = temp_csv['temp_c']
        temp_df = temp_csv.assign(**scenario_row)
        temp_df['temp_c'] = input_temps #ensure list of temperatures from input csv take priority over temp_c from scenario
        temp_df['scenario_id'] = scenario_id
        output_df = pd.DataFrame()
        
    #For each day/temperature in the given csv, run the API. 
    #output_dict will have one key per scenario, each corresponding to a df with a row per 15 minute time bucket
        for temp_id,temp_row in temp_df.iterrows():
            result = API_run(temp_row,api_key,smoothing)
            result['date'] = temp_row.date
            result['time'] = result.index
            result['weekday'] = temp_row.weekday
            result.index =  [datetime.strptime(x,"%Y-%m-%d %H:%M:%S") for x in str(temp_row['date'])+" "+result.index]
            
            
        #Smoothing: If day of week is a Saturday or Monday, make sure morning is smoothed with end of previous day
        #However, need to ensure the previous day is included in this dataset before smoothing
            prev_date = temp_row.date-timedelta(days = 1)
            if not output_df.empty:
                if (temp_row.weekday==5 or temp_row.weekday==0) & (prev_date in set(output_df.date)):
                    try:  
                        for charge_type in result.columns[0:6]:
                        #Smooth across last hour and first hour between days (8 total values)
                            slope_inc = (output_df.loc[str(prev_date)+" 23:00:00",charge_type]-result.loc[str(temp_row.date)+" 0:45:00",charge_type])/(8)
                            if slope_inc == 0:
                                pass
                            else:
                                slope_array = np.arange(output_df.loc[str(prev_date)+" 23:00:00",charge_type],result.loc[str(temp_row.date)+" 0:45:00",charge_type],-slope_inc)
                                slope_array = np.around(slope_array,2)
                                output_df.loc[str(prev_date)+" 23:00:00":str(prev_date)+" 23:45:00",charge_type] = slope_array[:4]
                                result.loc[str(temp_row.date)+" 0:00:00":str(temp_row.date)+" 0:45:00",charge_type] = slope_array[4:]
                    except ArithmeticError:
                        print("slope_inc: "+str(slope_inc))
#                    
            output_df = output_df.append(result) 
        output_dict[scenario_id] = output_df
        
    return output_dict

#Takes in a csv with one row for each parameter that is going to be run
def csv_run(input_csv, api_key, smoothing = 1):
    output_dict = {}
    #output_metadata_dict = {}
    for row_id, row in input_csv.iterrows(): #Each row here represents a particular scenario defined by the user. row_idx is used as scenario identifier
        for col_idx, val in enumerate(row):
            if val not in param_dict[list(param_dict)[col_idx]]:#param_series[col_idx]:
                if col_idx==2: #Find closest temperature rather than throwing an error
                    nearest_temp = find_nearest(param_dict['temp_c'],val)
                    print("Scenario "+str(row_id)+" temperature: "+str(val))
                    print("Nearest value: "+str(nearest_temp))
                    row[col_idx] = nearest_temp
                else:
                    print("Invalid input row index "+str(row_id)+", column index "+str(col_idx)+ (": "+param_dict[list(param_dict)[col_idx]]))
                break

            #Run API_run and append to new series to return with all data
            output_dict[row_id] = (API_run(row,api_key,smoothing))
    return output_dict


#This function is called by temp_apply and returns output from the API based on the row sent by temp_apply
def API_run(df_row, api_key, smoothing):  
    #Assign values for each parameter- must be in order given in documentation
    #if csv_temp parameter is defined, that means it is passed in via csv. Must replace temp_c with that value based on available temps defined for the tool
    if len(df_row)==15:
        date,weekday,temp_c,fleet_size,mean_dvmt,pev_type,pev_dist,class_dist,home_access_dist,home_power_dist,work_power_dist,pref_dist,res_charging,work_charging,scenario_id = df_row
        print(date)
    else:
        fleet_size,mean_dvmt,temp_c,pev_type,pev_dist,class_dist,home_access_dist,home_power_dist,work_power_dist,pref_dist,res_charging,work_charging = df_row
    temp_c = find_nearest(param_dict["temp_c"],temp_c)
    #day_of_week and dest_type are used to generate plots- therefore these cannot be set manually
    #Generate load profiles for home, public, and work on both weekends and weekdays and for different charger levels according to the selected parameters
    base_url = """https://developer.nrel.gov/api/evi-pro-lite/v1/daily-load-profile?api_key=%s&""" %(api_key)
    url = base_url+"""fleet_size=%s&mean_dvmt=%s&temp_c=%s&pev_type=%s&pev_dist=%s&class_dist=%s&home_access_dist=%s&home_power_dist=%s&work_power_dist=%s&pref_dist=%s&res_charging=%s&work_charging=%s""" \
        %(fleet_size,mean_dvmt,temp_c,pev_type,pev_dist,class_dist,home_access_dist,home_power_dist,work_power_dist,pref_dist,res_charging,work_charging)
    url=url.replace("\\", "")
    record_str = requests.get(url).text
    record_str = record_str.replace("'", "\"")
    raw_json=json.loads(record_str)
    try:
        raw_json['results']
    except KeyError:
        print("ERROR:"+raw_json['error']['code']+"\n")
        raise
    
#if day is a weekday, return the weekday load profile for the day, otherwise return weekend
    try:
        if weekday<5:
            result = pd.DataFrame(raw_json['results']['weekday_load_profile'])
        else:
            result = pd.DataFrame(raw_json['results']['weekend_load_profile'])
            
    #Change the index from integers to times throughout the day
        result.index = [str(i*timedelta(minutes=15)) for i in range(0,96)]
    #If we didn't pass in temperature data, weekday will not be defined
    except:
        result = pd.DataFrame(raw_json['results'])
    return result


#Return nearest value in array to single input value
def find_nearest(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return array[idx]

##Stack Plot
#defaults to plotting one week of data
def loadPlotting(result,scenario=0,filename = "",week=1):
    figlen = 12+len(result[scenario])/1000
    fig = plt.figure(figsize = (figlen,7))
    ax = plt.axes()
    
    if (len(result[scenario].index)>1000) & (week!=1):
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M"))

#Only plot the first week of data unless told otherwise
        if week==1:
            x_labels = result[scenario].index[0:672]
            ax.stackplot(x_labels,result[scenario][["home_l1","home_l2","work_l1","work_l2","public_l2","public_l3"]][0:672].T)
        else:
            x_labels = result[scenario].index
            ax.stackplot(x_labels,result[scenario][["home_l1","home_l2","work_l1","work_l2","public_l2","public_l3"]].T)
        
    plt.legend(['Home L1','Home L2','Work L1','Work L2','Public L2','DC Fast'],fontsize = 14,loc = 'upper left')
    plt.xlabel('Date',size=18)
    plt.ylabel('Grid Load [kW]',size=18)
    plt.title('Fleet-wide Grid load: Scenario '+str(scenario),size=18)
    plt.xticks(size=10)
    plt.yticks(size=14)

    ymin, ymax = ax.get_ylim()
    ax.xaxis_date()
    ax.set_xlim([x_labels[0],x_labels[-1]])

    ax.set_ylim([0,ymax*1.25])   
    ax.xaxis.set_major_locator(plt.MaxNLocator(8))

    if filename == "":
        filename = "scen"+str(scenario)+"_gridLoad"
        
    plt.savefig(os.path.join(os.path.curdir,'OutputData',filename))
    plt.close()


#Plotting for when there is no temperature data input and the output from API call is a single day's load profile for weekend and for weekday
def notemp_loadPlotting(result,scenario, dow,filename = ""):
    
    fig = plt.figure(figsize = (12,5))
    ax = plt.axes()
    xaxis_labels = [(x * 15.0)/60.0 for x in range(0,96)]
    ax.stackplot(xaxis_labels,result)
    day_title = dow.split("_")[0].capitalize()
    
    plt.legend(['Home L1','Home L2','Work L1','Work L2','Public L2','DC Fast'],fontsize = 14,loc = 'upper left')
    plt.xlabel('Hour of Day',size=18)
    plt.ylabel('Grid Load [kW]',size=18)
    plt.title(day_title+' Fleet-wide Grid load: Scenario '+str(scenario),size=18)
    plt.xticks(size=14)
    plt.yticks(size=14)

    ymin, ymax = ax.get_ylim()
    ax.set_xlim([0,24])

    ax.set_ylim([0,ymax*1.25])   
    ax.xaxis.set_major_locator(plt.MaxNLocator(6)) 
    
    if filename == "":
        filename = "scen"+str(scenario)+"_"+day_title+"_gridLoad.png"
        plt.savefig(os.path.join(os.path.curdir,"OutputData",filename))
    plt.close()
    
    
    
##Stack Plot
#plots data from startdate forward or from the first day of data forward if no startdate supplied
#startdate in yyyy-mm-dd format
#Plots forward numdays number of days (default is to plot one week)
def csvPlotting(path,startdate = "",numdays = 7,filename = ""):
    
    result = pd.read_csv(path)
    figlen = 12+len(result)/1000
    fig = plt.figure(figsize = (figlen,7))
    ax = plt.axes()

#Only plot the first week of data unless told otherwise
    if startdate=="":
        x_labels = result.date[0:numdays*96]+ " "+ result.time[0:numdays*96]
        x_labels = [datetime.strptime(x,"%Y-%m-%d %H:%M:%S") for x in x_labels]
        ax.stackplot(x_labels,result[["home_l1","home_l2","work_l1","work_l2","public_l2","public_l3"]][0:numdays*96].T)
    else:
        print("Assumed startdate in yyyy-mm-dd format...")
        try:
            datetime.strptime(startdate,"%Y-%m-%d")
        except:
            print("Start date in wrong format. Need yyyy-mm-dd")
#Get index of first entry for start date (at time 00:00)       
        startdate_idx = result[result.date==startdate].index[0]
        enddate_idx = startdate_idx+numdays*96
        x_labels = result.date[startdate_idx:enddate_idx]+ " "+ result.time[startdate_idx:enddate_idx]
        x_labels = [datetime.strptime(x,"%Y-%m-%d %H:%M:%S") for x in x_labels]
        ax.stackplot(x_labels,result[["home_l1","home_l2","work_l1","work_l2","public_l2","public_l3"]][startdate_idx:enddate_idx].T)
    
    if (len(x_labels)>1000):
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M"))
    
    plt.legend(['Home L1','Home L2','Work L1','Work L2','Public L2','DC Fast'],fontsize = 14,loc = 'upper left')
    plt.xlabel('Date',size=18)
    plt.ylabel('Grid Load [kW]',size=18)
    plt.title('Fleet-wide Grid load: '+str(numdays)+" days",size=18)
    plt.xticks(size=10)
    plt.yticks(size=14)

    ymin, ymax = ax.get_ylim()
    ax.xaxis_date()
    ax.set_xlim([x_labels[0],x_labels[-1]])

    ax.set_ylim([0,ymax*1.25])   
    ax.xaxis.set_major_locator(plt.MaxNLocator(8))

    if filename == "":
        filename = str(numdays)+"days_gridLoad_plot"
    plt.savefig(os.path.join(os.path.curdir,filename))
    plt.close()