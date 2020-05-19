# -*- coding: utf-8 -*-
import os

import django


class DjangoOptimizerSettings(object):
    """
    Container for settings exclusive for an app, with possibility to replace any in project settings.
    """
    def __getattribute__(self, item):
        try:
            return getattr(django.conf.settings, item)
        except AttributeError:
            return super(DjangoOptimizerSettings, self).__getattribute__(item)

    OPTIMIZER_CACHE = {
        'BACKEND': 'django_optimizer.cache.PersistentFileBasedCache',
        'LOCATION': os.path.join(django.conf.settings.BASE_DIR, '.django-optimizer-cache')
    }
    """
    Cache to be used in field registry (which contains tuples of fields gathered and used to optimize queries).
    
    Defaults to PersistentFileBasedCache (FileBasedCache, but with no-ops for functions clearing any keys in cache).
    Its' default path is equal to ``os.path.join(django.conf.settings.BASE_DIR, '.django-optimizer-cache')``.
    
    Keep in mind that cache shouldn't be eager to remove any entries contained, as they will be reappearing
    and overwriting constantly. Ideally should disable any overwriting.
    
    If performance issues occur, then it should be dropped in favor of manual in-code optimization (at least partially).
    """


settings = DjangoOptimizerSettings()
