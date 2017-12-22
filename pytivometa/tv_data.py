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
import os.path
import re
from time import strptime


import common
import tvdb_api_v2


# Flag to track if TV lookups are enabled.
HAS_TVDB = True

# Cache for series info.
SERIES_INFO_CACHE = {}

# debug level for messages of entire file
DEBUG_LEVEL = 0


def debug(level, text):
    if level <= DEBUG_LEVEL:
        print(text)

class TvData():
    def __init__(self, interactive=False, clobber=False, debug_level=0):
        self.tvdb_token = tvdb_api_v2.get_session_token()
        self.interactive = interactive
        self.clobber = clobber

        # TODO: DEBUG_LEVEL hack
        DEBUG_LEVEL = debug_level
        common.DEBUG_LEVEL = debug_level
        tvdb_api_v2.DEBUG_LEVEL = debug_level

    def find_series_by_year(self, series, year):
        matching_series = []
        for series_candidate in series:
            first_aired = series_candidate['firstAired']
            if first_aired:
                match = re.search(r'(\d\d\d\d)-\d\d-\d\d', first_aired)
                if match and year == match.group(1):
                    matching_series.append(series_candidate)
        # Return all that matched the year (which may be an empty list)
        return matching_series

    def get_series_file_info(self, show_name, show_dir, meta_dir):
        series_file_info = {}

        series_id_files = [
                os.path.join(show_dir, show_name + ".seriesID"),
                os.path.join(meta_dir, show_name + ".seriesID")
                ]
        series_id_files = list(set(series_id_files))

        # search possible paths for series info file
        for series_id_path in series_id_files:
            debug(2, "Looking for .seriesID file in " + series_id_path)
            # Get tvdb_series_id
            if os.path.exists(series_id_path):
                debug(2, "Reading seriesID from file: " + series_id_path)
                with open(series_id_path, 'r') as seriesidfile:
                    tvdb_series_id = seriesidfile.read()
                # remove trailing whitespace (including \n)
                series_file_info['tvdb_series_id'] = tvdb_series_id.rstrip()

        return series_file_info

    def search_tvdb_series_id(self, show_name):
        # See if there's a year in the name
        match = re.search(r'(.+?) *\(((?:19|20)\d\d)\)', show_name)
        if match:
            bare_title = match.group(1)
            year = match.group(2)
        else:
            bare_title = show_name
            year = ''

        series = tvdb_api_v2.search_series(self.tvdb_token, bare_title)

        if year and len(series) > 1:
            debug(2, "There are %d matching series, "%(len(series)) + \
                    "but we know what year to search for (%s)."%year
                    )
            series = self.find_series_by_year(series, year)
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

        return tvdb_series_id

    def get_series_info(self, show_name, show_dir, meta_dir):

        series_file_info = self.get_series_file_info(show_name, show_dir, meta_dir)
        tvdb_series_id = series_file_info.get('tvdb_series_id', None)

        if tvdb_series_id is not None and not self.clobber:
            debug(1, "Using stored seriesID: " + tvdb_series_id)
        else:
            tvdb_series_id = self.search_tvdb_series_id(show_name)

            # write out series info file
            if tvdb_series_id is not None:
                tvdb_series_id = str(tvdb_series_id)
                # creating series ID file from scratch, so pick best path
                seriesidpath = os.path.join(meta_dir, show_name + ".seriesID")
                debug(1, "Found seriesID: " + tvdb_series_id)
                debug(2, "Writing seriesID to file: " + seriesidpath)

                # only when we are about to write file make metadata dir (e.g. .meta) if
                #   we need to
                common.mkdir_if_needed(os.path.dirname(seriesidpath))
                with open(seriesidpath, 'w') as seriesidfile:
                    seriesidfile.write(tvdb_series_id)
            else:
                debug(1, "Unable to find tvdb_series_id.")

        series_info = {}
        if tvdb_series_id is not None:
            series_info['tvdb'] = tvdb_api_v2.get_series_info(self.tvdb_token, tvdb_series_id)

        return series_info

    def format_episode_data(self, ep_data, meta_filepath):
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
            # for 'time', pytivo wants either 'file' or 'oad' or time_str
            #   that works in: datetime(*uniso(time_str)[:6])
            'time' : 'NOT_IN_TVDB_INFO',
            'originalAirDate' : 'firstAired',
            'seriesTitle' : 'seriesName',
            'episodeTitle' : 'episodeName',
            'title' : 'episodeName', # seriesTitle - episodeTitle
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
            # only when we are about to write file make metadata dir (e.g. .meta) if
            #   we need to
            common.mkdir_if_needed(os.path.dirname(meta_filepath))
            with open(meta_filepath, 'w') as out_file:
                out_file.write(metadata_text)

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
        if not HAS_TVDB:
            debug(1, "Metadata service for TV shows is unavailable, skipping " + \
                    "this show.")
            return

        episode_info = {}

        meta_dir = os.path.dirname(meta_filepath)

        if tv_info['series'] not in SERIES_INFO_CACHE:
            SERIES_INFO_CACHE[tv_info['series']] = self.get_series_info(
                    tv_info['series'], show_dir, meta_dir
                    )
        series_info = SERIES_INFO_CACHE[tv_info['series']]

        if series_info.get('tvdb', {}).get('id', None):
            episode_info.update(series_info['tvdb'])

            if tv_info.get('season', None) and tv_info.get('episode', None):
                episode_info.update(
                        tvdb_api_v2.get_episode_info(
                            self.tvdb_token, str(series_info['tvdb']['id']),
                            tv_info['season'], tv_info['episode']
                            )
                        )
            else:
                episode_info.update(
                        tvdb_api_v2.get_episode_info_air_date(
                            self.tvdb_token, str(series_info['tvdb']['id']),
                            tv_info['year'], tv_info['month'], tv_info['day']
                            )
                        )

            if episode_info is not None:
                self.format_episode_data(episode_info, meta_filepath)
