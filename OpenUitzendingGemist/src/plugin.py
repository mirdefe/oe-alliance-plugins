from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ActionMap import ActionMap, NumberActionMap
from Components.Pixmap import Pixmap
from Components.AVSwitch import AVSwitch
from Components.ServiceEventTracker import ServiceEventTracker
from Components.Sources.StaticText import StaticText
from Components.ConfigList import ConfigListScreen
from Components.config import config, ConfigSubsection, ConfigBoolean, ConfigSelection, getConfigListEntry
from enigma import eServiceReference, eTimer, iPlayableService, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_WRAP, RT_VALIGN_TOP, ePicLoad
from ServiceReference import ServiceReference
from Screens.InfoBarGenerics import InfoBarNotifications, InfoBarSeek
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Screens.MessageBox import MessageBox
from Tools import NumericalTextInput
from Tools.LoadPixmap import LoadPixmap
from Tools.BoundFunction import boundFunction
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from urllib2 import Request, URLError, HTTPError, urlopen as urlopen2
from httplib import HTTPException
from twisted.web import client
from os import path as os_path, remove as os_remove, mkdir as os_mkdir
import socket
from datetime import date, timedelta
import time
import urlparse
import httplib



config.plugins.OpenUitzendingGemist = ConfigSubsection()
config.plugins.OpenUitzendingGemist.showpictures = ConfigBoolean(default = True)
config.plugins.OpenUitzendingGemist.Npolivestreams = ConfigBoolean(default = False)


def wgetUrl(target):
	std_headers = {
		'User-Agent': 'Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.9.2.6) Gecko/20100627 Firefox/3.6.6',
		'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
		'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
		'Accept-Language': 'en-us,en;q=0.5',
	}
	outtxt = Request(target, None, std_headers)
	try:
		outtxt = urlopen2(target, timeout = 5).read()
	except (URLError, HTTPException, socket.error):
		return ''
	return outtxt

def wgetUrlRefer(target, refer):
	req = Request(target)
	req.add_header('Referer', refer)
	try:
		r = urlopen2(req)
		outtxt = r.read()
	except:
		outtxt = ''
	return outtxt

def wgetUrlCookie(target, cookie):
	req = Request(target)
	req.add_header('Cookie', cookie)
	try:
		r = urlopen2(req)
		outtxt = r.read()
	except:
		outtxt = ''
	return outtxt

def resolve_http_redirect(url, depth=0):
	if depth > 10:
		raise Exception("Redirected "+depth+" times, giving up.")
	o = urlparse.urlparse(url,allow_fragments=True)
	conn = httplib.HTTPConnection(o.netloc)
	path = o.path
	if o.query:
		path +='?'+o.query
	conn.request("HEAD", path)
	res = conn.getresponse()
	headers = dict(res.getheaders())
	if headers.has_key('location') and headers['location'] != url:
		return resolve_http_redirect(headers['location'], depth+1)
	else:
		return url

def Csplit(data, string, number = None):
	if string in data:
		data = data.split(string)
		if number != None:
			data = data[number]
	return data

def MPanelEntryComponent(channel, text, png):
	res = [ text ]
	res.append((eListboxPythonMultiContent.TYPE_TEXT, 200, 15, 800, 100, 0, RT_HALIGN_LEFT|RT_WRAP|RT_VALIGN_TOP, text))
	res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 10, 5, 150, 150, png))
	return res

class MPanelList(MenuList):
	def __init__(self, list, selection = 0, enableWrapAround=True):
		MenuList.__init__(self, list, enableWrapAround, eListboxPythonMultiContent)
		self.l.setFont(0, gFont("Regular", 18))
		self.l.setItemHeight(120)
		self.selection = selection

	def postWidgetCreate(self, instance):
		MenuList.postWidgetCreate(self, instance)
		self.moveToIndex(self.selection)

def getShortName(name, serviceref):
	if serviceref.flags & eServiceReference.mustDescent: #Directory
		pathName = serviceref.getPath()
		p = os.path.split(pathName)
		if not p[1]: #if path ends in '/', p is blank.
			p = os.path.split(p[0])
		return p[1].upper()
	else:
		return name

class UGMediaPlayer(Screen, InfoBarNotifications, InfoBarSeek):
	STATE_IDLE = 0
	STATE_PLAYING = 1
	STATE_PAUSED = 2

	skin = """<screen name="MediaPlayer" flags="wfNoBorder" position="0,380" size="720,160" title="Media player" backgroundColor="transparent">
		<ePixmap position="0,0" pixmap="skin_default/info-bg_mp.png" zPosition="-1" size="720,160" />
		<ePixmap position="29,40" pixmap="skin_default/screws_mp.png" size="665,104" alphatest="on" />
		<ePixmap position="48,70" pixmap="skin_default/icons/mp_buttons.png" size="108,13" alphatest="on" />
		<ePixmap pixmap="skin_default/icons/icon_event.png" position="207,78" size="15,10" alphatest="on" />
		<widget source="session.CurrentService" render="Label" position="230,73" size="360,40" font="Regular;20" backgroundColor="#263c59" shadowColor="#1d354c" shadowOffset="-1,-1" transparent="1">
			<convert type="ServiceName">Name</convert>
		</widget>
		<widget source="session.CurrentService" render="Label" position="580,73" size="90,24" font="Regular;20" halign="right" backgroundColor="#4e5a74" transparent="1">
			<convert type="ServicePosition">Length</convert>
		</widget>
		<widget source="session.CurrentService" render="Label" position="205,129" size="100,20" font="Regular;18" halign="center" valign="center" backgroundColor="#06224f" shadowColor="#1d354c" shadowOffset="-1,-1" transparent="1">
			<convert type="ServicePosition">Position</convert>
		</widget>
		<widget source="session.CurrentService" render="PositionGauge" position="300,133" size="270,10" zPosition="2" pointer="skin_default/position_pointer.png:540,0" transparent="1" foregroundColor="#20224f">
			<convert type="ServicePosition">Gauge</convert>
		</widget>
		<widget source="session.CurrentService" render="Label" position="576,129" size="100,20" font="Regular;18" halign="center" valign="center" backgroundColor="#06224f" shadowColor="#1d354c" shadowOffset="-1,-1" transparent="1">
			<convert type="ServicePosition">Remaining</convert>
		</widget>
		</screen>"""

	def __init__(self, session, service, seekable = False, pauseable = False, radio = False):
		Screen.__init__(self, session)
		self.skinName = "MoviePlayer"
		InfoBarNotifications.__init__(self)
		if seekable == True:
			InfoBarSeek.__init__(self)
		elif pauseable == True:
			InfoBarSeek.__init__(self)
		self.session = session
		self.service = service
		self.seekable = seekable
		self.pauseable = pauseable
		self.radio = radio
		self.screen_timeout = 3000
		self.__event_tracker = ServiceEventTracker(screen = self, eventmap =
			{
				iPlayableService.evStart: self.__serviceStarted,
				iPlayableService.evSeekableStatusChanged: self.__seekableStatusChanged,
				iPlayableService.evEOF: self.__evEOF,
			})
		self["actions"] = ActionMap(["OkCancelActions", "InfobarSeekActions", "MediaPlayerActions", "MovieSelectionActions"],
		{
				"ok": self.ok,
				"cancel": self.leavePlayer,
				"stop": self.handleLeave,
				"showEventInfo": self.showVideoInfo,
				"playpauseService": self.playpauseService,
			}, -2)
		self.hidetimer = eTimer()
		self.hidetimer.timeout.get().append(self.ok)
		self.returning = False
		self.state = self.STATE_PLAYING
		self.lastseekstate = self.STATE_PLAYING
		self.onPlayStateChanged = [ ]
		self.play()
		self.onClose.append(self.__onClose)

	def __seekableStatusChanged(self):
		if self.seekable == False:
			return
		self.show()
		self.__setHideTimer()
		if not self.isSeekable():
			self["SeekActions"].setEnabled(False)
			self.setSeekState(self.STATE_PLAYING)
		else:
			self["SeekActions"].setEnabled(True)

	def __onClose(self):
		self.session.nav.stopService()

	def __evEOF(self):
		self.handleLeave()

	def __setHideTimer(self):
		if self.radio == False:
			self.hidetimer.start(self.screen_timeout)

	def showInfobar(self):
		self.show()
		if self.radio:
			pass
		elif self.state == self.STATE_PLAYING:
			self.__setHideTimer()
		else:
			pass

	def hideInfobar(self):
		self.hide()
		self.hidetimer.stop()

	def ok(self):
		if self.shown:
			self.hideInfobar()
		else:
			self.showInfobar()

	def showVideoInfo(self):
		if self.shown:
			self.hideInfobar()

	def playService(self, newservice):
		if self.state != self.STATE_IDLE:
			self.stopCurrent()
		self.service = newservice
		self.play()

	def play(self):
		if self.state == self.STATE_PAUSED:
			if self.shown:
				self.__setHideTimer()
		self.state = self.STATE_PLAYING
		self.session.nav.playService(self.service)
		if self.shown:
			self.__setHideTimer()

	def playpauseService(self):
		if self.pauseable == False:
			return
		if self.state == self.STATE_PLAYING:
			self.pauseService()
		elif self.state == self.STATE_PAUSED:
			self.unPauseService()

	def pauseService(self):
		if self.pauseable == False:
			return
		if self.state == self.STATE_PLAYING:
			self.setSeekState(self.STATE_PAUSED)

	def unPauseService(self):
		if self.pauseable == False:
			return
		if self.state == self.STATE_PAUSED:
			self.setSeekState(self.STATE_PLAYING)

	def stopCurrent(self):
		self.session.nav.stopService()
		self.state = self.STATE_IDLE

	def __serviceStarted(self):
		self.state = self.STATE_PLAYING
		self.__seekableStatusChanged()

	def playagain(self):
		if self.state != self.STATE_IDLE:
			self.stopCurrent()
			self.play()

	def handleLeave(self):
		self.close()

	def leavePlayer(self):
		self.session.openWithCallback(self.leavePlayerOnExitCallback, MessageBox, _("Exit movie player?"), simple=True)

	def leavePlayerOnExitCallback(self, answer):
		if answer == True:
			self.handleLeave()

	def doEofInternal(self, playing):
		if not self.execing:
			return
		if not playing :
			return
		self.handleLeave()

	def lockShow(self):
		return

	def unlockShow(self):
		return

	def setSeekState(self, wantstate, onlyGUI = False):
		print "setSeekState"
		if wantstate == self.STATE_PAUSED:
			print "trying to switch to Pause- state:",self.STATE_PAUSED
		elif wantstate == self.STATE_PLAYING:
			print "trying to switch to playing- state:",self.STATE_PLAYING
		service = self.session.nav.getCurrentService()
		if service is None:
			print "No Service found"
			return False
		pauseable = service.pause()
		if pauseable is None:
			print "not pauseable."
			self.state = self.STATE_PLAYING
		if pauseable is not None:
			print "service is pausable"
			if wantstate == self.STATE_PAUSED:
				print "WANT TO PAUSE"
				pauseable.pause()
				self.state = self.STATE_PAUSED
				if not self.shown:
					self.hidetimer.stop()
					self.show()
			elif wantstate == self.STATE_PLAYING:
				print "WANT TO PLAY"
				pauseable.unpause()
				self.state = self.STATE_PLAYING
				if self.shown:
					self.__setHideTimer()
		for c in self.onPlayStateChanged:
			c(self.state)
		return True

class OpenUgConfigureScreen(Screen, ConfigListScreen):
	def __init__(self, session):
		self.skin = """
				<screen position="center,center" size="400,100" title="">
					<widget name="config" position="10,10"   size="e-20,e-10" scrollbarMode="showOnDemand" />
				</screen>"""
		self.session = session
		Screen.__init__(self, session)
		self.list = []
		ConfigListScreen.__init__(self, self.list, session = self.session)
		self["actions"] = ActionMap(["SetupActions"],
		{
			"ok": self.keyGo,
			"cancel": self.leavePlayer,
		}, -2)
		self["config"].list = self.list
		self.list.append(getConfigListEntry(_("Show pictures"), config.plugins.OpenUitzendingGemist.showpictures))
		self.list.append(getConfigListEntry(_("Show NPO livestreams"), config.plugins.OpenUitzendingGemist.Npolivestreams))
		self["config"].l.setList(self.list)
		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		self.setTitle(_("Open Uitzending Gemist options"))

	def keyGo(self):
		for x in self["config"].list:
			x[1].save()
		self.close()

	def leavePlayer(self):
		self.session.openWithCallback(self.leavePlayerOnExitCallback, MessageBox, _("Save settings?"), simple=True)

	def leavePlayerOnExitCallback(self, answer):
		if answer == True:
			self.keyGo()
		else:
			self.keyCancel()

	def keyCancel(self):
		for x in self["config"].list:
			x[1].cancel()
		self.close()

class OpenUgSetupScreen(Screen):
	def __init__(self, session):
		self.skin = """
				<screen position="center,center" size="400,450" title="">
					<widget name="menu" position="10,10"   size="e-20,e-130" scrollbarMode="showOnDemand" />
					<widget name="info" position="10,e-125" size="e-20,150" halign="center" font="Regular;22" />
				</screen>"""
		self.session = session
		Screen.__init__(self, session)
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("OK"))
		self.lastservice = session.nav.getCurrentlyPlayingServiceReference()
		self["actions"] = ActionMap(["SetupActions"],
		{
			"ok": self.keyGo,
			"cancel": self.keyCancel,
		}, -2)
		self.imagedir = '/tmp/openUgImg/'
		self["info"] = Label(_("Open Uitzending Gemist\n\nBased on Xtrend code"))
		self.mmenu= []
		self.mmenu.append((_("NPO Uitgelicht"), 'uitgelicht'))
		self.mmenu.append((_("NPO Popular"), 'pop'))
		self.mmenu.append((_("NPO Gemist"), 'ugback'))
		self.mmenu.append((_("RTL XL A-Z"), 'rtl'))
		self.mmenu.append((_("RTL XL Gemist"), 'rtlback'))
		self.mmenu.append((_("SBS6 Gemist"), 'sbs6'))
		self.mmenu.append((_("Veronica Gemist"), 'veronica'))
		self.mmenu.append((_("NET5 Gemist"), 'net5'))
		self.mmenu.append((_("Radio Gemist"), 'radio'))
		self.mmenu.append((_("InternetTV"), 'inetTV'))
		self.mmenu.append((_("Setup"), 'setup'))
		self["menu"] = MenuList(self.mmenu)
		self.onLayoutFinish.append(self.layoutFinished)

	def loadUrl(self, url, sub):
		try:
			lines = open(url).readlines()
			for x in lines:
				if sub in x.lower():
					return True
		except:
			return False
		return False

	def layoutFinished(self):
		self.setTitle('Open Uitzending Gemist')

	def keyGo(self):
		selection = self["menu"].l.getCurrentSelection()
		if selection is not None:
			if selection[1] == 'ugback' or selection[1] == 'rtlback' or selection[1] == 'radio' or selection[1] == 'inetTV':
				self.session.open(SmallScreen, selection[1])
			elif selection[1] == 'setup':
				self.session.open(OpenUgConfigureScreen)
			else:
				self.session.open(OpenUg, selection[1])

	def keyCancel(self):
		self.removeFiles(self.imagedir)
		if self.lastservice is not None:
			self.session.nav.playService(self.lastservice)
		self.close()

	def removeFiles(self, targetdir):
		import os
		for root, dirs, files in os.walk(targetdir):
			for name in files:
				os.remove(os.path.join(root, name))


class SmallScreen(Screen):
	def __init__(self, session, cmd):
		self.skin = """
				<screen position="center,center" size="400,400" title="">
					<widget name="menu" position="10,10"   size="e-20,e-10" scrollbarMode="showOnDemand" />
				</screen>"""
		self.session = session
		Screen.__init__(self, session)
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("OK"))
		self["actions"] = ActionMap(["SetupActions"],
		{
			"ok": self.keyGo,
			"cancel": self.keyCancel,
		}, -2)
		self.cmd = cmd
		self.mmenu = []
		self.ttitle = 'Error'
		if cmd == 'rtlback' or cmd == 'ugback':
			count = 0
			now = date.today()
			if cmd == 'rtlback':
				self.ttitle = "RTL Number of days back"
				while count < 15:
					if count == 0:
						self.mmenu.append((_("Today"), now.strftime('%Y%m%d')))
					else:
						self.mmenu.append(((now.strftime("%A")), now.strftime('%Y%m%d')))
					now = now - timedelta(1)
					count += 1
			elif cmd == 'ugback':
				self.ttitle = "NPO Number of days back"
				while count < 8:
					if count == 0:
						self.mmenu.append((_("Today"), count + 128))
					else:
						self.mmenu.append(((now.strftime("%A")), count + 128))
					now = now - timedelta(1)
					count += 1
		elif cmd == 'radio':
			self.ttitle = "Radio gemist"
			self.mmenu.append((_("Veronica"), 'Rver'))
			self.mmenu.append((_("Decibel"), 'Rdec'))
			self.mmenu.append((_("Internet radio"), 'Rinetradio'))
		elif cmd == 'inetTV':
			self.ttitle = "InternetTV"
			self.mmenu.append((_("Dumpert.nl"), 'dumpert'))
			self.mmenu.append((_("VKMag.com"), 'vkmag'))
			self.mmenu.append((_("Livestreams"), 'livestreams'))
		elif cmd == 'dumpert':
			self.ttitle = "Dumpert.nl"
			self.mmenu.append((_("Nieuw"), 'dumpert-nieuw'))
			self.mmenu.append((_("Toppers"), 'dumpert-toppers'))
		elif cmd == 'vkmag':
			self.ttitle = "vkmag.com"
			self.mmenu.append((_("Video's"), 'vkmagVid'))
		elif cmd == 'Rver':
			self.ttitle = "Radio Veronica"
			self.mmenu.append((_("highlights"), 'Rverhighlights'))
		elif cmd == 'Rdec':
			self.ttitle = "Radio Decibel"
			self.mmenu.append((_("Podcasts"), 'Rdecpodcast'))
		elif cmd == 'Rinetradio':
			self.ttitle = "Internet radio"
			self.mmenu.append((_("538 Party"), 'http://82.201.100.9:8000/WEB16_WEB_MP3', ''))
			self.mmenu.append((_("538 Hitzone"), 'http://82.201.100.10:8000/WEB11', ''))
			self.mmenu.append((_("538 NonStop40"), 'http://82.201.100.9:8000/juizefm', ''))
			self.mmenu.append((_("Radio 53L8"), 'http://82.201.100.10:8000/WEB21', ''))
			self.mmenu.append((_("Radio 2 Top 2000"), 'http://icecast.omroep.nl/radio2-top2000-aac', ''))
			self.mmenu.append((_("Radio 2 In Concert"), 'http://icecast.omroep.nl/radio2-inconcert-aac', ''))
			self.mmenu.append((_("3FM Alternative"), 'http://icecast.omroep.nl/3fm-alternative-aac', ''))
			self.mmenu.append((_("Slam! Hardstyle"), 'http://82.201.100.23:80/WEB17_Hardstyle_AAC', ''))
			self.mmenu.append((_("NERadio Hardstyle"), 'http://load.hardstyle.nu:443/', ''))
			self.mmenu.append((_("NERadio Sweden - Best of Techno & Trance"), 'http://bigbrother.dinmamma.be:8000', ''))
			self.mmenu.append((_("Q-Music Het Foute Non Stop"), 'http://vip2.str.reasonnet.com/streamfout.mp3.96', ''))
		elif cmd == 'livestreams':
			self.ttitle = "Live Streams"
			if config.plugins.OpenUitzendingGemist.Npolivestreams.value:
				self.mmenu.append((_("Nederland 1"), 'tvlive/ned1/ned1.isml/ned1.m3u8', 'npo'))
				self.mmenu.append((_("Nederland 2"), 'tvlive/ned2/ned2.isml/ned2.m3u8', 'npo'))
				self.mmenu.append((_("Nederland 3"), 'tvlive/ned3/ned3.isml/ned3.m3u8', 'npo'))
				self.mmenu.append((_("Politiek 24"), 'thematv/politiek24/politiek24.isml/politiek24.m3u8', 'npo'))
				self.mmenu.append((_("Journaal 24"), 'thematv/journaal24/journaal24.isml/journaal24.m3u8', 'npo'))
				self.mmenu.append((_("Humor TV 24"), 'thematv/humor24/humor24.isml/humor24.m3u8', 'npo'))
				self.mmenu.append((_("Holland Doc 24"), 'thematv/hollanddoc24/hollanddoc24.isml/hollanddoc24.m3u8', 'npo'))
				self.mmenu.append((_("Z@ppelin/ Zapp"), 'thematv/zappelin24/zappelin24.isml/zappelin24.m3u8', 'npo'))
				self.mmenu.append((_("Cultura 24"), 'thematv/cultura24/cultura24.isml/cultura24.m3u8', 'npo'))
				self.mmenu.append((_("Best 24"), 'thematv/best24/best24.isml/best24.m3u8', 'npo'))
				self.mmenu.append((_("101 TV"), 'thematv/101tv/101tv.isml/101tv.m3u8', 'npo'))
			else:
				self.mmenu.append((_("No streams avaible"), None))
		else:
			self.mmenu.append((_("Error..."), None))
		self["menu"] = MenuList(self.mmenu)
		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		if self.ttitle != '':
			self.setTitle(_(self.ttitle))

	def keyGo(self):
		selection = self["menu"].l.getCurrentSelection()
		if selection[1] == None:
			return
		if self.cmd == 'rtlback':
			self.session.open(OpenUg, ['rtlback', selection[1]])
		elif self.cmd == 'radio' or self.cmd == 'inetTV':
			self.session.open(SmallScreen, selection[1])
		elif self.cmd == 'livestreams':
			if selection[2] == 'npo':
				API_URL = 'http://ida.omroep.nl/aapi/?stream='
				BASE_URL = 'http://livestreams.omroep.nl/live/npo/'
				data = wgetUrl(API_URL+BASE_URL+selection[1])
				data = Csplit(data, "?hash=", 1)
				data = Csplit(data, '"', 0)
				if data != '':
					url = BASE_URL+selection[1]+'?hash='+data
					url = resolve_http_redirect(url, 3)
					myreference = eServiceReference(4097, 0, url)
					myreference.setName(selection[0])
					self.session.open(UGMediaPlayer, myreference)
			else:
				myreference = eServiceReference(4097, 0, selection[1])
				myreference.setName(selection[0])
				self.session.open(UGMediaPlayer, myreference, False, False, True)
		elif self.cmd == 'Rinetradio':
			myreference = eServiceReference(4097, 0, selection[1])
			myreference.setName(selection[0])
			self.session.open(UGMediaPlayer, myreference, False, False, True)
		else:
			self.session.open(OpenUg, selection[1])

	def keyCancel(self):
		self.close()

class OpenUg(Screen):

	UG_PROGDATE = 0
	UG_PROGNAME = 1
	UG_SHORT_DESCR = 2
	UG_CHANNELNAME = 3
	UG_STREAMURL = 4
	UG_ICON = 5
	UG_ICONTYPE = 6
	UG_LEVEL_ALL = 0
	UG_LEVEL_SERIE = 1
	UG_LEVEL_SEASON = 2
	MAX_PIC_PAGE = 5
	TIMER_CMD_START = 0
	TIMER_CMD_VKEY = 1
	UG_BASE_URL = "http://hbbtv.distributie.publiekeomroep.nl"
	HBBTV_UG_BASE_URL = UG_BASE_URL + "/nu/ajax/action/"
	RTL_BASE_URL = "http://www.rtl.nl/system/s4m/vfd/version=1/d=pc/output=json"
	SBS_BASE_URL = "http://plus-api.sbsnet.nl"
	EMBED_BASE_URL = "http://embed.kijk.nl/?width=868&height=488&video="
	DUMPERT_BASE_URL = "http://www.dumpert.nl"

	def __init__(self, session, cmd):
		self.skin = """
				<screen position="80,70" size="e-160,e-110" title="">
					<widget name="list" position="0,0" size="e-0,e-0" scrollbarMode="showOnDemand" transparent="1" zPosition="2"/>
					<widget name="thumbnail" position="0,0" size="150,150" alphatest="on" />
					<widget name="chosenletter" position="10,10" size="e-20,150" halign="center" font="Regular;30" foregroundColor="#FFFF00" />
				</screen>"""
		self.session = session
		Screen.__init__(self, session)
		self["thumbnail"] = Pixmap()
		self["thumbnail"].hide()
		self.title
		self.cbTimer = eTimer()
		self.cbTimer.callback.append(self.timerCallback)
		self.Details = {}
		self.pixmaps_to_load = []
		self.picloads = {}
		self.color = "#33000000"
		self.numericalTextInput = NumericalTextInput.NumericalTextInput(mapping=NumericalTextInput.MAP_SEARCH_UPCASE)
		self["chosenletter"] = Label("")
		self["chosenletter"].visible = False
		self.page = 0
		self.numOfPics = 0
		self.isRtlBack = False
		self.choice = []
		self.channel = ''
		self.level = self.UG_LEVEL_ALL
		self.cmd = cmd
		self.timerCmd = self.TIMER_CMD_START
		self.png = LoadPixmap(resolveFilename(SCOPE_PLUGINS, "Extensions/OpenUitzendingGemist/oe-alliance.png"))
		self.tmplist = []
		self.mediaList = []
		self.imagedir = "/tmp/openUgImg/"
		if (os_path.exists(self.imagedir) != True):
			os_mkdir(self.imagedir)
		self["list"] = MPanelList(list = self.tmplist, selection = 0)
		self.list = self["list"]
		self.updateMenu()
		self["actions"] = ActionMap(["WizardActions", "MovieSelectionActions", "DirectionActions"],
		{
			"up": self.key_up,
			"down": self.key_down,
			"left": self.key_left,
			"right": self.key_right,
			"ok": self.go,
			"back": self.Exit,
		}
		, -1)
		self["NumberActions"] = NumberActionMap(["NumberActions", "InputAsciiActions"],
			{
				"gotAsciiCode": self.keyAsciiCode,
				"0": self.keyNumberGlobal,
				"1": self.keyNumberGlobal,
				"2": self.keyNumberGlobal,
				"3": self.keyNumberGlobal,
				"4": self.keyNumberGlobal,
				"5": self.keyNumberGlobal,
				"6": self.keyNumberGlobal,
				"7": self.keyNumberGlobal,
				"8": self.keyNumberGlobal,
				"9": self.keyNumberGlobal
			})
		self.onLayoutFinish.append(self.layoutFinished)
		self.cbTimer.start(10)

	def keyNumberGlobal(self, number):
		unichar = self.numericalTextInput.getKey(number)
		charstr = unichar.encode("utf-8")
		if len(charstr) == 1:
			self.moveToChar(charstr[0], self["chosenletter"])

	def keyAsciiCode(self):
		unichar = unichr(getPrevAsciiCode())
		charstr = unichar.encode("utf-8")
		if len(charstr) == 1:
			self.moveToString(charstr[0], self["chosenletter"])

	def moveToChar(self, char, lbl=None):
		self._char = char
		self._lbl = lbl
		if lbl:
			lbl.setText(self._char)
			lbl.visible = True
		self.moveToCharTimer = eTimer()
		self.moveToCharTimer.callback.append(self._moveToChrStr)
		self.moveToCharTimer.start(1000, True) #time to wait for next key press to decide which letter to use...

	def moveToString(self, char, lbl=None):
		self._char = self._char + char.upper()
		self._lbl = lbl
		if lbl:
			lbl.setText(self._char)
			lbl.visible = True
		self.moveToCharTimer = eTimer()
		self.moveToCharTimer.callback.append(self._moveToChrStr)
		self.moveToCharTimer.start(1000, True) #time to wait for next key press to decide which letter to use...

	def _moveToChrStr(self):
		currentIndex = self["list"].getSelectionIndex()
		found = False
		if currentIndex < (len(self.mediaList) - 1):
			itemsBelow = self.mediaList[currentIndex + 1:]
			#first search the items below the selection
			for index, item in enumerate(itemsBelow):
				itemName = self.mediaList[index][self.UG_PROGNAME]
				if len(self._char) == 1 and itemName.startswith(self._char):
					found = True
					self["list"].moveToIndex(index)
					break
				elif len(self._char) > 1 and itemName.find(self._char) >= 0:
					found = True
					self["list"].moveToIndex(index)
					break
		if found == False and currentIndex > 0:
			itemsAbove = self.mediaList[1:currentIndex]
			#first item (0) points parent folder - no point to include
			for index, item in enumerate(itemsAbove):
				itemName = self.mediaList[index][self.UG_PROGNAME]
				if len(self._char) == 1 and itemName.startswith(self._char):
					found = True
					self["list"].moveToIndex(index)
					break
				elif len(self._char) > 1 and itemName.find(self._char) >= 0:
					found = True
					self["list"].moveToIndex(index)
					break
		self._char = ''
		if self._lbl:
			self._lbl.visible = False

	def layoutFinished(self):
		if self.title == None or self.title == '':
			self.setTitle("Open Uitzending Gemist")
		else:
			self.setTitle(self.title)

	def updatePage(self):
		if self.page != self["list"].getSelectedIndex() / self.MAX_PIC_PAGE:
			self.page = self["list"].getSelectedIndex() / self.MAX_PIC_PAGE
			self.loadPicPage()

	def key_up(self):
		self["list"].up()
		self.updatePage()

	def key_down(self):
		self["list"].down()
		self.updatePage()

	def key_left(self):
		self["list"].pageUp()
		self.updatePage()

	def key_right(self):
		self["list"].pageDown()
		self.updatePage()

	def getThumbnailName(self, x):
		if self.choice == 'rtl':
			if x[self.UG_ICON]:
				return ""
			else:
				return ""
		return str(x[self.UG_STREAMURL]) + str(x[self.UG_ICONTYPE])

	def updateMenu(self):
		self.tmplist = []
		if len(self.mediaList) > 0:
			pos = 0
			for x in self.mediaList:
				self.tmplist.append(MPanelEntryComponent(channel = x[self.UG_CHANNELNAME], text = (x[self.UG_PROGNAME] + '\n' + x[self.UG_PROGDATE] + '\n' + x[self.UG_SHORT_DESCR]), png = self.png))
				tmp_icon = self.getThumbnailName(x)
				thumbnailFile = self.imagedir + tmp_icon
				self.pixmaps_to_load.append(tmp_icon)
				if not self.Details.has_key(tmp_icon):
					self.Details[tmp_icon] = { 'thumbnail': None}
				if x[self.UG_ICON] != '':
					if (os_path.exists(thumbnailFile) == True):
						self.fetchFinished(True, picture_id = tmp_icon, failed = False)
					else:
						if config.plugins.OpenUitzendingGemist.showpictures.value:
							client.downloadPage(x[self.UG_ICON], thumbnailFile).addCallback(self.fetchFinished, tmp_icon).addErrback(self.fetchFailed, tmp_icon)
				pos += 1
			self["list"].setList(self.tmplist)

	def Exit(self):
		self.close()

	def clearList(self):
		elist = []
		self["list"].setList(elist)
		self.mediaList = []
		self.pixmaps_to_load = []
		self.page = 0

	def setupCallback(self, retval = None):
		self.retval = retval
		if retval == 'cancel' or retval is None:
			return

		if type(retval) == list:
			if retval[0] == 'sbs':
				self.title = retval[2]
				tmp = retval[1]
				self.clearList()
				self.choice = 'sbs'
				self.channel = retval[2]
				self.level = self.UG_LEVEL_SERIE
				self.sbsGetEpisodeList(self.mediaList, tmp)
				if len(self.mediaList) == 0:
					self.mediaProblemPopup()
				else:
					self.updateMenu()
			elif retval[0] == 'rtlseason':
				self.title = 'rtl seizoen'
				tmp = retval[1]
				self.clearList()
				self.choice = 'rtl'
				self.level = self.UG_LEVEL_SEASON
				self.getRTLMediaDataSeason(self.mediaList, tmp)
				if len(self.mediaList) == 0:
					self.mediaProblemPopup()
				else:
					self.updateMenu()
			elif retval[0] == 'rtlepisode':
				self.title = 'rtl aflevering'
				tmp = retval[1]
				Skey = retval[2]
				self.clearList()
				self.choice = 'rtl'
				self.level = self.UG_LEVEL_SERIE
				self.getRTLSerie(self.mediaList, tmp, Skey)
				if len(self.mediaList) == 0:
					self.mediaProblemPopup()
				else:
					self.updateMenu()
			elif retval[0] == 'rtlback':
				self.title = 'rtl'
				self.clearList()
				self.choice = 'rtl'
				self.isRtlBack = True
				self.level = self.UG_LEVEL_SERIE
				self.getRTLMediaDataBack(self.mediaList, retval[1])
				if len(self.mediaList) == 0:
					self.mediaProblemPopup()
				else:
					self.updateMenu()
			elif retval[0] == 'dumpert':
				if 'toppers' in retval[1]:
					self.title = retval[0] + '-toppers pagina' + retval[1].split('/')[2]
				else:
					self.title = retval[0] + '-nieuw pagina' + self.cmd[1].split('/')[1]
				self.clearList()
				self.choice = 'dumpert'
				self.level = self.UG_LEVEL_SERIE
				self.dumpert(self.mediaList, retval[1])
				if len(self.mediaList) == 0:
					self.mediaProblemPopup()
				else:
					self.updateMenu()
			elif retval[0] == 'Rdecpodcast':
				self.title = 'Radio Decibel Podcasts'
				self.clearList()
				self.choice = 'rdec'
				self.level = self.UG_LEVEL_SERIE
				self.rdec(self.mediaList, 'http://www.decibel.nl'+retval[1], True)
				if len(self.mediaList) == 0:
					self.mediaProblemPopup()
				else:
					self.updateMenu()
		elif retval == 'uitgelicht':
			self.title = "Open Uitzending Gemist NPO"
			self.clearList()
			self.level = self.UG_LEVEL_SERIE
			offset = 0
			while 1:
				self.getMediaData(self.mediaList, self.HBBTV_UG_BASE_URL + "must_see/offset/%d/numrows/24?XHRUrlAddOn=1" % (offset))
				if len(self.mediaList) == 0:
					self.mediaProblemPopup()
					break
				if offset + 24 != len(self.mediaList):
					break
				offset += 24
			self.updateMenu()
		elif retval == 'pop':
			self.title = "Open Uitzending Gemist NPO"
			self.clearList()
			self.level = self.UG_LEVEL_SERIE
			offset = 0
			while 1:
				self.getMediaData(self.mediaList, self.HBBTV_UG_BASE_URL + "popular/offset/%d/numrows/24?XHRUrlAddOn=1" % (offset))
				if len(self.mediaList) == 0:
					self.mediaProblemPopup()
					break
				if offset + 24 != len(self.mediaList):
					break
				offset += 24
			self.updateMenu()
		elif retval == 'rsearch':
			self.choice = 'rtl'
			self.timerCmd = self.TIMER_CMD_VKEY
			self.cbTimer.start(10)
		elif retval == 'rtl':
			self.title = retval
			self.clearList()
			self.choice = 'rtl'
			self.level = self.UG_LEVEL_ALL
			self.getRTLMediaData(self.mediaList, "/fun=az/fmt=smooth")
			if len(self.mediaList) == 0:
				self.mediaProblemPopup()
			else:
				self.updateMenu()
		elif retval == 'net5' or retval == 'sbs6' or retval == 'veronica':
			self.title = retval
			self.clearList()
			self.choice = 'sbs'
			self.channel = retval
			self.level = self.UG_LEVEL_ALL
			self.sbsGetProgramList(self.mediaList)
			if len(self.mediaList) == 0:
				self.mediaProblemPopup()
			else:
				self.updateMenu()
		elif retval == 'dumpert-nieuw':
			self.title = retval
			self.clearList()
			self.choice = 'dumpert'
			self.level = self.UG_LEVEL_SERIE
			self.dumpert(self.mediaList, "")
			if len(self.mediaList) == 0:
				self.mediaProblemPopup()
			else:
				self.updateMenu()
		elif retval == 'dumpert-toppers':
			self.title = retval
			self.clearList()
			self.choice = 'dumpert'
			self.level = self.UG_LEVEL_SERIE
			self.dumpert(self.mediaList, "/toppers/")
			if len(self.mediaList) == 0:
				self.mediaProblemPopup()
			else:
				self.updateMenu()
		elif retval == 'Rverhighlights':
			self.title = 'Radio Veronica highlights'
			self.clearList()
			self.choice = 'rver'
			self.level = self.UG_LEVEL_SERIE
			self.rver(self.mediaList, 'http://www.radioveronica.nl/gemist/highlights')
			if len(self.mediaList) == 0:
				self.mediaProblemPopup()
			else:
				self.updateMenu()
		elif retval == 'vkmagVid':
			self.title = "Vkmag Video's"
			self.clearList()
			self.choice = 'vkmagvideo'
			self.level = self.UG_LEVEL_SERIE
			self.vkmag(self.mediaList, 'http://www.vkmag.com/magazine/video_archive')
			if len(self.mediaList) == 0:
				self.mediaProblemPopup()
			else:
				self.updateMenu()
		elif retval == 'Rdecpodcast':
			self.title = 'Radio Decibel Podcasts'
			self.clearList()
			self.choice = 'rdec'
			self.level = self.UG_LEVEL_ALL
			self.rdec(self.mediaList, 'http://www.decibel.nl/radio/podcasts')
			if len(self.mediaList) == 0:
				self.mediaProblemPopup()
			else:
				self.updateMenu()
		else:
			self.title = "Open Uitzending Gemist NPO"
			if retval >= 128:
				retval -=  128
				now = int(time.time())
				worktime =  '%s' % (time.strftime("%H:%M:%S", time.localtime()))
				wtime = worktime.split(":")
				if int(wtime[0]) < 6:
					t = int(wtime[0]) + (24 - 6)
				else:
					t = int(wtime[0]) - 6
				t = (t * 3600) + int(wtime[1]) * 60 + int(wtime[2]) + 1
				startime = int(now - t)
				day = 3600 * 24
				if (retval > 0):
					day *= retval
					startime -= day
					now = startime + (3600 * 24)
				self.clearList()
				self.level = self.UG_LEVEL_SERIE
				offset = 0
				while 1:
					self.getMediaData(self.mediaList, self.HBBTV_UG_BASE_URL + "epg/timeStart/%d/timeEnd/%d/day/%d/offset/%d/numrows/24?XHRUrlAddOn=1" % (startime, now, retval, offset))
					if len(self.mediaList) == 0:
						self.mediaProblemPopup()
						break
					if offset + 24 != len(self.mediaList):
						break
					offset += 24
				self.updateMenu()
				return

	def timerCallback(self):
		self.cbTimer.stop()
		if self.timerCmd == self.TIMER_CMD_START:
			self.setupCallback(self.cmd)
		elif self.timerCmd == self.TIMER_CMD_VKEY:
			self.session.openWithCallback(self.keyboardCallback, VirtualKeyBoard, title = (_("Search term")), text = "")

	def keyboardCallback(self, callback = None):
		if callback is not None and len(callback):
			self.clearList()
			self.level = self.UG_LEVEL_SERIE
			if self.choice == 'rtl':
				self.getRTLSerie(self.mediaList, "search.php?q=*" + callback + "*")
				self.updateMenu()
			if len(self.mediaList) == 0:
				self.session.openWithCallback(self.close, MessageBox, _("No items matching your search criteria were found"), MessageBox.TYPE_ERROR, timeout=5, simple = True)
		else:
			self.close()

	def mediaProblemPopup(self):
		self.session.openWithCallback(self.close, MessageBox, _("There was a problem retrieving the media list"), MessageBox.TYPE_ERROR, timeout=5, simple = True)

	def fetchFailed(self, string, picture_id):
		self.fetchFinished(False, picture_id, failed = True)

	def fetchFinished(self, x, picture_id, failed = False):
		if failed:
			return
		else:
			thumbnailFile = self.imagedir + str(picture_id)
		sc = AVSwitch().getFramebufferScale()
		if (os_path.exists(thumbnailFile) == True):
			start = self.page * self.MAX_PIC_PAGE
			end  = (self.page * self.MAX_PIC_PAGE) + self.MAX_PIC_PAGE
			count = 0
			for x in self.mediaList:
				if count >= start and count < end:
					if self.getThumbnailName(x) == picture_id:
						self.picloads[picture_id] = ePicLoad()
						self.picloads[picture_id].PictureData.get().append(boundFunction(self.finish_decode, picture_id))
						self.picloads[picture_id].setPara((150, 150, sc[0], sc[1], False, 1, "#00000000"))
						self.picloads[picture_id].startDecode(thumbnailFile)
				count += 1
				if count > end:
					break
		else:
			self.pixmaps_to_load.append(picture_id)
			self.fetchFinished(False, picture_id, failed = True)

	def loadPicPage(self):
		self.Details = {}
		self.updateMenu()

	def finish_decode(self, picture_id, info):
		ptr = self.picloads[picture_id].getData()
		thumbnailFile = self.imagedir + str(picture_id)
		if ptr != None:
			if self.Details.has_key(picture_id):
				self.Details[picture_id]["thumbnail"] = ptr
		self.tmplist = []
		pos = 0
		for x in self.mediaList:
			if self.Details[self.getThumbnailName(x)]["thumbnail"] is not None:
				self.tmplist.append(MPanelEntryComponent(channel = x[self.UG_CHANNELNAME], text = (x[self.UG_PROGNAME] + '\n' + x[self.UG_PROGDATE] + '\n' + x[self.UG_SHORT_DESCR]), png = self.Details[self.getThumbnailName(x)]["thumbnail"]))
			else:
				self.tmplist.append(MPanelEntryComponent(channel = x[self.UG_CHANNELNAME], text = (x[self.UG_PROGNAME] + '\n' + x[self.UG_PROGDATE] + '\n' + x[self.UG_SHORT_DESCR]), png = self.png))
			pos += 1
		self["list"].setList(self.tmplist)

	def go(self):
		if len(self.mediaList) == 0 or self["list"].getSelectionIndex() > len(self.mediaList) - 1:
			return
		if self.choice == 'sbs':
			if self.level == self.UG_LEVEL_ALL:
				tmp = self.mediaList[self["list"].getSelectionIndex()][self.UG_STREAMURL]
				self.session.open(OpenUg, ['sbs' , tmp , self.channel])
			elif self.level == self.UG_LEVEL_SERIE:
				tmp = self.sbsGetMediaUrl(self.mediaList[self["list"].getSelectionIndex()][self.UG_STREAMURL])
				if tmp != '':
					myreference = eServiceReference(4097, 0, tmp)
					myreference.setName(self.mediaList[self["list"].getSelectionIndex()][self.UG_PROGNAME])
					self.session.open(UGMediaPlayer, myreference, False)
		elif self.choice == 'rtl':
			if self.level == self.UG_LEVEL_ALL:
				tmp = self.mediaList[self["list"].getSelectionIndex()][self.UG_STREAMURL]
				self.session.open(OpenUg, ['rtlseason' , tmp])
			elif self.level == self.UG_LEVEL_SEASON:
				tmp = self.mediaList[self["list"].getSelectionIndex()][self.UG_STREAMURL]
				self.session.open(OpenUg, ['rtlepisode' , tmp[0], tmp[1]])
			elif self.level == self.UG_LEVEL_SERIE:
				tmp = self.getRTLStream(self.mediaList[self["list"].getSelectionIndex()][self.UG_STREAMURL])
				if tmp != '':
					myreference = eServiceReference(4097, 0, tmp)
					myreference.setName(self.mediaList[self["list"].getSelectionIndex()][self.UG_PROGNAME])
					self.session.open(UGMediaPlayer, myreference, True, True)
				else:
					self.session.openWithCallback(self.close, MessageBox, _("Voor deze aflevering moet waarschijnlijk betaald worden."), MessageBox.TYPE_ERROR, timeout=5, simple = True)
		elif self.choice == 'dumpert':
			if self.mediaList[self["list"].getSelectionIndex()][self.UG_PROGNAME] == ' ---> Volgende Pagina':
				tmp = self.mediaList[self["list"].getSelectionIndex()][self.UG_STREAMURL]
				self.session.open(OpenUg, ['dumpert' , tmp])
				self.close()
			elif self.mediaList[self["list"].getSelectionIndex()][self.UG_PROGNAME] == ' <--- Vorige Pagina':
				tmp = self.mediaList[self["list"].getSelectionIndex()][self.UG_STREAMURL]
				self.session.open(OpenUg, ['dumpert' , tmp])
				self.close()
			else:
				tmp = self.getDumpertStream(self.mediaList[self["list"].getSelectionIndex()][self.UG_STREAMURL])
				if tmp != '':
					myreference = eServiceReference(4097, 0, tmp)
					myreference.setName(self.mediaList[self["list"].getSelectionIndex()][self.UG_PROGNAME])
					self.session.open(UGMediaPlayer, myreference, True, True)
		elif self.choice == 'rver':
			tmp = self.getRverStream(self.mediaList[self["list"].getSelectionIndex()][self.UG_STREAMURL])
			if tmp != '':
				myreference = eServiceReference(4097, 0, tmp)
				myreference.setName(self.mediaList[self["list"].getSelectionIndex()][self.UG_PROGNAME])
				self.session.open(UGMediaPlayer, myreference, True, True, True)
		elif self.choice == 'vkmagvideo':
			tmp = self.getvkmagStream(self.mediaList[self["list"].getSelectionIndex()][self.UG_STREAMURL])
			if tmp != '':
				myreference = eServiceReference(4097, 0, tmp)
				myreference.setName(self.mediaList[self["list"].getSelectionIndex()][self.UG_PROGNAME])
				self.session.open(UGMediaPlayer, myreference, True, True)
		elif self.choice == 'rdec':
			if self.level == self.UG_LEVEL_ALL:
				tmp = self.mediaList[self["list"].getSelectionIndex()][self.UG_STREAMURL]
				self.session.open(OpenUg, ['Rdecpodcast' , tmp])
			else:
				tmp = self.mediaList[self["list"].getSelectionIndex()][self.UG_STREAMURL]
				if tmp != '':
					myreference = eServiceReference(4097, 0, tmp)
					myreference.setName(self.mediaList[self["list"].getSelectionIndex()][self.UG_PROGNAME])
					self.session.open(UGMediaPlayer, myreference, True, True, True)
		else:
			self.doUGPlay()

	def doUGPlay(self):
		out = wgetUrl(self.UG_BASE_URL + "/nu/bekijk/context/bekijk_gemist/trm_id/%s?XHRUrlAddOn=1" % (self.mediaList[self["list"].getSelectionIndex()][self.UG_STREAMURL]))
		if out !='':
			url = ''
			tmp = out.split('\n')
			for x in tmp:
				if 'fetchLinkAndStart' in x:
					tmp =  x.split("('")[1].split("'")[0]
					tmp = wgetUrl(self.UG_BASE_URL + tmp)
					tmp = tmp.replace('\/', '/')
					url = tmp.split("stream_link\":\"")[1].split("\",")[0]
					break
			if url != '':
				myreference = eServiceReference(4097, 0, url)
				myreference.setName(self.mediaList[self["list"].getSelectionIndex()][self.UG_PROGNAME])
				self.session.open(UGMediaPlayer, myreference, False)

	def getRTLStream(self, url):
		uuid = url
		data = wgetUrl('http://www.rtl.nl/system/s4m/xldata/ux/'+ url +'?context=rtlxl&d=pc&fmt=adaptive&version=3')
		state = 0
		url = ''
		name = ''
		icon = ''
		tmp = '<component_uri>'
		if tmp in data:
			url = data.split(tmp)[1].split('</component_uri>')[0]
			url = 'http://pg.us.rtl.nl/rtlxl/network/ipad/progressive' + url + '.ssm/' + uuid + '.mp4'
			return url
		else:
			return ''

	def getRTLSerie(self, weekList, url, Skey):
		url = self.RTL_BASE_URL + '/ak='+ url +'/sk='+ Skey +'/pg=1'
		data = wgetUrl(url)
		tmp = '\"schedule\":'
		if tmp in data:
			data = data.split(tmp)
			scheduledata = data[1].split('},{')
			data = data[0]
		tmp = '\"material\":'
		if tmp in data:
			data = data.split(tmp)
			uuiddata = data[1].split('},{')
			data = data[0]
		tmp = '\"episodes\":'
		if tmp in data:
			data = data.split(tmp)
			episode = data[1].split('\"key\"')
			data = data[0]
		tmp = '\"seasons\":'
		if tmp in data:
			data = data.split(tmp)
			seasons = data[1].split('\"key\"')
			data = data[0]
		tmp = '\"abstracts\":'
		if tmp in data:
			data = data.split(tmp)
			abstract = data[1].split('\"key\"')
			data = data[0]
		state = 0
		name = ''
		short = ''
		icon = ''
		stream = ''
		date = ''
		channel = ''
		for line in episode:
			if state == 0:
				if "\"name\":" in line:
					state = 1
			if state == 1:
				tmp = "\"name\":\""
				if tmp in line:
					name = line.split(tmp)[1].split('"')[0]
				tmp = '\"synopsis\":\"'
				if tmp in line:
					short = line.split(tmp)[1].split('\"')[0]
				key = line.split('\"')[1]
				key = "\"episode_key\":\"" + key
				for line in uuiddata:
					if key in line and '\"classname\":\"uitzending\"' in line:
						tmp = "\"uuid\":\""
						if tmp in line:
							stream = line.split(tmp)[1].split('"')[0]
						tmp = '\"station\":\"'
						if tmp in line:
							channel = line.split(tmp)[1].split('\"')[0]
						tmp = '\"duration\":\"'
						if tmp in line:
							date = line.split(tmp)[1].split('\"')[0]
				icon_type = icon
				if stream != '':
					weekList.append((date, name, short, channel, stream, icon, icon_type, True))
				name = ''
				short = ''
				icon = ''
				stream = ''
				date = ''
				channel = ''
				state = 0

	def getRTLMediaDataSeason(self, weekList, url):
		data = wgetUrl(self.RTL_BASE_URL + '/fun=getseasons/ak=' + url)
		tmp = '\"schedule\":'
		if tmp in data:
			data = data.split(tmp)
			scheduledata = data[1].split('},{')
			data = data[0]
		tmp = '\"material\":'
		if tmp in data:
			data = data.split(tmp)
			uuiddata = data[1].split('},{')
			data = data[0]
		tmp = '\"episodes\":'
		if tmp in data:
			data = data.split(tmp)
			episode = data[1].split('\"key\"')
			data = data[0]
		tmp = '\"seasons\":'
		if tmp in data:
			data = data.split(tmp)
			seasons = data[1].split('\"key\"')
			data = data[0]
		tmp = '\"abstracts\":'
		if tmp in data:
			data = data.split(tmp)
			abstract = data[1].split('\"key\"')
			data = data[0]
		state = 0
		name = ''
		short = ''
		icon = ''
		stream = ''
		date = ''
		channel = ''
		for line in seasons:
			if state == 0:
				if "\"name\"" in line:
					state = 1
			if state == 1:
				stream = line.split('\"')[1].replace(' ','')
				tmp = ".png"
				icon_type = ''
				if tmp in line:
					tmp = "\"proglogo\":\""
					icon_type = icon
				tmp = '\"synopsis\":\"'
				if tmp in line:
					short = line.split(tmp)[1].split('\"')[0]
				tmp = '\"station\":\"'
				if tmp in line:
					channel = line.split(tmp)[1].split('\"')[0]
				tmp = '\"abstract_key\":\"'
				if tmp in line:
					stream = [(line.split(tmp)[1].split('\"')[0]) , stream]
				tmp = "\"name\":\""
				if tmp in line:
					name = line.split(tmp)[1].split('"')[0]
				weekList.append((date, name, short, channel, stream, icon, icon_type, True))
				state = 0

	def getRTLMediaData(self, weekList, url):
		data = wgetUrl(self.RTL_BASE_URL + url)
		data = data.split('\"key\"')
		state = 0
		name = ''
		short = ''
		icon = ''
		stream = ''
		date = ''
		channel = ''
		for line in data:
			if state == 0:
				if "\"name\"" in line:
					state = 1
			if state == 1:
				stream = line.split('\"')[1].replace(' ','')
				tmp = ".png"
				if tmp in line:
					tmp = "\"proglogo\":\""
					icon_type = icon
				tmp = '\"synopsis\":\"'
				if tmp in line:
					short = line.split(tmp)[1].split('\"')[0]
				tmp = '\"station\":\"'
				if tmp in line:
					channel = line.split(tmp)[1].split('\"')[0]
				tmp = "\"name\":\""
				if tmp in line:
					name = line.split(tmp)[1].split('"')[0]
				weekList.append((date, name, short, channel, stream, icon, icon_type, True))
				state = 0

	def getRTLMediaDataBack(self, weekList, days):
		url = self.RTL_BASE_URL + "/fun=catchup/pg=1/bcdate=%s/station=RTL4,RTL5,RTL7,RTL8" % (days)
		data = wgetUrl(url)
		tmp = '\"schedule\":'
		if tmp in data:
			data = data.split(tmp)
			scheduledata = data[1].split('},{')
			data = data[0]
		tmp = '\"material\":'
		if tmp in data:
			data = data.split(tmp)
			uuiddata = data[1].split('},{')
			data = data[0]
		tmp = '\"episodes\":'
		if tmp in data:
			data = data.split(tmp)
			episode = data[1].split('\"key\"')
			data = data[0]
		tmp = '\"seasons\":'
		if tmp in data:
			data = data.split(tmp)
			seasons = data[1].split('\"key\"')
			data = data[0]
		tmp = '\"abstracts\":'
		if tmp in data:
			data = data.split(tmp)
			abstract = data[1].split('\"key\"')
			data = data[0]
		state = 0
		name = ''
		short = ''
		icon = ''
		stream = ''
		date = ''
		channel = ''
		akey = ''
		ekey = ''
		for line in scheduledata:
			if state == 0:
				if "\"episode_key\":" in line:
					state = 1
			if state == 1:
				tmp = "\"episode_key\":\""
				if tmp in line:
					ekey = line.split(tmp)[1].split('"')[0]
				tmp = '\"station\":\"'
				if tmp in line:
					channel = line.split(tmp)[1].split('"')[0]
				if ekey != '':
					state = 2
			if state == 2:
				for line in episode:
					if ekey in line:
						tmp = "\"name\":\""
						if tmp in line:
							date = line.split(tmp)[1].split('"')[0]
						tmp = '\"synopsis\":\"'
						if tmp in line:
							short = line.split(tmp)[1].split('\"')[0]
				ekey = "\"episode_key\":\"" + ekey
				for line in uuiddata:
					if ekey in line:
						tmp = "\"uuid\":\""
						if tmp in line:
							stream = line.split(tmp)[1].split('"')[0]
						tmp = '\"duration\":\"'
						if tmp in line:
							date = (line.split(tmp)[1].split('\"')[0] + ' | ' + date)
						tmp = "\"abstract_key\":\""
						if tmp in line:
							akey = line.split(tmp)[1].split('"')[0]
				for line in abstract:
					if akey in line:
						tmp = "\"name\":\""
						if tmp in line:
							name = line.split(tmp)[1].split('"')[0]
				icon_type = icon
				weekList.append((date, name, short, channel, stream, icon, icon_type, True))
				state = 0

	def getMediaData(self, weekList, url):
		data = wgetUrl(url)
		state = 0
		short = ''
		name = ''
		date = ''
		stream = ''
		channel = ''
		icon = ''
		tmp = "<div class=\"vid\""
		i = data.count(tmp)
		j = 1
		data = data.split(tmp)
		while j<i:
			short = ''
			name = ''
			date = ''
			stream = ''
			icon = ''
			line = data[j]
			tmp = 'rel="'
			if tmp in line:
				stream = line.split(tmp)[1].split('"')[0]
			tmp = "<img class=\"vid_view\" src=\""
			if tmp in line:
				icon = line.split(tmp)[1].split("\" />")[0]
			tmp = "<p class=\"titleshort\">"
			if tmp in line:
				short = line.split(tmp)[1].split("</p>")[0]
			tmp = "<p class=\"title\">"
			if tmp in line:
				name = line.split(tmp)[1].split("</p>")[0]
			tmp = "<p class=\"date_time bottom\">"
			if tmp in line:
				date = line.split(tmp)[1].split("</p>")[0]
			if stream and date and name and short and icon:
				icon_type = self.getIconType(icon)
				weekList.append((date, name, short, channel, stream, icon, icon_type, False))
			j = j + 1

	def sbsGetProgramList(self, progList):
		out = wgetUrl('%s/stations/%s/pages/kijk' % (self.SBS_BASE_URL, self.channel))
		tmp = out.split('\\n')
		for x in tmp:
			name = ''
			date = ''
			stream = ''
			icon = ''
			icon_type = ''
			if '<li ><a href=\\\"javascript:SBS.SecondScreen.Utils.loadPage(\'kijkdetail?videoId=' in x:
				name = x.split('>')[2].split('<')[0]
				stream = x.split('>')[1].split('videoId=')[1].split('\'')[0]
				progList.append((date, name, '', '', stream, icon, icon_type, False))

	def sbsGetEpisodeList(self, episodeList, uid):
		out = wgetUrl('%s/stations/%s/pages/kijkdetail?videoId=%s' % (self.SBS_BASE_URL, self.channel, uid))
		data = out.split('\\n')
		name = ''
		date = ''
		stream = ''
		icon = ''
		icon_type = ''
		for x in data:
			tmp = '<a href=\\"javascript:SBS.SecondScreen.Utils.loadPage(\'kijkdetail?videoId='
			if tmp in x and '<li' not in x:
				stream = x.split(tmp)[1].split('\'')[0]
			tmp = '<p class=\\"program\\">'
			if tmp in x:
				name = x.split(tmp)[1].split('<')[0]
			tmp = '<img src=\\"'
			if tmp in x:
				icon = x.split(tmp)[1].split('\\\"')[0].replace('\\', '')
			if stream != '' and name != '' and icon != '':
				icon_type = self.getIconType(icon)
				episodeList.append((date, name, '', '', stream, icon, icon_type, False))
				name = ''
				date = ''
				stream = ''
				icon = ''
				icon_type = ''

	def sbsGetMediaUrl(self, uid):
		out = wgetUrlRefer('%s%s' % (self.EMBED_BASE_URL, uid), '%s/kijkframe.php?videoId=%sW&width=868&height=488' % (self.SBS_BASE_URL, uid))
		data = out.split('\n')
		myexp = ''
		id = ''
		key = ''
		vplayer = ''
		oldBW = '1'
		BW = ''
		stream = ''
		for x in data:
			tmp = '\"myExperience'
			if tmp in x:
				myexp = x.split(tmp)[1].split('\\')[0]
			tmp = 'param name=\\\"playerID\\\" value=\\\"'
			if tmp in x:
				id = x.split(tmp)[1].split('\\')[0]
			tmp = '<param name=\\\"playerKey\\\" value=\\\"'
			if tmp in x:
				key = x.split(tmp)[1].split('\\')[0]
			tmp = '<param name=\\\"@videoPlayer\\\" value=\\\"'
			if tmp in x:
				vplayer = x.split('<param name=\\\"@videoPlayer\\\" value=\\\"')[1].split('\\')[0]
		url = ''
		if myexp != '' and id != '' and key != '' and vplayer != '':
			target = "http://c.brightcove.com/services/viewer/htmlFederated?&width=868&height=488&flashID=myExperience%s&bgcolor=%%23FFFFFF&playerID=%s&playerKey=%s&isVid=true&isUI=true&dynamicStreaming=true&wmode=opaque&%%40videoPlayer=%s&branding=sbs&playertitle=true&autoStart=&debuggerID=&refURL=%s/kijkframe.php?videoId=%s&width=868&height=488" % (myexp, id, key, vplayer, self.SBS_BASE_URL, uid)
			out = wgetUrlRefer(target, '%s%s' % (self.EMBED_BASE_URL, uid))
			tmp = out.split('{')
			for x in tmp:
				if 'defaultURL\":' in x and 'defaultURL\":null' not in x:
					url = x.split('defaultURL\":\"')[1].split('\"')[0].replace('\\', '')
		return url

	def dumpert(self, mediaList, url):
		data = wgetUrlCookie(self.DUMPERT_BASE_URL + url, 'filter=video')
		data = Csplit(data, '<section id="content">',1)
		data = Csplit(data, '<div id="footcontainer">', 0)
		nexturl = ''
		prevurl = ''
		if '<li class="volgende">' in data:
			nexturl = data.split('<li class="volgende"><a href="')[1].split('"')[0]
		if '<li class="vorige">' in data:
			prevurl = data.split('<li class="vorige"><a href="')[1].split('"')[0]
			mediaList.append(('', ' <--- Vorige Pagina', '', '', prevurl, '', '', True))
		data = Csplit(data, '</ol>', 1)
		data = Csplit(data, '</a>')
		state = 0
		name = ''
		short = ''
		icon = ''
		stream = ''
		date = ''
		channel = ''
		for line in data:
			if state == 0:
				if 'class="dumpthumb"' in line:
					state = 1
			if state == 1:
				stream = line.split('<a href="')[1].split('"')[0]
				tmp = 'title="'
				if tmp in line:
					name = line.split(tmp)[1].split('"')[0]
				tmp = '<img src="'
				if tmp in line:
					icon = line.split(tmp)[1].split('"')[0]
					icon_type = icon
				tmp = '<date>'
				if tmp in line:
					date = line.split(tmp)[1].split('</date>')[0]
				tmp = '<p class="stats">'
				if tmp in line:
					date = date + ' | ' + line.split(tmp)[1].split('</p>')[0]
				tmp = '<p class="description">'
				if tmp in line:
					short = line.split(tmp)[1].split('</p>')[0]
				mediaList.append((date, name, short, channel, stream, icon, icon_type, True))
				state = 0
		mediaList.append(('', ' ---> Volgende Pagina', '', '', nexturl, '', '', True))

	def getDumpertStream(self, url):
		data = wgetUrl(url)
		url = ''
		data = Csplit(data, '<section id="content">', 1)
		data = Csplit(data, '<div id="commentscontainer">', 0)
		tmp = 'data-vidurl="'
		if tmp in data:
			url = data.split(tmp)[1].split('"')[0]
		return url

	def rver(self, mediaList, url):
		data = wgetUrl(url)
		data = Csplit(data, '<h5>Kies programma</h5>', 1)
		data = Csplit(data, '</ul>', 0)
		data = Csplit(data, '<li data-category="', )
		state = 0
		name = ''
		short = ''
		icon = ''
		stream = ''
		date = ''
		channel = ''
		for line in data:
			if state == 0:
				if '<a href="' in line:
					state = 1
			if state == 1:
				name = line.split('"')[0]
				stream = line.split('<a href="')[1].split('"')[0]
				tmp = '<li data-category="'
				if tmp in line:
					name = line.split(tmp)[1].split('"')[0]
				tmp = '<span class="datum">'
				if tmp in line:
					date = line.split(tmp)[1].split('</span>')[0]
				tmp = '<br />'
				if tmp in line:
					short = line.split(tmp)[1].split('</a>')[0]
				mediaList.append((date, name, short, channel, stream, icon, '', True))
				state = 0

	def getRverStream(self, url):
		data = wgetUrl('http://www.radioveronica.nl' + url)
		url = ''
		tmp = '<meta property="og:audio" content="'
		if tmp in data:
			url = data.split(tmp)[1].split('"')[0]
			if '.MP3' in url:
				return url
		data = Csplit(data, '</head>', 1)
		tmp = '<audio  src="'
		if tmp in data:
			url = data.split(tmp)[1].split('"')[0]
		return url

	def vkmag(self, mediaList, url):
		data = wgetUrl(url)
		data = Csplit(data, '<div class="archive">', 1)
		data = Csplit(data, '<h4>Zoeken</h4>', 0)
		data = Csplit(data, '</article>', )
		state = 0
		name = ''
		short = ''
		icon = ''
		stream = ''
		date = ''
		channel = ''
		for line in data:
			if state == 0:
				if '<a href="' in line:
					state = 1
			if state == 1:
				name = line.split('"')[0]
				stream = line.split('<a href="')[1].split('"')[0]
				tmp = 'alt="'
				if tmp in line:
					name = line.split(tmp)[1].split('"')[0]
				tmp = '<img src="'
				if tmp in line:
					icon = line.split(tmp)[1].split('"')[0]
				tmp = '<date>'
				if tmp in line:
					date = line.split(tmp)[1].split('</date>')[0]
				mediaList.append((date, name, short, channel, stream, icon, '', True))
				state = 0

	def getvkmagStream(self, url):
		data = wgetUrl(url)
		url = ''
		data = Csplit(data, "jwplayer('my-video').setup({", 1)
		tmp = "file: '"
		if tmp in data:
			url = data.split(tmp)[1].split("'")[0]
		return url

	def rdec(self, mediaList, url, podcast=False):
		data = wgetUrl(url)
		data = Csplit(data, '<div class="contentBlok">', 1)
		data = Csplit(data, '<div id="footerContent">', 0)
		if podcast == True:
			data = Csplit(data, '<a href="', )
		else:
			data = Csplit(data, '<div class="top">', )
		state = 0
		name = ''
		short = ''
		icon = ''
		stream = ''
		date = ''
		channel = ''
		for line in data:
			if state == 0:
				if '<a href="' in line and podcast == False:
					state = 1
				elif 'class="potscast"' in line and podcast == True:
					state = 1
			if state == 1:
				if podcast == False:
					stream = line.split('<a href="')[1].split('"')[0]
				elif podcast == True:
					stream = line.split('"')[0]
				name = line.split('</div>')[0]		
				tmp = '>&#8226;'
				if tmp in line:
					name = line.split(tmp)[1].split('</a>')[0]
				mediaList.append((date, name, short, channel, stream, icon, '', True))
				state = 0

	def getIconType(self, data):
		tmp = ".png"
		if tmp in data:
			return tmp
		tmp = ".gif"
		if tmp in data:
			return tmp
		tmp = ".jpg"
		if tmp in data:
			return tmp
		return ""

def main(session, **kwargs):
	session.open(OpenUgSetupScreen)

def Plugins(**kwargs):

	return [PluginDescriptor(name = "Open uitzending gemist", description = _("Watch uitzending gemist"), where = PluginDescriptor.WHERE_PLUGINMENU, icon="oe-alliance.png", fnc = main),
			PluginDescriptor(name = "Open uitzending gemist", description = _("Watch uitzending gemist"), where = PluginDescriptor.WHERE_EXTENSIONSMENU, fnc = main)]
