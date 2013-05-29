#!/usr/bin/env python
#
#    Copyright (c) 2011-2013 Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    Cocaine is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>. 
#

import errno
import json
import socket
import tarfile
from time import ctime
from optparse import OptionParser

import msgpack

from cocaine.services import Service

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 10053
DEFAULT_TIMEOUT = 2

APPS_TAGS = ("app",)
RUNLISTS_TAGS = ("runlist",)
PROFILES_TAGS = ("profile",)


def sync_decorator(func, timeout):
    def wrapper(*args, **kwargs):
        res = ""
        try:
            info = func(timeout=kwargs.get("timeout") or timeout, *args, **kwargs)
            res = info.next()
            info.next()
        except StopIteration:
            return res
    return wrapper


def exists(namespace, tag, entity_name=""):
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            name = args[0]
            if not name in self._list(namespace, tag):
                print "%s %s is not uploaded" % (entity_name, name)
                exit(0)
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def not_exists(namespace, tag, entity_name=""):
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            name = args[0]
            if name in self._list(namespace, tag):
                print "%s %s has been already uploaded" % (entity_name, name)
                exit(0)
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def parse_crashlog_name(crashlog_name):
    timestamp, worker_uuid = crashlog_name.split(':')
    return timestamp, str(ctime(float(timestamp)/1000000)).strip('\n'), worker_uuid


class Sync_wrapper(object):
    def __init__(self, obj, timeout):
        self._obj = obj
        self._timeout = timeout

    def __getattr__(self, name):
        _async = getattr(self._obj, name)
        return sync_decorator(_async, self._timeout)


def print_json(data):
    print json.dumps(data, indent=2)


class Storage(object):
    def __init__(self, hostname, port, timeout):
        self._st = Sync_wrapper(Service("storage", hostname, port), timeout)

    def _list(self, namespace, tags):
        return self._st.perform_sync("find", namespace, tags)

    def apps(self):
        uploaded_apps = ['{0}. {1}'.format(i, app) for i, app in enumerate(self._list("manifests", APPS_TAGS), start=1)]
        return uploaded_apps

    @exists("manifests", APPS_TAGS, "manifest")
    @exists("apps", APPS_TAGS, "app")
    def view(self, name):
        try:
            print_json(msgpack.unpackb(self._st.perform_sync("read", "manifests", name)))
        except Exception as err:
            print "Error: unable to view application. %s" % str(err)
            exit(1)
        exit(0)

    #@not_exists("manifests", APPS_TAGS, "manifest")
    #@not_exists("apps", APPS_TAGS, "Source of app")
    def upload(self, name, manifest_path, archive_path):
        def pack_manifest(manifest_path):
            try:
                with open(manifest_path, 'rb') as manifest_file:
                    manifest_content = manifest_file.read()
                    manifest_json = json.loads(manifest_content)
                    manifest = msgpack.packb(manifest_json)
                    return manifest
            except IOError as err:
                raise ValueError("Unable to open manifest file %s - %s" % (manifest_path, err))
            except ValueError as err:
                raise ValueError("The app manifest in %s is corrupted - %s" % (manifest_path, err))

        def pack_package(archive_path):
            try:
                if not tarfile.is_tarfile(archive_path):
                    raise ValueError('File "{0}" is ot tar file'.format(archive_path))
                with open(archive_path, 'rb') as archive:
                    blob = msgpack.packb(archive.read())
                    return blob
            except IOError as err:
                raise ValueError('Error occurred while reading archive file "{0}" - {1}'.format(archive_path, err))

        manifest = pack_manifest(manifest_path)
        blob = pack_package(archive_path)
        # Upload
        try:
            self._st.perform_sync("write", "manifests", name, manifest, APPS_TAGS)
            self._st.perform_sync("write", "apps", name, blob, APPS_TAGS)
        except Exception as err:
            print "Error: unable to upload app. %s" % str(err)
        else:
            print "The %s app has been successfully uploaded." % name

    def remove(self, name):
        try:
            self._st.perform_sync("remove", "manifests", name)
        except Exception as err:
            print "Error: unable to remove manifest for app. %s" % str(err)
        else:
            print "The %s manifest of app has been successfully removed." % name

        try:
            self._st.perform_sync("remove", "apps", name)
        except Exception as err:
            print "Error: unable to remove app source. %s" % str(err)
        else:
            print "The %s source of app has been successfully removed." % name
        exit(0)

    def profiles(self):
        print "Currently uploaded profiles:"
        for n, profile in enumerate(self._list("profiles", PROFILES_TAGS)):
            print "\t%d. %s" % (n + 1, profile)
        exit(0)

    @not_exists("profiles", PROFILES_TAGS, "profile")
    def upload_profile(self, name, profile_path):
        try:
            with open(profile_path,'rb') as profile_file:
                profile = profile_file.read()
                profile = json.loads(profile)
                profile = msgpack.packb(profile)
        except IOError as err:
            print "Error: unable to open profile file %s." % profile_path
            exit(1)
        except ValueError as err:
            print "Error: the app profile in %s is corrupted." % profile_path
            exit(1)

        try:
            self._st.perform_sync("write", "profiles", name, profile, PROFILES_TAGS)
        except Exception as err:
            print "Error: unable to upload profile. %s" % str(err)
            exit(1)
        else:
            print "The %s profile has been successfully uploaded." % name
            exit(0)

    @exists("profiles", PROFILES_TAGS, "profile")
    def remove_profile(self, name):
        try:
            self._st.perform_sync("remove", "profiles", name)
        except Exception as err:
            print "Error: unable to remove profile. %s" % str(err)
            exit(1)
        else:
            print "The %s profile has been successfully removed." % name
            exit(0)

    @exists("profiles", PROFILES_TAGS, "profile")
    def view_profile(self, name):
        try:
            print_json(msgpack.unpackb(self._st.perform_sync("read", "profiles", name)))
        except Exception as err:
            print "Error: unable to view profile. %s" % str(err)
            exit(1)
        exit(0)

    def runlists(self):
        print "Currently uploaded runlists:"
        for n, runlist in enumerate(self._list("runlists", RUNLISTS_TAGS)):
            print "\t%d. %s" % (n + 1, runlist)
        exit(0)

    @exists("runlists", RUNLISTS_TAGS, "runlist")
    def view_runlist(self, name):
        try:
            print_json(msgpack.unpackb(self._st.perform_sync("read", "runlists", name)))
        except Exception as err:
            print "Error: unable to view runlist. %s" % str(err)
            exit(1)
        exit(0)

    #@not_exists("runlists", RUNLISTS_TAGS, "runlist")
    def upload_runlist(self, name, runlist_path):
        try:
            with open(runlist_path, 'rb') as runlist_file:
                runlist = runlist_file.read()
                runlist = json.loads(runlist)
                runlist = msgpack.packb(runlist)
        except IOError as err:
            print "Error: unable to open runlist file %s." % runlist_path
            exit(1)
        except ValueError as err:
            print "Error: the app runlist in %s is corrupted." % runlist_path
            exit(1)

        try:
            self._st.perform_sync("write", "runlists", name, runlist, RUNLISTS_TAGS)
        except Exception as err:
            print "Error: unable to upload runlist. %s" % str(err)
            exit(1)
        else:
            print "The %s runlist has been successfully uploaded." % name
            exit(0)

    @exists("runlists", RUNLISTS_TAGS, "runlist")
    def remove_runlist(self, name):
        try:
            self._st.perform_sync("remove", "runlists", name)
        except Exception as err:
            print "Error: unable to remove runlist. %s" % str(err)
            exit(1)
        else:
            print "The %s runlist has been successfully removed." % name
            exit(0)
    
    def _crashlogs_list(self, app_name, timestamp=None):
        if timestamp is None:
            flt = lambda x: True
        else:
            flt = lambda x: x == timestamp
        _lst = (log.split(':') for log in self._list("crashlogs", (app_name, )))
        return [(tmst, ctime(float(tmst)/1000000), name) for tmst, name in _lst if flt(tmst)]

    def crashlogs(self, app_name):
        print "Currently available crashlogs for application %s \n" % app_name
        for item in self._crashlogs_list(app_name):
            print ' '.join(item)
        exit(0)

    def crashlogs_view(self, app_name, timestamp):
        try:
            for item in self._crashlogs_list(app_name, timestamp):
                key = "%s:%s" % (item[0], item[2])
                print "Crashlog %s:" % key
                print '\n'.join(msgpack.unpackb(self._st.perform_sync("read", "crashlogs", key)))
        except Exception as err:
            print "Error: unable to view crashlog. %s" % str(err)
            exit(1)
        exit(0)

    def crashlogs_remove(self, app_name, timestamp=None):
        try:
            for item in self._crashlogs_list(app_name, timestamp):
                key = "%s:%s" % (item[0], item[2])
                self._st.perform_sync("remove", "crashlogs", key)
                print "Crashlog for %s succesfully removed" % app_name
        except Exception as err:
            print "Error: unable to remove crashlog. %s" % str(err)
            exit(1)
        exit(0)


def show_app_list(storage, options):
    uploaded_apps = storage.apps()
    print('Currently uploaded apps:')
    for uploaded_app in uploaded_apps:
        print('\t{0}'.format(uploaded_app))


def app_view(storage, options):
    if not options.name:
        raise ValueError('Specify name of application')
    storage.view(options.name)


def upload_app(storage, options):
    if not all([options.name, options.manifest, options.package]):
        raise ValueError('Specify name, manifest, package of the app')

    upload_config = {
        'name': options.name,
        'manifest_path': options.manifest,
        'archive_path': options.package
    }
    storage.upload(**upload_config)


def remove_app(storage, options):
    if not options.name:
        raise ValueError('Empty application name')
    storage.remove(options.name)


def profile_list(storage, options):
    storage.profiles()


def profile_upload(storage, options):
    if options.name is not None and options.manifest is not None:
        storage.upload_profile(options.name, options.manifest)
    else:
        print "Specify the name of the profile and profile filepath"


def profile_remove(storage, options):
    if options.name is not None:
        storage.remove_profile(options.name)
    else:
        print "Empty profile name"


def profile_view(storage, options):
    if options.name is not None:
        storage.remove_profile(options.name)
    else:
        print "Empty profile name"


def runlist_list(storage, options):
    storage.runlists()


def runlist_upload(storage, options):
    if options.name is not None and options.manifest is not None:
        storage.upload_runlist(options.name, options.manifest)
    else:
        print "Specify the name of the runlist and profile filepath"


def runlist_remove(storage, options):
    if options.name is not None:
        storage.remove_runlist(options.name)
    else:
        print "Empty runlist name"


def runlist_view(storage, options):
    if options.name is not None:
        storage.view_runlist(options.name)
    else:
        print "Empty runlist name"


def crashlog_list(storage, options):
    if options.name is not None:
        storage.crashlogs(options.name)
    else:
        print "Empty application name"


def crashlog_view(storage, options):
    if options.name is not None and options.manifest is not None:
        storage.crashlogs_view(options.name, options.manifest)
    else:
        print "Empty application name or timestamp"


def crashlog_remove(storage, options):
    if options.name is not None and options.manifest is not None:
        storage.crashlogs_remove(options.name, options.manifest)
    else:
        print "Empty application name or timestamp"


def crashlog_removeall(storage, options):
    if options.name is not None:
        storage.crashlogs_remove(options.name)
    else:
        print "Empty application name"

available_actions = {
    'app:list': show_app_list,
    'app:view': app_view,
    'app:upload': upload_app,
    'app:remove': remove_app,
    'profile:list': profile_list,
    'profile:upload': profile_upload,
    'profile:remove': profile_remove,
    'profile:view': profile_view,
    'runlist:list': runlist_list,
    'runlist:upload': runlist_upload,
    'runlist:remove': runlist_remove,
    'runlist:view': runlist_view,
    'crashlog:list': crashlog_list,
    'crashlog:view': crashlog_view,
    'crashlog:remove': crashlog_remove,
    'crashlog:removeall': crashlog_removeall
}


def doAction(action_name, options):
    try:
        storage = Storage(options.host, options.port, options.timeout)
        if action_name in available_actions:
            action = available_actions[action_name]
            action(storage, options)
        else:
            print('Error: action "{0}" is not available'.format(action_name))
            exit(0)
    except socket.error as err:
        if err.errno == errno.ECONNREFUSED:
            print "Invalid cocaine-runtime endpoint: %s:%d" % (options.host, options.port)
            exit(1)
    except ValueError as error:
        print('Error: {0}'.format(error))
    except Exception as error:
        print('Unknown error: {0}'.format(error))


DESCRIPTION = ""
USAGE = "Usage: %prog " + "%s <options>" % '|'.join(sorted(available_actions))
if __name__ == "__main__":
    parser = OptionParser(usage=USAGE, description=DESCRIPTION)
    parser.add_option("-m", '--manifest', type="str", dest="manifest",
                      help="location of the app manifest or runlist, profile")
    parser.add_option("-n", '--name', type="str", dest="name",
                      help="name of the app or profile")
    parser.add_option("-p", '--package', type="str", dest="package",
                      help="location of the app source package")
    parser.add_option("--timeout", type="float", default=DEFAULT_TIMEOUT,
                      help="timeout for synchronous operations [default: %defaults]")
    parser.add_option("--port", type="int", default=DEFAULT_PORT,
                      help="Port number [default: %default]")
    parser.add_option("--host", type="str", default=DEFAULT_HOST,
                      help="Hostname [default: %default]")
    (options, args) = parser.parse_args()

    if len(args) == 1:
        action_name = args[0]
        doAction(action_name, options)
    else:
        parser.print_usage()
        print('No action specified. Use one of the:\n\t{0}'.format('\n\t'.join(sorted(available_actions.keys()))))
