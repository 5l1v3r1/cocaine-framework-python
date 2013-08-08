import logging
import os
from opster import Dispatcher
from cocaine.asio.service import Locator, Service
from cocaine.exceptions import ToolsError
from cocaine.tools.cli import Executor, coloredOutput

__author__ = 'Evgeny Safronov <division494@gmail.com>'


DESCRIPTION = ''
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 10053


class Global(object):
    options = [
        ('h', 'host', DEFAULT_HOST, 'hostname'),
        ('p', 'port', DEFAULT_PORT, 'port'),
        ('', 'color', False, 'enable colored output'),
        ('', 'timeout', 1.0, 'timeout, s'),
        ('', 'debug', ('disable', 'tools', 'all'), 'enable debug mode')
    ]

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, color=False, timeout=False, debug=False):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._locator = None
        self.executor = Executor(timeout)

        if not color:
            coloredOutput.disable()

        if debug != 'disable':
            ch = logging.StreamHandler()
            ch.fileno = ch.stream.fileno
            ch.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(name)s: %(levelname)-8s: %(message)s')
            ch.setFormatter(formatter)

            logNames = [
                __name__,
                'cocaine.tools'
            ]
            if debug == 'all':
                logNames.append('cocaine')

            for logName in logNames:
                log = logging.getLogger(logName)
                log.setLevel(logging.DEBUG)
                log.propagate = False
                log.addHandler(ch)

    @property
    def locator(self):
        if self._locator:
            return self._locator
        else:
            try:
                locator = Locator()
                locator.connect(self.host, self.port, self.timeout, blocking=True)
                self._locator = locator
                return locator
            except Exception as err:
                raise ToolsError(err)

    def getService(self, name):
        try:
            service = Service(name, blockingConnect=False)
            service.connectThroughLocator(self.locator, self.timeout, blocking=True)
            return service
        except Exception as err:
            raise ToolsError(err)


def middleware(func):
    def extract_dict(source, *keys):
        dest = {}
        for k in keys:
            dest[k] = source.pop(k, None)
        return dest

    def inner(*args, **kwargs):
        opts = extract_dict(kwargs, 'host', 'port', 'color', 'timeout', 'debug')
        if func.__name__ == 'help_inner':
            return func(*args, **kwargs)
        locator = Global(**opts)
        return func(locator, *args, **kwargs)
    return inner


d = Dispatcher(globaloptions=Global.options, middleware=middleware)
appDispatcher = Dispatcher(globaloptions=Global.options, middleware=middleware)
profileDispatcher = Dispatcher(globaloptions=Global.options, middleware=middleware)
runlistDispatcher = Dispatcher(globaloptions=Global.options, middleware=middleware)
crashlogDispatcher = Dispatcher(globaloptions=Global.options, middleware=middleware)


@d.command()
def info(options):
    """Show information about cocaine runtime

    Return json-like string with information about cocaine-runtime.
    """
    options.executor.executeAction('info', **{
        'node': options.getService('node'),
        'locator': options.locator
    })


@d.command(usage='SERVICE [METHOD ["ARGS"]]')
def call(options,
         service, method='', args=''):
    """Invoke specified method from service.

    Performs method invocation from specified service. Service name should be correct string and must be correctly
    located through locator. By default, locator endpoint is `localhost, 10053`, but it can be changed by passing
    global `--host` and `--port` arguments.

    Method arguments should be passed in double quotes as they would be written in Python.
    If no method provided, service API will be printed.
    """
    command = service + '.' + method + '(' + args + ')'
    options.executor.executeAction('call', **{
        'command': command,
        'host': options.host,
        'port': options.port
    })

@appDispatcher.command(name='list')
def app_list(options):
    """Show installed applications list."""
    options.executor.executeAction('app:list', **{
        'storage': options.getService('storage')
    })


@appDispatcher.command(usage='--name=NAME', name='view')
def app_view(options,
             name=('n', '', 'application name')):
    """Show manifest context for application.

    If application is not uploaded, an error will be displayed.
    """
    options.executor.executeAction('app:view', **{
        'storage': options.getService('storage'),
        'name': name,
    })


@appDispatcher.command(name='upload', usage='[PATH] [--name=NAME] [--manifest=MANIFEST] [--package=PACKAGE]')
def app_upload(options,
               path=None,
               name=('n', '', 'application name'),
               manifest=('', '', 'manifest file name'),
               package=('', '', 'path to the application archive'),
               venv=('', ('None', 'P', 'R', 'J'), 'virtual environment type (None, P, R, J).')):
    """Upload application with its environment (directory) into the storage.

    Application directory or its subdirectories must contain valid manifest file named `manifest.json` or `manifest`
    otherwise you must specify it explicitly by setting `--manifest` option.

    You can specify application name. By default, leaf directory name is treated as application name.

    If you have already prepared application archive (*.tar.gz), you can explicitly specify path to it by setting
    `--package` option. Note, that PATH and --package options are mutual exclusive as well as --package and --venv
    options.

    If you specify option `--venv`, then virtual environment will be created for application.
    Possible values:
        N - do not create virtual environment (default)
        P - python virtual environment using virtualenv package
        R - ruby virtual environment using Bundler (not yet implemented)
        J - jar archive will be created (not yet implemented)

    You can control process of creating and uploading application by specifying `--debug=tools` option. This is helpful
    when some errors occurred.

    Warning: creating virtual environment may take a long time and can cause timeout. You can increase timeout by
    specifying `--timeout` option.
    """
    if path and package:
        print('Wrong usage: option PATH and --package are mutual exclusive, you can only force one')
        exit(os.EX_USAGE)

    if venv != 'None' and package:
        print('Wrong usage: option --package and --venv are mutual exclusive, you can only force one')
        exit(os.EX_USAGE)

    if package:
        options.executor.executeAction('app:upload-manual', **{
            'storage': options.getService('storage'),
            'name': name,
            'manifest': manifest,
            'package': package
        })
    else:
        if venv != 'None':
            print('You specified building virtual environment')
            print('It may take a long time and can cause timeout. Increase it by specifying `--timeout` option if'
                  ' needed')
        options.executor.executeAction('app:upload', **{
            'storage': options.getService('storage'),
            'path': path,
            'name': name,
            'manifest': manifest,
            'venv': venv
        })


@appDispatcher.command(name='remove')
def app_remove(options,
               name=('n', '', 'application name')):
    """Remove application from storage.

    No error messages will display if specified application is not uploaded.
    """
    options.executor.executeAction('app:remove', **{
        'storage': options.getService('storage'),
        'name': name
    })


@appDispatcher.command(name='start')
def app_start(options,
              name=('n', '', 'application name'),
              profile=('r', '', 'profile name')):
    """Start application with specified profile.

    Does nothing if application is already running.
    """
    options.executor.executeAction('app:start', **{
        'node': options.getService('node'),
        'name': name,
        'profile': profile
    })


@appDispatcher.command(name='pause')
def app_pause(options,
              name=('n', '', 'application name')):
    """Stop application.

    This command is alias for ```cocaine-tool app stop```.
    """
    options.executor.executeAction('app:pause', **{
        'node': options.getService('node'),
        'name': name
    })


@appDispatcher.command(name='stop')
def app_stop(options,
             name=('n', '', 'application name')):
    """Stop application."""
    options.executor.executeAction('app:stop', **{
        'node': options.getService('node'),
        'name': name
    })


@appDispatcher.command(name='restart')
def app_restart(options,
                name=('n', '', 'application name'),
                profile=('r', '', 'profile name')):
    """Restart application.

    Executes ```cocaine-tool app pause``` and ```cocaine-tool app start``` sequentially.

    It can be used to quickly change application profile.
    """
    options.executor.executeAction('app:restart', **{
        'node': options.getService('node'),
        'locator': options.locator,
        'name': name,
        'profile': profile
    })


@appDispatcher.command()
def check(options,
          name=('n', '', 'application name')):
    """Checks application status."""
    options.executor.executeAction('app:check', **{
        'node': options.getService('node'),
        'locator': options.locator,
        'name': name,
    })


@profileDispatcher.command(name='list')
def profile_list(options):
    """Show installed profiles."""
    options.executor.executeAction('profile:list', **{
        'storage': options.getService('storage')
    })


@profileDispatcher.command(name='view')
def profile_view(options,
                 name=('n', '', 'profile name')):
    """Show profile configuration context."""
    options.executor.executeAction('profile:view', **{
        'storage': options.getService('storage'),
        'name': name
    })


@profileDispatcher.command(name='upload')
def profile_upload(options,
                   name=('n', '', 'profile name'),
                   profile=('', '', 'path to profile file')):
    """Upload profile into the storage."""
    options.executor.executeAction('profile:upload', **{
        'storage': options.getService('storage'),
        'name': name,
        'profile': profile
    })


@profileDispatcher.command(name='remove')
def profile_remove(options,
                   name=('n', '', 'profile name')):
    """Remove profile from the storage."""
    options.executor.executeAction('profile:remove', **{
        'storage': options.getService('storage'),
        'name': name
    })


@runlistDispatcher.command(name='list')
def runlist_list(options):
    """Show uploaded runlists."""
    options.executor.executeAction('runlist:list', **{
        'storage': options.getService('storage')
    })


@runlistDispatcher.command(name='view')
def runlist_view(options,
                 name=('n', '', 'name')):
    """Show configuration context for runlist."""
    options.executor.executeAction('runlist:view', **{
        'storage': options.getService('storage'),
        'name': name
    })


@runlistDispatcher.command(name='upload')
def runlist_upload(options,
                   name=('n', '', 'name'),
                   runlist=('', '', 'path to the runlist configuration json file')):
    """Upload runlist with context into the storage."""
    options.executor.executeAction('runlist:upload', **{
        'storage': options.getService('storage'),
        'name': name,
        'runlist': runlist
    })


@runlistDispatcher.command(name='create')
def runlist_create(options,
                   name=('n', '', 'name')):
    """Create runlist and upload it into the storage."""
    options.executor.executeAction('runlist:create', **{
        'storage': options.getService('storage'),
        'name': name
    })


@runlistDispatcher.command(name='remove')
def runlist_remove(options,
                   name=('n', '', 'name')):
    """Remove runlist from the storage."""
    options.executor.executeAction('runlist:remove', **{
        'storage': options.getService('storage'),
        'name': name
    })


@runlistDispatcher.command(name='add-app')
def runlist_add_app(options,
                    name=('n', '', 'runlist name'),
                    app=('', '', 'application name'),
                    profile=('', '', 'suggested profile'),
                    force=('', False, 'create runlist if it is not exist')):
    """Add specified application with profile to the runlist.

    Existence of application or profile is not checked.
    """
    options.executor.executeAction('runlist:add-app', **{
        'storage': options.getService('storage'),
        'name': name,
        'app': app,
        'profile': profile,
        'force': force
    })


@crashlogDispatcher.command(name='list')
def crashlog_list(options,
                  name=('n', '', 'name')):
    """Show crashlogs list for application.

    Prints crashlog list in timestamp - uuid format.
    """
    options.executor.executeAction('crashlog:list', **{
        'storage': options.getService('storage'),
        'name': name
    })


@crashlogDispatcher.command(name='view')
def crashlog_view(options,
                  name=('n', '', 'name'),
                  timestamp=('t', '', 'timestamp')):
    """Show crashlog for application with specified timestamp."""
    options.executor.executeAction('crashlog:view', **{
        'storage': options.getService('storage'),
        'name': name,
        'timestamp': timestamp
    })


@crashlogDispatcher.command(name='remove')
def crashlog_remove(options,
                    name=('n', '', 'name'),
                    timestamp=('t', '', 'timestamp')):
    """Remove crashlog for application with specified timestamp from the storage."""
    options.executor.executeAction('crashlog:remove', **{
        'storage': options.getService('storage'),
        'name': name,
        'timestamp': timestamp
    })


@crashlogDispatcher.command(name='removeall')
def crashlog_removeall(options,
                       name=('n', '', 'name')):
    """Remove all crashlogs for application from the storage."""
    options.executor.executeAction('crashlog:removeall', **{
        'storage': options.getService('storage'),
        'name': name,
    })


d.nest('app', appDispatcher, 'application commands')
d.nest('profile', profileDispatcher, 'profile commands')
d.nest('runlist', runlistDispatcher, 'runlist commands')
d.nest('crashlog', crashlogDispatcher, 'crashlog commands')