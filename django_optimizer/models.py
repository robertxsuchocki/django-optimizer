# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models


class LoggingQuerySetMixin(object):
    def __bool__(self):
        if not self._result_cache:
            print(type(self).__name__ + ' evaluated to check for truthiness')
            return super(LoggingQuerySetMixin, self).__bool__()

    def __len__(self):
        if not self._result_cache:
            print(type(self).__name__ + ' evaluated to check for length')
            return super(LoggingQuerySetMixin, self).__len__()


class LoggingModelMixin(object):
    def __getattribute__(self, item):
        if item != '_meta' and item in [f.name for f in self._meta.get_fields()]:
            print(type(self).__name__ + '.' + item)
        return super(LoggingModelMixin, self).__getattribute__(item)
