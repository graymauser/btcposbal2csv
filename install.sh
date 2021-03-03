#!/bin/bash

if [ -z $BASH_VERSION ] ; then
	echo -e "You must run this script using bash." 1>&2
	exit 1
fi


# Make sure we are running as superuser
if [[ $EUID -ne 0 ]]; then
	echo -e "This script must be run using sudo." 1>&2
	exit 1
fi

apt-get update

apt-get install --no-install-recommends python-virtualenv
python -m virtualenv --no-site-packages venv
source venv/bin/activate

pip install ez_setup
apt-get install python-dev libpq-dev
easy_install hashlib
pip install plyvel
pip install base58
easy_install pysqlite

echo -e "Run source venv/bin/activate in your terminal before executing btcposbal2csv commands"

