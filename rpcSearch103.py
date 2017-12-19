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

def rpc_request(req_type, monitor=False, **kwargs):
    """Direct RPC request to TiVo Mind

    Args:
        req_type ():
        monitor (boolean):
        **kwargs: keys need to be in camelCase because they are passed on
            directly to request body
    """
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
            'RequestType: %s' % req_type,
            'ResponseCount: %s' % (monitor and 'multiple' or 'single'),
            'BodyId: %s' % body_id,
            'X-ApplicationName: Quicksilver',
            'X-ApplicationVersion: 1.2',
            'X-ApplicationSessionId: 0x%x' % SESSION_ID,
            )) + '\r\n'

    req_obj = dict(**kwargs)
    req_obj.update({'type': req_type})

    body = json.dumps(req_obj) + '\n'

    # The "+ 2" is for the '\r\n' we'll add to the headers next.
    start_line = 'MRPC/2 %d %d' % (len(headers) + 2, len(body))

    return '\r\n'.join((start_line, headers, body))

class Remote(object):
    def __init__(self, username, password):
        """Initialize Remote TiVo mind connection

        Args:
            username (str): tivo.com username
            password (str): tivo.com password
        """
        self.buf = ''
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ssl_socket = ssl.wrap_socket(self.socket, certfile='cdata.pem')
        try:
            self.ssl_socket.connect((TIVO_ADDR, TIVO_PORT))
        except:
            print('connect error')
            # re-raise so we know exact exception
            raise
        try:
            self._auth(username, password)
        except:
            print('credential error')
            # re-raise so we know exact exception
            raise

    def _read(self):
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

    def _write(self, data):
        logging.debug('SEND %s', data)
        self.ssl_socket.send(data)

    def _auth(self, username, password):
        """Private fxn only used in init of Remote to establish SSL credentials

        Args:
            username (str): tivo.com username
            password (str): tivo.com password
        """
        self._write(rpc_request('bodyAuthenticate',
                credential={
                        'type': 'mmaCredential',
                        'username': username,
                        'password': password,
                        }
                ))
        result = self._read()
        if result['status'] != 'success':
            logging.error('Authentication failed!  Got: %s', result)
            sys.exit(1)

    def collection_search_series(self, count, keywords):
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
        self._write(req)
        result = self._read()
        return result

    def offer_search_linear(self, title, subtitle, body_id):
        req = rpc_request('offerSearch',
              count=25,
              bodyId=body_id,
              title=title,
              subtitle=subtitle
        )
        self._write(req)
        result = self._read()
        return result

    def offer_search_linear_plus(self, title, body_id):
        req = rpc_request('offerSearch',
              count=25,
              bodyId=body_id,
              title=title
        )
        self._write(req)
        result = self._read()
        return result

    def offer_search_episodes(self, offset, collection_id):
        req = rpc_request('contentSearch',
            offset=offset,
            #filterUnavailable = 'false',
            count=25,
            orderBy=['seasonNumber', 'episodeNum'],
            levelOfDetail='medium',
            collectionId=collection_id
        )
        self._write(req)
        result = self._read()
        return result

    def search_episodes(self, count, max_matches, keywords):
        #matched = 0
        result = self.collection_search_series(count, keywords)
        collection = result.get('collection')
        found_it = False
        if collection:
            ok = True
            for c in collection:
                if found_it:
                    break
                if c.get('collectionId'):
                    #print('*******collectionId = ' + str(c.get('collectionId')))
                    #if c.get('collectionId') == 'tivo:cl.16645':
                    #print(json.dumps(c))
                    ok = True
                    if c.get('descriptionLanguage') and c.get('title'):
                        #print('lang = ' +c.get('descriptionLanguage') + \
                        #        ', title = ' + c.get('title'))
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
                        result = self.offer_search_episodes(
                                offset,
                                c.get('collectionId')
                                )
                        all_content = result.get('content')
                        if all_content:
                            for episode in all_content:
                                #print(json.dumps(episode))
                                #print('='*50)
                                if episode.get('episodeNum'):
                                    found_it = True
                                    print('S' + str(episode.get('seasonNumber')) + \
                                            'E' + str(episode.get('episodeNum')) + \
                                            ':' + str(episode.get('partnerContentId')) + \
                                            ' subTitle: ' + \
                                            str(episode.get('subtitle')).encode('utf8') + \
                                            '^')
                        #print(json.dumps(result))
                        #print('==============================')
                        offset += count
                        if matched > max_matches:
                            #print('max matches exceeded')
                            stop = True


    def collection_search(self, count, keywords):
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
        self._write(req)
        result = self._read()
        return result

    def offer_search(self, offset, collection_id):
        req = rpc_request('offerSearch',
              offset=offset,
              count=25,
              namespace='trioserver',
              levelOfDetail='medium',
              collectionId=collection_id
        )
        self._write(req)
        result = self._read()
        return result

    def search(self, count, max_matches, keywords):
        matched = 0
        #result = self.collection_search(count, 'as good as it gets')
        result = self.collection_search(count, keywords)
        collection = result.get('collection')
        if collection:
            for c in collection:
                if c.get('collectionId'):
                    stop = False
                    offset = 0
                    while not stop:
                        result = self.offer_search(offset, c.get('collectionId'))
                        offers = result.get('offer')
                        if offers:
                            for offer in offers:
                                if not stop:
                                    matched += 1
                                    #print(json.dumps(offer, indent=4) + '\r\n-------------\r\n')
                                    #print('{"offeritem": ' + json.dumps(offer) + '},')
                                    print(json.dumps(offer) + ',')
                                if matched > max_matches:
                                    stop = True
                        else:
                            stop = True

    def season_episode_search(self, title, season, episode):
        count = 25
        collections = self.collection_search_series(count, title)
        collection = collections.get('collection')
        if collection:
            for c in collection:
                if c.get('collectionId'):
                    collection_id = c.get('collectionId')
                    #print('=============')
                    #print('collectionId = ' + collection_id)
                    req = rpc_request('contentSearch',
                        collectionId=collection_id,
                        title=title,
                        seasonNumber=season,
                        episodeNum=episode,
                        count=1,
                    )
                    self._write(req)
                    result = self._read()
                    content = result.get('content')
                    if content:
                        print(content[0].get('partnerCollectionId') + '%' + \
                                content[0].get('partnerContentId') + '^')
        #return result


    def search_one_season(self, title, season, max_episode):
        count = 25
        stop = False
        collections = self.collection_search_series(count, title)
        collection = collections.get('collection')
        if collection:
            for c in collection:
                if stop:
                    return
                if c.get('collectionId'):
                    collection_id = c.get('collectionId')
                    #print('=============')
                    #print('collectionId = ' + collection_id)
                    for episode_num in range(1, int(max_episode)+1):
                        req = rpc_request('contentSearch',
                            collectionId=collection_id,
                            title=title,
                            seasonNumber=season,
                            episodeNum=str(episode_num),
                            count=1,
                        )
                        self._write(req)
                        result = self._read()
                        content = result.get('content')
                        if content:
                            stop = True
                            print(str(episode_num) + '%' + \
                                    content[0].get('partnerCollectionId') + \
                                    '%' + content[0].get('partnerContentId') + \
                                    '^'
                                    )

def main(argv):
    title = argv[1]
    username = argv[2]
    password = argv[3]
    search_type = argv[5]
    subtitle = argv[6]
    #print('credentials = ' + username + ' (and) ' + password)
    remote = Remote(username, password)
    if search_type == 'streaming':
        remote.search_episodes(25, 100, title) # test 100 was 25
    elif search_type == 'linear':
        body_id = 'tsn:' + argv[4]
        result = remote.offer_search_linear(title, subtitle, body_id)
        offers = result.get('offer')
        if offers:
            for offer in offers:
                pid = str(offer.get('partnerContentId'))
                cl = str(offer.get('partnerCollectionId'))
                print(cl + '%' + pid + '^')
                break
        else:
            print('error: no results')
    elif search_type == 'linearplus':
        body_id = 'tsn:' + argv[4]
        result = remote.offer_search_linear_plus(title, body_id)
        offers = result.get('offer')
        if offers:
            for offer in offers:
                pid = str(offer.get('partnerContentId'))
                cl = str(offer.get('partnerCollectionId'))
                # TODO: figure out what this should be.  Was:
                # subtitle = str(unicode(offer.get('subtitle')).encode('utf8') )
                subtitle = str(str(offer.get('subtitle')).encode('utf8'))
                season_num = str(offer.get('seasonNumber'))
                if offer.get('episodeNum'):
                    episode_num = str(offer.get('episodeNum'))
                    print('S' + season_num + 'E' + episode_num + ':' + pid + \
                            ' subTitle: ' + subtitle + '^')
                #break
        else:
            print('error: no results')
    elif search_type == 'movie':
        count = 25
        max_matches = 10
        print('{ "movieoffer":  [')
        remote.search(count, max_matches, argv[1])
        print('] }')
    elif search_type == 'seasonep':
        season = argv[6]
        episode = argv[7]
        remote.season_episode_search(title, season, episode)
        #print(json.dumps(remote.season_episode_search(title, season, episode)))
    elif search_type == 'season':
        season = argv[6]
        max_episode = argv[7]
        remote.search_one_season(title, season, max_episode)
    else:
        print('error: invalid search type: ' + search_type)

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
