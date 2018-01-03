#!/usr/bin/env/python3

#    tvdb_api_v2.py - module to access tvdb data using tvdb api v2
#    Copyright (C) 2017 Matthew A. Clapp
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
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
    Tags in TVDB /series/{id}
        {
            "added": "string",
            "airsDayOfWeek": "string",
            "airsTime": "string",
            "aliases": ["string",]
            "banner": "string",
            "firstAired": "string",
            "genre": ["string",]
            "id": 0,
            "imdbId": "string",
            "lastUpdated": 0,
            "network": "string",
            "networkId": "string",
            "overview": "string",
            "rating": "string",
            "runtime": "string",
            "seriesId": 0,
            "seriesName": "string",
            "siteRating": 0,
            "siteRatingCount": 0,
            "status": "string",
            "zap2itId": "string"
        }

    Tags in TVDB /series/{id}/actors
        [
            {
                "id": 0,
                "image": "string",
                "imageAdded": "string",
                "imageAuthor": 0,
                "lastUpdated": "string",
                "name": "string",
                "role": "string",
                "seriesId": 0,
                "sortOrder": 0
            },
        ]

    Tags in TVDB /series/{id}/episodes/query or /series/{id}/episodes
        [
            {
                "absoluteNumber": 0,
                "airedEpisodeNumber": 0,
                "airedSeason": 0,
                "dvdEpisodeNumber": 0,
                "dvdSeason": 0,
                "episodeName": "string",
                "firstAired": "string",
                "id": 0,
                "lastUpdated": 0,
                "overview": "string"
            }
        ]

    Tags in TVDB /episodes/{id}
    {
        "absoluteNumber": 0,
        "airedEpisodeNumber": 0,
        "airedSeason": 0,
        "airsAfterSeason": 0,
        "airsBeforeEpisode": 0,
        "airsBeforeSeason": 0,
        "director": "string",
        "directors": [ "string" ],
        "dvdChapter": 0,
        "dvdDiscid": "string",
        "dvdEpisodeNumber": 0,
        "dvdSeason": 0,
        "episodeName": "string",
        "filename": "string",
        "firstAired": "string",
        "guestStars": [ "string" ],
        "id": 0,
        "imdbId": "string",
        "lastUpdated": 0,
        "lastUpdatedBy": "string",
        "overview": "string",
        "productionCode": "string",
        "seriesId": "string",
        "showUrl": "string",
        "siteRating": 0,
        "siteRatingCount": 0,
        "thumbAdded": "string",
        "thumbAuthor": 0,
        "thumbHeight": "string",
        "thumbWidth": "string",
        "writers": [ "string" ]
    }
"""

import json
import logging
import re
#import urllib.error
import urllib.request
import urllib.parse

TVDB_APIKEY = "22FF0E9C529331C6"
TVDB_API_URL = "https://api.thetvdb.com/"


# Set up logger
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def get_session_token():
    """Get a current session token for thetvdb.com, necessary for any
    future requests of data.

    Returns:
        str: TVDB session token, used for all future requests in http header
    """
    # execute POST: send apikey, receive session token
    tvdb_api_login_url = TVDB_API_URL + "login"
    post_fields = {'apikey': TVDB_APIKEY}
    headers = {
            'Content-type': 'application/json',
            'Accept': 'application/json'
            }

    request = urllib.request.Request(
            tvdb_api_login_url,
            data=json.dumps(post_fields).encode('ascii'),
            headers=headers
            )
    try:
        json_reply_raw = urllib.request.urlopen(request)
    except urllib.error.HTTPError as http_error:
        print(http_error)
        # TODO: do something better than re-raise
        raise

    json_reply = json_reply_raw.read().decode()
    json_data = json.loads(json_reply)
    tvdb_sess_token = json_data['token']

    return tvdb_sess_token

class Tvdb:
    def __init__(self):
        self.session_token = get_session_token()

    def _tvdb_get(self, url, headers_extra=None):
        """Basic function handling low-level tvdb data requests

        Args:
            url (str): full URL to access
        """
        headers = {
                'Authorization': 'Bearer '+ self.session_token,
                'Accept': 'application/json'
                }
        if headers_extra is not None:
            headers.update(headers_extra)

        request = urllib.request.Request(url, headers=headers)

        try:
            json_reply_raw = urllib.request.urlopen(request)
        except urllib.error.HTTPError as http_error:
            # accidentally putting a real space into URL:
            #   HTTP Error 400: Bad request
            print(http_error)
            print("url: " + url)
            # TODO: do something better than re-raise
            raise

        json_reply = json_reply_raw.read().decode()
        json_data = json.loads(json_reply)

        return json_data

    def search_series(self, search_string):
        """Given a search string, return a list from thetvdb.com of all possible
        television series matches.

        Args:
            search_string (str): string to search for tvdb series info

        Returns:
            list: list of dicts, each dict contains data of a possibly-matching
                show

            e.g.
            [
                {'aliases': [], 'banner': 'graphical/314614-g6.jpg',
                    'firstAired': '2016-07-21', 'id': 314614,
                    'network': 'BBC Three',
                    'overview': 'Meet Fleabag. She’s not talking to all of us....',
                    'seriesName': 'Fleabag', 'status': 'Continuing'
                },
                {'aliases': [], 'banner': '', 'firstAired': '', 'id': 269062,
                    'network': '',
                    'overview': "A living, breathing, farting embodiment ....",
                    'seriesName': 'Fleabag Monkeyface', 'status': 'Ended'
                }
            ]
        """
        search_string = urllib.parse.quote(search_string)
        tvdb_search_series_url = TVDB_API_URL + "search/series?name="+ search_string

        json_data = self._tvdb_get(tvdb_search_series_url)

        return json_data['data']

    def get_series_info(self, tvdb_series_id):
        """Given a series ID, return info on the series

        Args:
            tvdb_series_id (str): TVDB series ID number for series

        Returns:
            dict: Available data from TVDB about series
                keys:
                [
                'actors'
                'added',
                'addedBy',
                'airsDayOfWeek',
                'airsTime',
                'aliases',
                'banner',
                'firstAired',
                'genre',
                'id',
                'imdbId',
                'lastUpdated',
                'network',
                'networkId',
                'overview',
                'rating',
                'runtime',
                'seriesId',
                'seriesName',
                'siteRating',
                'siteRatingCount',
                'status',
                'zap2itId',
                ]

            e.g.: {'id': 314614, 'seriesName': 'Fleabag', 'aliases': [],
                'banner': 'graphical/314614-g6.jpg', 'seriesId': '',
                'status': 'Continuing', 'firstAired': '2016-07-21',
                'network': 'BBC Three', 'networkId': '', 'runtime': '25',
                'genre': ['Comedy'],
                'overview': 'Meet Fleabag. She’s not talking to all of us.....',
                'lastUpdated': 1510663171, 'airsDayOfWeek': 'Thursday',
                'airsTime': '', 'rating': '', 'imdbId': 'tt5687612',
                'zap2itId': '', 'added': '2016-07-21 03:03:01', 'addedBy': 380790,
                'siteRating': 8.8, 'siteRatingCount': 9}
        """
        # TODO: can use /series/{id}/filter to get only desired tags
        tvdb_series_info_url = TVDB_API_URL + "series/" + tvdb_series_id

        json_data = self._tvdb_get(tvdb_series_info_url)
        series_info = json_data['data']

        json_data_actors = self._tvdb_get(tvdb_series_info_url + "/actors")
        #http.client.BadStatusLine: <html>
        #   when I accidentally erroneously gave <cr> in tvdb_series_id
        series_info_actors = json_data_actors['data']

        # sort by last name after sortOrder
        def sortorder_then_lastname(item):
            last_name_re = re.search(r'\s(\S+)$', item['name'])
            if last_name_re:
                return '%02d%s'%(item['sortOrder'], last_name_re.group(1))

            return '%02d'%item['sortOrder']

        #series_info_actors.sort(key=lambda x: x['sortOrder'])
        series_info_actors.sort(key=sortorder_then_lastname)

        actors = [actdata['name'] for actdata in series_info_actors]
        series_info['actors'] = actors

        return series_info

    def get_episode_info(self, tvdb_series_id, season=None, episode=None,
            year=None, month=None, day=None):
        """Given a series ID, return info on a particular episode

        Args:
            tvdb_series_id (str): TVDB series ID number for series
            season (str): string of season number
            episode (str): string of episode number

        Returns:
        """
        if season is None or episode is None:
            (season, episode) = self.get_season_ep_from_airdate(
                    tvdb_series_id, year, month, day
                    )

        get_episode_id_url = TVDB_API_URL + "series/" + tvdb_series_id + \
                "/episodes/query?airedSeason=" + season + \
                "&airedEpisode=" + episode
        json_data = self._tvdb_get(get_episode_id_url)
        episode_list_info = json_data['data']

        assert len(episode_list_info) == 1

        episode_id = str(episode_list_info[0]['id'])

        get_episode_info_url = TVDB_API_URL + "episodes/" + episode_id
        json_data = self._tvdb_get(get_episode_info_url)
        episode_info = json_data['data']
        return episode_info

    def get_season_ep_from_airdate(self, tvdb_series_id, year, month, day):
        season = None
        episode = None

        # assumes year, month, day are all strings
        search_date_num = int("%04d%02d%02d"%(int(year), int(month), int(day)))
        LOGGER.debug("searching for episode date %d"%search_date_num)

        # need to get all pages in /series/{id}/episodes to find air date
        get_episodes_url = TVDB_API_URL + "series/" + tvdb_series_id + "/episodes?page="

        page = 1
        done = False
        while not done:
            # go through each page of episodes until match is found, or
            #   we run out of pages (HTTP Error 404)
            page_str = str(page)
            LOGGER.debug("2,get_episode_info_air_date page %s"%page_str)
            try:
                json_data = self._tvdb_get(get_episodes_url + page_str)
            except urllib.error.HTTPError as http_error:
                if http_error.code == 404:
                    episode_list = []
                    done = True
                else:
                    print("HTTP error:")
                    print(http_error.code)
                    print(http_error.reason)
                    print(http_error.headers)
                    raise
            else:
                episode_list = json_data['data']

            if episode_list:
                for episode_info in episode_list:
                    # NOTE: currently episode list seems to be sorted odd!
                    #   All seasons' episode 1, then all seasons' episode 2, ...
                    if episode_info['firstAired']:
                        ep_date_re = re.search(r'(\d+)-(\d+)-(\d+)', episode_info['firstAired'])
                        if ep_date_re:
                            year = ep_date_re.group(1)
                            month = ep_date_re.group(2)
                            day = ep_date_re.group(3)
                            ep_date_num = int("%04d%02d%02d"%(int(year), int(month), int(day)))
                            LOGGER.debug("2,searching: episode date %d "%ep_date_num + \
                                    "season %s "%episode_info['airedSeason'] + \
                                    "episode %s"%episode_info['airedEpisodeNumber']
                                    )
                            if ep_date_num == search_date_num:
                                # found a match
                                season = episode_info['airedSeason']
                                episode = episode_info['airedEpisodeNumber']
                                done = True
                                break
            else:
                done = True

            page += 1

        return (str(season), str(episode))
