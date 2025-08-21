class LFMObj():
	def __init__(self, text='', mbid=None, text_alt='', mbid_alt=''):
		self.text = text
		self.mbid = mbid
		self.text_alt = text_alt
		self.mbid_alt = mbid_alt

	@property
	def __text_disp(self):
		text = 'text'
		if self.text_alt != '':
			text = self.text_alt
		return text

	@property
	def __mbid_disp(self):
		mbid = 'mbid'
		if self.mbid_alt != '':
			mbid = self.mbid_alt
		return mbid
	
	def __iter__(self):
		yield self.__text_disp, self.text
		yield self.__mbid_disp, self.mbid

	def __str__(self):
		return str(dict(self))
		

class Artist(LFMObj):
	def __init__(self, text='', mbid=None):
		super().__init__(text, mbid, 'artist')

	@property
	def artist(self):
		return self.text


class Album(LFMObj):
	def __init__(self, text='', mbid=None, album_artist=None):
		super().__init__(text, mbid, 'album')
		self.album_artist = album_artist

	def __iter__(self):
		if self.album_artist != '':
			yield 'artist', self.album_artist
		for k, v in  super().__iter__():
			yield k, v

	@property
	def album(self):
		return self.text

	
class Track(LFMObj):
	def __init__(self, name='', mbid=None, artist=None, album=None, url=''):
		super().__init__(name, mbid, 'name')
		self.url = url

		def get_obj(cls, param):
			if param == None:
				return None
			if type(param) == cls:
				return param
			elif type(param) == dict:
				return cls(**param)
			elif type(param) == str:
				return cls(param)
			else:
				return cls(str(param))

		self.track_artist = get_obj(Artist, artist)
		self.track_album = get_obj(Album, album)

	def __iter__(self):
		yield 'artist', dict(self.track_artist) if self.track_artist is not None else None
		yield 'name', self.text
		yield 'album', dict(self.track_album) if self.track_album is not None else None
		yield 'mbid', self.mbid
		yield 'url', self.url


class Scrobble(Track):
	def __init__(self, artist='', track='', timestamp=0, album=None, track_no=-1, mbid=None, album_artist=None, duration=-1):
		if artist == '':
			raise Exception(f'Artist name cannot be empty for a scrobble!')
		if track == '':
			raise Exception(f'Track name cannot be empty for a scrobble!')
		
		if album_artist != '' and album_artist is not None:
			if type(album) == Album and album.album_artist != album_artist:
				album.album_artist = album_artist
			elif type(album) == dict:
				album.update({'album_artist': album_artist})
			else:
				album = {'text': str(album), 'album_artist': album_artist}

		super().__init__(track, mbid, artist, album)
		self.timestamp = timestamp
		self.track_no = track_no
		self.duration = duration

	@property
	def artist(self):
		return self.track_artist.artist
	
	@property
	def album(self):
		return self.track_album.album
	
	@property
	def album_artist(self):
		return self.track_album.album_artist
	
	def __iter__(self):
		for k, v in  super().__iter__():
			yield k, v
		yield 'timestamp', self.timestamp
	
	def get_api_params(self, ind):
		params = {}
		
		# Artist (required)
		params[f'artist[{ind}]'] = self.track_artist.artist

		# Track (required)
		params[f'track[{ind}]'] = self.text

		# Timestamp (required)
		params[f'timestamp[{ind}]'] = self.timestamp

		# Album
		if self.track_album != None:
			params[f'album[{ind}]'] = self.track_album.album

		# Track Number
		if self.track_no != -1:
			params[f'trackNumber[{ind}]'] = self.track_no

		# MusicBrainz Track ID
		if self.mbid != None:
			params[f'mbid[{ind}]'] = self.mbid

		# Album Artist
		if self.track_album != None:
			params[f'albumArtist[{ind}]'] = self.track_album.album_artist

		# Duration
		if self.duration != -1:
			params[f'duration[{ind}]'] = self.duration

		return params