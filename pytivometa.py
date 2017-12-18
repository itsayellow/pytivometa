#!/usr/bin/env python3
# Copyright (c) 2008, Graham Dunn <gmd@kurai.org>
# Copyright (c) 2009-2011, Josh Harding <theamigo@gmail.com>
# Copyright (c) 2017, Matthew Clapp <itsayellow+dev@gmail.com>
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
#   modification, are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#    * Neither the name of the author nor the names of the contributors may be
#       used to endorse or promote products derived from this software without
#       specific prior written permission.
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

# Version : 0.5

# Python required: > 3.0

"""Look in current directory, or specified directory, find all video files,
fetch their metadata, and write metadata out into format that pytivo can
parse and use.

If the file name of a movie has a year in parentheses
(e.g. "Old Movie (1934)"), then it will aid in the search for the proper movie.

A filename will be considered a TV show if it has part of it with something
like a season and episode specification as part of it.
(e.g. "S01E02", or "s01e02", etc.)
"""


import argparse
from datetime import datetime
import json
import os
import os.path
import re
import sys
import textwrap
from time import strptime
#import urllib.error
import urllib.request

# Import the IMDbPY package.
try:
    import imdb
except ImportError:
    print('IMDB module could not be loaded. Movie Lookups will be disabled.\n'
          'See http://imdbpy.sourceforge.net')
    HAS_IMDB = False
else:
    # no exceptions, so set IMDB flag
    HAS_IMDB = True

# Which country's release date do we want to see:
#   Also as another way to search for an "Also Known As" title
COUNTRY = 'USA'

# What language to use for "Also Known As" title?
LANG = 'English'

# Flag to track if TV lookups are enabled.
HAS_TVDB = True

TVDB_APIKEY = "22FF0E9C529331C6"

TVDB_API_URL = "https://api.thetvdb.com/"

# When using a subdir for metadata files, what should it be called
META_DIR = '.meta'

# Types of files we want to get metadata for
VIDEO_FILE_EXTS = [
        ".mpg", ".avi", ".ogm", ".mkv", ".mp4",
        ".mov", ".wmv", ".vob", ".m4v", ".flv"
        ]

# string encoding for input from console
IN_ENCODING = sys.stdin.encoding or sys.getdefaultencoding()
# string encoding for output to console
OUT_ENCODING = sys.stdout.encoding or sys.getdefaultencoding()
# string encoding for output to metadata files.  Tivo is UTF8 compatible so use
#   that for file output
FILE_ENCODING = 'UTF-8'

# debug level for messages of entire file
DEBUG_LEVEL = 0

# True if interactive shell detected
INTERACTIVE = True

# Cache for series info.
SERIES_INFO_CACHE = {}


def debug(level, text):
    if level <= DEBUG_LEVEL:
        print(text)


def tvdb_v2_get(url, tvdb_token, headers_extra=None):
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

def tvdb_v2_get_session_token():
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

def tvdb_v2_search_series(tvdb_token, search_string):
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

    json_data = tvdb_v2_get(
            tvdb_search_series_url,
            tvdb_token=tvdb_token
            )

    return json_data['data']

def tvdb_v2_get_series_info(tvdb_token, tvdb_series_id):
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

    json_data = tvdb_v2_get(
            tvdb_series_info_url,
            tvdb_token=tvdb_token
            )
    series_info = json_data['data']

    json_data_actors = tvdb_v2_get(
            tvdb_series_info_url + "/actors",
            tvdb_token=tvdb_token
            )
    series_info_actors = json_data_actors['data']
    # TODO: sort by last name after sortOrder
    series_info_actors.sort(key=lambda x: x['sortOrder'])

    actors = [actdata['name'] for actdata in series_info_actors]
    series_info['actors'] = actors

    return series_info

def tvdb_v2_get_episode_info(tvdb_token, tvdb_series_id, season, episode):
    get_episode_id_url = TVDB_API_URL + "series/" + tvdb_series_id + \
            "/episodes/query?airedSeason=" + season + \
            "&airedEpisode=" + episode
    json_data = tvdb_v2_get(
            get_episode_id_url,
            tvdb_token=tvdb_token
            )
    episode_list_info = json_data['data']

    assert len(episode_list_info) == 1

    episode_id = str(episode_list_info[0]['id'])

    get_episode_info_url = TVDB_API_URL + "episodes/" + episode_id
    json_data = tvdb_v2_get(
            get_episode_info_url,
            tvdb_token=tvdb_token
            )
    episode_info = json_data['data']
    return episode_info

def tvdb_v2_get_episode_info_air_date(tvdb_token, tvdb_series_id, year, month, day):
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
        debug(2, "tvdb_v2_get_episode_info_air_date page %s"%page_str)
        try:
            json_data = tvdb_v2_get(
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
                        debug(2, "searching: episode date %d season %s episode %s"%(ep_date_num, episode_info['airedSeason'], episode_info['airedEpisodeNumber']))
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
        episode_info = tvdb_v2_get_episode_info(
                tvdb_token, tvdb_series_id,
                str(season), str(episode)
                )
    else:
        debug(0, "!! Error looking up data for this episode, skipping.")
        episode_info = None

    return episode_info

def ask_user(options_text, option_returns, max_options=5):
    indent = " "*4

    # Get number of movies found
    num_choices = len(option_returns)

    debug(2, "Found " + str(num_choices) + " matches.")
    # Show max max_options titles
    num_choices = min(num_choices, max_options)

    for i in range(num_choices):
        option_text = ""
        option_text_lines = options_text[i].splitlines()
        for line in option_text_lines:
            option_text += textwrap.fill(
                    line,
                    width=75,
                    initial_indent=indent,
                    subsequent_indent=indent
                    ) + "\n"
        option_text = option_text.strip()
        if num_choices < 10:
            print("%d   %s"%(i, option_text))
        else:
            print("%2d  %s"%(i, option_text))
    print("")
    try:
        choice_num = input(
                "Please choose the correct option, or 's' to skip [0]: "
                )
    except KeyboardInterrupt:
        print("\nCaught interrupt, exiting.")
        sys.exit(1)

    if not choice_num:
        # Empty string, default to the top choice
        choice_num = 0
    else:
        # Check for non-numeric input
        try:
            choice_num = int(choice_num)
        except ValueError:
            choice_num = None
        else:
            # Check for out-of-range input
            if choice_num < 0 or choice_num > num_choices:
                choice_num = None

    if choice_num is not None:
        print("Option %d chosen."%choice_num)
        returnval = option_returns[choice_num]
    else:
        print("No choice recorded, skipping...")
        returnval = None

    return returnval

def find_series_by_year(series, year):
    matching_series = []
    for series_candidate in series:
        first_aired = series_candidate['firstAired']
        if first_aired:
            match = re.search(r'(\d\d\d\d)-\d\d-\d\d', first_aired)
            if match and year == match.group(1):
                matching_series.append(series_candidate)
    # Return all that matched the year (which may be an empty list)
    return matching_series

def get_series_id(tvdb_token, show_name, show_dir,
        use_metadir=False, clobber=False):
    tvdb_series_id = None
    series_id_files = [os.path.join(show_dir, show_name + ".seriesID")]
    if use_metadir or os.path.isdir(os.path.join(show_dir, META_DIR)):
        series_id_files.append(
                os.path.join(show_dir, META_DIR, show_name + ".seriesID")
                )

    # See if there's a year in the name
    match = re.search(r'(.+?) *\(((?:19|20)\d\d)\)', show_name)
    if match:
        bare_title = match.group(1)
        year = match.group(2)
    else:
        bare_title = show_name
        year = ''

    # Prepare the seriesID file
    for seriesidpath in series_id_files:
        debug(2, "Looking for .seriesID file in " + seriesidpath)
        # Get tvdb_series_id
        if os.path.exists(seriesidpath):
            debug(2, "Reading seriesID from file: " + seriesidpath)
            with open(seriesidpath, 'r') as seriesidfile:
                tvdb_series_id = seriesidfile.read()
            debug(1, "Using stored seriesID: " + tvdb_series_id)

    if not clobber and tvdb_series_id:
        tvdb_series_id = re.sub("\n", "", tvdb_series_id)
    else:
        series = tvdb_v2_search_series(tvdb_token, bare_title)

        if year and len(series) > 1:
            debug(2, "There are %d matching series, "%(len(series)) + \
                    "but we know what year to search for (%s)."%year
                    )
            series = find_series_by_year(series, year)
            debug(2, "Series that match by year: %d." % len(series))

        if len(series) == 1:
            debug(1, "Found exact match")
            tvdb_series_id = series[0]['id']
        elif INTERACTIVE and len(series) > 1:
            # Display all the shows found
            print("\nMatches for TV series title '%s'"%show_name
                )
            print("------------------------------------")

            options_text = []
            for series_candidate in series:
                series_name = series_candidate['seriesName']
                series_overview = series_candidate['overview']
                first_aired = series_candidate['firstAired']

                text_option = "Series Name: %s\n"%series_name
                if first_aired:
                    text_option += "1st Aired: %s\n"%first_aired
                if series_overview is not None:
                    overview_text = " ".join(series_overview[0:239].split())
                    text_option += "Overview: %s\n"%overview_text
                text_option += "-"*30
                options_text.append(text_option)

            tvdb_series_ids = [s['id'] for s in series]
            tvdb_series_id = ask_user(
                    options_text, tvdb_series_ids, max_options=5
                    )
            print("------------------------------------")

        # Did we find any matches
        if series and tvdb_series_id is not None:
            tvdb_series_id = str(tvdb_series_id)
            # creating series ID file from scratch, so pick best path
            if use_metadir or os.path.isdir(os.path.join(show_dir, META_DIR)):
                seriesidpath = os.path.join(
                        show_dir, META_DIR, show_name + ".seriesID")
            else:
                seriesidpath = os.path.join(show_dir, show_name + ".seriesID")
            debug(1, "Found seriesID: " + tvdb_series_id)
            debug(2, "Writing seriesID to file: " + seriesidpath)
            with open(seriesidpath, 'w') as seriesidfile:
                seriesidfile.write(tvdb_series_id)
        else:
            debug(1, "Unable to find tvdb_series_id.")

    if tvdb_series_id is not None:
        series_info = tvdb_v2_get_series_info(tvdb_token, tvdb_series_id)
    else:
        series_info = {}

    return series_info, tvdb_series_id

def format_episode_data(ep_data, meta_filepath):
    # Takes a dict ep_data of XML elements, the series title, the Zap2It ID (aka
    #   the Tivo groupID), and a filepath meta_filepath
    metadata_text = ''

    # assuming we are TV episode, this is true
    ep_data["isEpisode"] = "true"

    # The following is a dictionary of pyTivo metadata attributes and how they
    #   map to thetvdb xml elements.

    # NOTE: 'NOT_IN_TVDB_INFO' is a placeholder to show it does not exist
    #       as metadata on TVDB
    pytivo_metadata = {
        # https://pytivo.sourceforge.io/wiki/index.php/Metadata
        'time' : 'NOT_IN_TVDB_INFO', # pytivo wants either 'file' or 'oad' or time_str that works in: datetime(*uniso(time_str)[:6])
        'originalAirDate' : 'firstAired',
        'seriesTitle' : 'seriesName',
        'episodeTitle' : 'episodeName',
        'title' : 'airedEpisodeName', # seriesTitle - episodeTitle
        'description' : 'overview',
        'isEpisode' : 'isEpisode',
        'seriesId' : 'zap2itId',
        'episodeNumber' : 'airedEpisodeNumber', # airedSeason + airedEpisodeNumber
        'displayMajorNumber' : 'NOT_IN_TVDB_INFO',
        'displayMinorNumber' : 'NOT_IN_TVDB_INFO',
        'callsign' : 'network',
        'showingBits' : 'NOT_IN_TVDB_INFO',
        'partCount' : 'NOT_IN_TVDB_INFO',
        'partIndex' : 'NOT_IN_TVDB_INFO',
        'tvRating' : 'rating',
        'vProgramGenre' : 'genre', # can be list
        'vSeriesGenre' : 'genre', # can be list
        'vActor' : 'actors',
        'vGuestStar' : 'guestStars',
        'vDirector' : 'directors',
        'vProducer' : 'NOT_IN_TVDB_INFO',
        'vExecProducer' : 'NOT_IN_TVDB_INFO',
        'vWriter' : 'writers',
        'vHost' : 'NOT_IN_TVDB_INFO', # check
        'vChoreographer' : 'NOT_IN_TVDB_INFO',
    }

    # These are thetvdb xml elements that have no corresponding Tivo metadata
    #   attribute.
    # absoluteNumber
    # added
    # addedBy
    # airedSeasonID
    # airsAfterSeason
    # airsBeforeEpisode
    # airsBeforeSeason
    # airsDayOfWeek
    # airsTime
    # aliases
    # banner
    # director - DEPRECATED, use directors instead
    # dvdChapter
    # dvdDiscid
    # dvdEpisodeNumber
    # dvdSeason
    # filename
    # id
    # imdbId
    # language
    # lastUpdated
    # lastUpdatedBy
    # network
    # networkId
    # productionCode
    # rating
    # runtime
    # seriesId
    # showUrl
    # siteRating
    # siteRatingCount
    # status
    # thumbAdded
    # thumbAuthor
    # thumbHeight
    # thumbWidth


    # pyTivo Metadata tag order
    pytivo_metadata_order = [
        'seriesTitle',
        'title',
        'episodeTitle',
        'originalAirDate',
        'description',
        'isEpisode',
        'seriesId',
        'episodeNumber',
        'vProgramGenre',
        'vSeriesGenre',
        'vActor',
        'vGuestStar',
        'vWriter',
        'vDirector',
        'vProducer',
        'vExecProducer',
        'vHost',
        'vChoreographer'
    ]

    # Metadata name fields
    metadata_name_fields = [
        'vActor',
        'vGuestStar',
        'vWriter',
        'vDirector',
        'vProducer',
        'vExecProducer',
        'vHost',
        'vChoreographer'
    ]

    transtable = {
        8217 : '\'', # Unicode RIGHT SINGLE QUOTATION MARK (U+2019)
        8216 : '\'', # Unicode LEFT SINGLE QUOTATION MARK (U+2018)
        8220 : '\"', # Unicode LEFT DOUBLE QUOTATION MARK (U+201C)
        8221 : '\"'  # Unicode RIGHT DOUBLE QUOTATION MARK (U+201D)
    }

    for tv_tag in pytivo_metadata_order:
        debug(3, "Working on " + tv_tag)
        if pytivo_metadata.get(tv_tag, '') and ep_data.get(pytivo_metadata[tv_tag], ''):
            # got data to work with
            line = term = ""

            if isinstance(ep_data[pytivo_metadata[tv_tag]], list):
                text = '|'.join(ep_data[pytivo_metadata[tv_tag]])
            else:
                text = str(ep_data[pytivo_metadata[tv_tag]])
            text = text.translate(transtable)
            # replace all whitespace chacaters with single spaces
            text = ' '.join(text.split())

            # for debugging character translations
            #if tv_tag == 'description':
            #    print "ord -> %s" % ord(text[370])

            debug(3, "%s : %s" % (tv_tag, text))

            if tv_tag == 'originalAirDate':
                text = datetime(*strptime(text, "%Y-%m-%d")[0:6]).strftime("%Y-%m-%dT%H:%M:%SZ")

            if tv_tag == 'seriesId':
                text = text.strip()
                # Look for either SH or EP followed by a number
                sh_ep_match = re.match(r'(?:SH|EP)(\d+)$', text)
                # Things like 'MV" won't match and will be left unchanged
                if sh_ep_match:
                    number = int(sh_ep_match.group(1))
                    # Pad to 6 or 8 digits as needed
                    if number < 1000000:
                        text = "SH%06d" % number
                    else:
                        text = "SH%08d" % number

            # Only check to see if Season is > 0, allow EpNum to be 0 for
            #   things like "1x00 - Bonus content"
            if (tv_tag == 'episodeNumber' and ep_data['airedEpisodeNumber'] and
                    int(ep_data['airedSeason'])):
                text = "%d%02d"%(int(ep_data['airedSeason']), int(ep_data['airedEpisodeNumber']))

            if tv_tag in metadata_name_fields:
                term = "|"

            if text is not None:
                if '|' in text:
                    people = text.strip('|').split('|')
                    for person in people:
                        debug(3, "Splitting " + person.strip())
                        line += "%s : %s\n" % (tv_tag, re.sub('\n', ' ', person.strip()+term))
                else:
                    line = "%s : %s\n" %(tv_tag, re.sub('\n', ' ', text+term))
                    debug(3, "Completed -> " + line)
                metadata_text += line
        else:
            debug(3, "No data for " + tv_tag)

    if metadata_text:
        with open(meta_filepath, 'w') as out_file:
            out_file.write(metadata_text)

def get_movie_info(title, is_trailer=False):
    debug(1, "Searching IMDb for: " + title)
    # IMDB access object
    imdb_access = imdb.IMDb()
    try:
        # Do the search, and get the results (a list of Movie objects).
        results = imdb_access.search_movie(title)
    except imdb.IMDbError as e:
        debug(0, "IMDb lookup error: " + str(e))
        sys.exit(3)

    if not results:
        debug(0, title + ": No IMDB matches found.")
        return

    if len(results) > 1 and INTERACTIVE:
        print("\nMatches for movie title '%s'"%title)
        print("------------------------------------")
        options_text = []
        for result in results:
            options_text.append(result['long imdb title'])
        movie_info = ask_user(options_text, results, max_options=5)
        print("------------------------------------")
    else:
        # automatically pick first match
        movie_info = results[0]
        report_match(movie_info, len(results))

    if movie_info is not None:
        # So far the movie_info object only contains basic information like the
        # title and the year; retrieve main information:
        try:
            imdb_access.update(movie_info)
            #debug(3, movie_info.summary())
        except Exception as e:
            debug(0, "Warning: unable to get extended details from IMDb for: " + str(movie_info))
            debug(0, "         You may need to update your imdbpy module.")

        try:
            pass
            #don't enable the next line unless you want the full cast,
            #   actors + everyone else who worked on the movie
            #imdb_access.update(movie_info, 'full credits')
        except:
            debug(1, "Warning: unable to retrieve full credits.")

        if is_trailer:
            try:
                # This slows down the process, so only do it for trailers
                imdb_access.update(movie_info, 'release dates')
            except Exception as e:
                debug(1, "Warning: unable to get release date.")

    return movie_info

def format_movie_data(movie_info, dir_, file_name, metadata_file_name, tags,
        genre_dir=None):
    line = ""

    # search for user language or country version of title if present
    title_aka = ''
    for aka in movie_info.get('akas', []):
        (title_aka, info_aka) = aka.split('::')
        # Note: maybe safer to search for '(imdb display title)' ?
        #   see: Volver, which finds "To Return" with USA, English?
        if COUNTRY in info_aka or '(' + LANG + ' title)' in info_aka:
            debug(3, "AKA: " + title_aka + "::" + info_aka)
            break
        else:
            title_aka = ''

    # title
    if title_aka and movie_info['title'] != title_aka:
        line = "title : %s (%s) %s\n" % (movie_info['title'], title_aka, tags)
    else:
        line = "title : %s %s\n" % (movie_info['title'], tags)

    # movieYear
    line += "movieYear : %s\n" % movie_info['year']

    if movie_info.get('release dates', None):
        # movie_info has key 'release dates' and it is not empty string
        reldate = get_rel_date(movie_info['release dates']) + '. '
    else:
        reldate = ''

    # description
    line += 'description : ' + reldate
    if "plot outline" in list(movie_info.keys()):
        line += movie_info['plot outline']
    # IMDB score if available
    if "rating" in list(movie_info.keys()):
        line += " IMDB: %s/10" % movie_info['rating']
    line += "\n"

    # isEpisode always false for movies
    line += "isEpisode : false\n"
    # starRating
    if "rating" in list(movie_info.keys()):
        line += "starRating : x%s\n" % (int((movie_info['rating']-1)/1.3+1))
    # mpaa_rating
    # kind of a hack for now...
    # maybe parsing certificates would work better?
    if "mpaa" in list(movie_info.keys()):
        mpaa_str = movie_info['mpaa']
        mpaa_rating = ""
        if "Rated G " in mpaa_str:
            mpaa_rating = "G1"
        elif "Rated PG " in mpaa_str:
            mpaa_rating = "P2"
        elif "Rated PG-13 " in mpaa_str:
            mpaa_rating = "P3"
        elif "Rated R " in mpaa_str:
            mpaa_rating = "R4"
        elif "Rated X " in mpaa_str:
            mpaa_rating = "X5"
        elif "Rated NC-17 " in mpaa_str:
            mpaa_rating = "N6"

        if mpaa_rating:
            line += "mpaaRating : %s\n" % mpaa_rating

    #vProgramGenre and vSeriesGenre
    if "genres" in list(movie_info.keys()):
        for i in movie_info['genres']:
            line += "vProgramGenre : %s\n" % i
        for i in movie_info['genres']:
            line += "vSeriesGenre : %s\n" % i
        if genre_dir:
            link_genres(dir_, genre_dir, file_name, metadata_file_name,
                    movie_info['genres']
                    )

    # vDirector (suppress repeated names)
    if "director" in list(movie_info.keys()):
        directors = {}
        for i in movie_info['director']:
            if i['name'] not in directors:
                directors[i['name']] = 1
                line += "vDirector : %s|\n" % i['name']
                debug(3, "vDirector : " + i['name'])
    # vWriter (suppress repeated names)
    if "writer" in list(movie_info.keys()):
        writers = {}
        for i in movie_info['writer']:
            if i['name'] not in writers:
                writers[i['name']] = 1
                line += "vWriter : %s|\n" % i['name']
                debug(3, "vWriter : " + i['name'])
    # vActor (suppress repeated names)
    if "cast" in list(movie_info.keys()):
        actors = {}
        for i in movie_info['cast']:
            if i['name'] not in actors:
                actors[i['name']] = 1
                line += "vActor : %s|\n" % i['name']
                debug(3, "vActor : " + i['name'])

    debug(2, "Writing to %s" % metadata_file_name)
    with open(metadata_file_name, 'w') as out_file:
        out_file.writelines(line)

def link_genres(work_dir, genre_dir, file_name, metadata_path, genres):
    for this_genre in genres:
        genrepath = os.path.join(genre_dir, this_genre)
        mkdir_if_needed(genrepath)
        # Create a symlink to the video
        link = os.path.join(genrepath, file_name)
        file_path = os.path.join(work_dir, file_name)
        mk_link(link, file_path)
        # Create a symlink to the metadata
        metadata_dir = os.path.basename(metadata_path)
        link = os.path.join(genrepath, metadata_dir)
        mk_link(link, metadata_path)

def mk_link(link_name, file_path):
    target = os.path.relpath(file_path, os.path.dirname(link_name))
    debug(2, "Linking " + link_name + " -> " + target)
    if os.path.islink(link_name):
        os.unlink(link_name)
        os.symlink(target, link_name)
    elif os.path.exists(link_name):
        debug(0, "Unable to create link '" + link_name + "', a file already exists with that name.")
    else:
        os.symlink(target, link_name)

def report_match(movie_info, num_results):
    matchtype = 'Using best match: '
    if num_results == 1:
        matchtype = 'Found exact match: '
    if 'long imdb title' in list(movie_info.keys()):
        debug(1, matchtype + movie_info['long imdb title'])
    else:
        debug(1, matchtype + str(movie_info))

def get_rel_date(reldates):
    for rel_date in reldates:
        if rel_date.encode(FILE_ENCODING, 'replace').lower().startswith(COUNTRY.lower() + '::'):
            return rel_date[len(COUNTRY)+2:]
    # Didn't find the country we want, so return the first one, but leave the
    #   country name in there.
    return reldates[0]

def get_video_files(dirname, dir_files):
    """Get list of file info objects for files of particular extensions, and
    subdirectories for recursive search
    """
    # get list of video files
    video_files = []
    for dir_file in dir_files:
        full_path = os.path.join(dirname, dir_file)
        (entry_base, entry_ext) = os.path.splitext(dir_file)
        if entry_ext in VIDEO_FILE_EXTS and entry_base and os.path.isfile(full_path):
            video_files.append(dir_file)
    video_files.sort()

    debug(2, "video_files after cull: %s" % str(video_files))

    return video_files

def fix_spaces(title):
    placeholders = ['[-._]', '  +']
    for place_holder in placeholders:
        title = re.sub(place_holder, ' ', title)
    # Remove leftover spaces before/after the year
    title = re.sub(r'\( ', '(', title)
    title = re.sub(r' \)', ')', title)
    title = re.sub(r'\(\)', '', title)
    return title

def clean_title(title):
    # strip a variety of common junk from torrented avi filenames
    striplist = (
            r'crowbone', r'joox-dot-net', r'DOMiNiON', r'LiMiTED',
            r'aXXo', r'DoNE', r'ViTE', r'BaLD', r'COCAiNE', r'NoGRP',
            r'leetay', r'AC3', r'BluRay', r'DVD', r'VHS', r'Screener',
            r'(?i)DVD SCR', r'\[.*\]', r'(?i)swesub', r'(?i)dvdrip',
            r'(?i)dvdscr', r'(?i)xvid', r'(?i)divx'
            )
    for strip in striplist:
        title = re.sub(strip, '', title)
    debug(3, "After stripping keywords, title is: " + title)
    return title

def extract_tags(title):
    # Look for tags that we want to show on the tivo, but not include in
    #   IMDb searches.
    tags = ""
    taglist = {
        # Strip these out      : return these instead
        r'(\d{3,4})([IiPp])'    : r'\1\2', #720p,1080p,1080i,720P,etc
        r'(?i)Telecine'         : r'TC',    #Telecine,telecine
        r'TC'                   : r'TC',
        r'(?i)Telesync'         : r'TS',    #Telesync,telesync
        r'TS'                   : r'TS',
        r'CAM'                  : r'CAM',
        r'(?i)CD ?(\d)'         : r'CD\1', #CD1,CD2,cd1,cd3,etc
        r'(?i)\(?Disc ?(\d)\)?' : r'CD\1', #Disc 1,Disc 2,disc 1,etc
        }
    for tag in list(taglist.keys()):
        match = re.search(tag, title)
        if match:
            tags += match.expand(taglist[tag]) + ' '
            title = re.sub(tag, '', title)
    debug(2, "    Tags: " + tags)
    return (tags, title)

def mkdir_if_needed(dirname):
    if not os.path.exists(dirname):
        # Don't use os.makedirs() because that would only matter if -p named a
        #   non-existant dir (which we don't want to create)
        os.mkdir(dirname, 0o755)
    elif not os.path.isdir(dirname):
        raise OSError(
                'Can\'t create "' + dirname + '" as a dir, a file already ' +\
                        'exists with that name.'
                )

def parse_movie(search_dir, filename, metadata_file_name,
        is_trailer, genre_dir=None):
    if not HAS_IMDB:
        print("No IMDB module, skipping movie: " + filename)
        return

    title = os.path.splitext(filename)[0]

    # Most tags and group names come after the year (which is often in parens
    #   or brackets)
    # Using the year when searching IMDb will help, so try to find it.
    year_match1 = re.match(
            r'(.*?\w+.*?)(?:([[(])|(\W))(.*?)((?:19|20)\d\d)(?(2)[])]|(\3|$))(.*?)$',
            title
            )
    if year_match1:
        (tags, _) = extract_tags(title)
        (title, year, _, _) = year_match1.group(1, 5, 4, 7)
        debug(2, "    Title: %s\n    Year: %s" % (title, year))
        title += ' (' + year + ')'
    else:
        # 2nd pass at finding the year.  Look for a series of tags in parens
        #   which may include the year.
        year_match2 = re.match(r'(.*?\w+.*?)\(.*((?:19|20)\d\d)\).*\)', title)
        if year_match2:
            (title, year) = year_match2.group([1, 2])
            debug(2, "    Title: %s\n    Year: %s" % (title, year))
            title += ' (' + year + ')'
        else:
            debug(2, "Cleaning up title the hard way.")
            title = clean_title(title)
            debug(2, "    Title: %s" % title)
        # Note: this also removes the tags from the title
        (tags, title) = extract_tags(title)
    debug(3, "Before fixing spaces, title is: " + title)
    title = fix_spaces(title)
    debug(3, "After fixing spaces, title is: " + title)

    movie_info = get_movie_info(title, is_trailer)

    if movie_info is not None:
        format_movie_data(movie_info, search_dir, filename, metadata_file_name,
                tags, genre_dir=genre_dir
                )

def tvinfo_from_filename(filename):
    # Regexes for filenames that match TV shows.
    #   group 1: series search string (i.e. series name)
    # ?P<name> at the beginning of a group calls the group 'name'
    tv_res = [
            r'(.+)[Ss](?P<season>\d\d?)[Ee](?P<episode>\d+)',
            r'(.+?)(?: -)? ?(?P<season>\d+)[Xx](?P<episode>\d+)',
            r'(.*).(?P<year>\d\d\d\d).(?P<month>\d+).(?P<day>\d+).*',
            r'(.*).(?P<month>\d+).(?P<day>\d+).(?P<year>\d\d\d\d).*',
            r'(?i)(.+)(?P<season>\d?\d)(?P<episode>\d\d).*sitv' # (?i) == re.I
            ]

    for tv_re in tv_res:
        match = re.search(tv_re, filename)
        if match:
            # Looks like a TV show
            break

    tv_info = {}
    if match:
        # fill in tv_info if we matched this filename to a regex
        tv_info['series'] = re.sub(r'[._]', ' ', match.group(1)).strip()
        if match.lastindex >= 4:
            # str(int()) strips out leading zeroes
            tv_info['year'] = str(int(match.group('year')))
            tv_info['month'] = str(int(match.group('month')))
            tv_info['day'] = str(int(match.group('day')))
        else:
            tv_info['season'] = str(int(match.group('season')))
            tv_info['episode'] = str(int(match.group('episode')))

        debug(2, "    Series: %s\n"%tv_info['series'] + \
                "    Season: %s\n"%tv_info.get('season', '') + \
                "    Episode: %s\n"%tv_info.get('episode', '') + \
                "    Year: %s\n"%tv_info.get('year', '') + \
                "    Month: %s\n"%tv_info.get('month', '') + \
                "    Day: %s"%tv_info.get('day', '')
                )

    return tv_info

def parse_tv(tvdb_token, tv_info, meta_filepath, show_dir,
        use_metadir=False, clobber=False):
    """
    Tags we need in episode_info if possible:
        'Actors',
        'Choreographer'
        'Director',
        'EpisodeName',
        'EpisodeNumber',
        'ExecProducer',
        'FirstAired',
        'Genre',
        'GuestStars',
        'Host',
        'Overview',
        'Producer',
        'SeriesName',
        'Writer',
        'callsign',
        'displayMajorNumber',
        'displayMinorNumber',
        'isEpisode',
        'showingBits',
        'startTime',
        'stopTime',
        'time',
        'tvRating',
        'zap2it_id',

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
    episode_info = {}
    if tv_info['series'] not in SERIES_INFO_CACHE:
        SERIES_INFO_CACHE[tv_info['series']] = get_series_id(
                tvdb_token, tv_info['series'], show_dir,
                use_metadir=use_metadir, clobber=clobber
                )
    (series_info, tvdb_series_id) = SERIES_INFO_CACHE[tv_info['series']]
    if tvdb_series_id and series_info:
        episode_info.update(series_info)
        if tv_info.get('season', None) and tv_info.get('episode', None):
            episode_info.update(
                    tvdb_v2_get_episode_info(
                        tvdb_token, tvdb_series_id,
                        tv_info['season'], tv_info['episode']
                        )
                    )
        else:
            episode_info.update(
                    tvdb_v2_get_episode_info_air_date(
                        tvdb_token, tvdb_series_id,
                        tv_info['year'], tv_info['month'], tv_info['day']
                        )
                    )

        if episode_info is not None:
            format_episode_data(episode_info, meta_filepath)

def process_dir(dir_proc, dir_files, tvdb_token, use_metadir=False,
        clobber=False, genre_dir=None):
    debug(1, "\n## Looking for videos in: " + dir_proc)

    video_files = get_video_files(dir_proc, dir_files)

    is_trailer = False
    # See if we're in a "Trailer" folder.
    if 'trailer' in os.path.abspath(dir_proc).lower():
        is_trailer = True

    # dir to put metadata in is either dir_proc or dir_proc/META_DIR
    if use_metadir or os.path.isdir(os.path.join(dir_proc, META_DIR)):
        meta_dir = os.path.join(dir_proc, META_DIR)
        mkdir_if_needed(meta_dir)
    else:
        meta_dir = dir_proc

    for filename in video_files:
        meta_filepath = os.path.join(meta_dir, filename + '.txt')

        debug(1, "\n--->working on: %s" % filename)
        debug(2, "Metafile is: " + meta_filepath)

        if os.path.exists(meta_filepath) and not clobber:
            debug(1, "Metadata file already exists, skipping.")
        else:
            # get info in dict if filename looks like tv episode, {} otherwise
            tv_info = tvinfo_from_filename(filename)

            if tv_info:
                if HAS_TVDB:
                    parse_tv(tvdb_token, tv_info, meta_filepath, dir_proc,
                            use_metadir=use_metadir, clobber=clobber
                            )
                else:
                    debug(1, "Metadata service for TV shows is " + \
                            "unavailable, skipping this show.")
            else:
                # assume movie if filename not matching tv
                parse_movie(dir_proc, filename, meta_filepath,
                        is_trailer, genre_dir=genre_dir
                        )

def check_interactive():
    if sys.platform not in ['win32', 'cygwin']:
        # On unix-like platforms, set interactive mode when running from a
        #   terminal
        if os.isatty(sys.stdin.fileno()):
            return True
    # On windows systems set interactive when running from a console
    elif 'PROMPT' in list(os.environ.keys()):
        return True
    return False

def create_genre_dir(genre_dir):
    # Python doesn't support making symlinks on Windows.
    if sys.platform in ['win32', 'cygwin']:
        debug(0, "The genre feature doesn't work on Windows as symlinks " +\
                "aren't well supported."
                )
        genre_dir = None
    else:
        if not os.path.exists(genre_dir):
            os.makedirs(genre_dir, 0o755)
        elif not os.path.isdir(genre_dir):
            raise OSError(
                    'Can\'t create "' + genre_dir + '" as a dir, a ' + \
                            'file already exists with that name.'
                    )
        else:
            debug(0, "Note: If you've removed videos, there may be old " +\
                    "symlinks in '" + genre_dir + "'.  If there's " +\
                    "nothing else in there, you can just remove the " +\
                    "whole thing first, then run this again (e.g. " +\
                    "rm -rf '" + genre_dir + "'), but be careful."
                    )
    return genre_dir

def process_command_line(argv):
    """Process command line invocation arguments and switches.

    Args:
        argv: list of arguments, or `None` from ``sys.argv[1:]``.

    Returns:
        args: Namespace with named attributes of arguments and switches
    """
    argv = argv[1:]

    # initialize the parser object:
    parser = argparse.ArgumentParser(
            description="Retrieve information from TVDB and IMDB to add "\
                    "TiVo metadatada to all media files in the current "\
                    "directory.  TV info from http://www.thetvdb.com/ ."\
                    "They welcome user contributions of show data."
                    )

    # optional positional list of directories:
    parser.add_argument(
            "dir", nargs="*", default=['.'],
            help="Specific directory(-ies) to process. (Default is current "\
                    "directory.)"
            )

    # switches/options:
    parser.add_argument(
            "-d", "--debug", action="count", default=0,
            help="Turn on debugging. More -d's increase debug level."
            )
    parser.add_argument(
            "-f", "--force", action="store_true", dest="clobber",
            help="Force overwrite of existing metadata"
            )
    parser.add_argument(
            "-t", "--tidy", action="store_true", dest="metadir",
            help="Save metadata files in .meta subdirectory. "
            )
    parser.add_argument(
            "-r", "--recursive", action="store_true",
            help="Generate metadata for all files in sub dirs too."
            )
    parser.add_argument(
            "-g", "--genre",
            help="Specify a directory in which to place symlinks to shows, "\
                    "organized by genre."
            )
    parser.add_argument(
            "-w", "--wait", dest="timeout", type=int, default=5,
            help="How many seconds to wait for a connection to thetvdb.com "\
                    "before giving up. (Default: 5s)"
            )

    args = parser.parse_args(argv)

    return args

def main():
    global INTERACTIVE
    global DEBUG_LEVEL

    args = process_command_line(sys.argv)

    # set master debug message level
    DEBUG_LEVEL = args.debug

    # set interactive if we are in an interactive shell
    INTERACTIVE = check_interactive()

    debug(2, "\nConsole Input encoding: %s" % IN_ENCODING)
    debug(2, "Console Output encoding: %s" % OUT_ENCODING)
    debug(2, "Metadata File Output encoding: %s\n" % FILE_ENCODING)

    # Initalize things we'll need for looking up data
    tvdb_token = tvdb_v2_get_session_token()

    # create/set genre dir if specified and possible
    if args.genre:
        genre_dir = create_genre_dir(args.genre)
    else:
        genre_dir = None

    # process all dirs
    for search_dir in args.dir:
        if args.recursive:
            for (dirpath, _, dir_files) in os.walk(search_dir):
                dirname = os.path.basename(dirpath)
                # only non-hidden dirs (no dirs starting with .)
                #   but '.' dir is OK
                if not re.search(r'\..+', dirname):
                    process_dir(dirpath, dir_files, tvdb_token,
                            use_metadir=args.metadir,
                            clobber=args.clobber,
                            genre_dir=genre_dir
                            )
        else:
            dir_files = os.listdir(search_dir)
            process_dir(search_dir, dir_files, tvdb_token,
                    use_metadir=args.metadir,
                    clobber=args.clobber,
                    genre_dir=genre_dir
                    )

if __name__ == "__main__":
    main()
