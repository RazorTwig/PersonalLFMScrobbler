# A tool that takes a list of scrobbles from either a TXT or CSV file and automatically sends them to Last.FM
This tool is purely meant to be used for when the user was unable to scrobble some tracks that they'd heard and were unable to send in some other way. For instance if the user was out at a store and wanted to input the songs they'd heard while there, or they'd been listening to a mix of songs on Soundcloud and wanted to put in the individual songs from the mix. This tool is NOT meant to be used for filling up a users profile with tracks they haven't listened to. Please see the official [Last.FM API Guidelines](https://www.last.fm/api/scrobbling#when-is-a-scrobble-a-scrobble) for more information.

## Usage:
```
py scrobbler.py [-h] [-f, --filename FILENAME] [-u, --user USER] [-i, --increment] [-s, --separator] {check, login, scrobble, logout}
```

### Arguments:
- Any arguments used will supercede their configured values in config.toml
- -f, --filename: Specifies the file to be parsed.
	- Default: 'tracklist.txt'
- -u, --user: Specifies the user profile from config.toml to be used
	- Will be populated any time the user logs into their account via the program, either by running 'scrobble' for the first time, or by using the 'login' command.
	- Default: 'USER'
- -i, --increment: Specifies the default amount of time between scrobbles in minutes.
	- Default: 3
- -s, --separator: Specifies the separator to use when parsing CSV files. Good for if a file has a lot of commas in either the artists or tracks.
	- Default: ','
- {check, login, scrobble, logout}: The action to run.
	- check: Attempts to parse the specified file and and outputs a summary of what will be scrobbled if no errors are found.
	- login: The program will ask Last.FM for authorization to do actions on the user's behalf. If the user allows it, will save the user session key and user name under the specified user profile for future scrobbling.
	- scrobble: The check action will be run to ensure that the file can be parsed and then the scrobbles will be sent to Last.FM for the specified user. If no user is logged in (no saved session key found for the specified user profile), the login action will be run first.
	- logout: The program will delete the session information (key and user name) for the specified user profile.

## TXT file format:
The TXT file should have either a command, a single track, or a blank line, on each line. Lines with more than one command or track will not be parsed correctly.

### Commands:
- !DATE (REQUIRED BEFORE ANY TRACK INFORMATION.)
	- Specifies the date and time to start at for any tracks which follow.
	- format: 'MM/DD(/YYYY) HH:MI(:SS)'
		- Year and Second are optional and will default to the current year and '00' respectively if left out.
		- If no date is specified, either the previously specified date will be used or the current date if it's the first !DATE command.
		- The time is assumed to be in 24 hour format.
- !ALB (Optional)
	- Specifies the album information for any tracks which follow.
	- By default, no album information is sent to Last.FM
	- format: blank or 'ALBUMARTIST - ALBUM'
		- If left blank, tracks which follow will have no album information sent to Last.FM.
		- If the ALBUMARTIST and ARTIST are specified, tracks which follow will have that information included in their information sent to Last.FM
- !INT (Optional)
	- Changes the interval between tracks which follow (in minutes.)
	- Default: 3
- !COMM (Optional)
	- For any comments the user may want to add to their tracklist file.
	- Anything on these lines will be ignored by the parser.

### Track format:
All tracks should be in the format of 'ARTIST - TRACK'.
- The separator between the ARTIST and TRACK can be a hypen, en dash, or em dash
- If more than 1 instance of ' - ' is found within a track name, the program will ask which to separate on.
	- e.g. "DJ Phil Ty(0)( - )A Kay A (Da Tweekaz Remix(1)( - )Activist 170 Edit)" contains multiple separator dashes. Which should be the split (or STOP)? [0, 1]:
- If no instances of ' - ' are found, the program will ask if the user would like to retype the line, delete the line (ignore it in parsing, but it will be left in the file,) or stop parsing altogether.
	- e.g. "Geck-o -It's What We Are VIP" cannot be split. Do you want to RETYPE or DELETE or STOP?

## CSV file format:
The CSV file should have its various supported values separated by commas. The first line of the file can be used to specify the column headers.

### Columns
- ARTIST (Required)
- TRACK (Required)
- DATE (Required)
	- At the least, the very first track needs to have this value populated.
	- If unspecified, the current time increment will be used to get the timestamp based off the previous tracks timestamp.
	- format: 'MM/DD(/YYYY) HH:MI(:SS)'
		- Year and Second are optional and will default to the current year and '00' respectively if left out.
		- If no date is specified, either the previously specified date will be used or the current date if it's the first line with a value in DATE.
		- The time is assumed to be in 24 hour format.
- ALBUM (Optional)
	- Specifies only the album name for the track.
- ALBUMARTIST (Optional)
	- If not included with the ALBUM column, will default to ARTIST.
	- If no ALBUM specified, this value will be ignored.
- TRACKNO (Optional)
- INCREMENT (Optional)
	- Changes the interval between tracks which follow (in minutes.)
	- Default: 3
- If the first row does not define the column headers, the default is 'ARTIST,TRACK,DATE'

### Track values
- Each line of the CSV must have the same number of columns (inferred by the number in the first row.)
- If a value for one of the columns includes a comma, the full values should be enclosed by double-quotes.
	- e.g. Plain White T's, "1, 2, 3, 4", 8/12 9:40

## Config file (config.toml)
This file is required for correct operation of the program.

### Sections
- DEFAULTS (Required)
	- Specifies various default values for operation within the program.
		- FILENAME: The default filename to parse.
		- PROFILE: The default user profile to use when scrobbling.
		- INCREMENT: The default amount of time between scrobbles in minutes.
		- CSV_SEPARATOR: The default separator to use when parsing CSV files
	- Command line arguments supercede these values.
	-If this section, or any values in it, are missing, they will be recreated at each program execution.
- API (Required)
	- This section holds the necessary API Key and Secret for utilizing the Last.FM API.
	- A (free) Last.FM API account will be necessary and can be obtained [here](https://www.last.fm/api/account/create) and the Key and Secret can then be obtained from [here](https://www.last.fm/api/accounts)
- One or more user profiles can be configured via logging in with using the '-u' argument.
	- If no profile is found with the specified name, the program will ask if the user wants to login and authorize the program and, once they do, it will save the session key and user name under the profile for future use.
	- Using the logout option will remove the session key and user name from the config file but not the profile itself.


## Future tasks
- Some checking before sending the scrobbles to Last.FM such as ensuring that the current set of scrobbles is not older than 14 days (Last.FM will not accept these), that they will not overrun the current time (Last.FM will default them all to the current moment so that any that overrun the current time will all look to be have been listened to at the same time), and that they will not overlap any other tracks that the user has already scrobbled.
- (maybe) Allowing a way for the user to specify a mix from something like Youtube/Soundcloud/Mixcloud/etc. and get the tracklist for it from 1001Tracklists (or possibly other sources where available.)