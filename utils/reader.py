from pathlib import Path
import re
from pendulum import now, local, from_timestamp

from utils.lfm_objects import Scrobble
from utils.funcs import get_path_obj

class Reader():
	implemented_ext = ['.txt', '.csv']
	curr_year = str(now().year)
	date_re = r'([0-9\/]+) ([0-9:]+)'
	time_re = r'([0-9:]+)'
	tz = now().tz

	def __init__(self, increment, csv_separator):
		self.default_increment = increment
		self.csv_separator = csv_separator

	def __get_timestamp(self, dt, curr_ts=-1):
		try:
			dt, tm = re.match(self.date_re, dt).groups()
		except AttributeError:
			tm = re.match(self.time_re, dt)
			if tm is None:
				raise Exception('Unable to parse timestamp')
			if curr_ts != -1:
				curr_dt = from_timestamp(curr_ts)
			else:
				curr_dt = now()
				
			tm = tm.groups()[0]
			dt = f'{curr_dt.month}/{curr_dt.day}'

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
	
	def read(self, fname):
		fpath = get_path_obj(fname)

		if fpath.suffix not in self.implemented_ext:
			raise Exception(f'Reader not yet implemented for {fpath.suffix} files.')
		
		if fpath.suffix.lower() == '.txt':
			return self.__txt(fpath)
		elif fpath.suffix.lower() == '.csv':
			return self.__csv(fpath)

	def __txt(self, fpath):
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

		with open(fpath, 'r', encoding='utf-8') as tracklist:
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
					# Change the date or time
					last_ts = self.__add_x_minutes(ts, (-1*increment))
					ts = self.__get_timestamp(command[1], ts)
					if (ts-last_ts) >= (15*60):
						curr_batch += 1
						tracks.update({curr_batch: {
							'start': from_timestamp(ts, self.tz),
							'end': from_timestamp(self.__add_x_minutes(ts, increment), self.tz),
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
								return {}
						else:
							# Too many dashes found
							resp = input(f'"{highlight_dashes(line, splits)}" contains multiple separator dashes. Which should be the split (or STOP)? {list(range(0, len(splits)))}:')
							if resp.upper() == 'STOP':
								# Stop processing and return without saving anything
								return {}
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

	def __csv(self, fpath):
		import csv
		c_artist = 0
		c_track = 1
		c_date = 2
		c_album = -1
		c_album_artist = -1
		c_trackno = -1
		c_increment = -1
		expected_cols = 3
		increment = self.default_increment

		column_names = [
			'ARTIST',
			'TRACK',
			'DATE',
			'ALBUM',
			'ALBUMARTIST',
			'TRACKNO',
			'INCREMENT'
		]

		def get_index(val_list, search):
			try:
				ind = val_list.index(search)
			except ValueError:
				ind = -1
			return ind
		
		def get_val(val_list, column, default=None):
			if column == -1 or val_list[column] == '':
				return default
			else:
				return val_list[column]

		with open(fpath, newline='', encoding='UTF-8') as csvfile:
			tracks = {}
			vals = csv.reader(csvfile, delimiter=self.csv_separator, skipinitialspace=True)
			firstline = True
			last_ts = -1000
			ts = -1000
			curr_batch = -1

			for row_num, row in enumerate(vals):
				# Checking if the first row has column names in it
				if firstline:
					firstline = False
					if row[0] in column_names:
						expected_cols = len(row)
						c_artist = get_index(row, 'ARTIST')
						c_track = get_index(row, 'TRACK')
						c_date = get_index(row, 'DATE')
						c_album = get_index(row, 'ALBUM')
						c_album_artist = get_index(row, 'ALBUMARTIST')
						c_trackno = get_index(row, 'TRACKNO')
						c_increment = get_index(row, 'INCREMENT')

						missing_req = []
						if c_artist == -1:
							missing_req.append('ARTIST')
						if c_track == -1:
							missing_req.append('TRACK')
						if c_date == -1:
							missing_req.append('DATE')
						if len(missing_req) > 0:
							raise Exception(f"Missing column(s): {','.join(missing_req)}")
						
						continue
				
				# Check that this line has the correct number of columns. 
				if len(row) != expected_cols:
					raise Exception(f'Incorrect number of columns found on line {row_num+1}. Expected: {expected_cols}, Found: {len(row)}')
				
				artist = get_val(row, c_artist)
				track = get_val(row, c_track)
				date = get_val(row, c_date)
				album = get_val(row, c_album)
				if album is not None:
					album_artist = get_val(row, c_album_artist, artist)
				else:
					album_artist = None
				track_no = get_val(row, c_trackno)
				increment = int(get_val(row, c_increment, increment))

				if date is not None:
					ts = self.__get_timestamp(date, last_ts)
				elif date is None and ts > 0:
					ts = self.__add_x_minutes(last_ts, increment)
				else:
					raise Exception(f'Unable to get a timestamp for line {row_num+1}')
				
				# Assuming a jump of >= 15 minutes is a new set of tracks
				if (ts-last_ts) >= (15*60):
					curr_batch += 1
					tracks.update({curr_batch: {
						'start': from_timestamp(ts, self.tz),
						'end': from_timestamp(self.__add_x_minutes(ts, increment), self.tz),
						'tracks': []
					}})

				# Creating the scrobble object and adding it to the current batch.
				scrobble = Scrobble(artist, track, ts, album=album,
									album_artist = album_artist, track_no=track_no)
				tracks[curr_batch]['tracks'].append(scrobble)
				tracks[curr_batch]['end'] = from_timestamp(self.__add_x_minutes(ts, increment), self.tz)
				last_ts = ts
		return tracks

	@staticmethod
	def print_summary(tracks):
		def dt_to_str(dt):
			year	= str(dt.year)
			month	= str(dt.month).zfill(2)
			day		= str(dt.day).zfill(2)
			hour	= str(dt.hour).zfill(2)
			minute	= str(dt.minute).zfill(2)
			second	= str(dt.second).zfill(2)

			return f'{year}/{month}/{day} {hour}:{minute}:{second}'

		summaries = []
		max_len = 0
		total_scrobbles = 0
		for ind in tracks.keys():
			group = tracks[ind]
			start = dt_to_str(group['start'])
			end   = dt_to_str(group['end'])
			count = len(group['tracks'])
			summary = f'{start} - {end} | {count} tracks'
			summaries.append(summary)
			max_len = max(max_len, len(summary))
			total_scrobbles += count
		
		header = 'Track Summary'
		pad = max_len - len(header)
		if pad%2 == 0:
			rjust = ljust = int(pad/2)
		else:
			rjust = ljust = int((pad-1)/2)
			rjust += 1
		header = f"{'_'*ljust}{header}{'_'*rjust}"

		print(header)
		for summary in summaries:
			print(summary)
		print(f'Total scrobbles: {total_scrobbles}')

	@staticmethod
	def serialize_scrobbles(tracks):
		scrobbles = []
		for dt in tracks.keys():
			scrobbles += tracks[dt]['tracks']
		return scrobbles