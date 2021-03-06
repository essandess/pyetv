import objc
import Foundation
import AppKit
from appscript import *
import time
import traceback

import PyFR.Utilities


CURRENT_RECORDING=None
verbose=0

def ensure_str(s):
    if isinstance(s, unicode):
        return s.encode("utf-8")
    return str(s)

def log(s,level=1):
    if verbose >= level:
        Foundation.NSLog( "%s: %@", "PyeTV", ensure_str(s))
    pass

class ETVChannel(PyFR.Utilities.ControllerUtilities):
    def __init__(self,chan):
        self.chan=chan

    def GetName(self):
        return str(self.chan.channel_number.get()) + " - " + self.chan.name.get()

    def Play(self):
        global CURRENT_RECORDING
        CURRENT_RECORDING=None
        try:
            log("Trying to play channel number %d" % self.chan.channel_number(),0)
            ETV.HideWindows()
            app("EyeTV").play()
            app("EyeTV").channel_change(channel_number = self.chan.channel_number())
        except:
            # recording? channnel is busy & can't be changed
            log(traceback.format_exc())
            app("EyeTV").player_windows()[0].show()
            pass
        ETV.EnterFullScreen()

    def GetProgramInfo(self):
        try:
            app("EyeTV").player_windows()[0].show()
            app("EyeTV").channel_change(channel_number = self.chan.channel_number())
            app("EyeTV").player_windows()[0].close()
            return False,app("EyeTV").player_windows()[0].program_info()
        except:
            # recording? channnel is busy & can't be changed
            try:
                info=app("EyeTV").player_windows()[0].program_info()
                return True, info
            except:
                # index [0] could be out of range if no tuner
                return False, {}

    def GetPreviewImagePath(self):
        return "/Applications/EyeTV.app/Contents/Resources/eyetv.icns"

class ETVRecording(PyFR.Utilities.ControllerUtilities):
    def __init__(self,rec):
        self.rec=rec

    def GetTitle(self):
        log("GetTitle called")
        try:
            ret=self.rec.title()
            return ret
        except:
            return ""

    def GetEpisode(self):
        log("GetEpisode called")
        try:
            ret = self.rec.episode()
        except:
            return ""
        log("GetEpisode done")
        return ret

    def GetPreviewImagePath(self):
        imgpath=""
        try:
            log("Get preview image path " + repr(self) + " " + repr(CURRENT_RECORDING))
            if self == CURRENT_RECORDING:
                fname=":tmp:screenshot.jpg"
                app("EyeTV").screenshot.set(fname)
                log("returning /tmp/screenshot.jpg")
                return "/tmp/screenshot.jpg"
            else:
                loc=self.rec.location()
                f=loc.file.path
                f=f[:-6]+"tiff"
                if len(f)>0:
                    imgpath=f
        except:
            pass
        log("returning " + imgpath.encode('ascii','replace'))
        return imgpath

    def GetStartTime(self):
        try:
            ret = self.rec.start_time()
            return ret.strftime("%b %d %I:%M%p")
        except:
            return ""

    def GetDate(self):
        try:
            return self.rec.start_time()
        except:
            return ""

    def GetEpisodeAndDate(self):
        try:
            return self.GetStartTime() + " " + self.GetEpisode() 
        except:
            return ""

    def ToStr(self,sec):
        log("ToStr called",2)
        shour = int(sec)/3600 # integer division
        smin = (sec - shour*3600)/60
        ret = "%d:%02d" % (shour, smin)
        log("ToStr done",2)
        return ret

    def GetPlaybackPosition(self, asString=False):
        log("GetPlaybackPosition called")
        try:
            ret=self.rec.playback_position()
        except:
            return ""
        if not asString:
            ret = ret
            return ret
        ret = self.ToStr(ret)
        log("GetPlaybackPosition done")
        return ret

    def GetDuration(self, asString=False):
        log("GetDuration called")
        try:
            ret=self.rec.actual_duration()
        except:
            return ""
        if not asString:
            ret = ret
            return ret
        ret = self.ToStr(ret)
        log("GetDuration done")
        return ret

    def GetDescription(self):
        log("GetDescription called")
        try:
            ret = self.rec.description()
        except:
            return ""
        log("GetDescription done")
        return ret

    def GetChannelStr(self):
        log("GetChannelStr called")
        try:
            ret = str(self.rec.channel_number())  + " " + self.rec.station_name()
        except:
            return ""
        log("GetChannelStr done")
        return ret

    def GetMarkerCount(self):
        log("GetMarkerCount called")
        try:
            return len(self.rec.markers())
        except:
            return 0


class EyeTV(PyFR.Utilities.ControllerUtilities):
    def __init__(self):
        self.deletion_list=[]

    def SweepDeleted(self):
        log("SweepDeleted")
        for r in self.deletion_list:
            app("EyeTV").delete(r)

    def GetRecordings(self):
        log("GetRecordings called")
        for i in range(1,10):  
            recs=app("EyeTV").recordings()
            if len(recs)>0:
                break
            time.sleep(1)
        retval=[]
        for r in recs:
            if r not in self.deletion_list:
                retval.append(ETVRecording(r))
        log("GetRecordings done")
        return retval

    def GetRecordingsDict(self):
        log("in getrecordingsdict")
        series_dict={}
        rec=self.GetRecordings()
        log("Got %d recordings" % len(rec))
        for r in rec:
            title=r.GetTitle()
            series_dict[title]=[]

        for r in rec:
            title=r.GetTitle()
            series_dict[title].append(r)
        return series_dict

    def GetChannels(self):
        log("GetChannels called")
        for i in range(1,10):  
            chan=app("EyeTV").channels()
            if len(chan)>0:
                break
            time.sleep(1)
        retval=[]
        for c in chan:
            if c.enabled():
                retval.append(ETVChannel(c))
        log("GetChannels done")
        return retval


    def GetFavoriteChannels(self):
        log("GetFavoriteChannels called")
        chan=[]
        try:
            chan=app("EyeTV").current_favorites_list().channels()
        except:
            return []
        retval=[]
        for c in chan:
            if c.enabled():
                retval.append(ETVChannel(c))
        log("GetFavoriteChannels done")
        return retval

    def IsPlaying(self):
        log("IsPlaying called")
        try:
            ret=app("EyeTV").playing()
            log("got ret" + str(ret))
        except:
            return false
        log("IsPlaying done")
        return ret

    def IsPaused(self):
        return not self.IsPlaying()

    def NotShowingMenu(self):
        log("NotShowingMenu called")
        ret=app("EyeTV").full_screen_menu()
        return not ret

    def ShowingMenu(self):
        log("ShowingMenu called")
        ret=app("EyeTV").full_screen_menu()
        return ret

    def IsFullScreen(self):
#        log("IsFullScreen called")
        ret=app("EyeTV").full_screen()
#        log("IsFullScreen done")
        return ret
        
    def EnterFullScreen(self):
        log("EnterFullScreen called")
        # - It is a requirement to be in full screen mode before leaving this function
        #   otherwise the ReturnToFrontRow in PyeTV.py make get executed before
        #   EyeTV ever even gets in to full screen mode
        count=0
        while (self.IsFullScreen()==False):
            app("EyeTV").enter_full_screen()
            if not self.IsFullScreen():
                count+=1
                if count>40: # bail out after 10 seconds
                    break
                time.sleep(0.25) # give it time to happen

        log("EnterFullScreen done")
        
    def HideMenu(self):
        app("EyeTV").full_screen_menu.set(False)
        app("EyeTV").stop()  # pause/stop any playback
                

    def Stop(self):
        app("EyeTV").stop()

    def ShowMenu(self):
        log("ShowMenu called")
        app("EyeTV").full_screen_menu.set(True)
        self.EnterFullScreen()
        log("ShowMenu done")

    def ShowGuide(self):
        log("ShowGuide called")
        self.HideWindows()
        app("EyeTV").play()
        self.EnterFullScreen()
        app("EyeTV").full_screen_menu.set(True)
        #time.sleep(0.25) # give it time to happen
        app("System Events").keystroke("g",using=k.command_down)
        log("ShowGuide done")

    def HideWindows(self):
        try:
           log("ETV: in HideWindows")
           app("EyeTV").controller_window.hide()
           app("EyeTV").programs_window.hide()
           wins=app("EyeTV").player_windows()
           for w in wins:
               log("ETV closing window %s" % str(w))
               w.hide()
               w.close()
        except:
            pass

    def DeleteRecording(self,rec):
        app("EyeTV").stop()
        app("EyeTV").player_windows.close()
        #self.deletion_list.append(rec.rec)
        app("EyeTV").delete(rec.rec)


    def PlayRecording(self,rec,fromBeginning):
        global CURRENT_RECORDING
        CURRENT_RECORDING=rec
        log("PlayRecording called to play recording %s%s" % (rec.GetTitle(), rec.GetEpisodeAndDate()),0)
        app("EyeTV").play(rec.rec)
        app("EyeTV").play() # necessary if recording is paused
        if fromBeginning:
            self.JumpTo(0)
        count=0
        while self.IsPlaying()==False:
            app("EyeTV").play(rec.rec)
            if not self.IsPlaying():
                count+=1
                if count>40: # bail out after 10 seconds
                    break
                time.sleep(0.25) # give it time to happen

        log("Recording is playing")    
        self.EnterFullScreen()
        log("PlayRecording done")

        log("Taking opportunity to sweep deleted recordings")
        self.SweepDeleted()
        return True

    def JumpTo(self,position):
        log("JumpTo called")
        app("EyeTV").jump(to=position)
        log("JumpTo done")

    def IsRecording(self):
        log("IsRecording called")
        return app("EyeTV").is_recording()

    def RecordingChannelName(self):
        if not self.IsRecording():
            return None
        return app("EyeTV").current_channel()


    # this was only used to update the screenshot of the current recording
    # while the window was still open.  it's no longer really used b/c we
    # the screenshot is automatically updated in the .eyetvr file when the
    # window is closed, and we are now closing the window now after
    # returning to PyeTV
    def UpdateScreenShot(self):
        try:
            app("EyeTV").screenshot.set(":tmp:screenshot.jpg")
            pass
        except:
            pass



ETV=EyeTV()

