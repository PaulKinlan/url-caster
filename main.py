#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import webapp2
import json
import logging
from datetime import datetime, timedelta
from google.appengine.ext import ndb
from google.appengine.api import urlfetch
import re


class BaseModel(ndb.Model):
    added_on = ndb.DateTimeProperty(auto_now_add = True)
    updated_on = ndb.DateTimeProperty(auto_now = True)

class Device(BaseModel):
    name = ndb.StringProperty()
    url = ndb.StringProperty()
        
class SiteInformation(BaseModel):
    url = ndb.StringProperty()
    favicon_url = ndb.StringProperty()
    title = ndb.StringProperty()
    description = ndb.StringProperty()
    content = ndb.TextProperty()
    
class ResolveScan(webapp2.RequestHandler):
    def post(self):
        input_data = self.request.body
        input_object = json.loads(input_data) # Data is not sanitised.
        
        metadata_output = []
        output = {
          "metadata": metadata_output
        }
        
        devices = []
        objects = input_object["objects"]
        
        # Resolve the devices
        
        for obj in objects:
            key_id = None
            url = None
            force = False
            
            if "id" in obj:
                key_id = obj["id"]
            elif "url" in obj:
                key_id = obj["url"]
                url = obj["url"]

            if "force" in obj:
                force = True
                
            # We need to go and fetch.  We probably want to asyncly fetch.

            rssi = obj["rssi"]
           
            # In this model we can only deal with one device with a given ID.
            device = Device.get_or_insert(key_id, name = key_id, url = url)
         
            device_data = {
              "id": device.name
            }
            
            if force or device.url is not None:
                # Really if we don't have the data we should not return it.
                siteInfo = SiteInformation.get_by_id(device.url)

                if siteInfo is None or siteInfo.updated_on < datetime.now() - timedelta(hours=5):
                    # If we don't have the data or it is older than 5 hours, fetch.
                    siteInfo = FetchAndStoreUrl(siteInfo, device.url)
                    logging.info(siteInfo)
               
                if siteInfo is not None:
                    device_data["url"] = siteInfo.url 
                    device_data["title"] = siteInfo.title
                    device_data["description"] = siteInfo.description
                    device_data["icon"] = siteInfo.favicon_url
                else:
                    device_data["url"] = device.url
                        
            metadata_output.append(device_data)
            
        # Resolve from DB based off key.
        logging.info(output)
        self.response.out.write(json.dumps(output))
        
class SaveUrl(webapp2.RequestHandler):
    def post(self):
        name = self.request.get("name")
        url = self.request.get("url")
        
        title = ""
        icon = "/favicon.ico"
        
        device = Device.get_or_insert(name, name = name, url = url)
        device.url = url
        device.put()
        
        
        # Index the page
        FetchAndStoreUrl(device.url)
        self.redirect("/index.html")
        
def FetchAndStoreUrl(siteInfo, url):
    # Index the page
    result = urlfetch.fetch(url)
    if result.status_code == 200:
        title = ""
        description = ""
        icon = "/favicon.ico"
        # parse the content
        title_search = re.search('<title>(.+)</title>', result.content)
        description_search = re.search('<meta name="description" content="([^\"]+)', result.content)
        if title_search:
            title = title_search.group(1)
       
        if description_search:
            description = description_search.group(1)
        
        icon_search = re.search('<link rel="shortcut icon"([^>]+)href="([^\"]+)', result.content) or \
            re.search("<link rel='shortcut icon'([^>]+)href='([^\']+)", result.content) or \
            re.search('<link rel="icon"([^>]+)href="([^\"]+)', result.content) or \
            re.search("<link rel='icon'([^>]+)href='([^\']+)", result.content) or \
            re.search('<link rel="apple-touch-icon"([^>]+)href=([^\"]+)', result.content) or \
            re.search("<link rel='apple-touch-icon'([^>]+)href=([^\']+)", result.content)
        
        if icon_search:
            icon = icon_search.group(2)

        
        if siteInfo is None:
            siteInfo = SiteInformation.get_or_insert(url, url = url, 
                title = title, 
                favicon_url = icon, 
                description = description, 
                content = result.content)
        else:
            # update the data because it already exists
            siteInfo.put()

    return siteInfo

class Index(webapp2.RequestHandler):
    def get(self):
        self.response.out.write("")

app = webapp2.WSGIApplication([
    ('/', Index),
    ('/resolve-scan', ResolveScan),
    ('/add-device', SaveUrl)
], debug=True)
