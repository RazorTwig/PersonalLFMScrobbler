This is planned to be a tool for allowing users to manually send track scrobbles to Last.FM. 

Currently working:
Parsing a formatted TXT file with a list of tracks to scrobble.
Logging a user into Last.FM.
Logging a user out of Last.FM (the tool just forgets the session key).
Sending a list of Scrobbles that have been read from a TXT file to Last.FM and logging which ones were accepted.

See the example-prog.py file to see how it can be used currently.

To do:
Parsing a CSV file with a list of tracks to scrobble.
Some checking before sending the scrobbles to Last.FM such as ensuring that the current set of scrobbles is not older than 14 days (Last.FM will not accept these), that they will not overrun the current time (Last.FM will default them all to the current moment so that any that overrun the current time will all look to be have been listened to at the same time), and that they will not overlap any other tracks that the user has already scrobbled.
Turning the tool into a command line tool so that the user won't have to write any Python code to run the tool.