# -*- coding: utf-8 -*-
"""
Conf module containing app settings
"""
import os

import django


class DjangoOptimizerSettings(object):
    """
    Container for settings exclusive for an app, with possibility to replace any in project settings
    """
    def __getattribute__(self, item):
        try:
            return getattr(django.conf.settings, item)
        except AttributeError:
            return super(DjangoOptimizerSettings, self).__getattribute__(item)

    DJANGO_OPTIMIZER_FIELD_REGISTRY = {
        'BACKEND': 'django_optimizer.cache.PersistentFileBasedCache',
        'LOCATION': os.path.join(django.conf.settings.BASE_DIR, '.django_optimizer_field_registry')
    }
    """
    Cache to be used in field registry (which contains tuples of fields gathered and used to optimize queries)
    
    Defaults to PersistentFileBasedCache (FileBasedCache, but with no-ops for functions clearing any keys in cache)
    Its' default path is equal to ``os.path.join(django.conf.settings.BASE_DIR, '.django_optimizer_field_registry')``
    
    Keep in mind that cache shouldn't be eager to remove any entries contained, as they will be reappearing
    and overwriting constantly. Ideally should disable any overwriting
    
    If performance issues occur, then it should be dropped in favor of manual in-code optimization (at least partially)
    """

    DJANGO_OPTIMIZER_MODEL_REGISTRY_LOCATION = '__django_optimizer_model_registry'
    """
    Name of a PersistentLocMemCache holding objects to be created after deferred_atomic block
    """

    DJANGO_OPTIMIZER_DISABLE_LOGGING = False
    """
    Whether model logging should be disabled
    
    Might be used to disable this app completely (with `DJANGO_OPTIMIZER_DISABLE_OPTIMIZATION`) or in a state
    where all fields have been gathered in a cache and overhead related with enabling object logging is unwanted
    """

    DJANGO_OPTIMIZER_DISABLE_OPTIMIZATION = False
    """
    Whether queryset optimization should be disabled
    
    Might be used to disable this app completely (with `DJANGO_OPTIMIZER_DISABLE_LOGGING`) or in some cases
    where only logging is required (caching is not desirable and app is used to generate source code changes)
    """


settings = DjangoOptimizerSettings()
