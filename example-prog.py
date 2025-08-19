from utils.lfm_api import LastFM
from utils.reader import Reader

# Instantiate the LastFM object.
# This will prompt the user to log in if 
# it finds no saved user session keys.
lfm = LastFM()

# Instantiate a Reader for the file 'tracklist.txt'.
r = Reader('tracklist.txt')

# Read the scrobbles from 'tracklist.txt'
# For future work with checking for overlaps, the response
# will be split into set of dates that were set in the txt file
t = r.read()

# Getting just the scrobbles to pass to the Last.FM object
scrobbles = []
for dt in t.keys():
	scrobbles += t[dt]['tracks']

# Scrobbling.
lfm.scrobble(scrobbles)