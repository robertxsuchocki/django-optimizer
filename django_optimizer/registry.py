# -*- coding: utf-8 -*-
import ast
import copy
import csv

from django.utils.module_loading import import_string

from django_optimizer.conf import settings


class QuerySetFieldRegistry:
    """
    Wrapper for a filebased cache for storing field sets used to optimize querysets.

    Holds 3 different sets containing names of fields to be passed to only(), select_related() and prefetch_related().
    """
    SELECT = 0
    PREFETCH = 1
    ONLY = 2

    KEY_SET = '__django_optimizer_key_set'

    def __init__(self):
        """
        Gets PersistentFileBasedCache with field sets (or FileBasedCache with custom options if stated in settings).
        """
        self.cache = self._get_cache()

    def add_key(self, key):
        """
        Adds a key name to separate cache field.

        :param key: key to be added
        """
        key_set = self.get_keys()
        key_set.add(key)
        self.cache.set(self.KEY_SET, key_set)

    def get_keys(self):
        """
        Gets all names of keys that has been added.

        They are later used on saving cache to csv as most caches don't have a way of getting all pairs.

        :return: set of key names
        """
        return self.cache.get(self.KEY_SET) or set()

    def get(self, qs_location):
        """
        Gets value from cache and returns it.

        If cache didn't have this value, initializes it with tuple of 3 empty sets.

        :param qs_location: queryset's ObjectLocation object defining cache key
        :return: tuple of 3 sets of field names
        """
        key = str(qs_location)
        return self.cache.get(key) or self._get_init_value(key)

    def _get_init_value(self, key):
        """
        Sets value of key in cache to initial value, then returns it.

        :param key: key in cache to initialize
        :return: init value
        """
        value = set(), set(), set()
        self.cache.set(key, value)
        self.add_key(key)
        return value

    def _append_tuple(self, qs_location, index, *args):
        """
        Core function to add field names to registry's queryset entry.

        Retrieves value from cache based on location object, appends one set and writes value back.

        :param qs_location: queryset's ObjectLocation object defining cache key
        :param values: set of field names to be inserted to one of the sets
        :param index: index of a set to append
        :return:
        """
        if qs_location:
            key = str(qs_location)
            tup = self.get(key)
            for arg in args:
                tup[index].add(arg)
            self.cache.set(key, tup)

    def set_select(self, qs_location, *args):
        self._append_tuple(qs_location, self.SELECT, *args)

    def set_prefetch(self, qs_location, *args):
        self._append_tuple(qs_location, self.PREFETCH, *args)

    def set_only(self, qs_location, *args):
        self._append_tuple(qs_location, self.ONLY, *args)

    @staticmethod
    def _get_cache():
        params = copy.deepcopy(settings.DJANGO_OPTIMIZER_CACHE)
        backend = params.pop('BACKEND')
        location = params.pop('LOCATION', '')
        backend_cls = import_string(backend)
        return backend_cls(location, params)

    def from_csv(self, filepath, clear=True):
        if clear:
            self.cache.clear()
        with open(filepath) as csv_file:
            reader = csv.reader(csv_file, delimiter=',')
            for row in reader:
                select, prefetch, only = [ast.literal_eval(r) for r in row[1:]]
                self.add_key(row[0])
                self.cache.set(row[0], (set(select), set(prefetch), set(only)))

    def to_csv(self, filepath):
        with open(filepath, mode='w') as csv_file:
            writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            for key in sorted(self.get_keys()):
                tup = self.get(key)
                writer.writerow([key, list(tup[0]), list(tup[1]), list(tup[2])])


field_registry = QuerySetFieldRegistry()
