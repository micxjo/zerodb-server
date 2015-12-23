#!/usr/bin/env python2

"""
Management console
"""

import click
import logging

import os.path
from IPython import embed
from functools import update_wrapper

from zerodb import DB
from zerodb.crypto import ecc
from zerodb.storage import client_storage
from zerodb.transform import init_crypto

logging.basicConfig()

_username = None
_passphrase = None
_sock = None

PERMISSIONS_TEMPLATE = """realm ZERO
{username}:{passphrase}"""

ZEO_TEMPLATE = """<zeo>
  address {sock}
  authentication-protocol ecc_auth
  authentication-database {authdb}
  authentication-realm ZERO
</zeo>

<filestorage>
  path {dbfile}
</filestorage>"""


@click.group()
def cli():
    pass


def auth_options(f):
    """Decorator to enable username, passphrase and sock options to command"""
    @click.option("--username", default=None, type=click.STRING, help="Admin username")
    @click.option("--passphrase", default=None, type=click.STRING, help="Admin passphrase or hex private key")
    @click.option("--sock", default="localhost:8001", type=click.STRING, help="Storage server socket (TCP or UNIX)")
    @click.pass_context
    def auth_func(ctx, username, passphrase, sock, *args, **kw):
        global _username
        global _passphrase
        global _sock

        if username:
            _username = str(username)
        else:
            _username = str(click.prompt("Username", default="root"))

        if passphrase:
            _passphrase = str(passphrase)
        else:
            _passphrase = str(click.prompt("Passphrase", hide_input=True))

        if sock.startswith("/"):
            _sock = sock
        else:
            sock = sock.split(":")
            _sock = (str(sock[0]), int(sock[1]))
        ctx.invoke(f, *args, **kw)
    return update_wrapper(auth_func, f)


@cli.command()
@auth_options
def console():
    """
    Console for managing users (add, remove, change password)
    """

    def useradd(username, password):
        storage.add_user(username, password)

    def userdel(username):
        storage.del_user(username)

    def chpass(username, password):
        storage.change_key(username, password)

    banner = "\n".join([
            "Usage:",
            "========",
            "useradd(username, password) - add user",
            "userdel(username) - remove user",
            "chpass(username, password) - change passphrase",
            "exit() or ^D - exit"
            ])

    DB.auth_module.register_auth()
    DB.encrypter.register_class(default=True)
    init_crypto(passphrase=_passphrase)

    storage = client_storage(_sock,
            username=_username, password=_passphrase, realm="ZERO")
    embed(banner1=banner)


@cli.command()
@click.option("--path", default=None, type=click.STRING, help="Path to db and configs")
@auth_options
def init_db(path):
    """
    Initialize database if doesn't exist.
    Creates conf/ directory with config files and db/ with database files
    """
    if path:
        if not os.path.exists(path):
            raise IOError("Path provided doesn't exist")
    else:
        path = os.getcwd()

    conf_dir = os.path.join(path, "conf")
    db_dir = os.path.join(path, "db")
    authdb_conf = os.path.join(conf_dir, "authdb.conf")
    zcml_conf = os.path.join(conf_dir, "server.zcml")

    if os.path.exists(authdb_conf) or os.path.exists(zcml_conf):
        raise IOError("Config files already exist, remove them or edit")

    if not os.path.exists(conf_dir):
        os.mkdir(conf_dir)
    if not os.path.exists(db_dir):
        os.mkdir(db_dir)

    key = ecc.private(_passphrase).get_pubkey().encode("hex")
    authdb_content = PERMISSIONS_TEMPLATE.format(
            username=_username,
            passphrase=key)
    zcml_content = ZEO_TEMPLATE.format(
            sock=_sock if isinstance(_sock, basestring) else "{0}:{1}".format(*_sock),
            authdb=os.path.join("conf", "authdb.conf"),
            dbfile=os.path.join("db", "db.fs"))

    with open(authdb_conf, "w") as f:
        f.write(authdb_content)

    with open(zcml_conf, "w") as f:
        f.write(zcml_content)

    click.echo("Config files created, you can start zerodb-server")


@cli.command()
def clear():
    """
    Remove all database files (including auth db)
    """
    for f in os.listdir("db"):
        if f.startswith("db.fs"):
            os.remove(os.path.join("db", f))
    for f in os.listdir("conf"):
        if f.startswith("authdb.db"):
            os.remove(os.path.join("conf", f))

    click.echo("Database removed")


if __name__ == "__main__":
    cli()