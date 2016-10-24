#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#    Copyright (C) 2016 Edison Yau (gedisony@gmail.com)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#

# this addon runs 3 threads. 
# 1.) worker thread you see here handles searching for images on web and put list of images into a queue
#     it uses scrapers in resources.lib.scrapers to do the search
# 2.) bggslide(screens.py) thread checks the queue and assigns images into image controls 
#     it spawns the animator thread. 
# 3.) animator(screens.py) thread animates the image controls.  

import random
import os, sys
import urlparse
#import pprint

from datetime import datetime, timedelta

if sys.version_info >= (2, 7):
    import json
else:
    import simplejson as json

import xbmc
import xbmcaddon
#import xbmcvfs
import re
import urllib
#import csv
#import resources.lib.requests_cache 

import threading
from Queue import Queue, Empty, Full

reload(sys)
sys.setdefaultencoding("utf-8")

addon = xbmcaddon.Addon()
ADDON_NAME = addon.getAddonInfo('name')
ADDON_ID   = addon.getAddonInfo('id')
ADDON_PATH = addon.getAddonInfo('path')

PROFILE_DIR=xbmc.translatePath("special://profile/addon_data/"+ADDON_ID)
CACHE_FILE=xbmc.translatePath(PROFILE_DIR+"/requests_cache")

facts_queue=Queue(maxsize=4)

#on a fresh install, the profile path is not yet created. Kodi will do this for our addon (after a user saves a setting)
#  the user will get an error because we cannot create our cache.sqlite file. 
#  we create it  
if not os.path.exists(PROFILE_DIR):
    os.makedirs(PROFILE_DIR)
    #resources.lib.requests_cache.install_cache( CACHE_FILE, backend='memory' )  #will create a cache in memory
    #log('using memory for requests_cache file')
 
#no need to install requests cache because searches have a unique id          
#resources.lib.requests_cache.install_cache(CACHE_FILE, backend='sqlite', expire_after=604800 )  #cache expires after 7 days

SEARCH_TEMPLATE=addon.getSetting("search_template")
SEARCH_TEMPLATE2=addon.getSetting("search_template2")

FILTER_URL  =addon.getSetting("filter_url")
FILTER_TITLE=addon.getSetting("filter_title")

try:
    search_no_music_interval=int( addon.getSetting("search_no_music_interval") )
except:
    search_no_music_interval=10

def cycle(iterable):
    saved = []
    for element in iterable:
        yield element
        saved.append(element)
    while saved:
        for element in saved:
            yield element

#load search templates for no audio
na=[]
for i in range(1,7) :
    na.append( addon.getSetting("search_no_music%d" %i) )    

na=filter(bool, na)     #remove empty strings
NO_AUDIO_SEARCH=cycle(na)   #search templates for when no audio playing. addon will cycles through them (for variety)

def start(arg1, arg2):
    from resources.lib.screens import bggslide
    #from resources.lib.scrapers import bulbgarden, boardgamegeek

    ev = threading.Event()

    log(' starting music duck go')

    #testing code
    
#    from resources.lib.scrapers import duckduckgo_image
#    ddg=duckduckgo_image()
#    ddg.get_images('aa')
#
#    return

#    from resources.lib.scrapers import songbpm_com
#    s=songbpm_com()
#    bpm=s.get_bpm( 'xanadu', 'olivia newton john' )
#    log( repr( bpm ))
#    return

    #if not xbmc.Player().isPlayingAudio():
    #    xbmc.executebuiltin('XBMC.Notification("%s","%s")' %(  'No music is playing', 'Exiting')  )
    #    return

    work_q = Queue()
    
    from resources.lib.scrapers import google_image, duckduckgo_image
    #bg=google_image()  #google is abandoned. because. limit 100 api search per day. each api search only returns 10. 
    bg=duckduckgo_image()   
    t = Worker(work_q, facts_queue, bg)
    s= bggslide(ev,facts_queue,t)

    #t.daemon = True
    t.start()
 
    xbmc.sleep(5000) #give the worker a headstart

    try:
        s.start_loop()
    except Exception as e: 
        log("  EXCEPTION slideshow:="+ str( sys.exc_info()[0]) + "  " + str(e) )    

    s.close()
    del s
    #sys.modules.clear()

    log('    main done')
    t.join()

def action(arg1, arg2):
    
    cache_file=CACHE_FILE + '.sqlite'  #requests cache automatically adds .sqlite to its cache file
    addon.setSetting('clear_cache_file_result', '')
    
    if os.path.exists(cache_file):
        #log('cache file exists ' + cache_file )
        
        os.remove( cache_file )
        xbmc.sleep(2000)
        
        if not os.path.exists(cache_file):
            set_clear_cache_file_result(localize(32305))
            log('  delete cache file success' )
        else:
            log('  delete cache file failed' )
    else:
        log('cache file NOT exist ' + cache_file)
        set_clear_cache_file_result(localize(32306))
        
    pass

def set_clear_cache_file_result(value):
    setSetting('clear_cache_button', value)

def setSetting(setting_id, value):
    addon.setSetting(setting_id, value)
    pass
    
class ExitMonitor(xbmc.Monitor):
    def __init__(self, exit_callback):
        self.exit_callback = exit_callback

#     def onScreensaverDeactivated(self):
#         self.exit_callback()

    def abortRequested(self):
        self.exit_callback()

class Worker(threading.Thread):
    last_playing_song=''
    no_audio_counter=0
    last_no_audio_search=datetime(2016, 10, 20, 11, 29, 54)   
    def __init__(self, q_in, q_out, slide_info_generator):
        threading.Thread.__init__(self)
        self.q_out = q_out
        self.q_in=q_in
        #self.ev=ev
        self.exit_monitor = ExitMonitor(self.stop)
        self.watchdog=20
        self.slide_info_generator=slide_info_generator
        #log('  p-init ' + str( self.work_list ))

    def stop(self):
        log('    #stop called')
        self.running=False
        self.exit_monitor = None

    def run(self):
        self.running = True
        while self.running:
            #log('    #worker thread ping')
            try:
                if self.q_out.full():
                    self.watchdog-=1
                    self.wait(3000)
                    #log('      #watchdog: %.2d output_queuesize(%.2d)' %(self.watchdog, self.q_out.qsize() ) )
                else:
                    self.do_work()
                    self.watchdog=40
                    #log('    #job processed %d %d' %(self.q_out.qsize(),self.watchdog ) )
                    self.wait(8000)
                
            except Empty:  #input queue is enpty. 
                # Allow other stuff to run
                self.wait(1000)
                
            except Full:  #Queue.Full
                self.watchdog-=1
                
            except Exception as e:
                log("    #worker EXCEPTION:="+ str( sys.exc_info()[0]) + "  " + str(e) )
            
            if self.watchdog<1:
                #failsafe machanism to prevent a worker thread running indefinitely
                log('    #worker thread self-terminating ')
                self.running=False

        log('    #worker thread done')

    def join(self, timeout=None):
        self.running=False
        log('    #join')
        super(Worker, self).join(timeout)
        
    def do_work(self):
        self.generate_slide_for_music()

    def get_bpm(self, song_title, artist):
        from resources.lib.scrapers import songbpm_com
        s=songbpm_com()
        bpm=s.get_bpm( song_title, artist )
        return bpm


    def generate_slide_for_music(self):
        thumbs=[]

        if xbmc.Player().isPlayingAudio():
            #log('audio is playing ' )
            song_title=xbmc.Player().getMusicInfoTag().getTitle()
            song_artist=xbmc.Player().getMusicInfoTag().getArtist()
            song_album=xbmc.Player().getMusicInfoTag().getAlbum()
            total_time=xbmc.Player().getTotalTime()
            play_time=xbmc.Player().getTime()
            
            song_title=remove_parens(song_title)  #some song with parenthesis gives very few results
            #response = xbmc.executeJSONRPC ( '{"jsonrpc":"2.0", "method":"Player.GetItem", "params":{"playerid":0, "properties":["artist", "musicbrainzartistid"]},"id":1}' )
            #artist_names = _json.loads(response).get( 'result', {} ).get( 'item', {} ).get( 'artist', [] )
            #mbids = _json.loads(response).get( 'result', {} ).get( 'item', {} ).get( 'musicbrainzartistid', [] )
            
            #song_file=xbmc.Player().getPlayingFile() #this returns something like 'musicdb://singles/499.mp3?singles=true' . not useful for getting song title
            #log('   Title:' + song_title ) 
            #log('  Artist:' + xbmc.Player().getMusicInfoTag().getArtist() )
            #log('    File:' + repr( xbmc.Player().getPlayingFile()  ) ) 
            #log('    time: %d %d' %(total_time, play_time))
            if self.last_playing_song==song_title:
                #log('    #playing the same song:' + self.last_playing_song) 
                if  abs( (total_time/2) - play_time ) < 5 : #we need to have the worker cycle faster or give tolerance for where the halfway point is 
                    log('  #song at halfway-point')
                    self.q_out.put( { 'factlet_type' : "music_status:half", 
                                          'title'        : song_title ,
                                          'artist'       : song_artist ,
                                          'album'        : song_album ,
                                    } )
            else:
                self.last_playing_song=song_title
                self.search_thumbs_to_queue( song_title, song_artist, song_album  )
                
        else:
            #log('    #audio is not playing ')    
            between_last_search_mins = (datetime.now() - self.last_no_audio_search).total_seconds() / 60
            #log('   #time delta ' + repr( between_last_search_mins ) + "cycle interval="  + repr(search_no_music_interval ))
            if between_last_search_mins > search_no_music_interval:
                log('    #doing no-audio search')
                self.search_thumbs_to_queue( pages=2 )
                self.last_no_audio_search=datetime.now()
    
    
    def search_thumbs_to_queue(self, song_title='', song_artist='', song_album='', pages=1):
        
        song_artist_search='art'
        if song_title:
            #various artist changed to just 'song'
            if 'various' in song_artist.lower(): 
                song_artist_search='song'
            else:
                song_artist_search=song_artist
                
            bpm=self.get_bpm(song_title,song_artist )                            

            search_string=SEARCH_TEMPLATE.format(title=song_title, artist=song_artist_search, album=song_album).strip()
        else:
            #NO_AUDIO_SEARCH should not be too specific as to return less than 40 images. otherwise SEARCH_TEMPLATE2 will be tried.
            #search_string=NO_AUDIO_SEARCH.strip() + ' ' + str( random.randint(0,100) )  #just to return a randomized result
            search_string=NO_AUDIO_SEARCH.next()
            search_string=search_string.format(random100=random.randint(0,100)).strip()
            bpm=0
           
        try:
            thumbs=self.slide_info_generator.get_images( search_string, pages )
            log('  #%d images' %len(thumbs) )
            if len(thumbs) < 40:
                #search again using alternate search string (this does not take into account wether music is playing or not
                search_string=SEARCH_TEMPLATE2.format(title=song_title, artist=song_artist_search, album=song_album).strip()
                log('    #+ alternate search string:' + search_string)
                thumbs.extend( self.slide_info_generator.get_images( search_string ) )
                
            thumbs = remove_dict_duplicates( thumbs, 'src')
            
            thumbs = process_filter( thumbs )
            #thumbs.extend( self.slide_info_generator.get_images( search_string, '&start=10' )  )
            self.q_out.put( { 'factlet_type' : "musicthumbs", 
                              "images"       : thumbs , 
                              'title'        : song_title ,
                              'artist'       : song_artist ,
                              'album'        : song_album ,
                              'bpm'          : bpm,
                             } )
        except:
            #read timeout
            self.last_playing_song=''
            raise
                            

    def wait(self, sleep_msec):
        # wait in chunks of 500ms to react earlier on exit request
        chunk_wait_time = 500 
        remaining_wait_time = sleep_msec   
        while remaining_wait_time > 0:
            if self.running == False:
                log('wait aborted')
                return
            if remaining_wait_time < chunk_wait_time:
                chunk_wait_time = remaining_wait_time
            remaining_wait_time -= chunk_wait_time
            xbmc.sleep(chunk_wait_time)

def process_filter( thumbs_dict ):
    #log('  #filtering')
    
    a = [thumb for thumb in thumbs_dict if not excluded_by( FILTER_TITLE, thumb.get('title') )  ]
    a = [thumb for thumb in           a if not excluded_by(   FILTER_URL, thumb.get('src') )  ]
    
    return a

def excluded_by( filter, str_to_check):
    #log( '      #exclude filter:' +str(filter))
    #log( '      #exclude check:' +str_to_check)
    if filter:
        filter_list=filter.split(',')
        #filter_list=[x.lower().strip() for x in filter_list]  #  list comprehensions
        #log( '    exclude filter:' +str(filter_list))
        
        #if str_to_check.lower() in filter_list:
        #    return True
        
        matches=[f for f in filter_list if f in str_to_check.lower()]
        if matches:
            log( '      #excluded_by match:' + repr(matches) + ' ' + repr(str_to_check))
            return True
        
    return False

def remove_dict_duplicates(list_of_dict, key):
    seen = set()
    return [x for x in list_of_dict if [ x.get(key) not in seen, seen.add(  x.get(key) ) ] [0]]

def remove_parens(string_with_parens):
    regex = re.compile(".*?\((.*?)\)")
    return re.sub(r'\([^)]*\)', '', string_with_parens)  #re.findall(regex, string_with_parens)[0]        

def localize(id):
    return addon.getLocalizedString(id).encode('utf-8')

def log(message, level=xbmc.LOGNOTICE):
    xbmc.log(ADDON_ID+":"+message, level=level)

if __name__ == '__main__':
    if len(sys.argv) > 1: 
        params=dict( urlparse.parse_qsl(sys.argv[1]) )
        #log("sys.argv[1]="+sys.argv[1]+"  ")        
    else: params={}

    mode   = params.get('mode', '')
    arg1    = params.get('arg1', '')
    arg2    = params.get('arg2', '') 
    
#    log("----------------------")
#    log("params="+ str(params))
#    log("mode="+ mode)
#    log("arg1="+ arg1) 
#    log("arg2="+ arg2)
#    log("-----------------------")
    
    if mode=='':mode='start'  #default mode is to list start page (index)

    script_modes = {'start'                 : start,
                    #'build_index_file'      : build_index_file,
                    'action'                : action
                    }

    script_modes[mode](arg1,arg2)
