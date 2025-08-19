class APIResponseError(Exception):
	def __init__(self, error_no, details):
		self.error_no = error_no
		self.details = details

	def __str__(self):
		return f'{self.error_no}: {self.details}'