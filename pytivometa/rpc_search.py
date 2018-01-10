#!/usr/bin/env python3
# Modified by KenV99
# Modified by Matthew Clapp

# debug_fxn_omit decorator is used when we don't want to write password to
#   log file

# TODO: catch HTTP errors of _rpc_request
#   HTTP 5xx server error
# TODO: catch RPC error dictionary error
#   {
#       "code": <error code string>
#       "text": <error explanation>
#       "type": <"error" or ?>
#   }

import logging
import os.path
import random
import re
import socket
import ssl
import sys
import json
import pprint


TIVO_ADDR = 'middlemind.tivo.com'
TIVO_PORT = 443

# Set up logger
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

PP = pprint.PrettyPrinter(indent=4, depth=3)


# debug decorator that announces function call/entry and lists args
def debug_fxn(func):
    """Function decorator that prints the function name and the arguments used
    in the function call before executing the function
    """
    def func_wrapper(*args, **kwargs):
        log_string = "FXN:" + func.__qualname__ + "(\n"
        for arg in args[1:]:
            log_string += "        " + repr(arg) + ",\n"
        for key in kwargs:
            log_string += "        " + key + "=" + repr(kwargs[key]) + ",\n"
        log_string += "        )"
        LOGGER.info(log_string)
        return func(*args, **kwargs)
    return func_wrapper

# debug decorator that announces function call/entry and lists args
#   this one accepts arguments of positional or keyword arguments to omit
def debug_fxn_omit(omit_args=None, omit_kwargs=None):
    if omit_args == None:
        omit_args = []
    if omit_kwargs == None:
        omit_kwargs = []
    def debug_fxn_int(func):
        """Function decorator that prints the function name and the arguments used
        in the function call before executing the function
        """
        def func_wrapper(*args, **kwargs):
            log_string = "FXN:" + func.__qualname__ + "(\n"
            for (i,arg) in enumerate(args[1:]):
                if i not in omit_args:
                    log_string += "        " + repr(arg) + ",\n"
                else:
                    log_string += "        " + "*** REDACTED ***" + ",\n"
            for key in kwargs:
                if key not in omit_kwargs:
                    log_string += "        " + key + "=" + repr(kwargs[key]) + ",\n"
                else:
                    log_string += "        " + key + "=" + "*** REDACTED ***" + ",\n"
            log_string += "        )"
            LOGGER.info(log_string)
            return func(*args, **kwargs)
        return func_wrapper
    return debug_fxn_int

class Error(Exception):
    """Base class for all RPC errors
    """
    pass

class AuthError(Error):
    pass

class MindTimeoutError(Error):
    pass

class MindInternalError(Error):
    pass

class Remote(object):
    @debug_fxn_omit(omit_args=[1])
    def __init__(self, username, password, lang='English'):
        """Initialize Remote TiVo mind SSL socket connection

        Args:
            username (str): tivo.com username
            password (str): tivo.com password
            lang (str): what language of description to look for (default is
                'English') Set to '' if all languages should be searched

        Returns:
            dict: one key 'collection' is collection list, other key
                'type' is 'collectionList'

        Raises:
            AuthError: in case unable to auth, possibly bad password and/or
                username
        """
        # language to search for descriptions in descriptionLanguage
        self.lang = lang

        # unique ID for entire session
        self.session_id = random.randrange(0x26c000, 0x27dc20)
        # unique ID for each request
        self.rpc_id = 0
        # read buffer is bytes
        self.buf = b''
        # initialize SSL socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ssl_socket = ssl.wrap_socket(
                self.socket,
                certfile=os.path.join(
                    os.path.dirname(os.path.realpath(__file__)),
                    'cdata.pem'
                    )
                )
        try:
            self.ssl_socket.connect((TIVO_ADDR, TIVO_PORT))
        except:
            print('connect error')
            LOGGER.error('SSL socket initial connection error', exc_info=True)
            # re-raise so we know exact exception to enumerate code
            raise

        # may raise AuthError, calling code should catch
        self._auth(username, password)

    @debug_fxn
    def _get_rpc_id(self):
        """Fetches and then increments self.rpc_id for RPC requests

        Returns:
            int: rpc_id to use now
        """
        rpc_id = self.rpc_id
        self.rpc_id = self.rpc_id + 1
        return rpc_id

    @debug_fxn_omit(omit_kwargs=['credential'])
    def _rpc_request(self, req_type, monitor=False, **kwargs):
        """Format key=value pairs into string for RPC request to TiVo Mind

        Args:
            req_type (str):
            monitor (boolean): ResponseCount = 'multiple' if True, 'single' if False
            **kwargs: keys need to be in camelCase because they are passed on
                directly to JSON request body

        Returns:
            str: actual json-formatted request with headers, body, etc.
        """
        if 'bodyId' in kwargs:
            body_id = kwargs['bodyId']
        else:
            body_id = ''

        headers = '\r\n'.join((
                'Type: request',
                'RpcId: %d' % self._get_rpc_id(),
                'SchemaVersion: 14',
                'Content-Type: application/json',
                'RequestType: %s' % req_type,
                'ResponseCount: %s' % (monitor and 'multiple' or 'single'),
                'BodyId: %s' % body_id,
                'X-ApplicationName: Quicksilver',
                'X-ApplicationVersion: 1.2',
                'X-ApplicationSessionId: 0x%x' % self.session_id,
                )) + '\r\n'

        req_obj = dict(**kwargs)
        req_obj.update({'type': req_type})

        body = json.dumps(req_obj) + '\n'

        # The "+ 2" is for the '\r\n' we'll add to the headers next.
        start_line = 'MRPC/2 %d %d' % (len(headers) + 2, len(body))

        return '\r\n'.join((start_line, headers, body))

    @debug_fxn
    def _read(self):
        """Reads json data from ssl socket, parses and returns data structure

        Returns:
            list, dict, etc.: Python arbitrary complex data structure
        """
        start_line = ''
        head_len = None
        body_len = None

        while True:
            self.buf += self.ssl_socket.read(16)
            match = re.match(r'MRPC/2 (\d+) (\d+)\r\n', self.buf.decode('utf-8'))
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

        # LOGGER.debug('READ %s', buf)

        returnval = json.loads(buf[-1 * body_len:].decode('utf-8'))

        if returnval.get('code', '') == 'mindUnavailable':
            raise MindTimeoutError()

        return returnval

    def _write(self, data):
        """Send string to established SSL RPC socket

        Args:
            data (str): raw string to send to RPC SSL socket
        """
        # the following nukes password in data so it isn't logged
        data_logged = re.sub(
                r'(["\']password["\']\s*:).+',
                r'\1 *** REDACTED ***',
                data
                )
        LOGGER.debug('SEND %s', data_logged)
        bytes_written = self.ssl_socket.send(data.encode('utf-8'))
        LOGGER.debug("%d bytes written", bytes_written)

    @debug_fxn_omit(omit_args=[1])
    def _auth(self, username, password):
        """Private fxn only used in init of Remote to establish SSL credentials

        Args:
            username (str): tivo.com username
            password (str): tivo.com password

        Raises:
            AuthError: for any failure to authenticate SSL RPC connection
        """
        self._write(self._rpc_request('bodyAuthenticate',
                credential={
                        'type': 'mmaCredential',
                        'username': username,
                        'password': password,
                        }
                ))
        result = self._read()
        # Successful response:
        #   {
        #       'message': '',
        #       'status': 'success',
        #       'deviceId': [
        #           {
        #               'friendlyName': "XXXXXXXX",
        #               'id': 'tsn:00000000000000A',
        #               'capabilities': {
        #                   'features': ['promptToExtendLive', 'overlapProtection'],
        #                   'type': 'bodyCapabilities'
        #                   },
        #               'serviceLocation': {
        #                   'port': 443,
        #                   'server': 'mm3.tivoservice.com',
        #                   'type': 'serviceLocationInstruction',
        #                   'serviceLocationType': 'secureApi'
        #                   },
        #               'type': 'anyBody',
        #               'deviceType': 'stb'
        #           },
        #           {
        #               'friendlyName': "XXXXXXXX",
        #               'id': 'tsn:00000000000000B',
        #               'capabilities': {
        #                   'features': [
        #                       'middlemind',
        #                       'supportsOnePass',
        #                       'promptToExtendLive',
        #                       'overlapProtection',
        #                       'middlemind-xmppActions',
        #                       'middlemindRouteBack'
        #                       ],
        #                   'type': 'bodyCapabilities'
        #                   },
        #               'serviceLocation': {
        #                   'port': 443,
        #                   'server': 'mm1.tivoservice.com',
        #                   'type': 'serviceLocationInstruction',
        #                   'serviceLocationType': 'secureApi'
        #                   },
        #               'type': 'anyBody',
        #               'deviceType': 'stb'
        #           }
        #           ],
        #       'type': 'bodyAuthenticateResponse',
        #       'mediaAccessKey': '0000000000'
        #   }
        #
        # Bad password response:
        #   {
        #       'code': 'authenticationFailed',
        #       'text': "error response from IT code: 'usernamePasswordError' text: 'Authentication Failed'",
        #       'type': 'error'
        #   }
        if result['type'] == 'error':
            LOGGER.error('Authentication failed!  RPC response: %s', result['text'])
            raise AuthError

    @debug_fxn
    def rpc_req_generic(self, req_type, **kwargs):
        """Send specified RPC request and accept returned value
        Args:
            req_type (str):
            **kwargs: key=value pairs sent directly as part of RPC request

        Returns:
            dict: key=value pairs representing all fields of RPC return val

        Raises:
            MindTimeoutError: if mind returns 'code':'mindUnavailable'
        """
        req = self._rpc_request(req_type, **kwargs)
        self._write(req)
        result = self._read()
        return result

    @debug_fxn
    def search_series(self, title_keywords):
        """
        Returns:
            list: of series collection dict objects

        Raises:
            MindTimeoutError: if mind returns 'code':'mindUnavailable'
        """
        resp_template = [
                {
                    'type': 'responseTemplate',
                    'fieldName': ['collection'],
                    'typeName': 'collectionList'
                    },
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'category',
                        'collectionId',
                        'credit',
                        'title',
                        'partnerCollectionId',
                        'description',
                        'descriptionLanguage',
                        'episodic',
                        'internalRating',
                        'rating',
                        'tvRating'
                        ],
                    'typeName': 'collection'
                    },
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'categoryId',
                        'displayRank',
                        'label',
                        'topLevel',
                        ],
                    'typeName': 'category'
                    },
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'personId',
                        'role',
                        'last',
                        'first',
                        'characterName',
                        'fullName',
                        ],
                    'typeName': 'credit'
                    },
                ]
        results = self.rpc_req_generic(
                'collectionSearch',
                titleKeyword=title_keywords,
                collectionType='series',
                responseTemplate=resp_template,
                count=25,
                filterUnavailable='false',
                includeBroadcast='true',
                includeFree='true',
                includePaid='false',
                includeVod='false',
                mergeOverridingCollections='true',
                orderBy='strippedTitle',
                )

        collection_list = results['collection']

        LOGGER.debug("ORIGINAL, Total: %d"%(len(collection_list)))

        # filter by language
        #   do this by hand because e.g. 'English' needs to be able to match
        #   'English' or 'English GB' and no way to do this using rpc filter
        collection_list = [
                x
                for x in collection_list
                if self.lang in x.get('descriptionLanguage', '')
                ]

        LOGGER.debug("AFTER LANGUAGE FILTERING, Total: %d"%(len(collection_list)))

        # filter for presence of 'partnerCollectionId', useless if absent
        collection_list = [
                x
                for x in collection_list
                if 'partnerCollectionId' in x
                ]

        LOGGER.debug("AFTER FILTERING FOR partnerCollectionId, Total: %d"%(len(collection_list)))

        for collection in collection_list:
            season1ep1 = self.get_first_aired(collection['collectionId'])
            collection['firstAired'] = season1ep1.get('originalAirdate', '')

        return collection_list

    @debug_fxn
    def get_first_aired(self, collection_id):
        """

        Raises:
            MindTimeoutError: if mind returns 'code':'mindUnavailable'
        """
        resp_template = [
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'content',
                        ],
                    'typeName': 'contentList'
                    },
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'originalAirdate',
                        'originalAirYear',
                        'releaseDate',
                        ],
                    'typeName': 'content'
                    },
                ]
        results = self.rpc_req_generic(
                'contentSearch',
                collectionId=collection_id,
                seasonNumber=1,
                episodeNum=1,
                count=1,
                responseTemplate=resp_template,
                )

        returnval = {}
        if results.get('content', None) is not None:
            returnval['originalAirdate'] = results['content'][0]['originalAirdate']
            returnval['originalAirYear'] = results['content'][0]['originalAirYear']
            returnval['releaseDate'] = results['content'][0]['releaseDate']

        return returnval

    @debug_fxn
    def get_series_info(self, collection_id):
        """Return info for series identified by Mind collection ID

        Args:
            collection_id (str): Mind collection ID string

        Returns:
            dict: key:values are info about series

        Raises:
            MindTimeoutError: if mind returns 'code':'mindUnavailable'
        """
        resp_template = [
                {
                    'type': 'responseTemplate',
                    'fieldName': ['collection'],
                    'typeName': 'collectionList'
                    },
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'category',
                        'collectionId',
                        'credit',
                        'title',
                        'partnerCollectionId',
                        'description',
                        'descriptionLanguage',
                        'episodic',
                        'internalRating',
                        'rating',
                        'tvRating'
                        ],
                    'typeName': 'collection'
                    },
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'categoryId',
                        'displayRank',
                        'label',
                        'topLevel',
                        ],
                    'typeName': 'category'
                    },
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'personId',
                        'role',
                        'last',
                        'first',
                        'characterName',
                        'fullName',
                        ],
                    'typeName': 'credit'
                    },
                ]
        results = self.rpc_req_generic(
                'collectionSearch',
                collectionId=collection_id,
                responseTemplate=resp_template,
                count=1,
                filterUnavailable='false',
                includeBroadcast='true',
                includeFree='true',
                includePaid='false',
                includeVod='false',
                mergeOverridingCollections='true',
                orderBy='strippedTitle',
                )
        return results['collection'][0]

    @debug_fxn
    def get_program_id(self, collection_id, season_num=None, episode_num=None,
            year=None, month=None, day=None):
        """Return specific program ID given some search criteria. Must have
        (season_num AND episode_num) OR (year AND month AND day)

        Args:
            collection_id (str):
            season_num (str):
            episode_num (str):
            year (str):
            month (str):
            day (str):
        Returns:
            str: str of Mind program ID

        Raises:
            MindTimeoutError: if mind returns 'code':'mindUnavailable'
        """
        resp_template = [
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'content',
                        ],
                    'typeName': 'contentList'
                    },
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'partnerContentId',
                        ],
                    'typeName': 'content'
                    },
                ]
        if season_num is not None and episode_num is not None:
            LOGGER.debug("rpc: season episode")
            results = self.rpc_req_generic(
                    'contentSearch',
                    collectionId=collection_id,
                    seasonNumber=season_num,
                    episodeNum=episode_num,
                    count=1,
                    responseTemplate=resp_template,
                    )
            program_id = results['content'][0]['partnerContentId']

        elif year is not None and month is not None and day is not None:
            LOGGER.debug("rpc: year month day")
            # search through all episodes, looking for air_date match
            result = self.get_program_id_airdate(
                    collection_id,
                    year=year,
                    month=month,
                    day=day,
                    )
            program_id = result.get('partnerContentId', None)
        else:
            # TODO: real error handling
            print("Error, not enough info to find specific episode")
            program_id = None

        return program_id

    @debug_fxn
    def get_program_id_airdate(self, collection_id,
            year=None, month=None, day=None):
        """Get Mind program ID given year AND month AND day
        Args:
            collection_id (str): Mind series ID
            year (str): year of program's airing
            month (str): month of program's airing
            day (str): day of program's airing

        Returns:
            str: program ID for episode

        Raises:
            MindTimeoutError: if mind returns 'code':'mindUnavailable'
        """
        returnval = {}
        air_date = "%04d-%02d-%02d"%(int(year), int(month), int(day))
        resp_template = [
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'content',
                        'isTop',
                        'isBottom',
                        ],
                    'typeName': 'contentList'
                    },
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'seasonNumber',
                        'episodeNum',
                        'originalAirdate',
                        'partnerContentId',
                        ],
                    'typeName': 'content'
                    },
                ]
        results_per_req = 25
        i = 0
        done = False
        while not done:
            results = self.rpc_req_generic(
                    'contentSearch',
                    collectionId=collection_id,
                    count=results_per_req,
                    offset=results_per_req*i,
                    responseTemplate=resp_template,
                    )
            if results['isBottom']:
                done = True
            for result in results['content']:
                if result.get('originalAirdate', '') == air_date:
                    returnval = result
                    done = True
                    break
            i += 1

        return returnval

    @debug_fxn
    def _filter_movie_results(self, collection_list, year=None):
        LOGGER.debug("ORIGINAL, Total: %d"%(len(collection_list)))
        # DEBUG DELETEME
        #for coll in collection_list:
        #    LOGGER.debug("--------")
        #    LOGGER.debug("title: " + str(coll['title']))
        #    LOGGER.debug("movieYear: " + str(coll.get('movieYear', '')))

        # no results or 1 result, return early
        #if len(collection_list) == 1:
        #    LOGGER.debug(collection_list[0]['collectionId'])
        #    self.search_movie_content(collection_list[0]['collectionId'])
        #    return collection_list
        #elif len(collection_list) == 0:
        #    return collection_list

        # Filter 1: by language
        # filter for either self.lang in descriptionLanguage or missing
        #   do this by hand because e.g. 'English' needs to be able to match
        #   'English' or 'English GB' or missing descriptionLanguage.
        #   No way to do this using rpc filter
        collection_list = [
                x
                for x in collection_list
                if self.lang in x.get('descriptionLanguage', self.lang)
                ]

        LOGGER.debug("AFTER LANGUAGE FILTERING, Total: %d"%(len(collection_list)))

        # DEBUG DELETEME
        #for coll in collection_list:
        #    LOGGER.debug("--------")
        #    LOGGER.debug("title: " + str(coll['title']))
        #    LOGGER.debug("movieYear: " + str(coll.get('movieYear', '')))

        # no results or 1 result, return early
        #if len(collection_list) == 1:
        #    LOGGER.debug(collection_list[0]['collectionId'])
        #    self.search_movie_content(collection_list[0]['collectionId'])
        #    return collection_list
        #elif len(collection_list) == 0:
        #    return collection_list

        # Filter 2: for presence of 'partnerCollectionId', (useless if absent)
        #   also look for 'epgProvider:' starting partnerCollectionId, otherwise
        #   not useful for pytivo
        collection_list = [
                x
                for x in collection_list
                if x.get('partnerCollectionId','').startswith('epgProvider:')
                ]

        LOGGER.debug("AFTER FILTERING FOR partnerCollectionId: epgProvider:, Total: %d"%(len(collection_list)))

        # DEBUG DELETEME
        for coll in collection_list:
            LOGGER.debug("--------")
            LOGGER.debug("title: " + str(coll['title']))
            LOGGER.debug("movieYear: " + str(coll.get('movieYear', '')))

        # no results or 1 result, return early
        #if len(collection_list) == 1:
        #    LOGGER.debug(collection_list[0]['collectionId'])
        #    self.search_movie_content(collection_list[0]['collectionId'])
        #    return collection_list
        #elif len(collection_list) == 0:
        #    return collection_list

        # Filter 3: for proper movieYear
        #   NOTE: sometimes RPC movie year can be (IMDB movie year + 1)
        if year is not None:
            year = int(year)
            old_collection_list = collection_list
            collection_list = [
                    x
                    for x in collection_list
                    if year == x.get('movieYear', 0)
                    ]
            if not collection_list:
                # if no movies left, try supplied year + 1 or year - 1
                LOGGER.debug("Trying year +/- 1")
                collection_list = [
                        x
                        for x in old_collection_list
                        if year - 1 <= x.get('movieYear', 0) <= year + 1
                        ]

        LOGGER.debug("AFTER YEAR FILTERING, Total: %d"%(len(collection_list)))

        # DEBUG DELETEME
        for coll in collection_list:
            LOGGER.debug("--------")
            LOGGER.debug("title: " + str(coll['title']))
            LOGGER.debug("movieYear: " + str(coll.get('movieYear', '')))

        return collection_list

    @debug_fxn
    def search_movie(self, title_keywords, year=None):
        """Search for movie in Mind database given title (or title keywords)
        and possibly year of movie

        Args:
            title_keywords (str): Can be space-separated title OR title keywords
            year (str): year of movie's release

        Returns:
            list: of matching movie collection dict objects

        Raises:
            MindTimeoutError: if mind returns 'code':'mindUnavailable'
        """
        # TODO: more restrictive resp_template
        resp_template = [
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'collection',
                        'isTop',
                        'isBottom',
                        ],
                    'typeName': 'collectionList'
                    },
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'category',
                        'collectionId',
                        'credit',
                        'title',
                        'partnerCollectionId',
                        'description',
                        'descriptionLanguage',
                        'internalRating',
                        'movieYear',
                        'mpaaRating',
                        'partnerCollectionId',
                        'rating',
                        'starRating',
                        'tvRating'
                        ],
                    'typeName': 'collection'
                    },
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'categoryId',
                        'displayRank',
                        'label',
                        'topLevel',
                        ],
                    'typeName': 'category'
                    },
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'personId',
                        'role',
                        'last',
                        'first',
                        'characterName',
                        'fullName',
                        ],
                    'typeName': 'credit'
                    },
                ]

        # TODO: get next batch of results if our filters remove all
        isBottom = False
        collection_list = []
        offset = 0
        results_per_req = 10
        while not isBottom and not collection_list:
            LOGGER.debug("Trying again to search for movie: offset=%d"%offset)
            results = self.rpc_req_generic(
                    'collectionSearch',
                    titleKeyword=title_keywords,
                    collectionType='movie',
                    responseTemplate=resp_template,
                    count=results_per_req,
                    offset=results_per_req*offset,
                    filterUnavailable='false',
                    includeBroadcast='true',
                    includeFree='true',
                    includePaid='false',
                    includeVod='false',
                    mergeOverridingCollections='true',
                    orderBy='strippedTitle',
                    )

            if 'code' in results:
                # Mind errors have a 'code'
                if results['code'] == 'internalError':
                    print(results['text'])
                    raise MindInternalError()

            if 'collection' in results:
                collection_list = results['collection']
            else:
                print("Unknown error.  results:")
                PP.pprint(results)
                return []

            isBottom = results['isBottom']
            isTop = results['isTop']

            offset += 1

            collection_list = self._filter_movie_results(collection_list, year=year)

        if len(collection_list) > 1:
            LOGGER.debug(
                    "%d in collection_list after "%(len(collection_list)) +
                    "filtering, is one of these best:"
                    )
            for coll in collection_list:
                LOGGER.debug("-----")
                for key in sorted(coll):
                    LOGGER.debug(key + ": " + str(coll[key]))
        if len(collection_list) > 0:
            LOGGER.debug(collection_list[0]['collectionId'])
            content_info = self.search_movie_content(collection_list[0]['collectionId'])
            collection_list[0].update(content_info)

        if collection_list:
            return collection_list[0]
        else:
            LOGGER.debug("No results survived filtering, returning empty dict.")
            print("No suitable results from RPC.")
            return {}

    @debug_fxn
    def search_movie_content(self, collection_id):
        # TODO: more restrictive resp_template ?
        resp_template = [
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'content',
                        'isTop',
                        'isBottom',
                        ],
                    'typeName': 'contentList'
                    },
                {
                    'type': 'responseTemplate',
                    'fieldName': [
                        'seasonNumber',
                        'episodeNum',
                        'partnerCollectionId',
                        'partnerContentId',
                        ],
                    'typeName': 'content'
                    },
                ]
        results = self.rpc_req_generic(
                'contentSearch',
                collectionId=collection_id,
                count=25,
                levelOfDetail='high',
                )

        assert len(results['content']) == 1

        content = results['content'][0]
        for key in sorted(content):
            LOGGER.debug(key + ": " + str(content[key]))

        return content


# -----------------------------------------------------------------------------
# OLD CODE BELOW

    @debug_fxn
    def collection_search(self, count, keywords):
        """Search collections for any results matching keywords

        Args:
            count (int): maximum records to fetch (max. value of 50)
            keywords (str): strings to search for matching records

        Returns:
            list: collectionList
        """
        req = self._rpc_request('collectionSearch',
              keyword=keywords,
              count=count,
              filterUnavailable='false',
              includeBroadcast='true',
              includeFree='true',
              includePaid='false',
              includeVod='false',
              levelOfDetail='medium',
              mergeOverridingCollections='true',
              orderBy='strippedTitle',
        )
        self._write(req)
        result = self._read()
        return result

    @debug_fxn
    def collection_search_series(self, count, keywords):
        """Search collections for any TV series matching keywords

        Args:
            count (int): maximum records to fetch
            keywords (str): strings to search for matching records

        Returns:
            list: collectionList
        """
        req = self._rpc_request('collectionSearch',
              keyword=keywords,
              collectionType='series',
              count=count,
              filterUnavailable='false',
              includeBroadcast='true',
              includeFree='true',
              includePaid='false',
              includeVod='false',
              levelOfDetail='medium',
              mergeOverridingCollections='true',
              orderBy='strippedTitle',
        )
        self._write(req)
        result = self._read()
        return result

    @debug_fxn
    def offer_search_linear(self, title, subtitle, body_id):
        """Search unit for works matching title and subtitle

        Args:
            title (str): title string to search for
            subtitle (str): subtitle string to search for
            body_id (str): 'tsn:' + <Tivo Service Number (no dashes)>

        Returns:
            list: offerList
        """
        req = self._rpc_request('offerSearch',
              count=25,
              bodyId=body_id,
              title=title,
              subtitle=subtitle
        )
        self._write(req)
        result = self._read()
        return result

    @debug_fxn
    def offer_search_linear_plus(self, title, body_id):
        """Search unit for works matching title

        Args:
            title (str): title string to search for
            body_id (str): 'tsn:' + <Tivo Service Number (no dashes)>

        Returns:
            list: offerList
        """
        req = self._rpc_request('offerSearch',
              count=25,
              bodyId=body_id,
              title=title
        )
        self._write(req)
        result = self._read()
        return result

    @debug_fxn
    def offer_search(self, offset, collection_id):
        req = self._rpc_request('offerSearch',
              offset=offset,
              count=25,
              namespace='trioserver',
              levelOfDetail='medium',
              collectionId=collection_id
        )
        self._write(req)
        result = self._read()
        return result

    @debug_fxn
    def content_search_episodes(self, offset, collection_id):
        """Search for TV episodes matching collection_id

        Args:
            offset (int): absolute episode number for results to start
            collection_id (str): string of collectionId

        Returns:
            list: contentList list of episodes, 25 at a time
        """
        req = self._rpc_request('contentSearch',
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

    @debug_fxn
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
                        result = self.content_search_episodes(
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

    @debug_fxn
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

    @debug_fxn
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
                    req = self._rpc_request('contentSearch',
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


    @debug_fxn
    def search_one_season(self, title, season, max_episode):
        """List episodes in season of a TV series, up to max_episode

        Args:
            title (str): TV Series title
            season (): Season number to view
            max_episode (): Highest episode to list in season (starts at 1)
        """
        count = 25
        stop = False
        collections = self.collection_search_series(count, title)
        collection_list = collections.get('collection')
        print("collection_list-----------------------------------------------")
        PP.pprint(collection_list)
        if collection_list:
            for collection in collection_list:
                if stop:
                    return
                if collection.get('collectionId'):
                    collection_id = collection.get('collectionId')
                    #print('=============')
                    #print('collectionId = ' + collection_id)
                    for episode_num in range(1, int(max_episode)+1):
                        req = self._rpc_request('contentSearch',
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

@debug_fxn
def main(argv):
    title = argv[1]
    username = argv[2]
    password = argv[3]
    search_type = argv[5]
    subtitle = argv[6]
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
    status = main(sys.argv)
    #try:
    #    status = main(sys.argv)
    #except KeyboardInterrupt:
    #    print("Stopped by Keyboard Interrupt", file=sys.stderr)
    #    # exit error code for Ctrl-C
    #    status = 130

    sys.exit(status)
