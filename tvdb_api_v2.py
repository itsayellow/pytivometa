#!/usr/bin/env/python3


import json
import re
#import urllib.error
import urllib.request


TVDB_APIKEY = "22FF0E9C529331C6"
TVDB_API_URL = "https://api.thetvdb.com/"

DEBUG_LEVEL = 0

def debug(level, text):
    if level <= DEBUG_LEVEL:
        print(text)


def tvdb_get(url, tvdb_token, headers_extra=None):
    headers = {
            'Authorization': 'Bearer '+ tvdb_token,
            'Accept': 'application/json'
            }
    if headers_extra is not None:
        headers.update(headers_extra)

    request = urllib.request.Request(url, headers=headers)

    try:
        json_reply_raw = urllib.request.urlopen(request)
    except urllib.error.HTTPError as http_error:
        print(http_error)
        # TODO: do something better than re-raise
        raise

    json_reply = json_reply_raw.read().decode()
    json_data = json.loads(json_reply)

    return json_data

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

def search_series(tvdb_token, search_string):
    """Given a search string, return a list from thetvdb.com of all possible
    television series matches.

    Args:
        tvdb_token (str): tvdb API session token
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
    tvdb_search_series_url = TVDB_API_URL + "search/series?name="+ search_string

    json_data = tvdb_get(
            tvdb_search_series_url,
            tvdb_token=tvdb_token
            )

    return json_data['data']

def get_series_info(tvdb_token, tvdb_series_id):
    """Given a series ID, return info on the series

    Args:
        tvdb_token (str): tvdb API session token
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

    json_data = tvdb_get(
            tvdb_series_info_url,
            tvdb_token=tvdb_token
            )
    series_info = json_data['data']

    json_data_actors = tvdb_get(
            tvdb_series_info_url + "/actors",
            tvdb_token=tvdb_token
            )
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

def get_episode_info(tvdb_token, tvdb_series_id, season, episode):
    get_episode_id_url = TVDB_API_URL + "series/" + tvdb_series_id + \
            "/episodes/query?airedSeason=" + season + \
            "&airedEpisode=" + episode
    json_data = tvdb_get(
            get_episode_id_url,
            tvdb_token=tvdb_token
            )
    episode_list_info = json_data['data']

    assert len(episode_list_info) == 1

    episode_id = str(episode_list_info[0]['id'])

    get_episode_info_url = TVDB_API_URL + "episodes/" + episode_id
    json_data = tvdb_get(
            get_episode_info_url,
            tvdb_token=tvdb_token
            )
    episode_info = json_data['data']
    return episode_info

def get_episode_info_air_date(tvdb_token, tvdb_series_id, year, month, day):
    season = None
    episode = None

    # assumes year, month, day are all strings
    search_date_num = int("%04d%02d%02d"%(int(year), int(month), int(day)))
    debug(1, "searching for episode date %d"%search_date_num)

    # need to get all pages in /series/{id}/episodes to find air date
    get_episodes_url = TVDB_API_URL + "series/" + tvdb_series_id + "/episodes?page="

    page = 1
    done = False
    while not done:
        # go through each page of episodes until match is found, or
        #   we run out of pages (HTTP Error 404)
        page_str = str(page)
        debug(2, "get_episode_info_air_date page %s"%page_str)
        try:
            json_data = tvdb_get(
                    get_episodes_url + page_str,
                    tvdb_token=tvdb_token
                    )
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
                        debug(2, "searching: episode date %d "%ep_date_num + \
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

    if season is not None and episode is not None:
        debug(1, "Air date %d matches: Season %d, Episode %d"%(search_date_num, season, episode))
        episode_info = get_episode_info(
                tvdb_token, tvdb_series_id,
                str(season), str(episode)
                )
    else:
        debug(0, "!! Error looking up data for this episode, skipping.")
        episode_info = None

    return episode_info
