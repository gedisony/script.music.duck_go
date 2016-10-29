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
import random
import sys

import requests
#import resources.lib.requests_cache 

import bs4
#import pickle  
import re

import xbmc


from screensaver import addon, ADDON_PATH
from screensaver import log, localize
import pprint

REQ_TIMEOUT=4  #requests timeout in seconds

class google_limit_exception(Exception):
    def __init__(self):
        Exception.__init__(self,"Daily Limit Exceeded") 

class factsBase(object):
    def __init__(self):
        self.load_settings()
    
    def load_settings(self):
        pass
    
    def generate_random_slide(self):
        pass

    def remove_parens(self, string_with_parens):
        regex = re.compile(".*?\((.*?)\)")
        return re.sub(r'\([^)]*\)', '', string_with_parens)  #re.findall(regex, string_with_parens)[0]        

class duckduckgo_image(factsBase):
    
    def load_settings(self):
        self.use_hq_image=addon.getSetting('use_hq_image') == "true"
    
    def do_searches(self, search_terms, pages_per_search=1 ):
        thumbs=[]
        for search_term in search_terms:
            thumbs.extend( self.do_search(search_term, pages_per_search) )
            xbmc.sleep(1000)  
            
        return thumbs
    
    def do_search(self, search_term, pages_to_load=1 ):
        addtl_query_options=''
        thumbs=[]
        query='{0}'.format(requests.utils.quote(  search_term  ) )
        
        #date_filter='df={}'.format( 'd')  # &df=m   #note you can also do date filter: m=past month w=past week d=past day...  but they don't seem to work
        
        url='https://api.duckduckgo.com/?q={0}&ia=images&iax=1'.format(query )  
        #log( '  ' + url )      
        
        page = requests.get(url , timeout=REQ_TIMEOUT)
        try:   log( '  #cached:{0} {1}'.format( repr(page.from_cache),url) )
        except:log( '  #cached:X {1}'.format( url) )  #if requests_cache is not installed, page will not have from_cache attribute
        #log( repr( page.text ))
        
#        soup = bs4.BeautifulSoup(page.text)
#        script = soup.select('script')
#        log('  script:' + repr( script ))
        
        #get some sort of id used by ajax call for this search
        match=re.findall("vqd=(\d+)", page.text)
        
        if match:
            #log( repr(match[0]) )
            vqd=match[0]
            
            #call the ajax function that returns the actual images    
            #url='https://api.duckduckgo.com/i.js?q={0}&l=wt-wt&cb=ddg_spice_images&vqd={1}'.format(query,vqd )  #<--the json is inside a ddg_spice_images( {...} )

            thumbs=self.call_the_ajax_query( query, vqd, addtl_query_options )  #to get 100 images:  thumbs.extend( self.call_the_ajax_query( query, vqd, '&s=50' ) )
            page_loaded=1
            while page_loaded < pages_to_load:
                s='&s={0}'.format( page_loaded*50 )   #first page returns 50 results, s=50 returns the next 50, s=100 the next 50...
                addtl_query_options=s
                xbmc.sleep(500)
                #log('  #loading more pages:' + s )
                thumbs.extend( self.call_the_ajax_query( query, vqd, addtl_query_options ) )
                page_loaded+=1
        
        return thumbs

    def call_the_ajax_query(self, query, vqd, addtl_query_options=''):
        thumbs=[]
        
        url='https://api.duckduckgo.com/i.js?l=wt-wt&o=json&q={0}{2}&vqd={1}'.format(query,vqd,addtl_query_options )             #<--direct json no cleanup
        log( '  ' + url )
         
        page = requests.get(url , timeout=REQ_TIMEOUT)
        #log( repr( page.text ))
        
        j = page.json()
        
        if j:
            results=j.get('results')
            if results:
                try:   log( '    #cached:{1} {0} results '.format( len(results), page.from_cache ))
                except:log( '    #{0} results'.format( len(results) ))
                for result in results:
#                    log( repr( result.get("source")))
#                    log( repr( result.get("thumbnail")))
#                    log( repr( result.get("url" )))
#                    log( repr( result.get("title" )))
#                    log( repr( result.get("height")))
#                    log( repr( result.get("width" )))
#                    log( repr( result.get("image"))) 

                    if self.use_hq_image:
                        src=result.get('image')
                    else:
                        src=result.get('thumbnail')
                        
                    width=int(result.get('width'))
                    height=int(result.get('height'))
                    #log( '  %dx%d %s' %(width, height, thumb)  )

                    thumbs.append( {'title' : result.get("title" ),
                                    'src'   : src,
                                    'width' : width,
                                    'height': height,
                                    }  )                    
        return thumbs
        

class songbpm_com():
    def get_bpm(self, song_title, artist):

        bpm=0
        #https://songbpm.com/?artist=whitney+houston&title=one+moment+in+time
        
        try:
            artist='artist={}'.format( requests.utils.quote(   artist  ) )
            title='title={}'.format( requests.utils.quote(   song_title  ) )
            
            url="https://songbpm.com/?"+artist+"&"+title
            log('  '+ url)
            r=requests.get(url, timeout=REQ_TIMEOUT, verify=False )
            if r.status_code== requests.codes.ok:
                
                soup = bs4.BeautifulSoup(r.text) 
                
                d = soup.select('div.side-container div.bpm.side div.number'  )
                ### probably get a more accurate parsing ? 
                #d = soup.select('div.listing.'  )
                #d=soup.find("div", {"class": "side-container"})
                
                #log( repr( d ) )
                if d:
                    bpm=int(d[0].text)
                else:
                    log('    #cannot get bpm info')
                
        except Exception as e:
            log("    #EXCEPTION:="+ repr( sys.exc_info() ) + "  " + str(e) )
            bpm=0
            
        return bpm

class google_image(factsBase):
    keys=[]
    cx=''
    key=''
    key_is_valid=False
    
    def load_settings(self):
        self.cx = addon.getSetting("cx1")
        for i in range(1,11) :
            key = addon.getSetting("key%d" %i)    # need many api keys to bypass 100 use
            #cx2 = addon.getSetting("cx2")        # need to create a second project in api manager, enable it for custom search then create an api key
            self.keys.append(key)

        self.keys.reverse()
        #log( pprint.pformat(self.keys) )
        #self.cx='014375826027693914980%3Ahnuemd0yq-e'  
        #self.key='AIzaSyDxA4JzUwD_nNiKtczVT52Jp9PtqUjm5Vg'
        
    def get_images(self, search_term, addtl_query_options='' ):
        
        for attempt in range(10):
            if not self.key_is_valid:
                if len(self.keys) > 1:
                    self.key=self.keys.pop()
                    #log(' ************* popped a key:'+ self.key )
                    self.key_is_valid=True
                else:
                    log('Tried all api keys. No more left.')
                    
                    break
    
            try:  
                return self.get_thumbs(search_term, addtl_query_options)
                break;
            except google_limit_exception as gdlex:
                #log('caught gdlex ')
                xbmc.executebuiltin('XBMC.Notification("%s","%s")' %( 'Daily limit exceeded for API Key %d' %attempt, 'Trying next API key in setting.' )  )
                self.key_is_valid=False
                xbmc.sleep(1000)
                pass
            
        
    def get_thumbs(self,search_term, addtl_query_options=''):
        #from requests.compat import urljoin
        #search_term='"Bitter sweet symphony"'
        log( 'searching for:' + search_term)
        
        query='q={0}'.format(requests.utils.quote(   search_term  ) )
        #cx="cx={0}".format( '014375826027693914980%3Ahnuemd0yq-e' )             #The custom search engine ID to scope this search query  create in https://cse.google.com/cse/all
        #api_key="key={0}".format('AIzaSyAEbCtxVBENFzrDSnYrnUskdMLr7KaglGY')     #create from https://console.developers.google.com/apis/library
        #q_cx="cx={0}".format( '014375826027693914980%3Ahnuemd0yq-e' )             #The custom search engine ID to scope this search query  create in https://cse.google.com/cse/all
        #q_key="key={0}".format('AIzaSyAEbCtxVBENFzrDSnYrnUskdMLr7KaglGY')     #create from https://console.developers.google.com/apis/library
        q_cx="cx={0}".format( self.cx )                                    #The custom search engine ID to scope this search query  create in https://cse.google.com/cse/all
        q_key="key={0}".format( self.key )                             #create from https://console.developers.google.com/apis/library
        
        #2 things to do
        #  1- crete a custom search api
        #  2- create an api key and enable it for a custom search api
        
        #https://console.developers.google.com/apis/library
        #new project at left top corner arrow down
        #view more projects if not seen
        #dashboard - enable api (button)
        #  pick custom search api in blue hexagon header  --enable
        #credentials - create credential - api key
        
        #  use this query to search for images. 
        #url="https://www.googleapis.com/customsearch/v1?" + query + "&"+cx+ "&" + api_key + "&searchType=image"
        
        #  use this query to search for websites.
        url="https://www.googleapis.com/customsearch/v1?" + query + "&"+q_cx+ "&" + q_key + addtl_query_options
        
        
        #use this site to test the parameters:  #https://developers.google.com/apis-explorer/#p/customsearch/v1/search.cse.list
        #https://cse.google.com:443/cse/publicurl?cx=014375826027693914980:hnuemd0yq-e
        
        log( '   url='+url)
        thumbs=[]
        
        #with resources.lib.requests_cache.disabled():
        r=requests.get(url, timeout=REQ_TIMEOUT )
            #log( repr( r.text ))

        if r.status_code== requests.codes.ok:
        
            j=r.json()
            
            #j='{\n "error": {\n  "errors": [\n   {\n    "domain": "usageLimits",\n    "reason": "accessNotConfigured",\n    "message": "Access Not Configured. CustomSearch API has not been used in project 882410056812 before or it is disabled. Enable it by visiting https://console.developers.google.com/apis/api/customsearch/overview?project=882410056812 then retry. If you enabled this API recently, wait a few minutes for the action to propagate to our systems and retry.",\n    "extendedHelp": "https://console.developers.google.com/apis/api/customsearch/overview?project=882410056812"\n   }\n  ],\n  "code": 403,\n  "message": "Access Not Configured. CustomSearch API has not been used in project 882410056812 before or it is disabled. Enable it by visiting https://console.developers.google.com/apis/api/customsearch/overview?project=882410056812 then retry. If you enabled this API recently, wait a few minutes for the action to propagate to our systems and retry."\n }\n}\n'
            
            #log( pprint.pformat( j ) )
            if j.get('items'):
                log('   items: ' + repr(len(j.get('items'))))
            else:
                log('   no search result'  )
                raise Exception('No search result')
    
    
            # with + "&searchType=image"    not using this because thumbnail is too small and actual image is too big.  
            #for i in j.get('items'):
            #    log( repr(i.get('title')) )
            #    log( repr(i.get('link')) )
            #    p=i.get('image')
            #    log( repr(p.get('height'))  )
            #    log( repr(p.get('width'))  )
            
            # without + "&searchType=image"
            for i in j.get('items'):
                #log( '  Title:' + repr(i.get('title')) )
                p=i.get('pagemap')
                if p: #some results have no pagemap item
                    #log( '  cse_thumbnail ' + repr(p.get('cse_thumbnail'))  )
                    #log( '  cse_image ' + repr(p.get('cse_image'))  )
                    #log( '  imageobject ' + repr(p.get('imageobject'))  )
                    cse_thumbnail=p.get('cse_thumbnail')
                    
                    if cse_thumbnail:
                        thumb=cse_thumbnail[0].get('src')
                        width=int(cse_thumbnail[0].get('width'))
                        height=int(cse_thumbnail[0].get('height'))
                        #log( '  %dx%d %s' %(width, height, thumb)  )
                        
                        thumbs.extend(cse_thumbnail)
                    
            #log( pprint.pformat(thumbs) )
    
        else:
            #gdlex=google_limit_exception()
            log( '  request status code:' + repr(r.status_code) + ' ' + repr(r.text) )
            j=r.json()
            error=j.get('error')    
            log( '  request status code:' + repr(error.get('message')) )
            
            if error.get('errors')[0].get('reason')=='dailyLimitExceeded':
                raise google_limit_exception()
            
            #xbmc.executebuiltin('XBMC.Notification("%s","%s")' %(  error.get('errors')[0].get('reason'), error.get('message') )  )
        
        return thumbs
         
def save_dict( dict_to_save, pickle_filename ):
    with open(pickle_filename, 'wb') as output:
        pickle.dump(dict_to_save, output)
        output.close()

def load_dict( pickle_filename ):    
    with open(pickle_filename, 'rb') as inputpkl:
        rows_dict= pickle.load(inputpkl)
        inputpkl.close()    
    return rows_dict

if __name__ == '__main__':
    pass

