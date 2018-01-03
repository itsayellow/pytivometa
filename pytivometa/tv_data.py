#!/usr/bin/env python3

#    tv_data.py - module to access tv data for pytivometa
#    Copyright (c) 2008, Graham Dunn <gmd@kurai.org>
#    Copyright (c) 2009-2011, Josh Harding <theamigo@gmail.com>
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

from datetime import datetime
import logging
import os.path
import re
from time import strptime


import common
import tvdb_api_v2


# debug level for messages of entire file
DEBUG_LEVEL = 0

# Set up logger
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def debug(level, text):
    if level <= DEBUG_LEVEL:
        LOGGER.debug(text)


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

def get_series_file_info(show_name, show_dir, meta_dir):
    series_file_info = {}

    # prefer .pytivometa files but fall back to reading .seriesID
    series_id_files = [
            os.path.join(meta_dir, show_name + ".pytivometa"),
            os.path.join(show_dir, show_name + ".pytivometa"),
            os.path.join(meta_dir, show_name + ".seriesID"),
            os.path.join(show_dir, show_name + ".seriesID"),
            ]
    series_id_files = list(set(series_id_files))

    # search possible paths for .pytivometa or .seriesID info file
    for series_id_path in series_id_files:
        debug(2, "Looking for pytivometa file in path " + series_id_path)
        # Get tvdb_series_id
        if os.path.exists(series_id_path):
            debug(2, "Reading seriesID from file: " + series_id_path)
            if series_id_path.endswith(".pytivometa"):
                with open(series_id_path, 'r') as series_id_fh:
                    for line in series_id_fh:
                        line = line.strip()
                        (key, data) = line.split(':', maxsplit=1)
                        debug(2, "key: %s, data: %s"%(key, data))
                        series_file_info[key] = data
            else:
                with open(series_id_path, 'r') as series_id_fh:
                    tvdb_series_id = series_id_fh.read()
                # remove trailing whitespace (including \n)
                series_file_info['tvdb_series_id'] = tvdb_series_id.rstrip()

    return series_file_info

def format_episode_data(ep_data, meta_filepath):
    """Write a pytivo metadata file from episode data

    Args:
        ep_data (dict): episode data (including parent series data)
        meta_filepath (str): full path of metadata file to write out
    """
    metadata_text = ''

    # assuming we are TV episode, this is true
    ep_data["isEpisode"] = "true"

    # The following is a list of pyTivo metadata attributes and how they
    #   map to ep_data keys.
    # Order of this list of lists is the order in which it is "pleasing" to
    #   have the metadata show up in a metadata file.  It is not
    #   functionally important to preserve this order.
    # https://pytivo.sourceforge.io/wiki/index.php/Metadata
    # for 'time', pytivo wants either 'file' or 'oad' or time_str
    #   that works in: datetime(*uniso(time_str)[:6])
    # NOTE: 'NOT_IN_EP_DATA' is a placeholder to show it does not exist
    #       as metadata in ep_data
    pytivo_metadata = [
        # [pytivo_tag, ep_data_key],
        ['seriesTitle', 'seriesName'],
        ['title', 'episodeName'], # seriesTitle - episodeTitle
        ['episodeTitle', 'episodeName'],
        ['originalAirDate', 'firstAired'],
        ['description', 'overview'],
        ['isEpisode', 'isEpisode'],
        ['seriesId', 'tivoSeriesId'], # currently only valid info from RPC
        ['programId', 'tivoProgramId'], # currently only valid info from RPC
        ['episodeNumber', 'airedEpisodeNumber'], # airedSeason + airedEpisodeNumber
        ['vProgramGenre', 'genre'], # can be list
        ['vSeriesGenre', 'genre'], # can be list
        ['vActor', 'actors'],
        ['vGuestStar', 'guestStars'],
        ['vDirector', 'directors'],
        ['vProducer', 'NOT_IN_EP_DATA'],
        ['vExecProducer', 'NOT_IN_EP_DATA'],
        ['vWriter', 'writers'],
        ['vHost', 'NOT_IN_EP_DATA'], # check
        ['vChoreographer', 'NOT_IN_EP_DATA'],
        ['time', 'NOT_IN_EP_DATA'],
        ['displayMajorNumber', 'NOT_IN_EP_DATA'], # channel number (e.g. 10-1)
        ['displayMinorNumber', 'NOT_IN_EP_DATA'], # unused by tivo
        ['callsign', 'network'],
        ['showingBits', 'NOT_IN_EP_DATA'],
        ['partCount', 'NOT_IN_EP_DATA'], # multipart episode, total parts
        ['partIndex', 'NOT_IN_EP_DATA'], # multipart episode, this part
        ['tvRating', 'rating'],
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

    for (pytivo_tag, ep_data_key) in pytivo_metadata:
        debug(3, "Working on " + pytivo_tag)
        if ep_data.get(ep_data_key, ''):
            # ep_data contains ep_data_key and value is not empty ''
            line = ""
            term = ""

            if isinstance(ep_data[ep_data_key], list):
                text = '|'.join(ep_data[ep_data_key])
            else:
                text = str(ep_data[ep_data_key])
            text = text.translate(transtable)
            # replace all whitespace chacaters with single spaces
            text = ' '.join(text.split())

            # for debugging character translations
            #if pytivo_tag == 'description':
            #    print "ord -> %s" % ord(text[370])

            debug(3, "%s : %s" % (pytivo_tag, text))

            if pytivo_tag == 'originalAirDate':
                text = datetime(*strptime(text, "%Y-%m-%d")[0:6]).strftime("%Y-%m-%dT%H:%M:%SZ")

            # Only check to see if Season is > 0, allow EpNum to be 0 for
            #   things like "1x00 - Bonus content"
            if (pytivo_tag == 'episodeNumber' and ep_data['airedEpisodeNumber'] and
                    int(ep_data['airedSeason'])):
                text = "%d%02d"%(int(ep_data['airedSeason']), int(ep_data['airedEpisodeNumber']))

            if pytivo_tag in metadata_name_fields:
                term = "|"

            if text is not None:
                if '|' in text:
                    people = text.strip('|').split('|')
                    for person in people:
                        debug(3, "Splitting " + person.strip())
                        line += "%s : %s\n" % (pytivo_tag, re.sub('\n', ' ', person.strip()+term))
                else:
                    line = "%s : %s\n" %(pytivo_tag, re.sub('\n', ' ', text+term))
                    debug(3, "Completed -> " + line)
                metadata_text += line
        else:
            debug(3, "No data for " + pytivo_tag)

    if metadata_text:
        # only when we are about to write file make metadata dir (e.g. .meta) if
        #   we need to
        common.mkdir_if_needed(os.path.dirname(meta_filepath))
        with open(meta_filepath, 'w') as out_file:
            out_file.write(metadata_text)

def write_series_file_info(series_file_info, filepath):
    # creating series ID file from scratch, so pick best path
    debug(2, "Writing series info to file: " + filepath)

    # only when we are about to write file make metadata dir (e.g. .meta) if
    #   we need to
    common.mkdir_if_needed(os.path.dirname(filepath))
    with open(filepath, 'w') as series_id_fh:
        for key in series_file_info:
            print(key + ":" + str(series_file_info[key]), file=series_id_fh)


class TvData():
    """TV Data access object storing persistent state (e.g. tvdb_access)
    and various options.
    """
    def __init__(self, rpc_remote=None, interactive=False, clobber=False,
            debug_level=0):
        """Initialize TV Access object and config

        Args:
            userpass (list): [<username>, <password>] for rpc access
            interactive (bool): are we able to interact with user
            clobber (bool): should we overwrite all metadata
            debug_level (int): code debug level for this module

        Returns:
            TvData object instance
        """
        # TVDB access
        self.tvdb_access = tvdb_api_v2.Tvdb()

        # RPC access
        self.rpc_remote = rpc_remote

        self.interactive = interactive
        self.clobber = clobber
        # Cache for series info.
        self.series_info_cache = {}

        # TODO: DEBUG_LEVEL hack
        global DEBUG_LEVEL
        DEBUG_LEVEL = debug_level
        common.DEBUG_LEVEL = debug_level
        tvdb_api_v2.DEBUG_LEVEL = debug_level

    def search_tvdb_series_id(self, show_name):
        # See if there's a year in the name
        match = re.search(r'(.+?) *\(((?:19|20)\d\d)\)', show_name)
        if match:
            bare_title = match.group(1)
            year = match.group(2)
        else:
            bare_title = show_name
            year = ''

        series = self.tvdb_access.search_series(bare_title)

        if year and len(series) > 1:
            debug(2, "There are %d matching series, "%(len(series)) + \
                    "but we know what year to search for (%s)."%year
                    )
            series = find_series_by_year(series, year)
            debug(2, "Series that match by year: %d." % len(series))

        if len(series) == 1:
            debug(1, "Found exact match")
            tvdb_series_id = series[0]['id']
        elif self.interactive and len(series) > 1:
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
            tvdb_series_id = common.ask_user(
                    options_text, tvdb_series_ids, max_options=5
                    )
            print("------------------------------------")

        return str(tvdb_series_id)

    def search_rpc_series_id(self, show_name, first_aired='', actors=None):
        # TODO: placeholder
        # use to search:
        #   title
        #   air date of season 1 episode 1
        #   cast
        #
        # get:
        #   title
        #   air date of season 1 episode 1
        #   cast
        if actors is None:
            actors = []

        results = self.rpc_remote.search_series(show_name)

        # First, search for original air date match between argument (TVDB)
        #   and RPC series.  If found, designate as positive match
        rpc_series_id = ''
        debug(1, "Searching for RPC series by matching orig. air date...")
        for series in results:
            debug(2, series.get('title', '') + " - " + series.get('description', '') + "\n")
            debug(2, " "*4 + "first aired:" + series.get('firstAired', ''))
            if series['firstAired'] == first_aired:
                #rpc_series_id = series['partnerCollectionId']
                rpc_series_id = series['collectionId']
                break
        # Second, if no original air date match, find the series with the most
        #   matching cast members, and call that the match
        if not rpc_series_id:
            debug(1, "Searching for RPC series by matching cast...")
            series_actor_match = []
            for series in results:
                debug(2, series.get('title', '') + " - " + series.get('description', '') + "\n")
                if 'credit' in series:
                    rpc_cast = [
                            x['fullName']
                            for x in series['credit']
                            if x['role'] == 'actor'
                            ]
                    actor_match = 0
                    for actor in actors:
                        if actor in rpc_cast:
                            actor_match += 1
                    series_actor_match.append(actor_match)
                    debug(2, " "*4 + "actor match: " + str(actor_match))
                else:
                    series_actor_match.append(-1)

            i_max = series_actor_match.index(max(series_actor_match))

            assert len(series_actor_match) == len(results)

            if series_actor_match[i_max] > 0:
                #rpc_series_id = results[i_max]['partnerCollectionId']
                rpc_series_id = results[i_max]['collectionId']

        return rpc_series_id

    def get_series_info(self, show_name, show_dir, meta_dir):
        series_info = {}

        # TODO: rpc and tvdb, how to merge?
        #   Ideally only ask user once.
        #   Data that both tvdb and rpc have to cross-index:
        #       title
        #       cast
        #       original air date

        series_file_info = get_series_file_info(show_name, show_dir, meta_dir)

        # TODO: proper check for this
        series_file_info_len = len(series_file_info.keys())

        # Get TVDB info
        if series_file_info.get('tvdb_series_id', None):
            tvdb_series_id = series_file_info.get('tvdb_series_id', '')
            debug(1, "Using stored TVDB series info: " + tvdb_series_id)
        else:
            tvdb_series_id = self.search_tvdb_series_id(show_name)
            series_file_info['tvdb_series_id'] = tvdb_series_id
            if not tvdb_series_id:
                debug(1, "Unable to find tvdb_series_id.")
        if tvdb_series_id is not None:
            debug(1, "tvdb series id: '" + tvdb_series_id + "'")
            series_info['tvdb'] = self.tvdb_access.get_series_info(tvdb_series_id)

        # Get RPC info
        # NOTE: TVDB and RPC can disagree on first airdate, e.g. Fleabag.
        # Search RPC for show that 1.) matches first airdate of TVDB series,
        #   and if that fails 2.) matches the most cast members of TVDB series
        if self.rpc_remote is not None:
            if series_file_info.get('rpc_series_id', None):
                rpc_series_id = series_file_info['rpc_series_id']
                debug(1, "Using stored RPC series info: " + rpc_series_id)
            elif 'tvdb' in series_info:
                rpc_series_id = self.search_rpc_series_id(
                        show_name,
                        first_aired=series_info['tvdb'].get('firstAired', ''),
                        actors=series_info['tvdb'].get('actors', None)
                        )
                series_file_info['rpc_series_id'] = rpc_series_id
            else:
                # TODO: fxn to ask user about multiple matching rpc series
                #   in case of no tvdb series
                pass

            if rpc_series_id:
                debug(1, "rpc_series_id: " + rpc_series_id)
                series_info['rpc'] = self.rpc_remote.get_series_info(rpc_series_id)
            else:
                debug(1, "Unable to find rpc_series_id.")

        have_more_info = len(series_info.keys()) > series_file_info_len
        if have_more_info or self.clobber:
            # write out series info file
            write_series_file_info(
                    series_file_info,
                    os.path.join(meta_dir, show_name + ".pytivometa")
                    )

        return series_info

    def parse_tv(self, tv_info, meta_filepath, show_dir):
        """
        Args:
            tv_info (dict): info gathered from video filename
            meta_filepath (str): filepath of output metadata file
            show_dir (str): directory containing video_file being processed

        Returns:
            dict: containing tvdb keys and values

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
        """
        episode_info = {}

        meta_dir = os.path.dirname(meta_filepath)

        if tv_info['series'] not in self.series_info_cache:
            self.series_info_cache[tv_info['series']] = self.get_series_info(
                    tv_info['series'], show_dir, meta_dir
                    )

        series_info = self.series_info_cache[tv_info['series']]

        #import pprint
        #pp = pprint.PrettyPrinter(indent=4, depth=3)
        #pp.pprint(series_info)

        if series_info.get('tvdb', {}).get('id', None):
            episode_info.update(series_info['tvdb'])

            episode_info.update(
                    self.tvdb_access.get_episode_info(
                        str(series_info['tvdb']['id']),
                        season=tv_info.get('season', None),
                        episode=tv_info.get('episode', None),
                        year=tv_info.get('year', None),
                        month=tv_info.get('month', None),
                        day=tv_info.get('day', None)
                        )
                    )

            # make sure tv_info now has season, episode, in case it did not
            tv_info['season'] = episode_info['airedSeason']
            tv_info['episode'] = episode_info['airedEpisodeNumber']

        if series_info.get('rpc', {}).get('collectionId', ''):
            tivo_series_id = series_info['rpc'].get('partnerCollectionId', '')
            tivo_program_id = self.rpc_remote.get_program_id(
                    series_info['rpc']['collectionId'],
                    season_num=tv_info.get('season', None),
                    episode_num=tv_info.get('episode', None),
                    year=tv_info.get('year', None),
                    month=tv_info.get('month', None),
                    day=tv_info.get('day', None),
                    )

            # format series_id properly
            tivo_series_id = re.sub(r'epgProvider:cl\.', '', tivo_series_id)
            tivo_program_id = re.sub(r'epgProvider:ct\.', '', tivo_program_id)

            episode_info['tivoSeriesId'] = tivo_series_id
            episode_info['tivoProgramId'] = tivo_program_id

        if episode_info:
            format_episode_data(episode_info, meta_filepath)
