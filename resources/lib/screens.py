#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#     Original Work Copyright (C) 2013 Tristan Fischer (sphere@dersphere.de)
#     Modified Work Copyright (C) 2016 Edison Yau (gedisony@gmail.com)
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

import random, math
import sys
import threading
import Queue

import xbmc, xbmcaddon
from xbmcgui import ControlImage, WindowXMLDialog, ControlTextBox, ControlLabel, ListItem, Window

from screensaver import log, cycle

import pprint

import PIL

reload(sys)
sys.setdefaultencoding("utf-8")

addon = xbmcaddon.Addon()

ADDON_PATH = addon.getAddonInfo('path')

CHUNK_WAIT_TIME = 250
ACTION_IDS_EXIT = [9, 10, 13, 92]
ACTION_IDS_PAUSE = [12,68,79,229]   #ACTION_PAUSE = 12  ACTION_PLAY = 68  ACTION_PLAYER_PLAY = 79   ACTION_PLAYER_PLAYPAUSE = 229

class LockedSet(set):
    """ http://stackoverflow.com/questions/13610654/how-to-make-built-in-containers-sets-dicts-lists-thread-safe """

    def __init__(self, *args, **kwargs):
        self._lock = threading.RLock()
        super(LockedSet, self).__init__(*args, **kwargs)

    def add(self, elem):
        with self._lock:
            super(LockedSet, self).add(elem)

    def remove(self, elem):
        with self._lock:
            super(LockedSet, self).remove(elem)

    def discard(self, elem):
        with self._lock:
            super(LockedSet, self).discard(elem)
    
    def clear(self):
        with self._lock:
            super(LockedSet, self).clear()

#def set_remove( visible_controls_set, elem ):
#    log('    func removing {}'.format(elem))
#    visible_controls_set.remove(elem)

class ctl_animator(threading.Thread):
    screen_w=1280
    screen_h=720
    GROUP_ID=100  #in the xml file. this is the groupcontrol where all images are on
    grid_positions=[]
    temp_list=[]  #temporary list for keeping track of control ids (for swap sequences)

    beat_patterns=[
                   [ [4,15],[3,16],[2,17],[1,18],[0,19],[5,14],[9,10] ],
                   [ [0,5,14,19],[1,6,13,18],[2,7,12,17],[3,8,11,16],[4,9,10,15] ],
                   [ [0,6,12,18],[1,7,13,19],[2,8,14],[3,9],[4],[15],[10,16],[5,11,17] ],
                   [ [0,2,4,6,8,10,12,14,16,18,],[1,3,5,7,9,11,13,15,17,19] ],
                   [ [0,5,10,15], [1,6,11,16], [2,7,12,17],[3,8,13,18],[4,9,14,19],[3,8,13,18], [2,7,12,17], [1,6,11,16] ],
                   [ [0,1,2,3,4],[10,11,12,13,14],[5,6,7,8,9],[15,16,17,18,19], ],  
                   [ [0],[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12],[13],[14],[15],[16],[17],[18],[19], ],
                   ]
    
    def __init__(self, window, image_control_ids, visible_controls_set ):
        threading.Thread.__init__(self)
        self.window=window
        self.controls_cycle=cycle(image_control_ids)
        self.image_control_ids=image_control_ids
        self.visible_controls_set=visible_controls_set           # a list of control id's that are visible
        self.group_ctl=self.window.getControl( self.GROUP_ID )
        self.exit_monitor = ExitMonitor(self.stop)
        
        self.define_grid_positions(5,4) #divide the screen into 5x4 grid 

    def define_grid_positions(self, rows=5, cols=4):
        #populates the 5x4 grid used by many animation methods 
        x_units = int( self.screen_w / rows )
        y_units = int( self.screen_h / cols )

        for y in range(0,cols):
            for x in range(0,rows):
                x_pos= x * x_units 
                y_pos= y * y_units 
                self.grid_positions.append( ( x_pos, y_pos ) )
        #log( pprint.pformat(self.grid_positions ) )

    def run(self):
        log('@animator thread start ' + repr(self.image_control_ids))    
        try:
            self.running = True
            while self.running:    #while not self.monitor.abortRequested():
                
                #log('  @control ids:' + repr(self.image_control_ids))    
                msec_per_image=2000
                
                option, f=random.choice(self.animation_functions)
                #option, f=self.animation_functions[13]
                #option, f=self.animation_functions[2]  
                #option, f=self.animation_functions[11]  #swap grid random
                #option, f=self.animation_functions[12]  #grid_zoom_pan
                #f=self.test; option='once'
                
                #log('  @animation: ' + repr( f ) ) 
                
                if option=='r': ctl_ids=reversed(self.image_control_ids)
                else:           ctl_ids=self.image_control_ids
                
                if option=='u': animation_time=30000;msec_per_image=5000      #make animation time same #used for star wars-like slide to horizon
                else:           animation_time=random.randint( 10000, 20000 ) #will make some images move faster
                
                if option=='once': #for animations that manipulate the canvas or use all controls at once (short time)
                    f(self, control_id=0, delay=0, time=random.randint(  10000, 20000 ) )
                    #self.wait(15000)

                elif option=='onceb': #for animations that animate all controls (long time)  e.g.: grid-beats
                    f(self, control_id=0, delay=0, time=50000 )

                else:
                    #fly images one at a time. 
                    for id in ctl_ids:
                        #log( repr(id) )
                        f(self, id, 0, animation_time )
                        self.wait(msec_per_image)

        except Exception:
            self.log( '  @' + repr(sys.exc_info()) )
                            
        log('@animator thread DONE' )                             

        
    def stop(self):
        log('    @stop')
        self.running=False           

    def join(self, timeout=None):
        self.running=False
        log('    @join')
        super(ctl_animator, self).join(timeout)

    def wait(self, sleep_msec):
        chunk_wait_time = 500 
        remaining_wait_time = sleep_msec   
        while remaining_wait_time > 0:
            if self.running == False:
                #log('  @wait aborted')
                return
            if remaining_wait_time < chunk_wait_time:
                chunk_wait_time = remaining_wait_time
            remaining_wait_time -= chunk_wait_time
            
            xbmc.sleep(chunk_wait_time)
            #xbmc.Monitor().waitForAbort( chunk_wait_time/1000  )
    
    def random_grid_out_animations(self, delay, time, additional_animation=[] ):
        
        #add a slow fade animation to all images after beats done 
        self.apply_animation_to_all_controls( [animation_format( delay,    0, 'zoom',  70,70,      '',    '','auto','' ),     #maintain zoom size so that transition won't be abrupt
                                               animation_format( delay, time, 'fade', 100, 0, 'cubic', 'out' ),],
                                               10
                                              )
        
        self.vis_ctl_remove_all()
        
    def test(self, style, control_id, delay, time):
        log('  running test animation method')
        #get some controls out of the way
#        img_ctl_b=self.window.getControl( 114 ); img_ctl_b.setVisible(False)
#        img_ctl_b=self.window.getControl( 120 ); img_ctl_b.setVisible(False)
#
#        control_id=102
#        self.slide_control_to_grid( control_id, 1, 0, 1000, [animation_format(    500, 1000,    'zoom',  100, 70,   'sine', 'in','auto','' ),],True)
#        #self.slide_control_to_grid( 114, 5, 0, 2000)
#        #img_ctl=self.window.getControl( control_id )
#        #
#
#        bpm=120
#        
#        msec_bpm      = 60000/bpm
#        half_msec_bpm = 30000/bpm
        

        self.arrange_all_controls_to_grid()
        xbmc.sleep(2000)

        x_pos, y_pos = self.grid_positions[5]
        end='{},{}'.format(x_pos, y_pos )
        end='{},{}'.format(1280, 200 )
        #log( end )
        #'0,0'
        #'0,240'
        #'0,480'
        xbmc.sleep(4000)
        
        
        #self.group_ctl.setAnimations( [ animation_format( 0, 2000, 'slide', '0,0',end,      '',    '','auto','' ) ] )
        
        #self.swap_control_positions(1, 19 )
        
        self.running=False
        pass
    
    def swap_control_positions(self, grid_index_a, grid_index_b, delay=0, time=2000, tween='cubic', easing='inout'):
        
        ctl_id_a=self.temp_list[ grid_index_a ]
        ctl_id_b=self.temp_list[ grid_index_b ]
        
        extra_animation=[animation_format(    0, 0,    'zoom',  70, 70,   'sine', 'in','auto','' ),]
        self.slide_control_to_grid( ctl_id_a, grid_index_b, delay, time, extra_animation ,True, tween, easing)
        self.slide_control_to_grid( ctl_id_b, grid_index_a, delay, time, extra_animation ,True, tween, easing)

        #keep a note of which controls were swapped
        self.temp_list[grid_index_a], self.temp_list[grid_index_b] = self.temp_list[grid_index_b], self.temp_list[grid_index_a]


    def rotate_animation(self, style, control_id, delay, time):

        img_ctl=self.window.getControl( control_id )
        img_w=320  #int(image_dict.get('width'))
        img_h=320  #int(image_dict.get('height'))
        half_img=int(img_w/2)
        ANIMATION=[]

        pos_or_neg=['','-']
        pn=random.choice(pos_or_neg)        
        rand_x_pos=random.randint(  0, (self.screen_w-img_w) )

        smallest_x_no_crop= int( self.screen_w*0.165 )  #about 210  #any lower and the image will crop when rotated
        start_x=random.choice([smallest_x_no_crop, 700])
        #log('    control ' + repr(control_id) + ' position '  +repr(smallest_x_no_crop) + ',' + repr( rand_y_pos)    )
        
        if style=='tower': 
            #need to limit how far from the screen center the image starts for tower. if it is too fat, it will crop when the image rotates 'near' the user 
            rand_y_pos=random.randint( (-1*half_img), (self.screen_h-half_img)) 
            img_ctl.setPosition(start_x, rand_y_pos)
            center='640,40'
        elif style=='cyclone':
            #cyclone animation depends on center being "auto". it has weird computation. 
            #   if image is near the top it will look like it is spinning. the further down the y position is, the bigger the 'cyclone' radius 
            rand_y_pos=random.randint( 0, (self.screen_h/2)) + random.randint( 0, (self.screen_h/2))
            img_ctl.setPosition(rand_x_pos, rand_y_pos)
            center='auto'
        
        ANIMATION.extend( [
                           animation_format( 0, time, 'rotatey',   360,  0,   'linear', None, center,'loop=true' ),
                           #animation_format( time, 2000, 'fade',   100,  0,   'quadratic',  'in', '','' ),
                           #animation_format( 0   , 2000, 'fade',     0,100,   'quadratic', 'out', '','' ),
                           ] )

        ANIMATION.extend( fade_in_out_animation(0,time,2000) )
        
        self.vis_ctl_add(control_id)
        img_ctl.setAnimations( ANIMATION )
        self.vis_ctl_remove_after( time+2000 , control_id)
            
    def rotating_tower(self,control_id, delay, time ):
        self.rotate_animation('tower', control_id, delay, time )

    def cyclone(self,control_id, delay, time ):
        self.rotate_animation('cyclone', control_id, delay, time )

    def drop_bounce(self, control_id, delay, time ):

        img_ctl=self.window.getControl( control_id )
        img_w=320  
        img_h=img_ctl.getHeight()
        half_img=int(img_w/2)
        
        time=time*1.2
        ANIMATION=[]
        bounce_delay=delay+(time*0.36)
        bounce_rotate_delay=delay+(time*0.38)  #delay for rotate animation after bounce. 
        
        fade_delay=delay+(time*0.95)
        
        rand_x_pos=random.randint(0,(1280-img_w))
        rand_y_pos=0

        img_ctl.setPosition(rand_x_pos, -200)

        sx=0;ex=0
        sy=(-1*img_h) ;ey=(720-img_h)
        cx=rand_x_pos+(img_w/2)  #image center for  rotate effect
        cy=0

        pos_or_neg=['','-']
        pn=random.choice(pos_or_neg)

        #log('  pos:%d,%d  %dx%d '   %(rand_x_pos,rand_y_pos, img_w,img_h ))

        start="{0},{1}".format(sx,sy)
        end="{0},{1}".format(ex,ey)
        
        #image hide animation either fade or flip as if falling backwards
        image_hide_animation=random.choice( [
                                            #animation_format(bounce_delay, 2000,  'zoom',   100, 150,'cubic', 'in', 'auto' ), 
                                            animation_format(bounce_delay, 2000,  'fade',   100,   0,'cubic', 'in'         ),
                                       
                                       #animation_format(fade_delay, 2000,  'rotatex', 0,  120,'circle', 'in','%d,0' %img_h)
                                            ])
        #animation_format(out_delay, time, 'rotatex', 0, '%s90'%pn, 'circle', 'in', '%s,0'%(random.choice([360,720])) ), #center x needs to be in the
        
        ANIMATION.extend( [
                           animation_format(    0,    0,  'zoom',   150,          150,       '',   '','auto' ),
                           animation_format(delay, time, 'slide', start,          end, 'bounce', 'out'       ),
                           animation_format(delay, time, 'slide', '0,0', '%s600,0'%pn,   'sine', 'in', '', '' ),
                           image_hide_animation,
                           ] )
        
        pos_or_neg=['','-']
        pn=random.choice(pos_or_neg)
        deg_end='{0}{1}'.format(pn,random.choice([0,180]))

        self.vis_ctl_add(control_id)
        img_ctl.setAnimations( ANIMATION )
        self.vis_ctl_remove_after(  (bounce_delay+2000) , control_id) 

    def udlr_slide(self, control_id, delay, time ):
        
        img_ctl=self.window.getControl( control_id )
        img_w=img_ctl.getWidth()
        img_h=img_ctl.getHeight()
        
        ANIMATION=[]
        rnd_delay=delay+random.choice([(time/2),(time/3),(time*0.6) ])
        #log('  %d rnd_delay:%d' %(time, rnd_delay) )
        
        rand_x_pos=random.randint(0,(1280-img_w))
        rand_y_pos=random.randint(0,(720-img_h))
        v_or_h=random.choice([1,0])
        
        direction=random.choice([1,0])

        #rnd_slide_tweens=random.choice(['sine','linear','quadratic','circle','cubic'])
        rnd_slide_tweens=random.choice(['linear','quadratic'])
        rnd_slide_easing=random.choice(['in','out'])

        
        if v_or_h:  #horizontal slide
            img_ctl.setPosition(0, rand_y_pos)
            rand_x_pos=0
            #ANIMATION.extend( [animation_format(delay, time, 'slide', start, end, 'sine', 'out' ), ] )
            sx=1280;ex=(-1*img_w)
            sy=0;ey=0
            cx=0
            cy=rand_y_pos+(img_h/2) #image center for  rotate effect
        else:      #vertical slide
            img_ctl.setPosition(rand_x_pos, 0)
            rand_y_pos=0
            #ANIMATION.extend( )
            sx=0;ex=0
            sy=(-1*img_h) ;ey=720
            cx=rand_x_pos+(img_w/2)  #image center for  rotate effect
            cy=0
        if direction:
            sx,ex=ex,sx
            sy,ey=ey,sy

        #log('  pos:%d,%d  %dx%d '   %(rand_x_pos,rand_y_pos, img_w,img_h ))

        start="{0},{1}".format(sx,sy)
        end="{0},{1}".format(ex,ey)
        
        ANIMATION.extend( [
                           animation_format(delay, time, 'slide', start, end, rnd_slide_tweens, rnd_slide_easing ), 
                           ] )
        
        ANIMATION.extend( fade_in_out_animation(delay,time,1000) )
        #ANIMATION.extend( self.addtl_animations_while_sliding( rnd_delay, 1000,cx,cy ) )

        self.vis_ctl_add(control_id)
        img_ctl.setAnimations( ANIMATION )
        self.vis_ctl_remove_after( time+1000 , control_id) 
        
        
    def warp(self,style,control_id, delay, time ):
        
        img_ctl=self.window.getControl( control_id )
        img_w=img_ctl.getWidth()
        img_h=img_ctl.getHeight()
        img_x, img_y = img_ctl.getPosition()
        
        center_x=640-img_x - 80 #center x & y for this image relative to its original position
        center_y=360-img_y - 80
        img_centered="{0},{1}".format(center_x,center_y)
        
        ANIMATION=[]
        
        #rand_x_pos=random.randint(0,(1280-img_w))
        #rand_y_pos=random.randint(0,(720-img_h))
        #style='out'
        if style=='out':
            #this part is added because we can't 'loop' the image fade-in. we just position the image outside the screen
            random_distance_from_center_x=self.screen_w + img_w
            random_distance_from_center_y=self.screen_h + img_h 
        else:
            random_distance_from_center_x=random.randint( self.screen_w/3, (self.screen_w/3 + self.screen_w/2 )  )
            random_distance_from_center_y=random.randint( self.screen_h/3, (self.screen_h/3 + self.screen_h/2 )  )

        deg=random.randint(0,360)
        #deg = 0
        rad=math.radians(deg)
        rand_x_pos = center_x + int( random_distance_from_center_x * math.cos(rad) )
        rand_y_pos = center_y + int( random_distance_from_center_y * math.sin(rad) )
        
        loop='loop=false'
        
        if style=='out':
            start="{0},{1}".format(rand_x_pos,rand_y_pos)
            end=img_centered
            zs=380;ze=0   #zoom start and end
            fs=100;fe=0   #fade start & end
            r_easing='in'
            rveasing='out'
            #edge animation does not work with zoom out. we cannot loop the fade-in of the image when it is at the edge because time is short, will loop too fast. 
            edge_animation=('conditional','condition=false') #animation_format( delay, 1000, 'fade',   0,  100, 'cubic',      'out',    '','' )
        elif style=='in':
            start=img_centered
            end="{0},{1}".format(rand_x_pos,rand_y_pos)
            zs=5;ze=200   #zoom start and end
            fs=0;fe=100   #fade start & end
            edge_animation=animation_format( time*0.91, 1000, 'fade',   100,    0, 'cubic',      'in',    '',loop )
            r_easing='out'
            rveasing='in'
        #end="{0},{1}".format(1200,700)
        #log( ' %d° start: %s end: %s'  %(deg, start, end ) )
        ANIMATION.extend( [
                           animation_format(delay, time, 'slide', start, end,   'cubic',rveasing,    '',loop ), 
                           animation_format(delay, time, 'zoom',    zs,   ze,   'cubic',rveasing,'auto',loop ),
                           animation_format(delay, time, 'fade',    fs,   fe, 'circle', r_easing,    '',loop ),
                           edge_animation,
                           ] )

        self.vis_ctl_add(control_id)
        img_ctl.setAnimations( ANIMATION )
        self.vis_ctl_remove_after( time+1000 , control_id) 
        
    def warp_out(self, control_id, delay, time ):    
        self.warp('out',control_id, delay, time)
        
    def warp_in(self, control_id, delay, time ):    
        self.warp('in',control_id, delay, time)

    def grid(self, control_id, delay, time ):
        #self.setPosition_5x4_grid(control_id, delay, (time/3), extra_animation)
        iid = ( control_id % 20 ) - 1  #our control id's start at 101 to 120. defined in xml
        if iid<0:iid=19 #<--grid_position_index
                
        #manipulate the fade wait so that the last few images don't linger  
        fade_wait= abs( (time*1.8) - ( (iid+iid) * 500 ) )

        extra_animation=fade_in_out_animation(0,fade_wait,2000)

        self.slide_control_to_grid(control_id, iid, delay, (time/3), extra_animation )

    def horizon(self, control_id, delay, time ):
        img_ctl=self.window.getControl( control_id )
        img_w=320  
        img_h=img_ctl.getHeight()
        half_img=int(img_w/2)

        img_x, img_y = img_ctl.getPosition()
        
        ANIMATION=[]
        
        rand_x_pos=random.randint((-1*half_img),(1280-half_img))
        rand_y_pos=self.screen_h  #start at bottom

        img_ctl.setPosition(rand_x_pos, -100)
        rand_y_pos=0

        sx=0;ex=0
        sy=self.screen_h-img_h ;ey=(-1*(img_h+800))
        start="{0},{1}".format(sx,sy)
        end="{0},{1}".format(ex,ey)

        ANIMATION.extend( [
                           animation_format( delay,               0, 'rotatex',   60,  60,   'linear', '','%d,0'%self.screen_h ),
                           animation_format( delay,               0,    'zoom',  300, 300,   'linear', '','auto' ),
                           animation_format( delay,            time,   'slide',start, end,   'linear', '','' ),
                           animation_format( delay+(time*0.1), time,    'fade',  100,   0,   'linear', '','' ),
                           ] )
        
        self.vis_ctl_add(control_id)
        img_ctl.setAnimations( ANIMATION )
        self.vis_ctl_remove_after( time, control_id)
        
        #add all controls into set
        #self.visible_controls_set |= self.image_control_ids

    def rotate_canvas(self, control_id, delay, time ):
        pn=random.choice(['','-'])
        
        start='%s360'%pn
        center_rx='%s,0'%(int(self.screen_h/2))
        center_ry='%s,0'%(int(self.screen_w/2))
        
        rotate_animations=[
                           [ animation_format( delay, (time/2),  'rotate', start, '0', 'cubic', 'inout',    'auto', '' ), ],
                           [ animation_format( delay, (time/2), 'rotatex', start, '0', 'cubic', 'inout', center_rx, '' ), ],                                                      
                           [ animation_format( delay, (time/2), 'rotatey', start, '0', 'cubic', 'inout', center_ry, '' ), ],
                          ]
        
        self.group_ctl.setAnimations( random.choice( rotate_animations ) )

    def arrange_all_controls_to_grid(self, time=4000):
        #save the control ids in a temporary list. to be used later if swap animation is run (their index correspond to grid positions
        #note:  self.temp_list=self.image_control_ids will not work. the lists are copied by pointers, modifying temp_list will also affect image_control_ids
        #we need to actually copy self.image_control_ids into self.temp_list
        #http://stackoverflow.com/questions/2612802/how-to-clone-or-copy-a-list
        self.temp_list = list(self.image_control_ids)
        
        time_slice = time/len(self.image_control_ids)
        extra_animation=[
                         animation_format( 0,            0, 'zoom', 70,  70,     '',   '','auto','' ),
                         animation_format( 0, time_slice*4, 'fade',  0, 100,'cubic', 'in',    '','' ),
                         ]
        random.shuffle(self.temp_list)
        for idx, id in enumerate(self.temp_list):
            increasing_delay=((idx/2)*time_slice)
            self.slide_control_to_grid(id, idx, 0, time-(increasing_delay), extra_animation,True )
            self.wait(time_slice)  #<-- need to do the delay here instead of in animation so that previous animation of last control is not interrupted as fast

    def apply_animation_to_all_controls(self, animation=[], sleep_msec_after_every_control=0 ):
        
        if bool(random.getrandbits(1)):
            image_control_ids=self.image_control_ids
        else:
            image_control_ids=reversed(self.image_control_ids)
        
        for control_id in image_control_ids:
            img_ctl=self.window.getControl( control_id )
            img_ctl.setAnimations( animation )
            if sleep_msec_after_every_control > 0:
                xbmc.sleep(sleep_msec_after_every_control)  #having it sleep will make the animation delay a bit. just to make it more interesting. 

    def bpm_grid_random(self, control_id, delay, time ):
        self.arrange_all_controls_to_grid(4000)
        
        msec_bpm = self.get_bpm_msec()
        
        number_of_beats = int( time / msec_bpm )
        for i in range(number_of_beats):
            iid1=random.randint(0,19)
            iid2=random.randint(0,19)
            iids= [iid1,iid2] 
            self.beat( iids, msec_bpm )
            xbmc.sleep( msec_bpm ) #make sure to sleep so that animation finishes
            
        self.random_grid_out_animations(0,2000)            

    def swap_grid_random(self, control_id, delay, time ):
        self.arrange_all_controls_to_grid(4000)
        
        msec_bpm = self.get_bpm_msec()
        msec_bpm = (msec_bpm * 2)
        
        number_of_beats = int( time / msec_bpm )
        for i in range(number_of_beats):
            iid1=0; iid2=0
            while iid1 == iid2: #make sure we didn't generate the same swap positions
                iid1=random.randint(0,19)
                iid2=random.randint(0,19)
            
            self.swap_control_positions( iid1, iid2, delay=0, time=msec_bpm, tween='cubic', easing='inout')
            xbmc.sleep( msec_bpm ) #make sure to sleep so that animation finishes
        
        self.random_grid_out_animations(0,2000)
    
    def bpm_grid(self, control_id, delay, time ):
        self.arrange_all_controls_to_grid(4000)
        #self.wait(4000) #wait for arrange_all_controls_to_grid animation to finish
        msec_bpm = self.get_bpm_msec()
                
        pattern_cycle=cycle( random.choice(self.beat_patterns) )
        #pattern_cycle=cycle( self.beat_patterns[0] )
        
        animation_style=random.choice(['zoom','fade'])
        number_of_beats = int( time / msec_bpm )
        for i in range(number_of_beats):
            index_ids=pattern_cycle.next()
            self.beat( index_ids, msec_bpm, animation_style )
            xbmc.sleep( msec_bpm )  #make sure to sleep so that animation finishes

        self.random_grid_out_animations(0,2000)

    def parade(self, control_id, delay, time ):

        concurrent_images=7
        time_slice = time/len(self.image_control_ids) #time wehen next image comes out
        a_time= time_slice * concurrent_images        #how long each image animation is performed
 
        direction=bool(random.getrandbits(1))
 
        for id in reversed(self.image_control_ids):

            img_ctl=self.window.getControl( id )
        
            ANIMATION=[]
    
            if direction:
                img_ctl.setPosition(750, 250)
                
                ANIMATION.extend( [
                                   animation_format(           0,      0, 'zoom',    200,    200,   'linear', None, 'auto','' ),
                                   animation_format(       delay, a_time, 'rotatey',-100,     10,   'sine', 'out', ' 0,00','' ), 
                                   animation_format( a_time*0.75,    800, 'fade',    100,      0,   'sine','in'   ),
                                   #animation_format(      a_time,    800, 'slide', '0,0','500,0',   'sine','in'   ),   #slide away
                                   ] )
            else:        
                img_ctl.setPosition(250, 250)
                
                ANIMATION.extend( [
                                   animation_format(           0,      0, 'zoom',    200,  200,   'linear', None, 'auto','' ),
                                   animation_format(       delay, a_time, 'rotatey', 100,  -10,   'sine', 'out', '1080,00','' ), 
                                   animation_format( a_time*0.75,    800, 'fade',    100,    0,   'sine','in'   ),
                                   #animation_format(      a_time,    800, 'slide', '0,0','-500,0',   'sine','in'   ),   #slide away
                                   ] )
    
            self.vis_ctl_add(control_id)
            img_ctl.setAnimations( ANIMATION )
            self.vis_ctl_remove_after( (a_time*0.75)+800, control_id)
        
            self.wait(time_slice) 

    def beat(self, index_ids, msec_bpm, animation_style='zoom' ):
        #'beat'-animate the control indicated by the grid index id
        half_msec_bpm=(msec_bpm/2)

        for index_id in index_ids:
            ctl_id=self.translate_grid_index_to_control_id( index_id )
            img_ctl=self.window.getControl( ctl_id )

            ANIMATION=[]
            if animation_style=='fade':
                start=20
                end=100
                out_delay=msec_bpm*1.5
                ANIMATION.extend( [ animation_format(0, 0,'zoom',70,70,'sine','in','auto','' ), ])
            else:
                start=70
                end=100
                out_delay=half_msec_bpm
            
            ANIMATION.extend( [
                           animation_format(             0, half_msec_bpm,animation_style,start,  end,   'sine', 'in','auto','' ),
                           animation_format( half_msec_bpm,     out_delay,animation_style,  end,start,   'sine',  'out','auto','' ),
                           ] )
            img_ctl.setAnimations( ANIMATION ) 
            
    def grid_zoom_pan(self, control_id, delay, time ):

        corners=[ (0,-10),(1280,-10),(0,730),(1280,730)  ]   #used to define the starting points for diagonal slide
        t_arrange_controls=6000

        r=[0,1,2,3,4]
        indexes=[]   #used to store indexes of the visible controls

        #divide the time allotted for this animation between zoom and slide
        time=time-t_arrange_controls
        time_slice=(time/4)
        t_zoom =time_slice*1
        t_slide=time_slice*2
        delay_zoom_out=delay+t_zoom+t_slide

        self.arrange_all_controls_to_grid(t_arrange_controls)
        
        diagonal=bool(random.getrandbits(1))
        if diagonal:
            #random corners
            c=random.randint(0,3)
            zx,zy=corners[c]
            if   c==0: sx=-860;sy=-500; indexes=[0,1,5,6,7,12,13,14,18,19]
            elif c==1: sx= 860;sy=-500; indexes=[3,4,7,8,9,10,11,12,15,16]
            elif c==2: sx=-860;sy= 500; indexes=[3,4,7,8,9,10,11,12,15,16]
            else:      sx= 860;sy= 500; indexes=[0,1,5,6,7,12,13,14,18,19]

        else:
            #random row zoom (start)          
            rr= random.randint(0,3)      
            zy = [-10,230,490,730][rr]   #log('zy='+repr( zy ))
            
            indexes=[ x+(rr*5) for x in r ] #log(repr( indexes ))
            
            #random direction
            direction=bool(random.getrandbits(1))
            if direction:
                zx=0
                sx=-860; sy=0
            else:
                zx=1280
                sx=860;  sy=0
                
        slide1='{},{}'.format(sx,sy)
        slide2='{},{}'.format(-sx,-sy)
        center='{},{}'.format(zx,zy)

        #this portion figures out which controls are visible (don't update with new image)
        zoomed_in_controls=[ self.translate_grid_index_to_control_id(x) for x in indexes ] 
        #log('zoomed_in_controls=' + repr( zoomed_in_controls ))
        self.vis_ctl_add_each(zoomed_in_controls, (delay+t_zoom)*0.7 )
        self.vis_ctl_remove_each(zoomed_in_controls, delay_zoom_out*1.3 )

        self.group_ctl.setAnimations( [ animation_format( delay,          t_zoom,  'zoom',   100,    303,  'sine', 'out',  center ),
                                        animation_format( delay+t_zoom  ,t_slide, 'slide', '0,0', slide1,  'sine','inout',     '' ), 
                                        animation_format( delay_zoom_out, t_zoom, 'slide', '0,0', slide2,  'sine','inout',     '' ),
                                        animation_format( delay_zoom_out, t_zoom,  'zoom',   100,     33,  'sine','inout', center ),
                                       ] )
        
#        self.group_ctl.setAnimations( [ animation_format(     0, 4000,  'zoom',   100,        303,  'sine', 'out',  '0,-10','' ),
#                                        animation_format(  4000,12000, 'slide', '0,0','-860,-500',  'sine','inout',     '','' ), 
#                                        animation_format( 16000, 4000, 'slide', '0,0',  '860,500',  'sine','inout',     '','' ),
#                                        animation_format( 16000, 4000,  'zoom',   100,        33,   'sine','inout', '0,-10','' ),
#                                       ] )
        self.wait(time) #wait for the entire time alloted to this animation sequence
        
        self.random_grid_out_animations(0,2000) 

    def slide_control_to_grid(self,control_id,grid_position_index, delay=0, time=0, extra_animation=[], set_position=False, tween='', easing=''  ):
        #log('   slide control to grid position %d' %(grid_position_index))
        img_ctl=self.window.getControl( control_id )
        img_w=img_ctl.getWidth()
        img_h=img_ctl.getHeight()
        img_x, img_y = img_ctl.getPosition()
        #log( '  @image starts at %.3d,%.3d' %( img_x, img_y ) )
        ANIMATION=[]
        
        #make sure invalid grid position index will just loop back to the beginning
        grid_position_index=grid_position_index % len(self.grid_positions)
        
        x_pos, y_pos = self.grid_positions[grid_position_index]

        if not tween:
            #tween=random.choice(['sine','linear','quadratic','circle','cubic'])
            tween=random.choice(['sine','quadratic'])
        
        if not easing:
            easing='out'

        #slide uses relative positioning. we compute the delta for the desired vs current location and animate to slide there.
        dx=x_pos - img_x
        dy=y_pos - img_y
        
        start="{0},{1}".format(0,0)
        end="{0},{1}".format(dx,dy)
        img_ctl.setVisible(False)    #setting visible to false seems to remove an issue where the image briefly flashes before animation begins

        #need to move control to new position if you want further animations on it.
        if set_position:
            
            img_ctl.setPosition(x_pos, y_pos)   #log( '  @set position %.3d,%.3d' %( x_pos, y_pos ) )
            #same concept here but we compute the delta based on where the image was originally from
            dx=img_x - x_pos
            dy=img_y - y_pos 
            
            start="{0},{1}".format(dx,dy)
            end="{0},{1}".format(0,0)

        #log( '  start:%s end:%s ' %( start, end ) )
        ANIMATION.extend( [
                           animation_format(delay, time, 'slide', start, end, tween, easing ), 
                           ] )
        
        ANIMATION.extend( extra_animation )
        img_ctl.setVisible(True)

        self.vis_ctl_add(control_id)
        img_ctl.setAnimations( ANIMATION )
        self.vis_ctl_remove_after( time, control_id)
        
    def translate_grid_index_to_control_id(self, grid_index):
        #this works because we arrange the image controls with grid id in define_grid_positions
        #return self.image_control_ids[ grid_index ]
        return self.temp_list[ grid_index ]   #<-- temp_list re-created in self.arrange_all_controls_to_grid(). it will start same as self.image_control_ids

    def get_bpm_msec(self, default=120):
        try: bpm=int( Window(10000).getProperty('bpm' ) )
        except: bpm=default
        if bpm==0: bpm=default  #songbpm.com call didn't return any result
        
        msec_bpm      = 60000/bpm
        return msec_bpm

    def reset_group_animation(self):
        self.group_ctl.setAnimations( [] )
    
    def log(self, msg):
        log(u'a-thread: %s' % msg)

    def center_setPosition(self, ctl, cx,cy):
        ix,iy=self.center_position(ctl, cx, cy)
        ctl.setPosition(ix, iy)
    
    def center_position(self, ctl, cx,cy):
        img_w=ctl.getWidth()
        img_h=ctl.getHeight()
        
        ix=cx - int(img_w/2)
        iy=cy - int(img_h/2)
        
        return ix, iy        
    #vis_ctl methods used to keep track of what controls are visible
    def vis_ctl_add(self, control_id):
        #log('  adding {}'.format(control_id))
        self.visible_controls_set.add(control_id)
    def vis_ctl_add_after(self, time, control_id):
        seconds=float(time/1000)
        #log('  removing af{}-{}'.format(seconds, control_id))
        threading.Timer(seconds, self.vis_ctl_add, [control_id] ).start()
    def vis_ctl_add_each(self, control_id_list, time=0):
        if time==0:
            for control_id in control_id_list:
                self.vis_ctl_add(control_id)
        else:
            for control_id in control_id_list:
                self.vis_ctl_add_after(time, control_id)
    def vis_ctl_remove_each(self, control_id_list, time=0):
        if time==0:
            for control_id in control_id_list:
                self.vis_ctl_remove(control_id)
        else:
            for control_id in control_id_list:
                self.vis_ctl_remove_after(time, control_id)
    def vis_ctl_remove_after(self, time, control_id):
        seconds=float(time/1000)
        #log('  removing af{}-{}'.format(seconds, control_id))
        threading.Timer(seconds, self.vis_ctl_remove, [control_id] ).start()
    def vis_ctl_remove(self, control_id):
        #log('  removing {}'.format(control_id))
        #self.visible_controls_set.remove( control_id ) 
        self.visible_controls_set.discard( control_id )
    def vis_ctl_remove_all(self):
        self.visible_controls_set.clear()
        pass

    animation_functions=[
                        ('',rotating_tower),
                        ('',cyclone),
                        ('',drop_bounce),
                        ('',udlr_slide),
                        ('r',warp_in),
                        ('',warp_out),
                        ('',grid),      
                        ('u',horizon),
                        ('once',rotate_canvas),
                        ('onceb',bpm_grid_random),
                        ('onceb',bpm_grid), 
                        ('onceb',swap_grid_random),
                        ('onceb',grid_zoom_pan),
                        ('onceb',parade),
                         ]


class ScreensaverXMLWindow(WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        WindowXMLDialog.__init__(self, *args, **kwargs)
        self.exit_callback = kwargs.get("exit_callback")

    def onAction(self, action):
        action_id = action.getId()
        self.exit_callback(action_id)

class ScreensaverBase(object):
    #MODE = None
    #IMAGE_CONTROL_COUNT = 10
    FAST_IMAGE_COUNT = 0
    NEXT_SLIDE_TIME = 2000
    BACKGROUND_IMAGE = 'srr_blackbg.jpg'
    image_control_ids=[101,102,103,104,105]   #control id's defined in ScreensaverXMLWindow xml file
    WINDOW_XML_FILE = "slideshow02.xml"
    
    pause_requested=False
    info_requested=False
    #image_controls_cycle=''

    def __init__(self, thread_event, facts_queue, worker_thread):
        #self.log('__init__ start')
        self.exit_requested = False
        self.background_control = None
        self.preload_control = None
        self.image_count = 0
        self.global_controls = []
        self.exit_monitor = ExitMonitor(self.stop)
        self.facts_queue=facts_queue
        self.worker_thread=worker_thread
        self.init_xbmc_window()
        self.init_global_controls()
        self.load_settings()
        #self.log('__init__ end')
    
    def init_xbmc_window(self):
        self.xbmc_window = ScreensaverXMLWindow( self.WINDOW_XML_FILE, ADDON_PATH, defaultSkin='Default', exit_callback=self.action_id_handler )
        self.xbmc_window.setCoordinateResolution(5)
        self.xbmc_window.show()

    def init_global_controls(self):
        #self.log('  init_global_controls start')
        
        loading_img = xbmc.validatePath('/'.join((ADDON_PATH, 'resources', 'skins', 'Default', 'media', 'srr_busy.gif' )))
        self.loading_control = ControlImage(576, 296, 128, 128, loading_img)
        self.preload_control = ControlImage(-1, -1, 1, 1, '')
        self.background_control = ControlImage(0, 0, 1280, 720, '')
        self.global_controls = [
            self.preload_control, self.background_control, self.loading_control
        ]
        self.xbmc_window.addControls(self.global_controls)
        #self.log('  init_global_controls end')

    def load_settings(self):
        pass

    def start_loop(self):
        self.log('screensaver start_loop')
        
        #tni_controls_cycle= cycle(self.tni_controls)
        self.image_controls_cycle= cycle(self.image_control_ids)

        self.hide_loading_indicator()
        
        log('   initial start: queue %d' %(self.facts_queue.qsize())  )
        
        factlet=self.facts_queue.get()
        #self.log('  image_url_cycle.next %s' % image_url)
        
        while not self.exit_requested:
            #self.log('  using image: %s ' % ( repr(factlet) ) )
            self.log( '  ' + pprint.pformat(factlet, indent=1) )

            #pops an image control
            
            image_control = self.image_controls_cycle.next()
            
            self.process_image(image_control, factlet)
            
            try:
                #if self.facts_queue.empty():
                #    self.wait()
                #    log('   queue empty %d' %(self.facts_queue.qsize())  )
                #else:
                factlet=self.facts_queue.get()
                    #log('   got next item from queue ' + factlet['name'])
                    #factlet=self.facts_queue.get(block=True,timeout=5000)  #doesn't throw exception if empty!
                    
            except Queue.Empty:
                self.log('   queue empty thrown')
                self.wait()
                
            self.wait()
            if self.image_count < self.FAST_IMAGE_COUNT:
                self.image_count += 1
            else:
                #self.preload_image(image_url)
                self.preload_image(factlet['image'])
                self.wait()
                
        self.log('start_loop end')
        
        #return the screensaver back
        #xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "id": 0, "method":"Settings.setSettingValue", "params": {"setting":"screensaver.mode", "value" : "%s"} }' % saver_mode )

    def hide_loading_indicator(self):
        bg_img = xbmc.validatePath('/'.join(( ADDON_PATH, 'resources', 'skins', 'Default', 'media', self.BACKGROUND_IMAGE )))
        #bg_img = self.BACKGROUND_IMAGE
        self.loading_control.setAnimations([(
            'conditional',
            'effect=fade start=100 end=0 time=500 condition=true'
        )])
        self.background_control.setAnimations([(
            'conditional',
            'effect=fade start=0 end=100 time=500 delay=500 condition=true'
        )])
        self.background_control.setImage(bg_img)

    def process_image(self, image_control_id, image_url):
        # Needs to be implemented in sub class
        raise NotImplementedError

    def preload_image(self, image_url):
        # set the next image to an unvisible image-control for caching
        #self.log('preloading image: %s' % repr(image_url))
        self.preload_control.setImage(image_url)
        #self.log('preloading done')

    def wait(self, msec=0):
        # wait in chunks of 500ms to react earlier on exit request
        
        chunk_wait_time = int(CHUNK_WAIT_TIME)
        remaining_wait_time = msec if msec > 0 else int(self.NEXT_SLIDE_TIME)
        #self.log('waiting for %d' %remaining_wait_time )
        while remaining_wait_time > 0:
            #self.log('waiting %d' %remaining_wait_time )
            if not self.worker_thread.isAlive():
                self.log('worker thread died')
                self.exit_requested=True

            if self.exit_requested:
                self.log('wait aborted')
                return
            
            if remaining_wait_time < chunk_wait_time:
                chunk_wait_time = remaining_wait_time
            remaining_wait_time -= chunk_wait_time
            xbmc.sleep(chunk_wait_time)

    def action_id_handler(self,action_id):
        #log('  action ID:' + str(action_id) )
        if action_id in ACTION_IDS_EXIT:
            #self.exit_callback()
            self.stop()
        if action_id in ACTION_IDS_PAUSE:  
            self.pause()          

        if action_id == 11: #xbmcgui.ACTION_SHOW_INFO:   
            self.info_requested=not self.info_requested            

    def stop(self,action_id=0):
        self.log('stop')
        self.exit_requested = True
        self.exit_monitor = None

    def pause(self):
        #pause feature disabled. too complicated(not possible?) to stop animation  
        #self.pause_requested = not self.pause_requested
        #self.log('pause %s' %self.pause_requested )
        pass

    def close(self):
        self.log('close')
        self.del_controls()

    def del_controls(self):
        self.xbmc_window.removeControls(self.global_controls)
        self.preload_control = None
        self.background_control = None
        self.loading_control = None
        #self.tni_controls = []
        self.global_controls = []
        self.xbmc_window.close()
        self.xbmc_window = None
        #self.log('del_controls end')

    def log(self, msg):
        log(u'slideshow: %s' % msg)

class ExitMonitor(xbmc.Monitor):

    def __init__(self, exit_callback):
        self.exit_callback = exit_callback

    def onScreensaverDeactivated(self):
        self.exit_callback()

    def abortRequested(self):
        self.exit_callback()

class bggslide(ScreensaverBase):
    BACKGROUND_IMAGE = '' #'srr_blackbg.jpg'
    SPEED = 1.0

    image_control_ids=[101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120]
    temp_list=[ {'src':'duckduckgo.png', 'width':'320','height':'180'} ]  #avoid random error at start due to empty list
    CTL_TEXT_GROUP=200
    CTL_TITLE_TBOX=201
    CTL_TITLE_TBOX2=203
    CTL_TITLE_TBOX3=204
    CTL_TITLE_DESC=202
    WINDOW_XML_FILE = "slideshow04.xml"
    visible_controls_set=LockedSet()
    
    def load_settings(self):
        self.SPEED = 1.0
        self.NEXT_SLIDE_TIME = int(50000)
        
        self.show_title=addon.getSetting('show_title') == "true"
        
        try: self.NEXT_IMAGE_TIME = float(addon.getSetting('new_image_wait_sec')) *1000
        except: self.NEXT_IMAGE_TIME = 5000   #default 5 seconds till new image is sent to animator thread

    def start_loop(self):
        #self.log('  start_loop')
        self.music_images_cycle=cycle( self.temp_list )
        
        self.image_controls_cycle= cycle(self.image_control_ids)
        self.hide_loading_indicator()

        #spawn the thread that animates the images
        self.animator_thread=ctl_animator( self.xbmc_window, self.image_control_ids, self.visible_controls_set )
        self.animator_thread.start()
        
        while not self.exit_requested:
            try:
                if self.facts_queue.empty():
                    #self.log('   queue empty '   )
                    self.log( repr(self.visible_controls_set) )
                    self.cycle_image_into_control()
                    self.wait( self.NEXT_IMAGE_TIME )  #taken from settings (default 5 secs)
                    #self.wait(789)
                else:
                    self.wait(2000)
                    #factlet=self.facts_queue.get()
                    factlet=self.facts_queue.get(block=True,timeout=5000)  #doesn't throw exception if empty!

                    #self.log( '  worker is alive:' + repr(self.worker_thread.isAlive()) )
                    self.log( '  using(%d):%s' %(self.facts_queue.qsize(),  pprint.pformat(factlet, indent=1, depth=1))  )
                    
                    factlet_type=factlet.get('factlet_type')
                    
                    if factlet_type =='music_status:stop':  
                        self.log( '  music_status:stop' )
                        #self.exit_requested=True
                        pass

                    elif factlet_type =='music_status:half':  #playing music is at halfway point
                        #self.log( '  show halfway point title' )
                        self.show_title_slide(factlet)

                    elif factlet_type =='musicthumbs':
                        #self.process_music_slide(factlet)
                        self.load_new_images_to_cycle(factlet)
                        self.show_title_slide(factlet)
                        
                    self.wait(480)  
                
            except Queue.Empty:
                self.log('   queue empty thrown')
                self.wait(5000)
            
            except:
                self.exit_requested=True   
                self.animator_thread.stop()  
                raise
        
        self.animator_thread.stop()
                
        self.log('start_loop end')


    def load_new_images_to_cycle(self, factlet):
        new_images=factlet.get('images') 
        
        if new_images:
            img_count=len( new_images )
            self.log('   loading %d new images into cycle' %img_count )
    
            if img_count > 0:
                new_images=self.filter_images_by_ar( factlet.get('images') )
                random.shuffle( new_images )
                self.music_images_cycle=cycle( new_images )
        else:
            self.log('   no images to load')
        
        #put bpm info for animator thread to use    
        current_bpm=factlet.get('bpm')
        Window(10000).setProperty('bpm',str(current_bpm) )
        #log('  wbpm:'+ repr( current_bpm ))
        
        #new song. put x the new images to controls to speed up transition
        self.cycle_image_into_control(8)

    def filter_images_by_ar(self, images_dict):
        #remove images that are too tall or too wide
        images_dict2 = [ img_dict for img_dict in images_dict if self.ar_is_acceptable(img_dict) ]
        
        return  images_dict2   

    def ar_is_acceptable( self, img_dict ):
        try:
            img_w=int(img_dict.get('width'))
            img_h=int(img_dict.get('height'))
            image=img_dict.get('src')
            
            ar=float(img_w)/img_h
            if (ar>0) and (ar <0.4 or ar > 3):
                self.log('  bad ar %.3f rejecting image %s' %(ar, image ) )
                return False
                
        except Exception:
            self.log( '  filter_images_by_ar:' + repr(sys.exc_info()) )                
            #just accept the image (no width/height) value?
            
        return True

    def show_title_slide(self, factlet):
        #show and animate the currently playing music title
        if self.show_title==False:  #taken from settings.xml
            return
        
        title_group_ctl=self.xbmc_window.getControl( self.CTL_TEXT_GROUP )
        song_title=factlet.get('title')
        song_artist=factlet.get('artist')
        song_album=factlet.get('album')

        control=self.xbmc_window.getControl(self.CTL_TITLE_TBOX)        
        control.setText( song_title )

        control=self.xbmc_window.getControl(self.CTL_TITLE_TBOX2)
        control.setText( song_artist )
        
        title_group_ctl.setAnimations( self.random_animations( 0, 20000, 800 )  )
        
    def cycle_image_into_control(self, images_to_cycle=1):
        #this method replaces process_music_slide()
        #  feeds one image at a time. called when queue is empty. this way, we will be able to react if new song is playing.
        for x in range(1,images_to_cycle+1):
            img_dict =self.music_images_cycle.next()
            iid      =self.image_controls_cycle.next()
            
            #we try to change image when the control is not visible. kodi does not have a way for us to check if a control is visible.
            #  the animator thread will maintain a list of control id's that are visible   
            while iid in self.visible_controls_set:
                #log(' bang! {} '.format(iid))
                iid =self.image_controls_cycle.next()
                self.wait(500)
                
            img_ctl=self.xbmc_window.getControl( iid )

            #self.log('   cycling image(%d) into control %d' %(x,iid) )
            self.fit_image_320_box(img_dict, img_ctl )

    def process_music_slide(self, factlet):
        #pushes images into control. no guard against having too many images --> how many img_controls we have 
        #  this method will feed images without checking that a new song is playing
        #  this is no longer used. left here for reference and testing.   
        
        images=factlet.get('images')
        img_count=len(images)
        for i, img in enumerate(images):
            iid=self.image_controls_cycle.next()
            
            #log('  %d %d - iid:%.4d image:%s' %(l, i, iid,repr(img.get('src'))  )          )
            #self.animate_by_udlr_slide( iid, img, (i)*2000, 10000 )
            #self.animate_by_drop( iid, img, (i)*2000, 10000 )
            #self.animate_by_rotating_tower( iid, img, (i)*2000, 10000 )
            img_ctl=self.xbmc_window.getControl( iid )
            img_w=int(img.get('width'))
            img_h=int(img.get('height'))
            image=img.get('src')
            
            self.log('  %dx%d - iid:%.4d image:%s' %(img_w, img_h, iid,repr(img.get('src'))  )          )
            
            ar=float(img_w)/img_h
            
            #log( 'ar:'+ repr( ar))
            if ar>1:
                if img_w >320:
                    img_w=320
                    img_h=int( img_w/ar )
                    #log( 'img w reduced to %dx%d' %(img_w,img_h))
            else:
                if img_h >320:
                    img_h=320
                    img_w=int( img_h*ar )
                    #log( 'img h reduced to %dx%d' %(img_w,img_h))
                
            #img_ctl.setVisible(False)
            img_ctl.setWidth( img_w )     ##  
            img_ctl.setHeight( img_h )    ##
            img_ctl.setImage(image)
            #img_ctl.setVisible(True)

            #feed the images slowly so that there is no abrupt change
            self.wait(self.NEXT_IMAGE_TIME)  #problem with this is that we feed the images without regard to new song. 
            
    def fit_image_320_box(self, img_dict, img_ctl ):

        img_w=int(img_dict.get('width'))
        img_h=int(img_dict.get('height'))
        image=img_dict.get('src')
        
        #self.log( '  {:<45.45}   src:{}'.format( img_dict.get('title'), image ) )
        #self.log('  %dx%d - iid:%.4d image:%s' %(img_w, img_h, iid,repr(img.get('src'))  )          )
        
        #use aspect ration to compute new size
        ar=float(img_w)/img_h
        
        if ar>1:
            if img_w >320:
                img_w=320
                img_h=int( img_w/ar )
                #log( 'img w reduced to %dx%d' %(img_w,img_h))
        else:
            if img_h >320:
                img_h=320
                img_w=int( img_h*ar )
                #log( 'img h reduced to %dx%d' %(img_w,img_h))
            
        img_ctl.setVisible(False)
        #i initially set out to have the controls exactly the same size as the images. changed to fit in a 320x320 square defined in the .xml file
        #img_ctl.setWidth(  img_w )   
        #img_ctl.setHeight( img_h )
        
        #this is done so that we can add other controls in animation (e.g. group control that shows the song title) 
        try: img_ctl.setImage( image ) #consequence is we skip one image in our cycle 
        except AttributeError:
            pass
            
        img_ctl.setVisible(True)

    def random_animations(self, start_delay, wait_time, ctl_w=0, ctl_h=0):
        #note start & end coords are relative to where image is on screen.

        time=4000   #animation time
        in_delay=start_delay
        out_delay=in_delay + wait_time - time
        
        rotates=['rotatex', 'rotatey']
        zoom_starts=[0,500]
        pos_or_neg=['','-']
        
        rotate=random.choice(rotates)
        pn=random.choice(pos_or_neg)
        
        zs=random.choice(zoom_starts)
        
        direction=random.choice([1,0])
        up_down=random.choice([1,0])
        
        deg=random.randint(0,360)
        rad=math.radians(deg)
        sx = 720 * math.cos(rad)
        sy = 720 * math.sin(rad)
        start='%d,%d'%(sx,sy)
        end  ='%d,%d'%( 0, 0)
        #log('  %d - (%d,%d)' %(deg, sx,sy )   )

        rnd_deg='%s%s'%(pn,(deg+deg))
                
        in_tweens=['circle','sine','back']  #,'elastic','bounce']
        in_tween=random.choice(in_tweens)    

        out_tweens=['circle','sine','back']
        out_tween=random.choice(out_tweens)    

        v_or_h=random.choice([1,0])
        direction=random.choice([1,0])

        udlr_x=random.randint(-500,500)
        udlr_y=random.randint(-200,200)
        if v_or_h:  #horizontal slide
            udlr_x=0
            udlr_sx=640;   udlr_ex= -640
            udlr_sy=udlr_y;udlr_ey=udlr_y
        else:      #vertical slide
            udlr_y=0
            udlr_sx=udlr_x;udlr_ex=udlr_x
            udlr_sy=360;udlr_ey=-560
            
        if direction:
            udlr_sx,udlr_ex=udlr_ex,udlr_sx
            udlr_sy,udlr_ey=udlr_ey,udlr_sy

        udlr_start='%d,%d'%(udlr_sx,udlr_sy)
        udlr_end  ='%d,%d'%(udlr_ex,udlr_ey)


        phase_in_animations=[
           [ #slide 360 from anywhere
            animation_format(in_delay, time, 'slide', start, end, in_tween, 'out' ),
           ],
           [ #drop from top
            #animation_format(in_delay, time, 'slide', '0,-720', 0, 'bounce', 'out' ),
           ],
           [ #rotates 
            animation_format(in_delay, time, rotate,      rnd_deg, 0, 'circle', 'out', 'auto' ),
           ],
           [ #spin 
            animation_format(in_delay, time, 'rotate', '%s360'%pn, 0, 'circle', 'out', '640,360' ),
           ],
           [ #zoom from very big or very small
            animation_format(in_delay, time, 'zoom', zs, 100, in_tween, 'out', 'auto' ),
            #('conditional', 'condition=true delay=%s time=%s effect=zoom    start=%s       end=100      tween=%s      easing=out   center=auto ' %(  in_delay, time, zs , in_tween) ),
           ],
           
        ]

        phase_out_animations=[
           [ #slide 360 away
            animation_format(out_delay, time, 'slide', end, start, out_tween, 'in' ),
            #('conditional', 'condition=true delay=%s time=%s effect=slide   start=%s   end=%s        tween=%s      easing=in    ' %( out_delay, time, end,start,   out_tween) ),
           ],
           [ #flip horizontal. the random.choice(360/720) is for the center.  makes the image either fall front/back or flip front/back
            animation_format(out_delay, time, 'rotatex', 0, '%s90'%pn, 'circle', 'in', '%s,0'%(random.choice([360,720])) ), #center x needs to be in the
            #('conditional', 'condition=true delay=%s time=%s effect=rotatex start=0    end=%s90      tween=circle  easing=in  center=%s,0  ' %( out_delay, time, pn,          centerx ) ),
           ],
           [ #random rotates
            animation_format(out_delay, time, rotate, 0, rnd_deg, 'circle', 'in', 'auto' ),
            #('conditional', 'condition=true delay=%s time=%s effect=%s      start=0    end=%s%s      tween=circle  easing=in  center=auto ' %( out_delay, time, rotate, pn, (deg+deg)  ) ),
           ],
           [ #spin 
            animation_format(out_delay, time, 'rotate', 0, '%s360'%pn, 'circle', 'in', '640,360' ),
           ],

           [ #zoom from very big or very small
            animation_format(out_delay, time, 'zoom', 100, zs, out_tween, 'in', 'auto' ),
            #('conditional', 'condition=true delay=%s time=%s effect=zoom    start=100    end=%s      tween=%s  easing=in  center=auto ' %( out_delay, time, zs , out_tween ) ),
           ],
           
        ]

        animation=[]
        animation.extend( fade_in_out_animation(in_delay, wait_time, time) )

        if random.choice([0,0,0,1]):   #random.getrandbits(1):
            #for single continuous animation (not in-wait-out)
            animation.extend( [animation_format(in_delay, wait_time, 'slide', udlr_start, udlr_end, 'linear', '' )] )
        else:
            animation.extend( random.choice(phase_in_animations) )
            #animation.extend( phase_in_animations[3] )
            animation.extend( random.choice(phase_out_animations) )
            #animation.extend( phase_out_animations[3] )
        
        return animation


def from_PIL( image_url ):
    from PIL import Image
    #Pillow does not support 'import _imaging'. please use 'from PIL.Image import core as _imaging' instead.    
    #from PIL.Image import core as _imaging
    
    from StringIO import StringIO
    r = requests.get( factlet.get('image') )
    pil_img=Image.open(StringIO(r.content))
    log('***cahced:'+ repr(r.from_cache) +'***' + repr(pil_img) )
        
def animation_format(delay, time, effect, start, end, tween='', easing='', center='', extras=''  ):
    a='condition=true delay={0} time={1} '.format(delay, time) 
        
    a+= 'effect={} '.format(effect)
    if start!=None: a+= 'start={} '.format(start)
    if end!=None:   a+= 'end={} '.format(end)
    
    if center: a+= 'center={} '.format(center)
    if tween:  a+= 'tween={} '.format(tween)
    if easing: a+= 'easing={} '.format(easing)  #'in' 'out'
    if extras: a+= extras  
    
    #log( '  ' + a ) 
    return ('conditional', a )
    
def fade_in_out_animation(start_delay, wait_time, fade_time=2000 ):
    out_delay=start_delay + wait_time - fade_time
    fade_in_animation= ('conditional', 'condition=true delay={delay} time={time} effect=fade  start=0    end=100  tween=quadratic easing=out  '.format(delay=start_delay, time=fade_time) )
    fade_out_animation=('conditional', 'condition=true delay={delay} time={time} effect=fade  start=100  end=0    tween=quadratic easing=in   '.format(delay=out_delay  , time=fade_time) )
    
    return [fade_in_animation,fade_out_animation]
    

if __name__ == '__main__':
    pass
