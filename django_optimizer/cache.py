# -*- coding: utf-8 -*-
"""
Cache module containing a definition of a PersistentFileBasedCache
"""
import pickle

from django.core.cache.backends.filebased import FileBasedCache
from django.core.cache.backends.locmem import LocMemCache


class PersistentLocMemCache(LocMemCache):
    """
    A modified version on django's LocMemCache, that skips the code removing existing keys
    """
    def _cull(self):
        pass

    def _has_expired(self, key):
        """
        Method's name is misleading as it's also used to check whether key was added at all
        """
        return self._expire_info.get(key, -1) == -1


class PersistentFileBasedCache(FileBasedCache):
    """
    A modified version on django's FileBasedCache, that skips the code removing existing keys

    Parameters 'timeout', 'max_entries' and 'cull_frequency' passed to constructor won't have any effect

    Do keep in mind that this cache may get really big as it's not limited in size in any way
    """
    def _cull(self):
        pass

    def _is_expired(self, f):
        """
        Confirms that key has not expired
        ``pickle.load(f)`` is mirrored from superclass, lack of it breaks file read afterwards
        """
        pickle.load(f)
        return False
