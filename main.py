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
from google.appengine.ext import ndb
from google.appengine.api import urlfetch
import re


class BaseModel(ndb.Model):
    added_on = ndb.DateTimeProperty(auto_now_add = True)
    updated_on = ndb.DateTimeProperty(auto_now = True)

class Device(BaseModel):
    name = ndb.StringProperty()
    url = ndb.StringProperty()
    
class DeviceLocation(BaseModel):
    """
    A device is normally in one location.  This model is all the known locations
    for one device and it's signal strength.  
    
    This store can get quite large and will probably need to be refactored or pruned.
    """
    location = ndb.GeoPtProperty()
    rssi = ndb.FloatProperty()
    
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
        lat = input_object["location"]["lat"]
        lon = input_object["location"]["lon"]
        
        # Resolve the devices
        
        for obj in objects:
            key_id = None
            url = None
            
            if "id" in obj:
                key_id = obj["id"]
            elif "url" in obj:
                key_id = obj["url"]
                url = obj["url"]
                
                # We need to go and fetch.  We probably want to asyncly fetch.

            rssi = obj["rssi"]
            location = ndb.GeoPt(lat, lon)
            
            # In this model we can only deal with one device with a given ID.
            device = Device.get_or_insert(key_id, name = key_id, url = url)
            location = DeviceLocation(parent = device.key, location = location, rssi = rssi)
            location.put()
            
            device_data = {
              "id": device.name
            }
            
            if device.url is not None:
                #FetchAndStoreUrl(device.url)
               
                # Really if we don't have the data we should not return it.
                siteInfo = SiteInformation.get_by_id(device.url)
               
                if siteInfo is not None:
                    device_data["url"] = siteInfo.url 
                    device_data["title"] = siteInfo.title
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
        
def FetchAndStoreUrl(url):
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
        
        icon_search = re.search('<link rel="shortcut icon" src="([^\"]+)', result.content)
        if icon_search:
            icon = icon_search.group(1)
        
        SiteInformation.get_or_insert(url, url = url, title = title, description = description, content = result.content)

        
class Index(webapp2.RequestHandler):
    def get(self):
        self.response.out.write("")

class ResolveLocation(webapp2.RequestHandler):
    def post(self):
        self.response.out.write("")

app = webapp2.WSGIApplication([
    ('/', Index),
    ('/resolve-scan', ResolveScan),
    ('/resolve-location', ResolveLocation),
    ('/add-device', SaveUrl)
], debug=True)
