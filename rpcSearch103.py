#!/usr/bin/env python3
# Modified by KenV99
# Modified by Matthew Clapp

import logging
import random
import re
import socket
import ssl
import sys
import json


TIVO_ADDR = 'middlemind.tivo.com'
TIVO_PORT = 443

RPC_ID = 0
SESSION_ID = random.randrange(0x26c000, 0x27dc20)

def rpc_request(type, monitor=False, **kwargs):
    global RPC_ID
    RPC_ID += 1
    if 'bodyId' in kwargs:
        body_id = kwargs['bodyId']
    else:
        body_id = ''

    headers = '\r\n'.join((
            'Type: request',
            'RpcId: %d' % RPC_ID,
            'SchemaVersion: 14',
            'Content-Type: application/json',
            'RequestType: %s' % type,
            'ResponseCount: %s' % (monitor and 'multiple' or 'single'),
            'BodyId: %s' % body_id,
            'X-ApplicationName: Quicksilver',
            'X-ApplicationVersion: 1.2',
            'X-ApplicationSessionId: 0x%x' % SESSION_ID,
            )) + '\r\n'

    req_obj = dict(**kwargs)
    req_obj.update({'type': type})

    body = json.dumps(req_obj) + '\n'

    # The "+ 2" is for the '\r\n' we'll add to the headers next.
    start_line = 'MRPC/2 %d %d' % (len(headers) + 2, len(body))

    return '\r\n'.join((start_line, headers, body))

class Remote(object):
    def __init__(self, username, password):
        self.buf = ''
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ssl_socket = ssl.wrap_socket(self.socket, certfile='cdata.pem')
        try:
            self.ssl_socket.connect((TIVO_ADDR, TIVO_PORT))
        except:
            print('connect error')
        try:
            self.Auth(username, password)
        except:
            print('credential error')

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

    def Auth(self, username, password):
        self.Write(rpc_request('bodyAuthenticate',
                credential={
                        'type': 'mmaCredential',
                        'username': username,
                        'password': password,
                        }
                ))
        result = self.Read()
        if result['status'] != 'success':
            logging.error('Authentication failed!  Got: %s', result)
            sys.exit(1)

    def collectionSearchSeries(self, count, keywords):
        req = rpc_request('collectionSearch',
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

    def offerSearchLinear(self, title, subtitle, body_id):
        req = rpc_request('offerSearch',
              count=25,
              bodyId=body_id,
              title=title,
              subtitle=subtitle
        )
        self.Write(req)
        result = self.Read()
        return result

    def offerSearchLinearPlus(self, title, body_id):
        req = rpc_request('offerSearch',
              count=25,
              bodyId=body_id,
              title=title
        )
        self.Write(req)
        result = self.Read()
        return result

    def OfferSearchEpisodes(self, offset, collectionId):
        req = rpc_request('contentSearch',
            offset=offset,
            #filterUnavailable = 'false',
            count=25,
            orderBy=['seasonNumber', 'episodeNum'],
            levelOfDetail='medium',
            collectionId=collectionId
        )
        self.Write(req)
        result = self.Read()
        return result

    def SearchEpisodes(self, count, max, keywords):
        #matched = 0
        result = self.collectionSearchSeries(count, keywords)
        collection = result.get('collection')
        foundIt = False
        if collection:
            ok = True
            for c in collection:
                if foundIt:
                    break
                if c.get('collectionId'):
                    #print '*******collectionId = ' + str(c.get('collectionId'))
                    #if c.get('collectionId') == 'tivo:cl.16645':
                    #print json.dumps(c)
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
                                    print('S' + str(ep.get('seasonNumber')) + 'E' + str(ep.get('episodeNum')) + ':' + str(ep.get('partnerContentId')) + ' subTitle: ' + str(ep.get('subtitle')).encode('utf8') + '^')
                        #print json.dumps(result)
                        #print '=============================='
                        offset += count
                        if matched > max:
                            #print 'max exceeded'
                            stop = True


    def collectionSearch(self, count, keywords):
        req = rpc_request('collectionSearch',
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
        req = rpc_request('offerSearch',
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
        #result = self.collectionSearch(count, 'as good as it gets')
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
                                    print(json.dumps(offer) + ',')
                                if matched > max:
                                    stop = True
                        else:
                            stop = True

    def seasonEpisodeSearch(self, title, season, ep):
        count = 25
        collections = self.collectionSearchSeries(count, title)
        collection = collections.get('collection')
        if collection:
            for c in collection:
                if c.get('collectionId'):
                    id = c.get('collectionId')
                    #print '============='
                    #print 'collectionId = ' + id
                    req = rpc_request('contentSearch',
                        collectionId=id,
                        title=title,
                        seasonNumber=season,
                        episodeNum=ep,
                        count=1,
                    )
                    self.Write(req)
                    result = self.Read()
                    content = result.get('content')
                    if content:
                        print(content[0].get('partnerCollectionId') + '%' + content[0].get('partnerContentId') + '^')
                    #if result.get('content').get('partnerCollectionId') == 'epgProvider:cl.SH016916':
                        #print json.dumps(result)
        #return result


    def searchOneSeason(self, title, season, maxEp):
        count = 25
        stop = False
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
                    for epn in range(1, int(maxEp)+1):
                        ep = str(epn)
                        req = rpc_request('contentSearch',
                            collectionId=id,
                            title=title,
                            seasonNumber=season,
                            episodeNum=ep,
                            count=1,
                        )
                        self.Write(req)
                        result = self.Read()
                        content = result.get('content')
                        if content:
                            stop = True
                            print(ep + '%' + content[0].get('partnerCollectionId') + '%' + content[0].get('partnerContentId') + '^')

def main(argv):
    title = argv[1]
    username = argv[2]
    password = argv[3]
    searchType = argv[5]
    subtitle = argv[6]
    #print 'credentials = ' + username + ' (and) ' + password
    remote = Remote(username, password)
    if searchType == 'streaming':
        remote.SearchEpisodes(25, 100, title) # test 100 was 25
    elif searchType == 'linear':
        body_id = 'tsn:' + argv[4]
        result = remote.offerSearchLinear(title, subtitle, body_id)
        offers = result.get('offer')
        if offers:
            for offer in offers:
                pid = str(offer.get('partnerContentId'))
                cl = str(offer.get('partnerCollectionId'))
                print(cl + '%' + pid + '^')
                break
        else:
            print('error: no results')
    elif searchType == 'linearplus':
        body_id = 'tsn:' + argv[4]
        result = remote.offerSearchLinearPlus(title, body_id)
        offers = result.get('offer')
        if offers:
            for offer in offers:
                pid = str(offer.get('partnerContentId'))
                cl = str(offer.get('partnerCollectionId'))
                # TODO: figure out what this should be.  Was:
                # st = str(unicode(offer.get('subtitle')).encode('utf8') )
                st = str(str(offer.get('subtitle')).encode('utf8'))
                s = str(offer.get('seasonNumber'))
                if offer.get('episodeNum'):
                    e = str(offer.get('episodeNum'))
                    print('S' + s + 'E' + e + ':' + pid + ' subTitle: ' + st + '^')
                #break
        else:
            print('error: no results')
    elif searchType == 'movie':
        count = 25
        max = 10
        print('{ "movieoffer":  [')
        remote.Search(count, max, argv[1])
        print('] }')
    elif searchType == 'seasonep':
        season = argv[6]
        ep = argv[7]
        remote.seasonEpisodeSearch(title, season, ep)
        #print json.dumps(remote.seasonEpisodeSearch(title, season, ep))
    elif searchType == 'season':
        season = argv[6]
        maxEp = argv[7]
        remote.searchOneSeason(title, season, maxEp)
    else:
        print('error: invalid search type: ' + searchType)

    # no error status
    return 0

if __name__ == "__main__":
    try:
        status = main(sys.argv)
    except KeyboardInterrupt:
        print("Stopped by Keyboard Interrupt", file=sys.stderr)
        # exit error code for Ctrl-C
        status = 130

    sys.exit(status)
