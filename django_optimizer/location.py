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
        source = self.get_source()
        self.type = self.get_type(qs)
        self.file = self.get_file(source)
        self.scope = self.get_scope(source)
        self.variable = self.get_variable(source)

    def __str__(self):
        """
        Joins all fields retrieved in __init__().

        :return: string representation, unique key to be used in caching field lists
        """
        return '/'.join([self.type, self.file, self.scope, self.variable])

    @staticmethod
    def get_source():
        """
        Gets full stack, then ignores frames executing libraries' code and frames executing code
        from a file different to last source code frame.

        :return: list of frame objects that execute latest file of source code existing on traceback
        """
        latest_file_name = [s[1] for s in inspect.stack() if django_settings.BASE_DIR in s[1]][0]
        return [s for s in inspect.stack() if s[1] == latest_file_name]

    @staticmethod
    def get_type(obj):
        return obj.model.__name__.lower()

    @staticmethod
    def get_file(source):
        _, filename, _, _, _, _ = source[0]
        return filename.replace(django_settings.BASE_DIR, '.').replace('.py', '')

    @staticmethod
    def get_scope(source):
        _, filename, _, _, _, _ = source[0]
        return '.'.join(reversed([str(s[3]) for s in source if s[1] == filename]))

    # TODO remove
    @staticmethod
    def get_variable(source):
        def __extract_name_from_line(line):
            for prefix in ['class', 'def']:
                if prefix in line:
                    line = line.split(prefix)[-1]
            for postfix in ['=']:
                if postfix in line:
                    line = line.split(postfix)[0]
            return line.strip()

        _, _, _, _, code_context, index = source[0]
        return __extract_name_from_line(code_context[index])

    # TODO reconsider & fix
    # @staticmethod
    # def get_variable(source):
    #     def __get_code_from_frame(frame):
    #         from io import StringIO
    #         from uncompyle6 import deparse_code2str
    #
    #         code = StringIO()
    #         deparse_code2str(frame.f_code, out=code)
    #         return code.getvalue().split('\n')[frame.f_lineno]
    #     return __get_code_from_frame(source[0])
