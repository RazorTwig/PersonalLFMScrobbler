from time import time
import sys
from tomlkit import parse, dumps
from pathlib import Path

def progressbar_batch(it, batch_size=50, prefix="", size=60, out=sys.stdout):
	count = len(it)
	start = time()
	def show(j):
		x = int(size*j/count)
        # time estimate calculation and string
		remaining = ((time() - start) / j) * (count - j)        
		mins, sec = divmod(remaining, 60) # limited to minutes
		time_str = f'{int(mins):02d}:{sec:04.1f}'
		print(f"{prefix}[{u'█'*x}{('.'*(size-x))}] {j}/{count} Est wait {time_str}    ", end='\r', file=out, flush=True)
	for batch, i in loop_batch(it, batch_size, True):
		yield batch
		show(i+1)
		batch = []
	print("", flush=True, file=out)

def progressbar(it, prefix="", size=60, out=sys.stdout):
	for x in progressbar_batch(it, 1, prefix, size, out):
		yield x[0]

def loop_batch(it, batch_size=50, return_index=False):
	batch = []
	for i, item in enumerate(it):
		batch.append(item)
		if (i+1)%batch_size > 0 and (i+1) != len(it):
			continue
		if return_index:
			yield (batch, i)
		else:
			yield batch
		batch = []

def get_configs(section=None, key=None, config_file='config.toml'):
	config_path = Path(config_file)
	if not config_path.exists():
		raise Exception(f'Unable to find config file at {config_path.resolve()}')
	
	with open(config_file, 'r') as f:
		configs = parse(f.read())

	if section is not None:
		configs = configs.get(section, {})
		if key is not None:
			configs = configs.get(key, '')

	return configs

def set_configs(section=None, key=None, val=None, config_file='config.toml'):
	config_path = Path(config_file)
	if not config_path.exists():
		raise Exception(f'Unable to find config file at {config_path.resolve()}')

	with open(config_file, 'r') as f:
		configs = parse(f.read())

	if section is not None:
		if section not in configs:
			configs[section] = {}
		configs[section].update({key: val})
	
	with open(config_file, 'w') as f:
		f.write(dumps(configs))