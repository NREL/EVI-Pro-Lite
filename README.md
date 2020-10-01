
EVI-Pro Lite API Load Profile Generation

To Run:
- Run this script by opening terminal and navigating to the directory the script is downloaded to
- Enter 'python' to start python shell and 'import EVIProLite_LoadPlotting'
- EVIProLite_LoadPlotting.run("<file path to scenario csv with parameters as described above>","<file path to optional temperature csv>")

	You can run the script using the provided csvs as a test with:
	EVIProLite_LoadPlotting.run("./InputData/Scenarios_test.csv","./InputData/ShortTemps_test.csv")

Plotting:
- The script will produce plots automatically as part of the run function but csvPlotting can alternatively be used to import data and plot
- Defaults to plotting the first week of data or alternatively the user can specify the number of days and the start date
- The plots will be saved to the OutputData folder

- Input csv must have values in order as follows: 
	- fleet_size, mean_dvmt, temp_c, pev_type, pev_dist, class_dist, home_access_dist, home_power_dist, work_power_dist, pref_dist, res_charging, work_charging 
	- View ./InputData/Scenarios_test.csv for proper formatting of this file
- Each row then represents a single run. All runs from the input csv are output in a dataframe with data for both weekend and weekday


- The temperature csv needs two columns: "date" and "temperature"
    - Each row in the temperature csv is one day and function aggregates across all included dates. 
    - View ./InputData/ShortTemps_test.csv for proper formatting of this file
    - Graph is cumulative so doesn't matter how many days are included in the input
- Assume temp CSV is in celsius

