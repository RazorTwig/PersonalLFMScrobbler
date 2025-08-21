import webbrowser
import requests
from time import sleep, time
from hashlib import md5
from datetime import datetime
from pathlib import Path

from utils.funcs import get_configs, set_configs, progressbar_batch, get_default
from utils.exceptions import APIResponseError

# LastFM Statuses
LFM_STATUS_NO_ERROR = 0
LFM_STATUS_INVALID_SERVICE = 2
LFM_STATUS_INVALID_METHOD = 3
LFM_STATUS_AUTHENTICATION_FAILED = 4
LFM_STATUS_INVALID_FORMAT = 5
LFM_STATUS_INVALID_PARAMS = 6
LFM_STATUS_INVALID_RESOURCE = 7
LFM_STATUS_OPERATION_FAILED = 8
LFM_STATUS_INVALID_SESSION_KEY = 9
LFM_STATUS_INVALID_API_KEY = 10
LFM_STATUS_SERVICE_OFFLINE = 11
LFM_STATUS_INVALID_SIGANTURE = 13
LFM_STATUS_TOKEN_NOT_AUTHORIZED = 14
LFM_STATUS_TEMPORARY_ERROR = 16
LFM_STATUS_SUSPENDED_API_KEY = 26
LFM_STATUS_RATE_LIMIT_EXCEEDED = 29

# Some statuses can be retried, others are a straight failure.
LFM_STATUS_RETRY = [
	LFM_STATUS_SERVICE_OFFLINE,
	LFM_STATUS_TOKEN_NOT_AUTHORIZED,
	LFM_STATUS_TEMPORARY_ERROR
]
LFM_STATUS_FAILURE = [
	LFM_STATUS_OPERATION_FAILED,
	LFM_STATUS_INVALID_SERVICE,
	LFM_STATUS_INVALID_METHOD,
	LFM_STATUS_AUTHENTICATION_FAILED,
	LFM_STATUS_INVALID_FORMAT,
	LFM_STATUS_INVALID_PARAMS,
	LFM_STATUS_INVALID_RESOURCE,
	LFM_STATUS_INVALID_API_KEY,
	LFM_STATUS_INVALID_SIGANTURE,
	LFM_STATUS_INVALID_SESSION_KEY,
	LFM_STATUS_SUSPENDED_API_KEY,
	LFM_STATUS_RATE_LIMIT_EXCEEDED
]

class LastFM:
	__AUTH_URL	 = 'http://www.last.fm/api/auth/'
	__API_URL	 = 'http://ws.audioscrobbler.com/2.0/'
	__API_KEY	 = None
	__API_SECRET = None

	__API_DELAY		  = 1
	__API_DELAY_STEPS = 0.4
	__LAST_REQUEST_AT = -1

	def __init__(self, config_file=None, api_key=None, api_secret=None, login=True, user=get_default('PROFILE')):
		if api_key is not None and api_secret is not None:
			self.__API_KEY = api_key
			self.__API_SECRET = api_secret
		else:
			if config_file is not None:
				configs = get_configs('API', config_file=config_file)
			else:
				configs = get_configs('API')
			
			if 'API_KEY' in configs and 'API_SECRET' in configs:
				self.__API_KEY = configs['API_KEY']
				self.__API_SECRET = configs['API_SECRET']
			else:
				raise Exception('Unable to find API settings in config.toml')

		if self.__API_KEY is None:
			raise Exception('LastFM API Key cannot be empty.')
		
		self.__SESSION_NAME = user
		

		session = get_configs(self.__SESSION_NAME)
		if 'SESSION_KEY' in session and session['SESSION_KEY'] != '':
			self.__SESSION = session
		elif login:
			resp = input('No saved user sessions found. Would you like to login now?\n')
			if resp.upper() == 'Y':
				success, user = self.login()
				if success:
					print(f'User {user} logged in.')
				else:
					print(f'Unable to log in user profile {user}.')
			else:
				self.__SESSION = None
		else:
			self.__SESSION = None

	@property
	def is_logged_in(self):
		return self.__SESSION != None
	
	@property
	def last_call_time(self):
		return self.__LAST_REQUEST_AT

	@property
	def api_delay_time(self):
		return self.__API_DELAY
	
	@property
	def api_delay_wait(self):
		return self.__API_DELAY_STEPS
	
	@property
	def user(self):
		if self.__SESSION is not None:
			return self.__SESSION['USER']
		else:
			return 'No user logged in.'
	
	def set_new_call_time(self, ts):
		self.__LAST_REQUEST_AT = ts

	# decorator for checking if the user is logged in before doing certain actions
	def __check_logged_in():
		def deco(func):
			def wrapper(*args, **kwargs):
				self = args[0]
				if not self.is_logged_in:
					raise Exception('A valid user session is needed for this function.')
				else:
					func(*args, **kwargs)
			return wrapper
		return deco
	
	# decorator for rate limiting certain actions
	def __rate_limit():
		def deco(func):
			def wrapper(*args, **kwargs):
				self = args[0]
				curr_time = time()
				while(curr_time < (self.last_call_time + self.api_delay_time)):
					sleep(self.api_delay_wait)
					curr_time = time()
				val = func(*args, **kwargs)
				self.set_new_call_time(curr_time)
				return val
			return wrapper
		return deco
	
	# decorator for handling the return value of requests
	def __handle_req_error(timeout=180, retry=1, silent=False):
		def deco(function):
			def wrapper(*args, **kwargs):
				retries = 0
				while retries < retry:
					status_code, resp_json, ret_val = function(*args, **kwargs)
					if status_code == 200:
						return ret_val
					elif resp_json['error'] in LFM_STATUS_FAILURE:
						raise APIResponseError(resp_json['error'], resp_json['message'])
					elif resp_json['error'] in LFM_STATUS_RETRY:
						retries += 1
						if not silent:
							print(f'An error ({resp_json["error"]}) occurred during the last request. Retrying... ({retries} of {retry})')
						sleep(timeout)
					else:
						raise APIResponseError(resp_json['error'], resp_json['message'])
				raise APIResponseError(resp_json['error'], resp_json['message'])
			return wrapper
		return deco
	
	# Creates a signature. Necessary for authenticated requests.
	def __create_signature(self, params):
		sig = ''
		sorted_keys = sorted(list(params.keys()))

		for key in sorted_keys:
			sig += f'{key}{params[key]}'
		
		sig += self.__API_SECRET
		md5_sig = md5(sig.encode())
		return md5_sig.hexdigest()
	
	@__rate_limit()
	def __send_get_request(self, params={}):
		url = self.__API_URL
		params['format'] = 'json'
		resp = requests.get(url, params)

		status_code = resp.status_code
		msg = resp.json()
		return (status_code, msg)

	@__rate_limit()
	def __send_post_request(self, params={}):
		url = self.__API_URL
		params['format'] = 'json'
		resp = requests.post(url, params)

		status_code = resp.status_code
		msg = resp.json()
		return (status_code, msg)

	@__handle_req_error(0, 1)
	def __get_login_token(self):
		params = {
			'method': 'auth.getToken',
			'api_key': self.__API_KEY
		}
		status_code, msg = self.__send_get_request(params)
		return (status_code, msg, msg.get('token'))
	
	def __get_session_from_token(self, token):
		auth_url = self.__AUTH_URL
		api_key = self.__API_KEY
		webbrowser.open_new_tab(f'{auth_url}?api_key={api_key}&token={token}')
		return self.__get_session_auth_response(token)

	@__handle_req_error(4, 15, True)
	def __get_session_auth_response(self, token):
		params = {
			'method': 'auth.getSession',
			'api_key': self.__API_KEY,
			'token': token
		}
		params['api_sig'] = self.__create_signature(params)
		status_code, msg = self.__send_get_request(params)
		ret_val = None
		if 'session' in msg:
			ret_val = (msg['session'].get('key'), msg['session'].get('name'))
		return (status_code, msg, ret_val)

	def login(self):
		try:
			token = self.__get_login_token()
			session_key, user = self.__get_session_from_token(token)
			self.__SESSION = {
				'SESSION_KEY': session_key,
				'USER': user
			}
			set_configs(self.__SESSION_NAME, 'SESSION_KEY', session_key)
			set_configs(self.__SESSION_NAME, 'USER', user)
			return (True, user)
		except APIResponseError:
			return (False, self.__SESSION_NAME)

	def logout(self):
		ret_val = (False, self.__SESSION_NAME)
		if self.__SESSION is not None:
			user = self.user
			self.__SESSION = None
			set_configs(self.__SESSION_NAME, 'SESSION_KEY', '')
			set_configs(self.__SESSION_NAME, 'USER', '')
			ret_val = (True, user)
		return ret_val

	@__handle_req_error(0, 1)
	def __scrobble(self, scrobbles):
		params = {
			'method': 'track.scrobble',
			'api_key': self.__API_KEY,
			'sk': self.__SESSION['SESSION_KEY']
		}

		ind = sorted([str(x) for x in range(0, len(scrobbles))])
		ind_int = [int(x) for x in ind]
		for x in range(0, len(ind)):
			params.update(scrobbles[ind_int[x]].get_api_params(ind[x]))
		params['api_sig'] = self.__create_signature(params)

		status_code, msg = self.__send_post_request(params)
		ret_val = []
		for x in msg['scrobbles']['scrobble']:
			scrobble = {
				'status': 'Accepted',
				'track': f"{x['artist']['#text']} - {x['track']['#text']}",
				'timestamp': x['timestamp'],
			}
			
			if x['ignoredMessage']['code'] != '0':
				scrobble.update({
					'status': 'Ignored',
					'ignore_code': x['ignoredMessage']['code'],
					'ignore_text': x['ignoredMessage']['#text']
				})
			
			ret_val.append(scrobble)

		return (status_code, msg, ret_val)
	
	@__check_logged_in()
	def scrobble(self, scrobbles, num_per_batch=50):
		# Max amount allowed at a time by the LastFM API
		if num_per_batch > 50:
			num_per_batch = 50

		curr_date = datetime.fromtimestamp(time())
		log_file_name = f'scrob_{curr_date.strftime("%y%m%d%H%M%S")}.log'
		log_folder = Path('logs')
		if not log_folder.exists():
			log_folder.mkdir()
		log_file_path = Path('logs') / log_file_name

		accepted = 0
		ignored = 0

		print(f'Scrobbling {len(scrobbles)} tracks to user {self.user}')
		with open(log_file_path, 'w', encoding='UTF-8') as log_file:
			log_file.write(f'Scrobbling {len(scrobbles)} tracks to user {self.user}')
			for batch in progressbar_batch(scrobbles, num_per_batch):
				resp = self.__scrobble(batch)
				for scrobble in resp:
					log_file.write(f"{scrobble['status']}: {scrobble['track']} ({scrobble['timestamp']})\n")
					if scrobble['status'] == 'Accepted':
						accepted += 1
					elif scrobble['status'] == 'Ignored':
						ignored += 1
						log_file.write(f"\tIgnore Code: {scrobble['ignore_code']}\n")
						log_file.write(f"\tIgnore Message: {scrobble['ignore_text']}\n")
			log_file.write(f'Accepted: {accepted}\n')
			log_file.write(f'Ignored: {ignored}\n')