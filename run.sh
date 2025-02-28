#!/bin/sh

cd /opt/menuflow

if [ ! -f /data/config.yaml ]; then
	cp example-config.yaml /data/config.yaml
	echo "Didn't find a config file."
	echo "Copied default config file to /data/config.yaml"
	echo "Modify that config file to your liking."
	echo "Start the container again."
	exit
fi

if [ "$1" = "dev" ]; then
	pip install --ignore-installed -r requirements-dev.txt
	# Configure git to use the safe directory
	if ! [ $(git config --global --get safe.directory) ]; then
		echo "Setting safe.directory config to /opt/menuflow"
		git config --global --add safe.directory /opt/menuflow
	fi
	# Getting the version from git repository
	python3 setup.py --version
    watchmedo auto-restart -R -p="*.py" -d="." /opt/menuflow/run.sh
fi

exec python3 -m menuflow -c /data/config.yaml
