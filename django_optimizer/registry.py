# -*- coding: utf-8 -*-
"""
Registry module

Contains a definition of a FieldRegistry - object containing information
about field names required to optimize querysets
"""
import ast
import copy
import csv

from django.utils.module_loading import import_string

from django_optimizer.conf import settings


class Registry(object):
    def __init__(self, cache_settings, initial_value, key_list_id):
        """
        Gets registry wrapping cache object with key management and csv conversion enabled

        :param cache_settings: parameters passed to cache
        :param initial_value: empty value in cache
        :param key_list_id: unique id for key list
        """
        self.cache = self._get_cache(cache_settings)
        self.initial_value = initial_value
        self.key_list_id = key_list_id

    @staticmethod
    def _get_cache(cache_params):
        """
        Instantiates cache object based on settings

        :param cache_params: parameters passed to cache including required 'BACKEND' and 'LOCATION' settings
        :return: cache object for registry
        """
        params = copy.deepcopy(cache_params)
        backend = params.pop('BACKEND')
        location = params.pop('LOCATION', '')
        backend_cls = import_string(backend)
        return backend_cls(location, params)

    def has_key(self, key):
        """
        Checks whether given key has been added before
        
        :param key: key to be checked
        :return: whether key exists in field
        """
        key_list = self.get_keys()
        return key in key_list

    def add_key(self, key):
        """
        Adds a key name to separate cache field

        :param key: key to be added
        """
        key_list = self.get_keys()
        key_list.append(key)
        self.cache.set(self.key_list_id, key_list)

    def remove_key(self, key):
        """
        Removes a key name from cache field

        :param key: key to be removed
        """
        key_list = self.get_keys()
        key_list.remove(key)
        self.cache.set(self.key_list_id, key_list)

    def get_keys(self):
        """
        Gets all names of keys that has been added

        They may be later used on listing all entries or dumping cache to csv
        as most caches don't have a way of getting all pairs

        :return: set of key names
        """
        return self.cache.get(self.key_list_id) or []

    def get(self, key):
        """
        Gets value from cache and returns it

        If cache didn't have value for this location, returns an initial value

        :param key: any object, which str method defines cache key
        :return: value received from registry cache or init value
        """
        return self.cache.get(str(key)) or copy.deepcopy(self.initial_value)

    def set(self, key, modifier=lambda x: None):
        """
        Sets a new value on key based on passed setter function

        Adds a key to key set if corresponding value in cache didn't exist

        :param key: any object, which str method defines cache key
        :param modifier: function to be used with value retrieved from cache, which modifies a value
        :return: value received from cache and modified by setter
        """
        key = str(key)
        value = self.get(key)
        if value == self.initial_value:
            self.add_key(key)
        modifier(value)
        self.cache.set(key, value)
        return value

    @staticmethod
    def row_to_pair(row):
        """
        Converts csv row to cache (k, v) pair

        :param row: list of contents in a csv file row
        :return: key and value pair for cache
        """
        return None, None

    @staticmethod
    def pair_to_row(key, value):
        """
        Converts cache (k, v) pair to csv row

        :param key: cache key
        :param value: value from cache
        :return: list of contents in a row to be added to csv file
        """
        return []

    def from_csv(self, filepath, clear=True):
        """
        Reads file contents from file and initializes registry's cache

        :param filepath: file to read from
        :param clear: whether cache should be cleared before operation
        """
        if clear:
            self.cache.clear()
        with open(filepath) as csv_file:
            reader = csv.reader(csv_file, delimiter=',')
            for row in reader:
                key, val = self.row_to_pair(row)
                self.add_key(key)
                self.cache.set(key, val)

    def to_csv(self, filepath):
        """
        Dumps cache contents to csv file

        :param filepath: file to write to
        """
        with open(filepath, mode='w') as csv_file:
            writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            for key in sorted(self.get_keys()):
                row = self.pair_to_row(key, self.get(key))
                writer.writerow(row)


class FieldRegistry(Registry):
    """
    Registry with a cache for storing field sets used to optimize querysets

    Holds 3 different sets containing names of fields to be passed to select_related(), prefetch_related() and only()
    """
    SELECT = 0
    PREFETCH = 1
    ONLY = 2

    def __init__(self):
        super(FieldRegistry, self).__init__(
            cache_settings=settings.DJANGO_OPTIMIZER_FIELD_REGISTRY,
            initial_value=(set(), set(), set()),
            key_list_id='__field_registry_key_set'
        )

    def add(self, qs_location, index, field):
        """
        Adds new field name to set in cache on given index

        :param qs_location: queryset's ObjectLocation object defining cache key
        :param index: index of a set to append
        :param field: field name to be inserted to one of the sets
        :return: appended tuple from cache
        """
        return self.set(qs_location, lambda x: x[index].add(field))

    @staticmethod
    def row_to_pair(row):
        select, prefetch, only = [ast.literal_eval(r) for r in row[1:]]
        return row[0], (set(select), set(prefetch), set(only))

    @staticmethod
    def pair_to_row(key, value):
        return [key, list(value[0]), list(value[1]), list(value[2])]


class ModelRegistry(Registry):
    def __init__(self):
        super(ModelRegistry, self).__init__(
            cache_settings={
                'BACKEND': 'django_optimizer.cache.PersistentLocMemCache',
                'LOCATION': settings.DJANGO_OPTIMIZER_MODEL_REGISTRY_LOCATION
            },
            initial_value=[],
            key_list_id='__model_registry_key_set'
        )

    def add(self, obj):
        self.set(
            '{module}.{name}'.format(module=obj.__module__, name=obj._meta.model.__name__),
            lambda x: x.append(obj)
        )

    def pop_pair(self, key):
        cache = [(import_string(key), self.get(key))]
        self.remove_key(key)
        self.cache.delete(key)
        return cache

    def pop_all(self):
        cache = [(import_string(key), self.get(key)) for key in self.get_keys()]
        self.cache.clear()
        return cache


field_registry = FieldRegistry()
model_registry = ModelRegistry()
