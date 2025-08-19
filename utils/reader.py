from pathlib import Path
import re
from pendulum import now, local, from_timestamp

from utils.lfm_objects import Scrobble

class Reader():
	implemented_ext = ['.txt', '.csv']
	curr_year = str(now().year)
	date_re = r'([0-9\/]+) ([0-9:]+)'
	tz = now().tz
	default_increment = 3

	def __init__(self, fname):
		self.fname = Path(fname)
		if not self.fname.exists():
			raise Exception(f'File {fname} not found!')
		
		if self.fname.suffix not in self.implemented_ext:
			raise Exception(f'Reader not yet implemented for {self.fname.suffix}')
		
		self.ext = self.fname.suffix.lower()

	def __get_timestamp(self, dt):
		dt, tm = re.match(self.date_re, dt).groups()

		# Date and Time are padded with the default values for year and second
		# Either the values are split into year/second and the defaults go to dummy
		# and they're thrown away or the defaults are split into year/second and 
		# dummy is an empty list that's thrown away
		month, day, year, *dummy = f'{dt}/{self.curr_year}'.split('/')
		hour, minute, second, *dummy = f'{tm}:00'.split(':')

		start_dt = local(int(year), int(month), int(day), hour=int(hour), minute=int(minute), second=int(second))
		ts = int(start_dt.timestamp())
		return ts
	
	@staticmethod
	def __add_x_minutes(ts, x):
		return ts+(x*60)

	def read(self):
		if self.ext == '.txt':
			return self.__txt()
		elif self.ext == '.csv':
			return self.__csv()

	def __txt(self):
		tracks = {}
		increment = self.default_increment
		album = None
		album_artist = None
		curr_batch = -1
		ts = -1

		def find_dashes(source):
			dashes = [' - ', ' – ', ' — ']
			indexes = []
			for dash in dashes:
				indexes += [(i.start(), i.end()) for i in re.finditer(dash, source)]
			indexes.sort()
			return indexes

		def highlight_dashes(source, splits):
			h_track = source
			splits.sort()
			h_splits = [x+(i,) for i, x in enumerate(splits)]
			h_splits.reverse()
			for start, end, ind in h_splits:
				h_track = f'{h_track[:start]}({ind})({h_track[start:end]}){h_track[end:]}'
			return h_track

		def split_on_dash(source, splits, index=0):
			splits = splits[index]
			artist, track = [source[:splits[0]],source[splits[1]:]]
			return (artist, track)

		with open(self.fname, 'r', encoding='utf-8') as tracklist:
			# Generator function to read each line of the file
			# Split is used to remove any extra whitespace like double spaces, tabs, or newlines
			def readline(file):
				for line in file:
					line = ' '.join(line.split())
					if line:
						yield line

			for line in readline(tracklist):
				command = line.split(' ', 1)
				if command[0] == '!COMM':
					# Comment row, ignore
					continue
				elif command[0] == '!INT':
					# Change the increment between songs (in minutes)
					increment = float(command[1])
				elif command[0] == '!ALB':
					# Add or remove the album artist and album of the scrobble
					if len(command) == 1 or command[1] == '':
						album = None
						album_artist = None
					else:
						splits = find_dashes(command[1])
						album_artist, album = split_on_dash(command[1], splits)
				elif command[0] == '!DATE':
					# Start a new set with a new date
					ts = self.__get_timestamp(command[1])
					curr_batch += 1
					tracks.update({curr_batch: {
						'start': from_timestamp(ts, self.tz),
						'end': '',
						'tracks': []
					}})
				else:
					# Assume it's a track otherwise
					track = {
						'artist': '',
						'track': '',
						'timestamp': 0
					}
					# Attempt to split the line on a hyphen, en dash, or em dash
					splits = find_dashes(line)
					skip = False
					while len(splits) != 1 and not skip:
						if len(splits) == 0:
							# No dashes found
							resp = input(f'"{line}" cannot be split. Do you want to RETYPE or DELETE or STOP? ')
							if resp.upper() == 'DELETE':
								# Skip this line
								skip = True
							elif resp.upper() == 'RETYPE':
								# Give the user another chance
								resp = input('What should the track be? ')
								line = resp
								splits = find_dashes(line)
							elif resp.upper() == 'STOP':
								# Stop processing and return without saving anything
								return ['',[],[]]
						else:
							# Too many dashes found
							resp = input(f'"{highlight_dashes(line, splits)}" contains multiple separator dashes. Which should be the split (or STOP)? {list(range(0, len(splits)))}:')
							if resp.upper() == 'STOP':
								# Stop processing and return without saving anything
								return ['',[],[]]
							if resp.isnumeric() and 0 <= int(resp) < len(splits):
								# Chosen split is used
								index = int(resp)
								splits = splits[index:index+1]
					if skip:
						continue
					track['artist'], track['track'] = split_on_dash(line, splits)
					track['timestamp'] = ts
					if album is not None:
						track.update({
										'album': album,
										'albumArtist': album_artist	
									})
					scrobble = Scrobble(track['artist'], track['track'], ts,
						 				album=track.get('album'),
										album_artist = track.get('albumArtist'))
					tracks[curr_batch]['tracks'].append(scrobble)
					ts = int(self.__add_x_minutes(ts, increment))
					tracks[curr_batch]['end'] = from_timestamp(ts, self.tz)
		return tracks

	def __csv(self):
		pass