################################################################################
#      Copyright (C) 2018 Arthur Liberman (arthur_liberman (at) hotmail.com)
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
################################################################################

import xbmcaddon
import threading
import os
from resources.lib import vfdstates
from resources.lib import vfddisplay
from resources.lib import vfddev
from resources.lib import vfdsettings
from resources.lib.vfdutils import *

addon = xbmcaddon.Addon(id='service.openvfd')

class vfdMonitor(xbmc.Monitor):
	def __init__(self):
		super(vfdMonitor, self).__init__()
		self._settingsChangedCallback = None

	def setSettingsChangedCallback(self, callbackObject):
		self._settingsChangedCallback = callbackObject

	def onSettingsChanged(self):
		kodiLog('Enter vfdMonitor.onSettingsChanged')
		if (self._settingsChangedCallback != None):
			self._settingsChangedCallback.onSettingsChanged()

class vfdAddon():
	def __init__(self, monitor):
		self._vfd = vfddev.vfdDev()
		self._states = []
		self._monitor = monitor
		self._monitor.setSettingsChangedCallback(self)
		self._settings = vfdsettings.vfdSettings()
		self._vfdon = '/sys/class/leds/openvfd/led_on'
		self._vfdoff = '/sys/class/leds/openvfd/led_off'
		self._rlock = threading.RLock()
		self._modeManager = vfddisplay.vfdDisplayManager('/tmp/openvfd_service', self._rlock)
		self._modes = [
				vfddisplay.vfdDisplayModeTemperature(self._modeManager, self._settings),
				vfddisplay.vfdDisplayModeDate(self._modeManager, self._settings),
				vfddisplay.vfdDisplayModePlaybackTime.factory(self._modeManager, self._settings)
			]

	def run(self):
		firstLoop = True
		while not self._monitor.abortRequested():
			if self._monitor.waitForAbort(0.5):
				break
			if (not os.path.isfile(self._vfdon) or not os.path.isfile(self._vfdoff)):
				firstLoop = True
				continue
			if (firstLoop):
				self.onSettingsChanged()
				firstLoop = False
			self.__updateIndicators()
			self._modeManager.update()
		self.__cleanUp()

	def __updateIndicators(self):
		ledon = []
		ledoff = []
		if (self._rlock.acquire()):
			for state in self._states:
				state.update()
				if (state.hasChanged()):
					if (state.getValue()):
						ledon.append(state.getLedName())
					else:
						ledoff.append(state.getLedName())
			self.__writeFile(self._vfdon, ledon)
			self.__writeFile(self._vfdoff, ledoff)
			self._rlock.release()

	def __cleanUp(self):
		self.__turnOffIndicators()
		self._monitor = None
		for mode in self._modes:
			mode.enable(False)
		self._modeManager.clear()

	def __turnOffIndicators(self):
		if (self._rlock.acquire()):
			ledoff = [state.getLedName() for state in self._states]
			self.__writeFile(self._vfdoff, ledoff)
			self._rlock.release()

	def __writeFile(self, path, values):
		if (os.path.isfile(path)):
			with open(path, "wb") as vfd:
				for j in values:
					vfd.write(j)
					vfd.flush()

	def onSettingsChanged(self):
		kodiLog('Enter vfdAddon.onSettingsChanged')
		self._settings.readValues()
		if (self._rlock.acquire()):
			self.__createStates()
			self._vfd.enableDisplay(self._settings.isDisplayOn())
			if (self._settings.isDisplayOn()):
				self._vfd.setBrightness(self._settings.getBrightness())
				if (self._settings.isAdvancedSettings()):
					self._vfd.setDisplayType(self._settings.getDisplay())
					self._vfd.setCharacterOrder(self._settings.getCharacterIndexes())
				else:
					self._vfd.useDtbConfig()
				if (self._colonIcon != None and self._settings.isColonOn()):
					self._colonIcon.turnOn()
			self.__updateIndicators()
			self._rlock.release()
		self._modeManager.clear()
		for mode in self._modes:
			mode.onSettingsChanged()
		kodiLog('isDisplayOn = {0}'.format(self._settings.isDisplayOn()))
		kodiLog('getBrightness = {0}'.format(self._settings.getBrightness()))
		kodiLog('isAdvancedSettings = {0}'.format(self._settings.isAdvancedSettings()))
		kodiLog('getDisplayType = {0}'.format(self._settings.getDisplayType()))
		kodiLog('isCommonAnode = {0}'.format(self._settings.isCommonAnode()))
		kodiLog('getCharacterIndexex = {0}'.format(self._settings.getCharacterIndexes()))

	def __createStates(self):
		settingsWindows = ['settings', 'systeminfo', 'systemsettings', 'servicesettings', 'pvrsettings', \
		'playersettings', 'mediasettings', 'interfacesettings', 'profiles', 'skinsettings', 'videossettings', \
		'musicsettings', 'appearancesettings', 'picturessettings', 'weathersettings', 'gamesettings', \
		'service-CoreELEC-Settings-mainWindow.xml', 'service-CoreELEC-Settings-wizard.xml', \
		'service-CoreELEC-Settings-getPasskey.xml', \
		'service-LibreELEC-Settings-mainWindow.xml', 'service-LibreELEC-Settings-wizard.xml', \
		'service-LibreELEC-Settings-getPasskey.xml']
		appsWindows = ['addonbrowser', 'addonsettings', 'addoninformation', 'addon', 'programs']
		states = []
		states.append(vfdstates.vfdIconIndicator(True, 'power'))
		states.append(vfdstates.vfdCondVisibility('play', 'Player.Playing'))
		states.append(vfdstates.vfdCondVisibility('pause', 'Player.Paused'))
		states.append(vfdstates.vfdFileContains('hdmi', '/sys/class/amhdmitx/amhdmitx0/hpd_state', ['1']))
		states.append(vfdstates.vfdFileContains('cvbs', '/sys/class/display/mode', ['cvbs']))
		states.append(vfdstates.vfdFileContains('eth', '/sys/class/net/eth0/operstate', ['up', 'unknown']))
		states.append(vfdstates.vfdFileContains('wifi', '/sys/class/net/wlan0/operstate', ['up']))
		states.append(vfdstates.vfdWindowChecker('setup', settingsWindows))
		states.append(vfdstates.vfdWindowChecker('apps', appsWindows))
		states.append(vfdstates.vfdExtStorageChecker('usb', '/dev/sd'))
		states.append(vfdstates.vfdExtStorageChecker('sd', '/dev/mmcblk'))
		self._colonIcon = vfdstates.vfdIconIndicator(False, 'colon')
		states.append(self._colonIcon)
		if (self._settings.isStorageIndicator()):
			for state in states:
				if (state.getLedName() == self._settings.getStorageIndicatorIcon()):
					states.remove(state)
					break
			states.append(vfdstates.vfdExtStorageCount(self._settings.getStorageIndicatorIcon(), None, 'rw'))
			kodiLog('Active states: ' + str([str(state) for state in states]))
		self.__turnOffIndicators()
		self._states = states

monitor = vfdMonitor()
vfd = vfdAddon(monitor)
kodiLog('Service start.')
vfd.run()
kodiLog('Service stop.')
