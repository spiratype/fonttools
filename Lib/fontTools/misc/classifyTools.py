""" fontTools.misc.classifyTools.py -- tools for classifying things.
"""

from __future__ import print_function, absolute_import
from fontTools.misc.py23 import *

class Classifier:

	"""
	Main Classifier object, used to classify things into similar sets.
	"""

	def __init__(self, sorted=True):

		self._things = set() # set of all things known so far
		self._sets = [] # list of class sets produced so far
		self._mapping = {} # map from things to their class set
		self._dirty = False
		self._sorted = sorted

	def add(self, set_of_things):
		"""
		Add a set to the classifier.  Any iterable is accepted.
		"""
		if not set_of_things:
			return;

		self._dirty = True

		things, sets, mapping = self._things, self._sets, self._mapping

		s = set(set_of_things)
		intersection = s.intersection(things) # existing things
		s.difference_update(intersection) # new things
		difference = s
		del s

		# Add new class for new things
		if difference:
			things.update(difference)
			sets.append(difference)
			for thing in difference:
				mapping[thing] = difference
		del difference

		while intersection:
			# Take one item and process the old class it belongs to
			old_class = mapping[next(iter(intersection))]
			old_class_intersection = old_class.intersection(intersection)

			# Update old class to remove items from new set
			old_class.difference_update(old_class_intersection)

			# Remove processed items from todo list
			intersection.difference_update(old_class_intersection)

			# Add new class for the intersection with old class
			sets.append(old_class_intersection)
			for thing in old_class_intersection:
				mapping[thing] = old_class_intersection
			del old_class_intersection

	def update(self, list_of_sets):
		"""
		Add a a list of sets to the classifier.  Any iterable of iterables is accepted.
		"""
		for s in list_of_sets:
			self.add(s)

	def _process(self):
		if not self._dirty:
			return

		# Do any deferred processing
		sets = self._sets
		self._sets = [s for s in sets if s]

		if self._sorted:
			self._sets = sorted(self._sets, key=lambda s: (-len(s), s))

		self._dirty = False

	# Output methods

	def getThings(self):
		"""Returns the set of all things known so far.

		The return value belongs to the Classifier object and should NOT
		be modified while the classifier is still in use.
		"""
		self._process()
		return self._things

	def getMapping(self):
		"""Returns the mapping from things to their class set.

		The return value belongs to the Classifier object and should NOT
		be modified while the classifier is still in use.
		"""
		self._process()
		return self._mapping

	def getClasses(self):
		"""Returns the list of class sets.

		The return value belongs to the Classifier object and should NOT
		be modified while the classifier is still in use.
		"""
		self._process()
		return self._sets


def classify(list_of_sets, sorted=True):
	"""
	Takes a iterable of iterables (list of sets from here on; but any
	iterable works.), and returns the smallest list of sets such that
	each set, is either a subset, or is disjoint from, each of the input
	sets.

	In other words, this function classifies all the things present in
	any of the input sets, into similar classes, based on which sets
	things are a member of.

	If sorted=True, return class sets are sorted by decreasing size and
	their natural sort order within each class size.  Otherwise, class
	sets are returned in the order that they were identified, which is
	generally not significant.

	>>> classify([])
	([], {})
	>>> classify([[]])
	([], {})
	>>> classify([[], []])
	([], {})
	>>> classify([[1]])
	([set([1])], {1: set([1])})
	>>> classify([[1,2]])
	([set([1, 2])], {1: set([1, 2]), 2: set([1, 2])})
	>>> classify([[1],[2]])
	([set([1]), set([2])], {1: set([1]), 2: set([2])})
	>>> classify([[1,2],[2]])
	([set([1]), set([2])], {1: set([1]), 2: set([2])})
	>>> classify([[1,2],[2,4]])
	([set([1]), set([4]), set([2])], {1: set([1]), 2: set([2]), 4: set([4])})
	>>> classify([[1,2],[2,4,5]])
	([set([4, 5]), set([1]), set([2])], {1: set([1]), 2: set([2]), 4: set([4, 5]), 5: set([4, 5])})
	>>> classify([[1,2],[2,4,5]], sorted=False)
	([set([1]), set([4, 5]), set([2])], {1: set([1]), 2: set([2]), 4: set([4, 5]), 5: set([4, 5])})
	>>> classify([[1,2,9],[2,4,5]], sorted=False)
	([set([1, 9]), set([4, 5]), set([2])], {1: set([1, 9]), 2: set([2]), 4: set([4, 5]), 5: set([4, 5]), 9: set([1, 9])})
	>>> classify([[1,2,9,15],[2,4,5]], sorted=False)
	([set([1, 15, 9]), set([4, 5]), set([2])], {1: set([1, 15, 9]), 2: set([2]), 4: set([4, 5]), 5: set([4, 5]), 9: set([1, 15, 9]), 15: set([1, 15, 9])})
	>>> classify([[1,2,9,15],[2,4,5],[15,5]], sorted=False)
	([set([1, 9]), set([4]), set([2]), set([5]), set([15])], {1: set([1, 9]), 2: set([2]), 4: set([4]), 5: set([5]), 9: set([1, 9]), 15: set([15])})
	"""
	classifier = Classifier(sorted=True)
	classifier.update(list_of_sets)
	return classifier.getClasses(), classifier.getMapping()


if __name__ == "__main__":
	import doctest
	sys.exit(doctest.testmod(optionflags=doctest.ELLIPSIS).failed)