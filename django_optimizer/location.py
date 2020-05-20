# -*- coding: utf-8 -*-
import inspect

from django.conf import settings as django_settings


class QuerySetLocation:
    """
    Object for storing information about queryset location.
    """
    def __init__(self, qs):
        """
        Gets values from queryset (model name) and source code stack frames
        (file name, function names, variable name) to differentiate between different querysets.

        :param qs: QuerySet object, which location is stored by this object
        """
        self.source = self.get_source()
        if self.source:
            self.type = self.get_type(qs)
            self.file = self.get_file()
            self.scope = self.get_scope()
            self.variable = self.get_variable()

    def __str__(self):
        """
        Joins all fields retrieved in __init__().

        :return: string representation, unique key to be used in caching field sets
        """
        if self.source:
            return '/'.join([self.type, self.file, self.scope, self.variable])
        else:
            return ''

    def __bool__(self):
        """
        Tells optimizer whether queryset has any reasonable location in source code and whether it should be optimized.

        :return: True if there are any source code stack frames
        """
        return bool(self.source)

    @staticmethod
    def get_source():
        """
        Gets full stack, then ignores frames executing libraries' code and frames executing code
        from a file different to last source code frame.

        :return: list of frame objects that execute latest file of source code existing on traceback
        """
        try:
            latest_file_name = [s[1] for s in inspect.stack() if django_settings.BASE_DIR in s[1]][0]
            return [s for s in inspect.stack() if s[1] == latest_file_name]
        except IndexError:
            return []

    @staticmethod
    def get_type(obj):
        return obj.model.__name__.lower()

    def get_file(self):
        _, filename, _, _, _, _ = self.source[0]
        return filename.replace(django_settings.BASE_DIR + '/', '').replace('.py', '')

    def get_scope(self):
        _, filename, _, _, _, _ = self.source[0]
        return '.'.join(reversed([str(s[3]) for s in self.source if s[1] == filename]))

    # TODO remove
    def get_variable(self):
        return str(self.source[0][2])

    # TODO reconsider & fix
    # def get_variable(self):
    #     def __get_code_from_frame(frame):
    #         from io import StringIO
    #         from uncompyle6 import deparse_code2str
    #
    #         code = StringIO()
    #         deparse_code2str(frame.f_code, out=code)
    #         return code.getvalue().split('\n')[frame.f_lineno]
    #     return __get_code_from_frame(self.source[0])
