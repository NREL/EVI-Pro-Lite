"""
README

- Input csv must have values in order as follows: 
- fleet_size, mean_dvmt, temp_c, pev_type, pev_dist, class_dist, home_access_dist, home_power_dist, work_power_dist, pref_dist 
- Each row then represents a single run. All runs from the input csv are output in a dataframe with data for both weekend and weekday


- Temperature csv needs two columns: "date" and "temperature"
    - Each row in the temperature csv is one day and function aggregates across all included dates. 
    - Graph is cumulative so doesn't matter how many days- it is defined by user in the temp_csv input
- Assume temp CSV is in celsius

#TO RUN
-Run this script by opening terminal and navigating to the directory the script is downloaded to
-Enter 'python' to start python shell and 'import EVIProLite_CSVScript'
-'EVIProLite_CSVScript.run("<file path to scenario csv with parameters as described above>","<file path to optional temperature csv>")

#PLOTTING
-The script will produce plots automatically as part of the run function but csvPlotting can alternatively be used to import data and plot
-Defaults to plotting the first week of data or alternatively the user can specify the number of days and the start date
"""