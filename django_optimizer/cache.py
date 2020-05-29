# -*- coding: utf-8 -*-
"""
Cache module containing a definition of a PersistentFileBasedCache
"""
import pickle

from django.core.cache.backends.filebased import FileBasedCache


class PersistentFileBasedCache(FileBasedCache):
    """
    A modified version on django's FileBasedCache, that skips the code removing existing keys

    Parameters 'timeout', 'max_entries' and 'cull_frequency' passed to constructor won't have any effect

    Do keep in mind that this cache may get really big as it's not limited in size in any way
    """
    def _cull(self):
        """
        Skips removal of keys
        """
        pass

    def _is_expired(self, f):
        """
        Confirms that key has not expired
        ``pickle.load(f)`` is mirrored from superclass, lack of it breaks file read afterwards
        """
        pickle.load(f)
        return False
