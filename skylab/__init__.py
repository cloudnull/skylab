# =============================================================================
# Copyright [2013] [cloudnull]
# License Information :
# This software has no warranty, it is provided 'as is'. It is your
# responsibility to validate the behavior of the routines and its accuracy
# using the code provided. Consult the GNU General Public license for further
# details (see GNU General Public License).
# http://www.gnu.org/licenses/gpl.html
# =============================================================================

import os
import prettytable
import shelve


class LimitsUnavailable(Exception):
    pass


class TooManyNetworks(Exception):
    pass


class NoNetworksAvailable(Exception):
    pass


class NotEnoughRam(Exception):
    pass


class NotEnoughNodes(Exception):
    pass


class RetryError(Exception):
    pass


class DeploymentFailure(Exception):
    pass


def print_horiz_table(data):
    """Print a horizontal pretty table from data."""

    base_data = [dict(d) for d in data]
    all_keys = []

    for keys in base_data:
        for key in keys.keys():
            if key not in all_keys:
                all_keys.append(key)

    for data in base_data:
        for key in all_keys:
            if key not in data.keys():
                data[key] = None

    table = prettytable.PrettyTable(all_keys)
    for info in base_data:
        table.add_row(info.values())
    for tbl in table.align.keys():
        table.align[tbl] = 'l'
    print(table)


class Shelve(object):
    """Context Manager for opening and closing access to the DBM."""

    def __init__(self, file_path):
        """Set the Path to the DBM to create/Open.

        :param file_path: Full path to file
        """

        self.shelve = file_path
        self.open_shelve = None

    def __enter__(self):
        """Open the DBM in r/w mode.

        :return: Open DBM
        """

        self.open_shelve = shelve.open(self.shelve, writeback=True)
        return self.open_shelve

    def __exit__(self, type, value, traceback):
        """Close DBM Connection."""

        self.open_shelve.sync()
        self.open_shelve.close()


def dbm_create(db_path, db_name, db_key):
    """Create a DBM.

    :param db_path: Path to a directory
    :param db_name: Name of DBM
    """

    db_path = os.path.expanduser(db_path)
    if not os.path.exists(db_path):
        os.mkdir(db_path)

    database_path = os.path.join(db_path, db_name)
    with Shelve(file_path=database_path) as db:
        host = db.get(db_key)
        if host is None:
            db[db_key] = {}

    return database_path