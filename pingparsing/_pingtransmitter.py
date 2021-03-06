# encoding: utf-8

"""
.. codeauthor:: Tsuyoshi Hombashi <tsuyoshi.hombashi@gmail.com>
"""

from __future__ import absolute_import

from collections import namedtuple
import ipaddress
import platform
import warnings

import six
import typepy
from typepy.type import Integer

from ._logger import logger


DEFAULT_DEADLINE = 3


class PingResult(namedtuple("PingResult", "stdout stderr returncode")):
    """
    Data class to store ``ping`` command execution result.

    .. py:attribute:: stdout

        Standard output of ``ping`` command execution result.

    .. py:attribute:: stderr

        Standard error of ``ping`` command execution result.

    .. py:attribute:: returncode

        Return code of ``ping`` command execution result.
    """


class PingTransmitter(object):
    """
    Transmitter class to send ICMP packets by using the OS built-in ``ping``
    command.

    .. py:attribute:: destination_host

        Hostname or IP-address (IPv4/IPf6) to sending ICMP packets.

    .. py:attribute:: deadline

        Time ``[sec]`` of sending ICMP packets. The attribute ignored if
        the value is ``None``. If both :py:attr:`~.deadline` and
        :py:attr:`~.count` are ``None``, :py:attr:`~.deadline` set to ``1``.
        Defaults to ``None``.

    .. py:attribute:: count

        Number of sending ICMP packets. This attribute ignored if the value is
        ``None``. Defaults to ``None``.

    .. py:attribute:: ping_option

        Additional ``ping`` command option.

    .. py:attribute:: interface

        Interface name or zone-id. The attribute required when
        :py:attr:`~.destination_host` is IPv6 link-local scope address.
        Defaults to ``None``.

    .. py:attribute:: auto_codepage

        [Only for Windows environment] Automatically change code page if
        ``True``. Defaults to ``True``.
    """

    @property
    def waittime(self):
        warnings.warn(
            "waittime will be deleted in the future, use deadline instead.",
            DeprecationWarning)

        return self.deadline

    @waittime.setter
    def waittime(self, value):
        warnings.warn(
            "waittime will be deleted in the future, use deadline instead.",
            DeprecationWarning)

        self.deadline = value

    def __init__(self):
        self.destination_host = ""
        self.deadline = None
        self.count = 5
        self.ping_option = ""
        self.interface = None
        self.auto_codepage = True
        self.tos = 0
        self.packet_size = 8
        self.num_count = 5

    def ping(self):
        """
        Sending ICMP packets.

        :return: ``ping`` command execution result.
        :rtype: :py:class:`.PingResult`
        :raises ValueError: If parameters not valid.
        """

        import subprocess

        self.__validate_ping_param()

        command = self.__get_ping_command()

        logger.debug(command)

        ping_proc = subprocess.Popen(
            command, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = ping_proc.communicate()

        return PingResult(stdout, stderr, ping_proc.returncode)

    @staticmethod
    def __is_linux():
        return platform.system() == "Linux"

    @staticmethod
    def __is_osx():
        return platform.system() == "Darwin"

    @staticmethod
    def __is_windows():
        return platform.system() == "Windows"

    def __is_ipv6(self):
        try:
            network = ipaddress.ip_address(
                six.text_type(self.destination_host))
        except ValueError as e:
            logger.debug("{:s}: {}".format(e.__class__.__name__, e))
            return False

        logger.debug("IP address: version={}, address={}".format(
            network.version, self.destination_host))

        return network.version == 6

    def __validate_ping_param(self):
        if typepy.is_null_string(self.destination_host):
            raise ValueError("required destination_host")

        self.__validate_deadline()
        self.__validate_count()
        self.__validate_interface()

    def __validate_deadline(self):
        if self.deadline is None:
            return

        try:
            deadline = Integer(self.deadline).convert()
        except typepy.TypeConversionError:
            raise ValueError("deadline must be an integer: actual={}".format(
                self.deadline))

        if deadline <= 0:
            raise ValueError(
                "deadline must be greater than zero: actual={}".format(
                    self.deadline))

    def __validate_count(self):
        if self.count is None:
            return

        try:
            count = Integer(self.count).convert()
        except typepy.TypeConversionError:
            raise ValueError("count must be an integer: actual={}".format(
                self.count))

        if count <= 0:
            raise ValueError("count must be greater than zero")

    def __validate_interface(self):
        if not self.__is_ipv6():
            return

        if not ipaddress.ip_network(
                six.text_type(self.destination_host)).is_link_local:
            return

        if typepy.is_null_string(self.interface):
            raise ValueError(
                "interface required to ping to IPv6 link local address")

    def __get_ping_command(self):
        command_list = []

        if self.__is_windows() and self.auto_codepage:
            command_list.append("chcp 437 &")

        command_list.extend([
            self.__get_builtin_ping_command(),
            # self.__get_deadline_option(),
            self.__get_count_option(),
            self.__get_quiet_option(),
            self.__get_tos_option(),
            self.__get_size_option(),
        ])

        if self.__is_linux() and typepy.is_not_null_string(self.interface):
            command_list.append("-I {}".format(self.interface))

        if typepy.is_not_null_string(self.ping_option):
            command_list.append(self.ping_option)

        command_list.append(self.__get_destination_host())

        return " ".join(command_list)

    def __get_destination_host(self):
        if self.__is_windows() and self.__is_ipv6():
            return "{:s}%{}".format(self.destination_host, self.interface)

        return self.destination_host

    def __get_builtin_ping_command(self):
        if self.__is_windows():
            return "ping"

        if self.__is_ipv6():
            return "ping6"

        return "ping"

    def __get_quiet_option(self):
        if self.__is_windows():
            return ""

        return "-q"

    def __get_deadline_option(self):
        try:
            deadline = Integer(self.deadline).convert()
        except typepy.TypeConversionError:
            if self.count:
                return ""

            deadline = DEFAULT_DEADLINE

        if self.__is_windows():
            # ping for Windows not have the option with equals to the deadline
            # option.
            return "-n {:d}".format(deadline)
        elif self.__is_osx():
            return "-t {:d}".format(deadline)

        return "-w {:d}".format(deadline)

    def __get_count_option(self):
        try:
            count = Integer(self.count).convert()
        except typepy.TypeConversionError:
            return ""

        if self.__is_windows():
            return "-n {:d}".format(count)

        return "-c {:d}".format(count)

    def __get_tos_option(self):
        try:
            tos = Integer(self.tos).convert()
        except typepy.TypeConversionError:
            return ""

        if self.__is_windows():
            return "-v {:d}".format(tos)
        elif self.__is_linux():
            return "-Q {:d}".format(tos)
        elif self.__is_osx():
            return "-z {:d}".format(tos)

    def __get_size_option(self):
        try:
            packet_size = Integer(self.packet_size).convert()
        except typepy.TypeConversionError:
            return ""
        if packet_size < 0:
            return ""
        if self.__is_windows():
            return "-l {:d}".format(packet_size)
        else:
            return "-s {:d}".format(packet_size)
