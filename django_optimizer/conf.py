# -*- coding: utf-8 -*-
import os

import django


class AppSettings:
    """
    Container for settings exclusive for an app, with possibility to replace any in project settings.
    """
    def __getattribute__(self, item):
        try:
            return getattr(django.conf.settings, item)
        except AttributeError:
            return super(AppSettings, self).__getattribute__(item)


# TODO allow bigger customization (e.g. providing own caching class, which is not FileBasedCache)
class DjangoOptimizerSettings(AppSettings):
    OPTIMIZER_CACHE_LOCATION = os.path.join(django.conf.settings.BASE_DIR, '.django-optimizer-cache')
    """
    Location for a file-based cache with tuples of fields gathered and used to optimize queries.
    
    Can be both relative and absolute path.

    Defaults to ``os.path.join(django.conf.settings.BASE_DIR, '.django-optimizer-cache')``.
    """

    OPTIMIZER_CACHE_PERSISTENT = True
    """
    Whether a field cache should be persistent or not.
    
    If it's persistent, then cache is a django FileBasedCache, but with no-ops for functions clearing any keys in cache.
    Otherwise it's just a django FileBasedCache, which can then be modified with ``OPTIMIZER_CACHE_PARAMS``
    
    Created to allow FileBased cache usage, but in most cases should not be changed, 
    as optimizer shouldn't drop any entries.
    """

    OPTIMIZER_CACHE_PARAMS = {}
    """
    Parameters passed to field cache.
    
    Note that if ``OPTIMIZER_CACHE_PERSISTENT == True``, then 'timeout', 'max_entries' and 
    'cull_frequency' won't have effect.
    """


settings = DjangoOptimizerSettings()
