# PyeTV
# 
# Copyright 2008 Jon A Christopher. All rights reserved.

import os, time

# PyFR imports
from PyFR.BackRow import *
import PyFR.AppLauncherController
import PyFR.Appliance 
import PyFR.MenuController
import PyFR.Utilities
import PyFR.Debugging
import PyFR.OptionDialog
import Foundation

# PyeTV imports
from PyeTVMetaData import *
from PyeTVWaitController import *
from etv import ETV

from translate import tr


verbose=0

def log(s,level=1):
    if verbose >= level:
        Foundation.NSLog( u"%s: %@", "PyeTV", s )
    pass


SERIES_LABEL=tr("Recordings by Series")

class RecordingsMenu(PyFR.MenuController.Menu):
    def GetRightText(self):
        return str(len(self.items))

class SeriesMenu(PyFR.MenuController.Menu):
    def GetRightText(self):
        return str(len(self.items)-1)

################################################################################
# Work around EyeTV bug:
#
# When EyeTV is showing Live TV, and "menu" is pressed to return to front row
# it (unfortunately) "remembers" that live tv was playing and tries to re-open
# a live tv window after Front Row exits, even though we've closed the window.
#
# Therefore, we have to install this "Cleaner" thread which waits until after
# Front Row is no longer visible to close all windows.
#
# When we exit Front Row, we don't want EyeTV windows open.

import threading
CleanerShouldHideWindow=False
class Cleaner ( threading.Thread ):
    def run ( self ):
        global CleanerShouldHideWindow

        self.shouldHide=False
        fr = BRAppManager.sharedApplication().delegate()

        while(1):
            time.sleep(0.5)
            if CleanerShouldHideWindow and not fr.uiVisible():
                # by user requests; let's hide all EyeTV windows before we leave the appliance
                ETV.HideWindows()
                ETV.SweepDeleted()
                CleanerShouldHideWindow=False


################################################################################

class ETVMenuController(PyFR.MenuController.MenuController):
    inEyeTV=0   # On starting EyeTV, this flag is set

    # ReturnToFrontRow
    # - The etv class guarantees that EyeTV has entered full screen mode
    #   on playing a recording, viewing the guide, etc, so all this needs to
    #   do is check if EyeTV has left full screen mode which would be due to the
    #   user hitting the menu remote button, or escape key on the keyboard
    def ReturnToFrontRow(self):
        if self.inEyeTV==1 and ETV.IsFullScreen()==False:
            log("Exited EyeTV full screen mode, return to FrontRow");
            self.inEyeTV=0
            return True
        return False
    
    def AppRunning(self, appname):
        process = os.popen("ps xc | grep %s" % appname).read()
        if process:
            return True
        return False

    def GetRecordingMetadata(self, controller, rec):
        ret=PyeTVPreviewMetadataController.alloc().initWithRecording_(rec)
        return ret

    def GetRecordingMetadataFromTuple(self, controller, rec):
        ret=PyeTVPreviewMetadataController.alloc().initWithRecording_(rec[0])
        return ret

    def GetSeriesMetadata(self, controller, series):
        #log(u"requested preview for series %s" % series)
        if series not in self.series_dict.keys():
            return None
        ret=PyeTVPreviewMetadataController.alloc().initWithSeriesEpisode_(self.series_dict[series][0])
        return ret

    def GetChannelMetadata(self, controller, channel):
        #log(u"requested preview for channel %s" % str(channel))
        ret=PyeTVPreviewMetadataController.alloc().initWithChannel_(channel)
        return ret

    def MakeSeriesMenu(self):
        root=RecordingsMenu(SERIES_LABEL, [],  self.GetSeriesMetadata)
        log("recordings menu now has %d items" % len(root.items))
        self.series_dict=series=ETV.GetRecordingsDict()
        k=series.keys()
        k.sort()
        for s in k:
            submenu=SeriesMenu(s, [], self.GetSeriesMetadata)
            root.AddItem(submenu)

            # sort by date
            series_episodes={}
            for ep in series[s]:
                series_episodes[ep.GetDate()]=ep
            date_keys=series_episodes.keys();
            date_keys.sort()
            for epdate in date_keys:
                ep=series_episodes[epdate]
                epstr=ep.GetEpisodeAndDate()
                item=PyFR.MenuController.MenuItem(epstr, self.RecordingOptionsMenu, ep, self.GetRecordingMetadata, True)
                submenu.AddItem(item)
            item=PyFR.MenuController.MenuItem(tr("Delete All"),self.ConfirmDeleteRecordingDialog, series[s], None, True)
            submenu.AddItem(item)
        return root

    def MakeChannelsMenu(self):
        chan=ETV.GetChannels()
        root=PyFR.MenuController.Menu(tr("All Channels"),[])
        if not chan:
            return root
        for c in chan:
            chstr=c.GetName()
            item=PyFR.MenuController.MenuItem(chstr, self.PlayChannel, c, self.GetChannelMetadata, False)
            root.AddItem(item)
        return root

    def MakeFavoriteChannelsMenu(self):
        chan=ETV.GetFavoriteChannels()
        root=PyFR.MenuController.Menu(tr("Favorite Channels"),[])
        if not chan:
            return root
        for c in chan:
            chstr=c.GetName()
            item=PyFR.MenuController.MenuItem(chstr, self.PlayChannel, c, self.GetChannelMetadata, False)
            root.AddItem(item)
        return root

    def ConfirmDeleteRecordingDialog(self, controller, rec):
        #log("in confirm delete recordings dialog")
        options=[ PyFR.OptionDialog.OptionItem(tr("Yes"),rec), 
                  PyFR.OptionDialog.OptionItem(tr("No"),rec) ]
        if isinstance(rec,list):
            title=tr("Are you sure you want to delete %d recordings from %s?") % (len(rec),rec[0].GetTitle())
            dlg=PyFR.OptionDialog.OptionDialog.alloc().initWithTitle_Items_Handler_(tr("Delete Recording(s):"), options, self.ConfirmDeleteRecordingDialogHandler)
            dlg.setPrimaryInfoText_withAttributes_(title,BRThemeInfo.sharedTheme().promptTextAttributes())
        else:
            title=tr("Are you sure you want to delete") + "'" + rec.GetTitle()+ ": " + rec.GetEpisode() + " " + rec.GetStartTime() + "' ?"
            dlg=PyFR.OptionDialog.OptionDialog.alloc().initWithTitle_Items_Handler_(tr("Delete Recording(s):"), options, self.ConfirmDeleteRecordingDialogHandler)
            dlg.setPrimaryInfoText_withAttributes_(title,BRThemeInfo.sharedTheme().promptTextAttributes())
        ret=controller.stack().pushController_(dlg)
        return ret

    def ConfirmDeleteRecordingDialogHandler(self, controller, idx, item):
        log("ConfirmDeleteRecordingDialogHandler")
        rec=item.data
        if idx!=0:
            return True

        if isinstance(rec,list):
            currentSeries=rec[0].GetTitle()
            for r in rec:
                ETV.DeleteRecording(r)
        else:
            currentSeries=rec.GetTitle()
            ETV.DeleteRecording(rec)
                
        # now, re-build menu tree
        self.updateMainMenu()

        # if the series still exists, back up that far
        for item in self.series_menu.items:
            if item.page_title==currentSeries:
                con=PyFR.MenuController.MenuController.alloc().initWithMenu_(item)
                controller.stack().replaceControllersAboveLabel_withController_(SERIES_LABEL,con)
                return False

        # series is gone, back up to EyeTV menu
        con=PyFR.MenuController.MenuController.alloc().initWithMenu_(self.series_menu)
        controller.stack().replaceControllersAboveLabel_withController_("EyeTV",con)
        return False

    def RecordingOptionsMenuHandler(self, controller, data):
        log("in RecordingOptionsMenuHandler")
        try:
            rec=data[0]
            idx=data[1]
        except:
            return

        log("Got idx: %s rec %s" % (repr(idx), repr(rec).encode("ascii","replace")))
        if idx==0 or idx==1:
            fn=lambda : ETV.PlayRecording(rec,idx==1)
            self.inEyeTV = 1
            newCon=PyeTVWaitController.alloc().initWithStartup_exitCond_(fn,self.ReturnToFrontRow)
            ret=controller.stack().pushController_(newCon)
            return ret
        if idx==2:
            return self.ConfirmDeleteRecordingDialog(controller, rec)
        if idx==3:
            if self.AppRunning("ComSkipper"):
                os.system("/usr/bin/killall ComSkipper &")
                self.CurrentOptionsMenu.ds.menu.items[3].layer.setTitle_(tr("ComSkipper                     [Off]")) # deep magic
            else:
                os.system("/Library/Application\ Support/ETVComskip/ComSkipper.app/Contents/MacOS/ComSkipper &")
                self.CurrentOptionsMenu.ds.menu.items[3].layer.setTitle_(tr("ComSkipper                      [On]")) # deep magic
            #time.sleep(0.5)

        if idx==4:
            log("/Library/Application\ Support/ETVComskip/MarkCommercials.app/Contents/MacOS/MarkCommercials --log %s &" % rec.rec.unique_ID.get())
            os.system("/Library/Application\ Support/ETVComskip/MarkCommercials.app/Contents/MacOS/MarkCommercials --log %s &" % rec.rec.unique_ID.get())

        # if we return true, we'll pop the controller and back up past the option dialog
        return False

    def GetRecordingOptionsMenu(self, rec):
        items= [
            PyFR.MenuController.MenuItem(tr("Play"),   self.RecordingOptionsMenuHandler, (rec, 0), self.GetRecordingMetadataFromTuple),
            PyFR.MenuController.MenuItem(tr("Restart"), self.RecordingOptionsMenuHandler, (rec, 1), self.GetRecordingMetadataFromTuple),
            PyFR.MenuController.MenuItem(tr("Delete"),   self.RecordingOptionsMenuHandler, (rec, 2), self.GetRecordingMetadataFromTuple)
            ]
        
        if self.HasETVComskip:
            comskip_state=tr("ComSkipper                      [Off]")
            if self.AppRunning("ComSkipper"):
                comskip_state=tr("ComSkipper                      [On]")
            items.append(PyFR.MenuController.MenuItem(comskip_state,   self.RecordingOptionsMenuHandler, (rec, 3), self.GetRecordingMetadataFromTuple))
            if rec.GetMarkerCount()==0:
                mc_state="Mark Commercials"
                if self.AppRunning("MarkCommercials"):
                    mc_state=tr("Mark Commercials    [Running]")
                items.append(PyFR.MenuController.MenuItem(mc_state, self.RecordingOptionsMenuHandler, (rec, 4), self.GetRecordingMetadataFromTuple))

        menu=PyFR.MenuController.Menu(rec.GetTitle(), items)
        dlg=PyFR.MenuController.MenuController.alloc().initWithMenu_(menu)
        self.CurrentOptionsMenu = dlg
        return dlg

    def RecordingOptionsMenu(self, controller, rec):
        log("in recording options dialog")
        dlg=self.GetRecordingOptionsMenu(rec)
        ret=controller.stack().pushController_(dlg)
        return ret

    # WaitController startup callback
    def PlayChannel(self, controller, chan):
        self.inEyeTV = 1
        newCon=PyeTVWaitController.alloc().initWithStartup_exitCond_(chan.Play,self.ReturnToFrontRow)
        ret=controller.stack().pushController_(newCon)
        return ret

    # WaitController startup callback
    def StartETVGuide(self, controller, arg):
        log("in StartETVGuide")
        self.inEyeTV = 1
        newCon=PyeTVWaitController.alloc().initWithStartup_exitCond_(ETV.ShowGuide,self.ReturnToFrontRow)        
        ret=controller.stack().pushController_(newCon)
        return ret

    # re-create series menu tree and sub it into the main menu
    def updateMainMenu(self):
        self.series_menu=self.MakeSeriesMenu()
        self.MainMenu.items[0]=self.series_menu


    def StartEyeTV(self):
        if self.AppRunning("EyeTV"):
            return
        ETV.GetRecordings()

    def init(self):
        self.HasETVComskip = os.path.exists("/Library/Application Support/ETVComskip/ComSkipper.app") and \
                             os.path.exists("/Library/Application Support/ETVComskip/MarkCommercials.app")

        log("Initing recordings")
        self.series_menu=self.MakeSeriesMenu()
        log("Initing menus")
        self.MainMenu=PyFR.MenuController.Menu("EyeTV",
                  [
                self.series_menu,
                self.MakeFavoriteChannelsMenu(),
                self.MakeChannelsMenu(),
                PyFR.MenuController.MenuItem(tr("Program Guide"), self.StartETVGuide),
                ])

        # chain to parent's ctor
        ac=PyFR.MenuController.MenuController.initWithMenu_(self,self.MainMenu)
        log("Done initing menus",2)
        return ac

    def willBePushed(self):
        global CleanerShouldHideWindow
        CleanerShouldHideWindow =  False
        
    def willBePopped(self):
        global CleanerShouldHideWindow
        log("ETVMenuController willBePopped")
        CleanerShouldHideWindow = True 
        return BRMediaMenuController.willBePopped(self)

class RUIPyeTVAppliance( PyFR.Appliance.Appliance ):
    def initialize(cls):
        name =  u"com.apple.frontrow.appliance.PyeTV"
        BRFeatureManager.sharedInstance().enableFeatureNamed_( name )

    @classmethod
    def className(cls):
        # This more sophisticated method doesn't seem to be necessary!
        #  
        # clsName =  cls.__name__
        # backtrace = BRBacktracingException.backtrace()
        # range = backtrace.rangeOfString_( "_loadApplianceInfoAtPath:" )
        # if range.location == Foundation.NSNotFound and cls.sanityCheck == False:
        #    range = backtrace.rangeOfString_( "(in BackRow)" )
        #    cls.sanityCheck = True
        # if range.location != Foundation.NSNotFound:
        #    clsName =  "RUIMoviesAppliance"
        # return clsName

        return "RUIMoviesAppliance"

    def getController(self):
        self.log("************ PyeTV Starting **********************************")
        Cleaner().start() # init clean up thread 

        # Optionally enable ObjC logging now
        #a=PyFR.Utilities.ControllerUtilities();
        #a.enableObjCCapture() # call this to to enable flushing cache!

        # Or, turn on logging to /tmp/msgSends while /tmp/FRLOG exists
        #PyFR.Debugging.EnableObjcLogger()

        emc=ETVMenuController.alloc()
        emc.StartEyeTV() # make sure EyeTV is started before we try to use it
        ret=emc.init()
        return ret
