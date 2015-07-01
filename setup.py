#! /usr/bin/python


from distutils.core import setup

setup(
	name = "SmartShine",
	version = "0.36",
	description = "SmartShine is a GUI for aaphoto utility, which automatically adjusts levels/contrast/white balance/saturation of your photos.",
	author = "Dariusz Duma",
	author_email = "dhor@toxic.net.pl",
	url = "https://launchpad.net/smartshine",
	license = 'GNU GPL-3',
	packages = ["smartshine"],
	package_data = {"smartshine": [
		"smartshine.py",
		"images/smartshine.png",
		"ui/smartshine_g3.ui",
		"locale/pl/LC_MESSAGES/smartshine.po",
		"locale/pl/LC_MESSAGES/smartshine.mo",
	]},
	scripts = ["bin/smartshine"],
)
