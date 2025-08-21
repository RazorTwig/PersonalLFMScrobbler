from argparse import ArgumentParser

from utils.reader import Reader
from utils.lfm_api import LastFM
from utils.funcs import set_defaults, get_default

# Setting defaults in case the user removed any necessary ones from the config.toml file.
set_defaults()

parser = ArgumentParser(
	prog='Personal Last.FM Scrobbler',
	description='This program is meant to read a list of tracks from either a txt or csv\nfile and send them to Last.FM (known as \'scrobbling\').'
)

DEFAULT_FILENAME = get_default('FILENAME')
DEFAULT_PROFILE = get_default('PROFILE')
DEFAULT_INC = get_default('INCREMENT')
DEFAULT_SEP = get_default('CSV_SEPARATOR')

parser.add_argument('action', choices=['check', 'login', 'scrobble', 'logout'])
parser.add_argument('-f', '--filename', default=DEFAULT_FILENAME, help=f'Specifies the file to read the scrobbles from. Default: {DEFAULT_FILENAME}')
parser.add_argument('-u','--user', default=DEFAULT_PROFILE, help=f'Specifies the user session to be used from the config.toml file. Default: {DEFAULT_PROFILE}')
parser.add_argument('-i', '--increment', default=DEFAULT_INC, help=f'Specifies the default amount of time between scrobbles in minutes. Default: {DEFAULT_INC}')
parser.add_argument('-s', '--separator', default=DEFAULT_SEP, help=f'Specifies the separator to be used when parsing CSV files. Default: {DEFAULT_SEP}')


def get_tracks(args):
	r = Reader(args.increment, args.separator)
	tracks = r.read(args.filename)
	return tracks


def check(args):
	tracks = get_tracks(args)
	Reader.print_summary(tracks)
	return tracks


def login(user):
	lfm = LastFM(login=False, user=user)
	success, user = lfm.login()
	if success:
		print(f'User {user} logged in.')
	else:
		print(f'Unable to log in user profile {user}.')


def logout(user):
	lfm = LastFM(login=False, user=user)
	success, user = lfm.logout()
	if success:
		print(f'User {user} logged out.')
	else:
		print(f'No user to logout for profile {user}.')	


def scrobble(args):
	lfm = LastFM(user=args.user)
	tracks = check(args)

	scrobbles = Reader.serialize_scrobbles(tracks)
	lfm.scrobble(scrobbles)


if __name__ == '__main__':
	args = parser.parse_args()
	
	if args.action == 'check':
		_ = check(args)
	elif args.action == 'login':
		login(args.user)
	elif args.action == 'logout':
		logout(args.user)
	elif args.action == 'scrobble':
		scrobble(args)