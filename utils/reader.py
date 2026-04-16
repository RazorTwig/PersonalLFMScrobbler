from pathlib import Path
import re
from pendulum import now, local, from_timestamp
import requests
from bs4 import BeautifulSoup

from utils.lfm_objects import Scrobble
from utils.funcs import get_path_obj, get_configs

class timer:
	date_re = r'([0-9\/]+) ([0-9:]+)'
	time_re = r'([0-9:]+)'
	tz = now().tz
	curr_year = str(now().year)
	min_age = int(now().subtract(days=14).timestamp())
	ts = -1
	last_ts = -1
	increment = -1

	@staticmethod
	def set_increment(increment):
		timer.increment = increment

	@staticmethod
	def set_ts(dt):
		try:
			dt, tm = re.match(timer.date_re, dt).groups()
		except AttributeError:
			tm = re.match(timer.time_re, dt)
			if tm is None:
				raise Exception('Unable to parse timestamp')
			if timer.ts != -1:
				curr_dt = from_timestamp(timer.ts)
			else:
				curr_dt = now()
				
			tm = tm.groups()[0]
			dt = f'{curr_dt.month}/{curr_dt.day}'

		# Date and Time are padded with the default values for year and second
		# Either the values are split into year/second and the defaults go to dummy
		# and they're thrown away or the defaults are split into year/second and 
		# dummy is an empty list that's thrown away
		month, day, year, *dummy = f'{dt}/{timer.curr_year}'.split('/')
		hour, minute, second, *dummy = f'{tm}:00'.split(':')

		start_dt = local(int(year), int(month), int(day), hour=int(hour), minute=int(minute), second=int(second))
		new_ts = int(start_dt.timestamp())
		
		if new_ts < timer.min_age:
			raise Exception(f'Date {from_timestamp(new_ts, timer.tz)} is over 14 days ago and will not be accepted by Last.FM.')
		
		timer.last_ts = timer.ts
		timer.ts = new_ts
		return new_ts

	@staticmethod
	def increment_ts():
		if timer.ts == -1:
			raise Exception('Timestamp has not been set yet!')
		if timer.increment == -1:
			raise Exception('Increment has not been set yet!')
		timer.last_ts = timer.ts
		timer.ts += timer.increment*60
		return timer.ts

	@staticmethod
	def from_timestamp(ts=None):
		if ts is None:
			ts = timer.ts
		return from_timestamp(ts, timer.tz)

class Reader:
	implemented_ext = ['.txt', '.csv']

	def __init__(self, increment, csv_separator):
		timer.set_increment(increment)
		self.csv_separator = csv_separator
	
	class __scrobbleBatch:
		def __init__(self):
			self.scrobbles = []

		def __getitem__(self, item):
			return self.scrobbles[item]
		
		@property
		def start(self):
			if len(self.scrobbles) == 0:
				return None
			else:
				return from_timestamp(self.scrobbles[0].timestamp, timer.tz)

		@property
		def end(self):
			if len(self.scrobbles) == 0:
				return None
			else:
				return from_timestamp(self.scrobbles[-1].timestamp, timer.tz)
			
		def add_scrobble(self, scrobble):
			self.scrobbles.append(scrobble)

		def add_scrobbles(self, scrobbles):
			self.scrobbles += scrobbles
	
	def read(self, fname):
		fpath = get_path_obj(fname)

		if fpath.suffix not in self.implemented_ext:
			raise Exception(f'Reader not yet implemented for {fpath.suffix} files.')
		
		if fpath.suffix.lower() == '.txt':
			return self.__txt(fpath)
		elif fpath.suffix.lower() == '.csv':
			return self.__csv(fpath)

	def __txt(self, fpath):
		scrobble_batches = []
		current_batch = None
		album = None
		album_artist = None

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
					timer.set_ts(command[1])
					current_batch = self.__scrobbleBatch()
					scrobble_batches.append(current_batch)
				elif command[0] == '!URL':
					# Attempt to get a tracklist from 1001Tracklists by searching it for the URL provided
					liveset_url = command[1]
					current_batch.add_scrobbles(self.__scrape_tracklist(liveset_url))
					# current_batch.add_scrobbles(self.__scrape_tracklist_test())
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
							# If this is in an album, default to the Album Artist and rerun the splits
							if album_artist is not None:
								line = f'{album_artist} - {line}'
								splits = find_dashes(line)
								continue

							# No Album Artist set, ask the user what to do
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
					track['timestamp'] = timer.ts
					if album is not None:
						track.update({
										'album': album,
										'albumArtist': album_artist	
									})
					scrobble = Scrobble(track['artist'], track['track'], timer.ts,
						 				album=track.get('album'),
										album_artist = track.get('albumArtist'))
					current_batch.add_scrobble(scrobble)
					timer.increment_ts()
		return scrobble_batches

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
			scrobble_batches = []
			current_batch = None
			vals = csv.reader(csvfile, delimiter=self.csv_separator, skipinitialspace=True)
			firstline = True

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
				timer.set_increment(int(get_val(row, c_increment, timer.increment)))

				if date is not None:
					timer.set_ts(date)
				elif date is None and timer.ts > 0:
					timer.increment_ts()
				else:
					raise Exception(f'Unable to get a timestamp for line {row_num+1}')
				
				# Assuming a jump of >= 15 minutes is a new set of tracks
				if (timer.ts-timer.last_ts) >= (15*60):
					current_batch = self.__scrobbleBatch()
					scrobble_batches.append(current_batch)

				# Creating the scrobble object and adding it to the current batch.
				scrobble = Scrobble(artist, track, timer.ts, album=album,
									album_artist = album_artist, track_no=track_no)
				current_batch.add_scrobble(scrobble)
		return scrobble_batches

	def __scrape_tracklist(self, liveset_url):
		scrobbles = []
		headers = get_configs("1001TL_HEADERS")
		params = {
		'p': liveset_url,
		'noIDFieldCheck': 'true',
		'fixedMode': 'true',
		'sf': 'p',
		'acc': 'oss62eea'
		}

		def translate_url(tracklist_url):
			chars_to_remove = [',']
			for char in chars_to_remove:
				tracklist_url = tracklist_url.replace(char, '')
				tracklist_url = tracklist_url.replace(' ', '-').lower()
			return tracklist_url

		search_url = 'https://www.1001tracklists.com/ajax/search_tracklist.php'
		search_results = requests.get(search_url, params=params, headers=headers)
		if search_results.status_code != 200:
			raise Exception(f'Unable to search 1001Tracklists for URL {liveset_url}. Status code: {search_results.status_code}')
		else:
			tl_results = search_results.json()
			tl_info = tl_results['data'][0] if len(tl_results['data']) > 0 else None
			if tl_info is None:
				raise Exception(f'No tracklist found on 1001Tracklists for URL {liveset_url}.')
			else:
				tracklist_url_template = 'https://www.1001tracklists.com/tracklist/@id/@url.html'
				tracklist_url = tracklist_url_template.replace('@id', tl_info['properties']['id_unique']).replace('@url', translate_url(tl_info['properties']['url_name']))
				tl_html = requests.get(tracklist_url, headers=headers)
				if tl_html.status_code != 200:
					raise Exception(f'Unable to get tracklist page from 1001Tracklists for URL {liveset_url}. Status code: {tl_html.status_code}')
				else:
					tl_soup = BeautifulSoup(tl_html.content, 'html.parser')
					scrobbles = self.parse_soup(tl_soup)
		return scrobbles

	def parse_soup(self, soup):
		tracks = []
		scrobbles = []

		def validate_track(track):
			if track.startswith('ID - ') or track.endswith(' - ID'):
				return False
			return True
		
		def track_edits(track):
			# I prefer 'feat.' to 'ft.'
			track = track.replace(' ft. ', ' feat. ')

			# Generally like to remove that an acappella was used
			track = track.replace(' (Acappella)', '')

			# Sometimes, they come through with weird, non-breaking spaces
			track = track.replace(' ', ' ').replace(' ', ' ')

			# Niche, but 'TNT' doesn't need to be 'TNT aka Technoboy 'N' Tuneboy
			track = track.replace(" aka Technoboy 'N' Tuneboy", '')

			return track

		for track in soup.find_all('div', class_='tlpTog'):
			track_tag = track.find('meta', itemprop='name')
			if track_tag:
				track_text = track_tag['content']
				if validate_track(track_text):
					tracks.append(track_edits(track_text))
		
		if len(tracks) > 0:
			temp_fname = Path('tmp_1001.txt')
			with open(temp_fname, 'w', encoding='utf-8') as temp_file:
				temp_file.write(f'!DATE {timer.from_timestamp().strftime('%m/%d %H:%M')}\n')
				for track in tracks:
					temp_file.write(f'{track}\n')
			scrobble_batch = self.__txt(temp_fname)
			scrobbles = scrobble_batch[0].scrobbles
			temp_fname.unlink()

		return scrobbles



	@staticmethod
	def print_summary(scrobble_batches):
		summaries = []
		max_len = 0
		total_scrobbles = 0
		for batch in scrobble_batches:
			start = batch.start.strftime('%Y/%m/%d %H:%M:%S')
			end   = batch.end.strftime('%Y/%m/%d %H:%M:%S')
			count = len(batch.scrobbles)
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
