# -*- coding: utf-8 -*-
from django.core.cache.backends.filebased import FileBasedCache

from django_optimizer.cache import PersistentFileBasedCache
from django_optimizer.conf import settings


class QuerySetFieldRegistry:
    """
    Wrapper for a filebased cache for storing field lists used to optimize querysets.

    Holds 3 different lists containing names of fields to be passed to only(), select_related() and prefetch_related().
    """
    ONLY = 0
    SELECT = 1
    PREFETCH = 2

    def __init__(self):
        """
        Gets PersistentFileBasedCache with field lists (or FileBasedCache with custom options if stated in settings).
        """
        self.cache = self._get_cache()

    def get(self, qs_location):
        """
        Gets value from cache and returns it.

        If cache didn't have this value, initializes it with tuple of 3 empty lists.

        :param qs_location: QuerySetLocation object defining cache key
        :return: tuple of 3 lists of field names
        """
        key = str(qs_location)
        return self._get_init_value(key)
        # return self.cache.get(key) or self._get_init_value(key)

    def _get_init_value(self, key):
        """
        Sets value of key in cache to initial value, then returns it.

        :param key: key in cache to initialize
        :return: init value
        """
        value = [], [], []
        self.cache.set(key, value)
        return value

    def _append_tuple(self, qs_location, value, index):
        """
        Core function to add field names to registry's queryset entry.

        Retrieves value from cache based on location object, appends one list and writes value back.

        :param qs_location: QuerySetLocation object defining cache key
        :param value: field name to be inserted to one of the lists
        :param index: index of a list to append
        :return:
        """
        key = str(qs_location)
        tup = self.cache.get(key)
        tup[index].append(value)
        self.cache.set(key, tup)

    def set_only(self, qs_location, value):
        self._append_tuple(qs_location, value, self.ONLY)

    def set_select(self, qs_location, value):
        self._append_tuple(qs_location, value, self.SELECT)

    def set_prefetch(self, qs_location, value):
        self._append_tuple(qs_location, value, self.PREFETCH)

    @staticmethod
    def _get_cache():
        cache_class = PersistentFileBasedCache if settings.OPTIMIZER_CACHE_PERSISTENT else FileBasedCache
        return cache_class(settings.OPTIMIZER_CACHE_LOCATION, settings.OPTIMIZER_CACHE_PARAMS)


field_registry = QuerySetFieldRegistry()
