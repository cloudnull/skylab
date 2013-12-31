# =============================================================================
# Copyright [2013] [cloudnull]
# License Information :
# This software has no warranty, it is provided 'as is'. It is your
# responsibility to validate the behavior of the routines and its accuracy
# using the code provided. Consult the GNU General Public license for further
# details (see GNU General Public License).
# http://www.gnu.org/licenses/gpl.html
# =============================================================================

import StringIO
import os
import tempfile

import skylab as sk
from skylab import utils as ut

import fabric.api as api


# Colorize Errors if they happen
api.env.colorize_errors = True


class InstallationFailed(Exception):
    pass


class Engine(object):
    """Fabric Runerator Engine."""

    def __init__(self, args):
        self.args = args

    def _fab_settings(self):
        """Return a general purpose settings dict."""

        return {
            'warn_only': True,
            'linewise': True,
            'keepalive': 10,
            'combine_stderr': True,
            'connection_attempts': 10,
            'disable_known_hosts': True,
            'key_filename': self.args.get('key_path'),
            'user': self.args.get('ssh_user'),
            'port': self.args.get('ssh_port'),
        }

    def run_action(self, action_dict, target):
        env_settings = self._fab_settings()
        if isinstance(target, list):
            api.env.hosts = target
        else:
            env_settings['host_string'] = target

        settings = api.settings(**env_settings)

        if self.args.get('debug') is True:
            hide = api.hide()
        else:
            hide = api.hide('running', 'stdout', 'output', 'warnings')

        ad = action_dict.copy()
        method = ad.pop('method')

        # grab the api method from fabric
        method = getattr(api, method)

        # Run all the things
        with hide, settings:
            result = method(**ad)

        if hasattr(result, 'return_code'):
            # Check for Failures.
            code = result.return_code
            # TODO(kevin) Make this do something smart
            if code != 0:
                pass
        else:
            return result

    def get(self, name, string_obj, target):
        ad = {'method': 'get'}
        print('Grabbing [%s]' % name)
        ad['remote_path'] = string_obj
        temp_file = ad['local_path'] = tempfile.mktemp()
        self.run_action(action_dict=ad, target=target)
        with open(temp_file, 'rb') as tf:
            with sk.Shelve(file_path=self.args['db_path']) as db:
                get_obj = db[self.args['db_name']][name] = tf.read()
        try:
            os.remove(temp_file)
        except OSError:
            pass
        finally:
            return get_obj

    def parallel_put(self, name, string_obj, remote_path, target):
        proc_args = {'name': name,
                     'string_obj': string_obj,
                     'target': target,
                     'remote_path': remote_path,
                     'queue': ut.basic_queue(iters=target),
                     'job_action': self.run}
        ut.worker_proc(
            kwargs=proc_args
        )

    def put(self, name, string_obj, remote_path, target):
        ad = {'method': 'put'}
        print('Putting [%s]' % name)
        ad['local_path'] = StringIO.StringIO(string_obj)
        ad['remote_path'] = remote_path
        self.run_action(action_dict=ad, target=target)

    def parallel_run(self, name, string_obj, target):
        proc_args = {'name': name,
                     'string_obj': string_obj,
                     'queue': ut.basic_queue(iters=target),
                     'job_action': self.run}
        ut.worker_proc(
            kwargs=proc_args
        )

    def run(self, name, string_obj, target):
        ad = {'method': 'run'}
        print('Executing [%s]' % name)
        ad['command'] = string_obj
        self.run_action(action_dict=ad, target=target)
