
#!/usr/bin/env python
# Modified by KenV99
# Modified a bit more by George Stockfisch <gstock.public@gmail.com>
#
# copied from https://github.com/KenV99/Tivo-Mind-Query
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
#    * Neither the name of the author nor the names of the contributors may be used to endorse or promote products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import logging
import random
import re
import socket
import ssl
import sys
import json

import __builtin__
#to set the log level of this script from the importer set "__builtin__.RPCLOGLEVEL = logging.INFO" or DEBUG/etc
if 'RPCLOGLEVEL' not in vars(__builtin__):
  print "Logelevel not defined by importee, setting to DEBUG"
  RPCLOGLEVEL = logging.DEBUG
logging.basicConfig(format='%(message)s', level=RPCLOGLEVEL)


tivo_addr = 'middlemind.tivo.com'
tivo_port = 443

rpc_id = 0
session_id = random.randrange(0x26c000, 0x27dc20)
remote = None

def RpcRequest(type, monitor=False, **kwargs ):
  global rpc_id
  rpc_id += 1
  if 'bodyId' in kwargs:
    body_id = kwargs['bodyId']
  #elif (type == "bodyAuthenticate" or type == "contentSearch" or type == "collectionSearch"):
  else:
    body_id = ''
  #else:
    #body_id = bodyId
  #  body_id = '8400001903B33D0'

  headers = '\r\n'.join((
      'Type: request',
      'RpcId: %d' % rpc_id,
      'SchemaVersion: 14',
      'Content-Type: application/json',
      'RequestType: %s' % type,
      'ResponseCount: %s' % (monitor and 'multiple' or 'single'),
      'BodyId: %s' % body_id,
      'X-ApplicationName: Quicksilver',
      'X-ApplicationVersion: 1.2',
      'X-ApplicationSessionId: 0x%x' % session_id,
      )) + '\r\n'

  req_obj = dict(**kwargs)
  req_obj.update({'type': type})

  body = json.dumps(req_obj) + '\n'

  # The "+ 2" is for the '\r\n' we'll add to the headers next.
  start_line = 'MRPC/2 %d %d' % (len(headers) + 2, len(body))

  return '\r\n'.join((start_line, headers, body))

def RpcRequestWithTsn(type, monitor=False, **kwargs ):
  global rpc_id
  rpc_id += 1
  if 'bodyId' in kwargs:
    body_id = kwargs['bodyId']
  else:
    body_id = '8400001903B33D0'

  headers = '\r\n'.join((
      'Type: request',
      'RpcId: %d' % rpc_id,
      'SchemaVersion: 14',
      'Content-Type: application/json',
      'RequestType: %s' % type,
      'ResponseCount: %s' % (monitor and 'multiple' or 'single'),
      'BodyId: %s' % body_id,
      'X-ApplicationName: Quicksilver',
      'X-ApplicationVersion: 1.2',
      'X-ApplicationSessionId: 0x%x' % session_id,
      )) + '\r\n'

  req_obj = dict(**kwargs)
  req_obj.update({'type': type})

  body = json.dumps(req_obj) + '\n'

  # The "+ 2" is for the '\r\n' we'll add to the headers next.
  start_line = 'MRPC/2 %d %d' % (len(headers) + 2, len(body))

  return '\r\n'.join((start_line, headers, body))

class Remote(object):
  username = ''
  password = ''
  tsn = ''

  def __init__(self, myusername, mypassword, mytsn):
    username = myusername
    password = mypassword
    self.username = myusername
    self.password = mypassword
    self.tsn = mytsn
    self.buf = ''
    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.ssl_socket = ssl.wrap_socket(self.socket, certfile='cdata.pem')
    try:
      self.ssl_socket.connect((tivo_addr, tivo_port))
    except:
      print  'connect error'
    try:
      self.Auth()
    except:
      print 'credential error'

  def PPrintJson(self, jsonString):
    if type(jsonString) is str:
      logging.debug(json.dumps(json.loads(jsonString), sort_keys=False, indent=4))
    else:
      logging.debug(json.dumps(jsonString, sort_keys=False, indent=4))
    return None


  def Read(self):
    start_line = ''
    head_len = None
    body_len = None

    while True:
      self.buf += self.ssl_socket.read(16)
      match = re.match(r'MRPC/2 (\d+) (\d+)\r\n', self.buf)
      if match:
        start_line = match.group(0)
        head_len = int(match.group(1))
        body_len = int(match.group(2))
        break

    need_len = len(start_line) + head_len + body_len
    while len(self.buf) < need_len:
      self.buf += self.ssl_socket.read(1024)
    buf = self.buf[:need_len]
    self.buf = self.buf[need_len:]

    # logging.debug('READ %s', buf)
    return json.loads(buf[-1 * body_len:])

  def Write(self, data):
    logging.debug('SEND %s', data)
    self.ssl_socket.send(data)

  def Auth(self):
    logging.debug("user:"+ self.username+ " pass: ********" )
    self.Write(RpcRequest('bodyAuthenticate',
        credential={
            'type': 'mmaCredential',
            'username': self.username,
            'password': self.password,
            }
        ))
    result = self.Read()
    if result['status'] != 'success':
      logging.error('Authentication failed!  Got: %s', result)
      sys.exit(1)

  def collectionSearchSeries(self, count, keywords):
    req = RpcRequest('collectionSearch',
       keyword=keywords,
       orderBy='strippedTitle',
       includeBroadcast='true',
       includeFree='true',
       includePaid='false',
       includeVod='false',
       levelOfDetail='medium',
       count=count,
       mergeOverridingCollections='true',
       filterUnavailable='false',
       collectionType='series'
    )
    self.Write(req)
    result = self.Read()
    return result

  def offerSearchLinear(self, title, subtitle):
    req = RpcRequest('offerSearch',
       count=25,
       bodyId=body_id,
       title=title,
       subtitle = subtitle
    )
    self.Write(req)
    result = self.Read()
    return result

  def offerSearchLinearPlus(self, title):
    req = RpcRequest('offerSearch',
       count=25,
       bodyId=body_id,
       title=title
    )
    self.Write(req)
    result = self.Read()
    return result

  def OfferSearchEpisodes(self, offset, collectionId, count = 25):
    req = RpcRequest('contentSearch',
      offset = offset,
      #filterUnavailable = 'false',
      count = count,
      orderBy = ['seasonNumber', 'episodeNum'],
      levelOfDetail = 'medium',
      collectionId = collectionId
    )
    self.Write(req)
    result = self.Read()
    return result

  def SearchEpisodes(self, count, max, keywords):
    #matched = 0
    result = self.collectionSearchSeries(count, keywords)
    logging.debug( "COllSearch:::: " + json.dumps(result))
    #return result
    collection = result.get('collection')
    foundIt = False
    if collection:
      ok = True
      for c in collection:
        if foundIt:
          break
        if c.get('collectionId'):
          logging.debug( '*******collectionId = ' + str(c.get('collectionId')))
          #if c.get('collectionId') == 'tivo:cl.16645':
          #print json.dumps(c)
          if (str(c.get('descriptionLanguage')) == "English"): 
            logging.debug( "title: " + str(c.get('title')) + " type: " + str(c.get('collectionType')))
          ok = True 
          if c.get('descriptionLanguage') and c.get('title'):
            #print 'lang = ' +c.get('descriptionLanguage') + ', title = ' + c.get('title')
            if not c.get('descriptionLanguage') == 'English':
              ok = False
            elif not c.get('title').lower() == keywords.lower():
              ok = False
          else:
            ok = False
            continue
          if not ok:
            continue
          stop = False
          offset = 0
          matched = 0
          while not stop:
            matched += 1
            result = self.OfferSearchEpisodes(offset, c.get('collectionId'))
            all = result.get('content')
            if all:
              for ep in all:
                #print json.dumps(ep)
                #print '==================================================='
                if ep.get('episodeNum'):
                  foundIt = True
                  logging.debug( 'S' + str(ep.get('seasonNumber')) + 'E' + str(ep.get('episodeNum')) + ':' + str(ep.get('partnerContentId')) + ' subTitle: ' + unicode(ep.get('subtitle')).encode('utf8') + '^' )
            #print json.dumps(result)
            #print '=============================='
            offset += count
            if matched > max:
              #print 'max exceeded'
              stop = True


  def collectionSearch(self, count, keywords):
    req = RpcRequest('collectionSearch',
       keyword=keywords,
       orderBy='strippedTitle',
       includeBroadcast='true',
       includeFree='true',
       includePaid='false',
       includeVod='false',
       levelOfDetail='medium',
       count=count,
       mergeOverridingCollections='true',
       filterUnavailable='false'
    )
    self.Write(req)
    result = self.Read()
    return result

  def offerSearch(self, offset, id):
    req = RpcRequest('offerSearch',
       offset=offset,
       count=25,
       namespace='trioserver',
       levelOfDetail='medium',
       collectionId=id
    )
    self.Write(req)
    result = self.Read()
    return result

  def Search(self, count, max, keywords):
    matched = 0
    #result = remote.collectionSearch(count, 'as good as it gets')
    result = self.collectionSearch(count, keywords)
    collection = result.get('collection')
    if collection:
      for c in collection:
        if c.get('collectionId'):
          stop = False
          offset = 0
          while not stop:
            result = self.offerSearch(offset, c.get('collectionId'))
            offers = result.get('offer')
            if offers:
              for offer in offers:
                if not stop:
                   matched += 1
                   #print json.dumps(offer, indent=4) + '\r\n-------------\r\n'
                   #print '{"offeritem": ' + json.dumps(offer) + '},'
                   logging.debug( json.dumps(offer) + ',')
                if matched > max:
                   stop = True
            else:
              stop = True

  def GetCollectionID(self,title, count=25):
    collections = self.collectionSearchSeries(count, title)
    collections = self.collectionSearch(count, title)
    collection = collections.get('collection')
    validCollections = []
    if collection:
      
      

      if( len(collection) > 1 ):
        logging.info( "Found more then 1 collection for : " + title)
        for c in collection:
          if ((c.get('descriptionLanguage') == "English" or c.get('descriptionLanguage') == None) 
            #and c.get('collectionId').startswith("tivo:cl.ts")
            and c.get('title').lower() == title.lower()): 
            logging.debug("CollectionID: " +  str(c.get('collectionId')))
            foundDescription = c.get('description')
            if (foundDescription != None):
              foundDescription = foundDescription.encode('utf-8')
            logging.debug( "title: " + str(c.get('title')))
            logging.debug( "desc_lang: " + str(c.get('descriptionLanguage')) )
            logging.debug( "desc: " )
            logging.debug( foundDescription )
            validCollections.append( c.get('collectionId'))
            #print c
    else:
      logging.info( "FAILED to get collection for title: " + title)

    if (len(validCollections) > 1 ):
      logging.info( "More then 1 collection found, not sure which to use")
      collectionCounter = 0
      collectionNumberArray = []
      for singleCollection in validCollections:
        logging.debug(  "SIngle collection:::: " + json.dumps(singleCollection).encode('utf-8') )
        firstEpisode = self.GetFirstEpisode(title,singleCollection,1,1)
        if ( firstEpisode.get('content') is not None):
          collectionNumberArray.append(singleCollection)
          #logging.debug( "FIrst episode: " )
          #self.PPrintJson(firstEpisode)
          logging.info( '[' + str(collectionCounter) + "] First epiiii: " + singleCollection )

          logging.info( firstEpisode.get('content')[0].get('collectionDescription'))#.get('collectionDescription')
          collectionCounter += 1
      inputSeries = input("Enter the number of the correct series: ")
      #TODO: this doesn't seem to work, in python 2.7, but the exception out will be a clue
      if ( type(inputSeries) != int):
        logging.info("Not a valid value")
      logging.info("Selected collectionid: " + collectionNumberArray[inputSeries])
      retCollectionID = collectionNumberArray[inputSeries]
      #return None
    else:
      print str(validCollections)
      retCollectionID = validCollections
    return retCollectionID

  def EpisodeSearch(self, title, collectionId, season, ep, count=1):
    logging.info("Episearch: " + str(title) + " coll: " + str(collectionId) + " sea: " + season + " ep: " + ep)
    req = RpcRequest('contentSearch',
            collectionId = collectionId,
            title = title,
            seasonNumber = season,
            episodeNum = ep,
            count = count,
            #mergeOverridingCollections='true',
           # filterUnavailable='false',
            collectionType='series'
          )
    self.Write(req)
    result = self.Read()
    logging.info( "Found: " + str(result) )
    return result

  def seasonEpisodeSearch(self, title, season, ep, count=25):
    #if remote:
    #  collections = remote.collectionSearchSeries(count, title)
    #else:
    collections = self.collectionSearchSeries(count, title)
    collection = collections.get('collection')
    if collection:
      logging.debug( "COLLLLL: " + str(collection) )
      for c in collection:
        if c.get('collectionId'):
          id = c.get('collectionId')
          logging.debug( '=============')
          logging.debug( 'collectionId = ' + id )
          req = RpcRequest('contentSearch',
            collectionId = id,
            title = title,
            seasonNumber = season,
            episodeNum = ep,
            count = 1,
            filterUnavailable='false',
            collectionType='series'
          )
          self.Write(req)
          result = self.Read()
          logging.debug( "contentID22222: " + str(req) )
          content = result.get('content')
          if content:
            logging.debug( json.dumps(content) )
            logging.debug( "contentID: " )
            logging.debug( content[0].get('partnerCollectionId') + '%' + content[0].get('partnerContentId') + '^' )
          #if result.get('content').get('partnerCollectionId') == 'epgProvider:cl.SH016916':
            #print json.dumps(result)
      return result

  def GetFirstEpisode(self, title, collectionId, seasonNum, episodeNum):
    req = RpcRequest('contentSearch',
              collectionId = collectionId,
              title = title,
              seasonNumber = seasonNum,
              episodeNum = episodeNum,
              count = 1,
              levelOfDetail = 'medium',
            )
    self.Write(req)
    result = self.Read()
    return result 


  def searchOneSeason(self, title, season, maxEp):
    count = 25
    stop = False;
    collections = self.collectionSearchSeries(count, title)
    collection = collections.get('collection')
    if collection:
      for c in collection:
        if stop == True:
          return
        if c.get('collectionId'):
          id = c.get('collectionId')
          #print '============='
          #print 'collectionId = ' + id
          for epn in range(1,int(maxEp)+1):
            ep = str(epn)
            req = RpcRequest('contentSearch',
              collectionId = id,
              title = title,
              seasonNumber = season,
              episodeNum = ep,
              count = 1,
            )
            self.Write(req)
            result = self.Read()
            content = result.get('content')
            if content:
              stop = True
              print ep + '%' + content[0].get('partnerCollectionId') + '%' + content[0].get('partnerContentId') + '^'

if __name__ == '__main__':
  try:
    title = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    searchType = sys.argv[5]
    subtitle = sys.argv[6]
    #print 'credentials = ' + username + ' (and) ' + password
    remote = Remote(username, password)
    if searchType == 'streaming':
      remote.SearchEpisodes (25, 100, title) # test 100 was 25
    elif searchType == 'linear':
      body_id = 'tsn:' + sys.argv[4]
      result = remote.offerSearchLinear(title, subtitle)
      offers = result.get('offer')
      if offers:
        for offer in offers:
          pid = str(offer.get('partnerContentId'))
          cl = str(offer.get('partnerCollectionId'))
          logging.debug( cl + '%' + pid + '^' )
          break
      else:
        logging.debug( 'error: no results' )
    elif searchType == 'linearplus':
      body_id = 'tsn:' + sys.argv[4]
      result = remote.offerSearchLinearPlus(title)
      offers = result.get('offer')
      if offers:
        for offer in offers:
          pid = str(offer.get('partnerContentId'))
          cl = str(offer.get('partnerCollectionId'))
          st = str(unicode(offer.get('subtitle')).encode('utf8') )
          s  = str(offer.get('seasonNumber') )
          if offer.get('episodeNum'):
            e  = str(offer.get('episodeNum') )
            logging.debug( 'S' + s + 'E' + e + ':' + pid + ' subTitle: ' + st + '^' )
          #break
      else:
        logging.debug(  'error: no results' )
    elif searchType == 'movie':
      count = 25
      max = 10
      logging.info( '{ "movieoffer":  [' )
      remote.Search(count, max, sys.argv[1] )
      logging.info( '] }' )
    elif searchType == 'seasonep':
      season = sys.argv[6]
      ep = sys.argv[7]
      logging.debug( json.dumps(remote.seasonEpisodeSearch(title, season, ep)) )
      logging.debug( "title: " + title + "ep: " + str(ep) + " season: " + season )
      #print json.dumps(remote.seasonEpisodeSearch(title, season, ep))
    elif searchType == 'season':
      season = sys.argv[6]
      maxEp = sys.argv[7]
      logging.debug( "title: " + title + " max: " + str(maxEp) + " season: " + season  )
      logging.debug( json.dumps(remote.searchOneSeason(title, season, maxEp)) )
    else:
      logging.debug( 'error: invalid search type: ' + searchType )
  except:
    logging.info( 'ErrorError' )
