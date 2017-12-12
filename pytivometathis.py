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

# Version : 0.3 with .meta patch

# Python required: > 3.0

import urllib.request
import urllib.parse
import urllib.error
import sys
import re
import os
import gzip
import io
import argparse

from xml.etree.ElementTree import parse, Element, SubElement
from time import gmtime, strftime, strptime
from datetime import datetime
from functools import reduce

# Import the IMDbPY package.
IMDB = 1
try:
    import imdb
except ImportError:
    print('IMDB module could not be loaded. Movie Lookups will be disabled.\n'
          'See http://imdbpy.sourceforge.net')
    IMDB = 0

# Which country's release date do we want to see:
COUNTRY = 'USA'

OPTIONS = None

# Flag to track if TV lookups are enabled.
TVDB = 1
APIKEY = "0403764A0DA51955"

GETSERIESID_URL = '/api/GetSeries.php?'
GETEPISODEID_URL = '/GetEpisodes.php?'
GETEPISODEINFO_URL = '/EpisodeUpdates.php?'

# Cache for series info.
SINFOCACHE = {}

# When using a subdir for metadata files, what should it be called
METADIR = '.meta'

# Regexes that match TV shows.
tvres = [
        r'(.+)[Ss](\d\d?)[Ee](\d+)', r'(.+?)(?: -)? ?(\d+)[Xx](\d+)',
        r'(.*).(\d\d\d\d).(\d+).(\d+).*', r'(.*).(\d+).(\d+).(\d\d\d\d).*',
        r'(?i)(.+)(\d?\d)(\d\d).*sitv'
        ]
# Types of files we want to get metadata for
fileExtList = [
        ".mpg", ".avi", ".ogm", ".mkv", ".mp4",
        ".mov", ".wmv", ".vob", ".m4v", ".flv"
        ]
# string encoding for input from console
in_encoding = sys.stdin.encoding or sys.getdefaultencoding()
# string encoding for output to console
out_encoding = sys.stdout.encoding or sys.getdefaultencoding()
# string encoding for output to metadata files.  Tivo is UTF8 compatible so use
#   that for file output
file_encoding = 'UTF-8'


def debug(level, text):
    if level <= OPTIONS.debug:
        try:
            print(text)
        except UnicodeDecodeError as e:
            try:
                # This can fail on unicode chars
                print(text)
            except UnicodeDecodeError as e:
                try:
                    # If sys.stdout.encoding is ascii (or 'ANSI_X3.4-1968')
                    #   then the previous two attempts were the same thing, try
                    #   something else
                    print(text.encode('latin-1', 'replace'))
                except UnicodeDecodeError as e:
                    print("Unable to display debug message, error is: " + str(e))

def get_mirror_url():
    global TVDB
    # Query tvdb for a list of mirrors
    mirrorsURL = "http://www.thetvdb.com/api/%s/mirrors.xml" % APIKEY
    mirrorURL = ''
    # If we don't hear back after timeout seconds, give up and move on
    timeout = OPTIONS.timeout
    try:
        mirrorsXML = parse(urllib.request.urlopen(mirrorsURL, None, timeout))
        mirrors = [Item for Item in mirrorsXML.findall('Mirror')]
        mirrorURL = mirrors[0].findtext('mirrorpath')
    except:
        debug(0, "Error looking information from thetvdb, no metadata will "\
                "be retrieved for TV shows."
             )
        TVDB = 0
    return mirrorURL

def find_series_by_year(series, year):
    matchingSeries = []
    for show in series:
        first_aired = show.findtext('FirstAired')
        if first_aired:
            match = re.search(r'(\d\d\d\d)-\d\d-\d\d', first_aired)
            if match and year == match.group(1):
                matchingSeries.append(show)
    # Return all that matched the year (which may be an empty list)
    return matchingSeries

# patched function to allow hex
def to_hex(s):
    lst = []
    for ch in s:
        hv = hex(ord(ch)).replace('0x', '')
        if len(hv) == 1:
            hv = '0'+hv
        lst.append(hv)

    return reduce(lambda x, y: x+y, lst)

# patched function to allow parsing gzipped data
def get_xml(url):
    debug(3, "get_xml: Using URL " + url)
    try:
        rawXML = urllib.request.urlopen(url).read()
    except Exception as e:
        debug(0, "\n Exception = " + str(e))
        return None

    xml = None
    #check for gzip compressed data
    if to_hex(rawXML[0:2]) != "1f8b":
        filestream = io.StringIO(rawXML)
        debug(0, "Not gzip compressed data " +  to_hex(rawXML[0:2]))
    else:
        filestream = gzip.GzipFile(fileobj=io.StringIO(rawXML))
        debug(0, "gzip compressed data")
    try:
        xml = parse(filestream).getroot()
    except Exception as e:
        debug(0, "\n Exception = " + str(e))
        debug(3, "\nrawXML = " + rawXML + "\n\nhexXML = " + to_hex(rawXML))

    return xml

def get_series_id(mirror_url, show_name, show_dir):
    seriesid = ''
    sidfiles = [os.path.join(show_dir, show_name + ".seriesID")]
    if OPTIONS.metadir or os.path.isdir(os.path.join(show_dir, METADIR)):
        sidfiles.append(os.path.join(show_dir, METADIR, show_name + ".seriesID"))

    # See if there's a year in the name
    match = re.search(r'(.+?) *\(((?:19|20)\d\d)\)', show_name)
    if match:
        bare_title = match.group(1)
        year = match.group(2)
    else:
        bare_title = show_name
        year = ''

    # Prepare the seriesID file
    for seriesidpath in sidfiles:
        debug(2, "Looking for .seriesID file in " + seriesidpath)
        # Get seriesid
        if os.path.exists(seriesidpath):
            debug(2, 'Reading seriesID from file: ' + seriesidpath)
            seriesidfile = open(seriesidpath, 'r')
            seriesid = seriesidfile.read()
            seriesidfile.close()
            debug(1, 'Using stored seriesID: ' + seriesid)

    if not OPTIONS.clobber and len(seriesid) > 0:
        seriesid = re.sub("\n", "", seriesid)
    else:
        debug(1, 'Searching for: ' + bare_title)
        url = mirror_url + GETSERIESID_URL + urllib.parse.urlencode({"seriesname" : bare_title})
        debug(3, 'series_xml: Using URL ' + url)
        # patch new
        series_xml = get_xml(url)
        if series_xml is None:
            debug(3, "Error getting Series Info")
            return None, None
        #series_xml = parse(urllib.urlopen(url)).getroot()
        series = [Item for Item in series_xml.findall('Series')]

        if year and len(series) > 1:
            debug(2, 'There are %d matching series, but we know what year ' +\
                    'to search for (%s).' % (len(series), year)
                    )
            series = find_series_by_year(series, year)
            debug(2, 'Series that match by year: %d.' % len(series))

        if len(series) == 1:
            debug(1, "Found exact match")
            seriesid = series[0].findtext('id')
        elif OPTIONS.interactive:
            # Display all the shows found
            if len(series) >= 2:
                print("####################################\n")
                print("Multiple TV Shows found:\n")
                print("Found %s shows for Series Title %s"%(
                    len(series), show_name.encode(out_encoding, 'replace')
                    )
                    )
                print("------------------------------------")
                for episode in series:
                    ep_series_name = episode.findtext('SeriesName')
                    ep_id = episode.findtext('id')
                    ep_overview = episode.findtext('Overview')
                    first_aired = episode.findtext('FirstAired')
                    # ep_overview may not exist, so default them to something so
                    #   print doesn't fail
                    if ep_overview is None:
                        ep_overview = "<None>"
                    if len(ep_overview) > 240:
                        ep_overview = ep_overview[0:239]
                    print("Series Name:\t%s" % ep_series_name.encode(out_encoding, 'replace'))
                    print("Series ID:\t%s" % ep_id.encode(out_encoding, 'replace'))
                    if first_aired:
                        print("1st Aired:\t%s" % first_aired.encode(out_encoding, 'replace'))
                    print("Description:\t%s\n------------------------------------" % ep_overview.encode(out_encoding, 'replace'))
                print("####################################\n\n")
                try:
                    seriesid = input('Please choose the correct seriesid: ')
                except KeyboardInterrupt:
                    print("\nCaught interrupt, exiting.")
                    sys.exit(1)

        elif len(series) > 1:
            debug(1, "Using best match: " + series[0].findtext('SeriesName'))
            seriesid = series[0].findtext('id')

        # Did we find any matches
        if len(series) and len(seriesid):
            debug(1, 'Found seriesID: ' + seriesid)
            debug(2, 'Writing seriesID to file: ' + seriesidpath)
            seriesidfile = open(seriesidpath, 'w')
            seriesidfile.write(seriesid)
            seriesidfile.close()
        else:
            debug(1, "Unable to find seriesid.")

    series_url_xml = None
    if seriesid:
        series_url = mirror_url + "/api/" + APIKEY + "/series/" + seriesid + "/en.xml"
        debug(3, "getSeriesInfoXML: Using URL " + series_url)
        # patch new
        series_url_xml = get_xml(series_url)
        if series_url_xml is None:
            debug(0, "!! Error parsing series info, skipping.")
        #try:
        #    series_url_xml = parse(urllib.urlopen(series_url)).getroot()
        #except Exception, e:
        #    debug(0, "!! Error parsing series info, skipping.")
        #    debug(0, "!! Error description is: " + str(e))
        #    debug(3, "!! XML content is:\n" + str(urllib.urlopen(series_url).read()))
    return series_url_xml, seriesid

def get_episode_info_xml(mirror_url, seriesid, season, episode):
    # Takes a seriesid, season number, episode number and return xml data`
    url = mirror_url + "/api/" + APIKEY + "/series/" + seriesid + "/default/" + season + "/" + episode + "/en.xml"
    debug(3, "get_episode_info_xml: Using URL " + url)
    # patch new
    episode_info_xml = get_xml(url)

    if episode_info_xml is None:
        debug(0, "!! Error looking up data for this episode, skipping.")
    #try:
    #    episode_info_xml = parse(urllib.urlopen(url)).getroot()
    #except Exception, e:
    #    debug(0, "!! Error looking up data for this episode, skipping.")
    #    print "exception is:"
    #    print e
    #    episode_info_xml = None

    return episode_info_xml

def get_episode_info_xml_by_air_date(mirror_url, seriesid, year, month, day):
    # Takes a seriesid, year number, month number, day number, and return xml data
    url = mirror_url + "/api/GetEpisodeByAirDate.php?apikey=" + APIKEY + \
            "&seriesid=" + seriesid + "&airdate=" + year + "-" + month + "-" + day
    debug(3, "get_episode_info_xml_by_air_date: Using URL " + url)
    # patch new
    episode_info_xml = get_xml(url)
    if episode_info_xml is None:
        debug(0, "!! Error looking up data for this episode, skipping.")
    #try:
    #    episode_info_xml = parse(urllib.urlopen(url)).getroot()
    #except Exception, e:
    #    debug(0, "!! Error looking up data for this episode, skipping.")
    #    episode_info_xml = None

    return episode_info_xml

def format_episode_data(ep_data, meta_dir, f):
    # Takes a dict e of XML elements, the series title, the Zap2It ID (aka
    #   the Tivo groupID), and a filename f
    # TODO : Split up multiple guest stars / writers / etc. Split on '|'.
    #   (http://trac.kurai.org/trac.cgi/ticket/2)
    # This is weak. Should just detect if EpisodeNumber exists.
    metadata_text = ''
    ep_data["isEpisode"] = "true"

    # The following is a dictionary of pyTivo metadata attributes and how they
    #   map to thetvdb xml elements.
    pytivo_metadata = {
        # As seen on http://pytivo.armooo.net/wiki/MetaData
        'time' : 'time',
        'originalAirDate' : 'FirstAired',
        'seriesTitle' : 'SeriesName',
        'title' : 'EpisodeName',
        'episodeTitle' : 'EpisodeName',
        'description' : 'Overview',
        'isEpisode' : 'isEpisode',
        'seriesId' : 'zap2it_id',
        'episodeNumber' : 'EpisodeNumber',
        'displayMajorNumber' : 'displayMajorNumber',
        'callsign' : 'callsign',
        'showingBits' : 'showingBits',
        'displayMinorNumber' : 'displayMinorNumber',
        'startTime' : 'startTime',
        'stopTime' : 'stopTime',
        'tvRating' : 'tvRating',
        'vProgramGenre' : 'Genre',
        'vSeriesGenre' : 'Genre',
        'vActor' : 'Actors',
        'vGuestStar' : 'GuestStars',
        'vDirector' : 'Director',
        'vProducer' : 'Producer',
        'vExecProducer' : 'ExecProducer',
        'vWriter' : 'Writer',
        'vHost' : 'Host',
        'vChoreographer' : 'Choreographer',
    }

    # These are thetvdb xml elements that have no corresponding Tivo metadata attribute. Maybe someday.
    unused = {
        'id' : 'id',
        'seasonid' : 'seasonid',
        'ProductionCode' : 'ProductionCode',
        'ShowURL' : 'ShowURL',
        'lastupdated' : 'lastupdated',
        'flagged' : 'flagged',
        'DVD_discid' : 'DVD_discid',
        'DVD_season' : 'DVD_season',
        'DVD_episodenumber' : 'DVD_episodenumber',
        'DVD_chapter' : 'DVD_chapter',
        'absolute_number' : 'absolute_number',
        'filename' : 'filename',
        'lastupdatedby' : 'lastupdatedby',
        'mirrorupdate' : 'mirrorupdate',
        'lockedby' : 'lockedby',
        'SeasonNumber': 'SeasonNumber'
    }

    #for pyTivoTag in pytivo_metadata.keys():
    #    print "%s : %s" % (pyTivoTag, pytivo_metadata[pyTivoTag])

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
        'vHost' ,
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
        'vHost' ,
        'vChoreographer'
    ]

    transtable = {
        8217 : '\'',
        8216 : '\'',
        8220 : '\"',
        8221 : '\"'
    }

    for tv_tag in pytivo_metadata_order:

        debug(3, 'Working on ' + tv_tag)
        if tv_tag in pytivo_metadata and (pytivo_metadata[tv_tag]) and pytivo_metadata[tv_tag] in ep_data and ep_data[pytivo_metadata[tv_tag]]:
            # got data to work with
            line = term = ""
            text = str(ep_data[pytivo_metadata[tv_tag]]).translate(transtable)

            # for debugging character translations
            #if tv_tag == 'description':
            #    print "ord -> %s" % ord(text[370])

            debug(3, "%s : %s" % (tv_tag, text))

            if tv_tag == 'originalAirDate':
                text = datetime(*strptime(text, "%Y-%m-%d")[0:6]).strftime("%Y-%m-%dT%H:%M:%SZ")

            if tv_tag == 'seriesId':
                text = text.strip()
                # Look for either SH or EP followed by a number
                m = re.match(r'(?:SH|EP)(\d+)$', text)
                # Things like 'MV" won't match and will be left unchanged
                if m:
                    number = int(m.group(1))
                    # Pad to 6 or 8 digits as needed
                    if number < 1000000:
                        text = "SH%06d" % number
                    else:
                        text = "SH%08d" % number

            # Only check to see if Season is > 0, allow EpNum to be 0 for
            #   things like "1x00 - Bonus content"
            if tv_tag == 'episodeNumber' and ep_data['EpisodeNumber'] and int(ep_data['SeasonNumber']):
                text = "%d%02d" % (int(ep_data['SeasonNumber']), int(ep_data['EpisodeNumber']))

            if tv_tag in metadata_name_fields:
                term = "|"

            if text is not None:
                if '|' in text:
                    people = text.strip('|').split('|')
                    for person in people:
                        debug(3, 'Splitting ' + person.strip())
                        line += "%s : %s\n" % (tv_tag, re.sub('\n', ' ', person.strip()+term))
                else:
                    line = "%s : %s\n" %(tv_tag, re.sub('\n', ' ', text+term))
                    debug(3, 'Completed -> ' + line)
                metadata_text += line
        else:
            debug(3, 'No data for ' + tv_tag)

    if metadata_text:
        mkdir_if_needed(meta_dir)
        out_file = open(os.path.join(meta_dir, f), 'w')
        out_file.write(metadata_text.encode(file_encoding, 'replace'))
        out_file.close()

def format_movie_data(title, dir_, file_name, metadata_file_name, tags, is_trailer):
    line = ""

    debug(1, 'Searching IMDb for: ' + title)
    imdb_access = imdb.IMDb() # create new object to access IMDB
    title = str(title, in_encoding, 'replace')
    try:
        # Do the search, and get the results (a list of Movie objects).
        results = imdb_access.search_movie(title)
    except imdb.IMDbError as e:
        debug(0, 'IMDb lookup error: ' + str(e))
        sys.exit(3)

    if not results:
        debug(1, 'No matches found.')
        return

    if OPTIONS.interactive:
        # Get number of movies found
        num_titles = len(results)

        # If only one found, select and go on
        if num_titles == 1:
            movie = results[0]
            report_match(movie, len(results))
        else:
            debug(2, 'Found ' + str(num_titles) + ' matches.')
            # Show max 5 titles
            num_titles = min(num_titles, 5)

            print("\nMatches for '%s'" % (title.encode(out_encoding, 'replace')))
            print("------------------------------------")
            print("Num\tTitle")
            print("------------------------------------")
            for i in range(0, num_titles):
                m_title = results[i]['long imdb title']
                print("%d\t%s" % (i, m_title.encode(out_encoding, 'replace')))
            print("")
            try:
                movie_num = input("Please choose the correct movie, or 's' to skip [0]: ")
            except KeyboardInterrupt:
                print("\nCaught interrupt, exiting.")
                sys.exit(1)

            if not len(movie_num):
                # Empty string, default to the top choice
                movie_num = 0
            else:
                # Check for non-numeric input
                try:
                    movie_num = int(movie_num)
                except ValueError:
                    print("Skipping this movie.")
                    return
                # Check for out-of-range input
                if movie_num < 0 or movie_num > num_titles:
                    print("Skipping this movie.")
                    return
            movie = results[movie_num]
            print("------------------------------------")

    else: # automatically pick first match
        movie = results[0]
        report_match(movie, len(results))

    # So far the Movie object only contains basic information like the
    # title and the year; retrieve main information:
    try:
        imdb_access.update(movie)
        #debug(3, movie.summary())
    except Exception as e:
        debug(0, 'Warning: unable to get extended details from IMDb for: ' + str(movie))
        debug(0, '         You may need to update your imdbpy module.')

    # title
    line = "title : %s %s\n" % (movie['title'], tags)

    # movieYear
    line += "movieYear : %s\n" % movie['year']

    reldate = ''
    if is_trailer:
        try:
            # This slows down the process, so only do it for trailers
            imdb_access.update(movie, 'release dates')
        except Exception as e:
            debug(1, 'Warning: unable to get release date.')
        if 'release dates' in list(movie.keys()) and len(movie['release dates']):
            reldate += rel_date(movie['release dates']) + '. '
    # description
    line += 'description : ' + reldate
    if "plot outline" in list(movie.keys()):
        line += movie['plot outline']
    # IMDB score if available
    if "rating" in list(movie.keys()):
        line += " IMDB: %s/10" % movie['rating']
    line += "\n"

    # isEpisode always false for movies
    line += "isEpisode : false\n"
    # starRating
    if "rating" in list(movie.keys()):
        line += "starRating : x%s\n" % (int((movie['rating']-1)/1.3+1))
    # mpaa_rating
    # kind of a hack for now...
    # maybe parsing certificates would work better?
    if "mpaa" in list(movie.keys()):
        mpaa_str = movie['mpaa']
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
            line += "mpaa_rating : %s\n" % mpaa_rating

    #vProgramGenre and vSeriesGenre
    if "genres" in list(movie.keys()):
        for i in movie['genres']:
            line += "vProgramGenre : %s\n" % i
        for i in movie['genres']:
            line += "vSeriesGenre : %s\n" % i
        if OPTIONS.genre:
            link_genres(dir_, file_name, metadata_file_name, movie['genres'])

    try:
        pass
        #don't enable the next line unless you want the full cast,
        #   actors + everyone else who worked on the movie
        #imdb_access.update(movie, 'full credits')
    except:
        debug(1, "Warning: unable to retrieve full credits.")

    # vDirector (suppress repeated names)
    if "director" in list(movie.keys()):
        directors = {}
        for i in movie['director']:
            if i['name'] not in directors:
                directors[i['name']] = 1
                line += "vDirector : %s|\n" % i['name']
                debug(3, 'vDirector : ' + i['name'])
    # vWriter (suppress repeated names)
    if "writer" in list(movie.keys()):
        writers = {}
        for i in movie['writer']:
            if i['name'] not in writers:
                writers[i['name']] = 1
                line += "vWriter : %s|\n" % i['name']
                debug(3, 'vWriter : ' + i['name'])
    # vActor (suppress repeated names)
    if "cast" in list(movie.keys()):
        actors = {}
        for i in movie['cast']:
            if i['name'] not in actors:
                actors[i['name']] = 1
                line += "vActor : %s|\n" % i['name']
                debug(3, 'vActor : ' + i['name'])

    debug(2, "Writing to %s" % metadata_file_name)
    out_file = open(metadata_file_name, 'w')
    out_file.writelines(line.encode(file_encoding, 'replace'))
    out_file.close()

def link_genres(work_dir, file_name, metadata_path, genres):
    for genre in genres:
        genrepath = os.path.join(OPTIONS.genre, genre)
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

def report_match(movie, num_results):
    matchtype = 'Using best match: '
    if num_results == 1:
        matchtype = 'Found exact match: '
    if 'long imdb title' in list(movie.keys()):
        debug(1, matchtype + movie['long imdb title'])
    else:
        debug(1, matchtype + str(movie))

def rel_date(reldates):
    for rd in reldates:
        if rd.encode(file_encoding, 'replace').lower().startswith(COUNTRY.lower() + '::'):
            return rd[len(COUNTRY)+2:]
    # Didn't find the country we want, so return the first one, but leave the
    #   country name in there.
    return reldates[0]

def get_files(directory):
    """Get list of file info objects for files of particular extensions
    """
    entries = os.listdir(directory)
    file_list = [f for f in entries if os.path.splitext(f)[1].lower() in fileExtList and len(os.path.splitext(f)[0]) and os.path.isfile(os.path.join(directory, f))]
    file_list.sort()
    debug(2, "file_list after cull: %s" % str(file_list))
    dir_list = []
    if OPTIONS.recursive:
        # Get a list of all sub dirs
        dir_list = [d for d in entries if os.path.isdir(os.path.join(directory, d)) and not d[0] == '.']
        dir_list.sort()
        debug(2, "dir_list after cull: %s" % str(dir_list))
    return (file_list, dir_list)

def parse_movie(search_dir, filename, metadata_file_name, is_trailer):
    if not IMDB:
        print("No IMDB module, skipping movie: " + filename)
        return

    title = os.path.splitext(filename)[0]

    # Most tags and group names come after the year (which is often in parens
    #   or brackets)
    # Using the year when searching IMDb will help, so try to find it.
    m = re.match(r'(.*?\w+.*?)(?:([[(])|(\W))(.*?)((?:19|20)\d\d)(?(2)[])]|(\3|$))(.*?)$', title)
    if m:
        (tags, _) = extract_tags(title)
        (title, year, _, _) = m.group(1, 5, 4, 7)
        debug(2, "    Title: %s\n    Year: %s" % (title, year))
        title += ' (' + year + ')'
    else:
        # 2nd pass at finding the year.  Look for a series of tags in parens
        #   which may include the year.
        m = re.match(r'(.*?\w+.*?)\(.*((?:19|20)\d\d)\).*\)', title)
        if m:
            (title, year) = m.group([1, 2])
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
    format_movie_data(title, search_dir, filename, metadata_file_name, tags, is_trailer)

def extract_tags(title):
    # Look for tags that we want to show on the tivo, but not include in IMDb searches.
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
    debug(2, '    Tags: ' + tags)
    return (tags, title)

def clean_title(title):
    # strip a variety of common junk from torrented avi filenames
    striplist = (r'crowbone', r'joox-dot-net', r'DOMiNiON', r'LiMiTED',
            r'aXXo', r'DoNE', r'ViTE', r'BaLD', r'COCAiNE', r'NoGRP',
            r'leetay', r'AC3', r'BluRay', r'DVD', r'VHS', r'Screener',
            r'(?i)DVD SCR', r'\[.*\]', r'(?i)swesub', r'(?i)dvdrip',
            r'(?i)dvdscr', r'(?i)xvid', r'(?i)divx'
            )
    for strip in striplist:
        title = re.sub(strip, '', title)
    debug(3, "After stripping keywords, title is: " + title)
    return title

def fix_spaces(title):
    placeholders = ['[-._]', '  +']
    for ph in placeholders:
        title = re.sub(ph, ' ', title)
    # Remove leftover spaces before/after the year
    title = re.sub(r'\( ', '(', title)
    title = re.sub(r' \)', ')', title)
    title = re.sub(r'\(\)', '', title)
    return title

def parse_tv(mirror_url, match, meta_dir, meta_file, show_dir):
    series = re.sub(r'[._]', ' ', match.group(1)).strip()
    if match.lastindex >= 4:
        season = 0
        episode = 0
        if int(match.group(2)) >= 1000:
            year = str(int(match.group(2)))
            month = str(int(match.group(3)))
            day = str(int(match.group(4)))
        else:
            year = str(int(match.group(4)))
            month = str(int(match.group(2)))
            day = str(int(match.group(3)))
    else:
        season = str(int(match.group(2))) # strip out leading zeroes
        episode = str(int(match.group(3)))
        year = 0
        month = 0
        day = 0
    debug(2, "    Series: %s\n    Season: %s\n    Episode: %s\n    Year: %s\n    Month: %s\n    Day: %s" % (series, season, episode, year, month, day))

    episode_info = {}
    if series not in SINFOCACHE:
        SINFOCACHE[series] = get_series_id(mirror_url, series, show_dir)
    (series_info_xml, seriesid) = SINFOCACHE[series]
    if seriesid is not None and series_info_xml is not None:
        for node in series_info_xml.getiterator():
            episode_info[node.tag] = node.text
        if year == 0:
            episode_info_xml = get_episode_info_xml(mirror_url, seriesid, season, episode)
        else:
            episode_info_xml = get_episode_info_xml_by_air_date(mirror_url, seriesid, year, month, day)
        if episode_info_xml is not None:
            for node in episode_info_xml.getiterator():
                episode_info[node.tag] = node.text
            format_episode_data(episode_info, meta_dir, meta_file)

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

def process_dir(dir_proc, mirror_url):
    debug(1, '\n## Looking for videos in: ' + dir_proc)
    (file_list, dir_list) = get_files(dir_proc)

    is_trailer = 0
    # See if we're in a "Trailer" folder.
    if 'trailer' in os.path.abspath(dir_proc).lower():
        is_trailer = 1

    meta_dir = dir_proc
    if OPTIONS.metadir or os.path.isdir(os.path.join(dir_proc, METADIR)):
        meta_dir = os.path.join(dir_proc, METADIR)
        mkdir_if_needed(meta_dir)
    for filename in file_list:
        meta_file = filename + '.txt'
        debug(1, "\n--->working on: %s" % filename)
        debug(2, "Metadir is: " + meta_dir)
        if os.path.exists(os.path.join(meta_dir, meta_file)) and not OPTIONS.clobber:
            debug(1, "Metadata file already exists, skipping.")
        else:
            ismovie = 1;
            for tvre in tvres:
                match = re.search(tvre, filename)
                if match: # Looks like a TV show
                    if not TVDB:
                        debug(1, "Metadata service for TV shows is unavailable, skipping this show.")
                    else:
                        parse_tv(mirror_url, match, meta_dir, meta_file, dir_proc)
                    ismovie = 0
                    break
            if ismovie:
                parse_movie(dir_proc, filename, os.path.join(meta_dir, meta_file), is_trailer)
    for subdir in dir_list:
        process_dir(os.path.join(dir_proc, subdir), mirror_url)

def check_interactive():
    if sys.platform not in ['win32', 'cygwin']:
        # On unix-like platforms, set interactive mode when running from a terminal
        if os.isatty(sys.stdin.fileno()):
            return True
    # On windows systems set interactive when running from a console
    elif 'PROMPT' in list(os.environ.keys()):
        return True
    return False

def process_command_line(argv):
    """Process command line invocation arguments and switches.

    Args:
        argv: list of arguments, or `None` from ``sys.argv[1:]``.

    Returns:
        args: Namespace with named attributes of arguments and switches
    """
    #script_name = argv[0]
    argv = argv[1:]

    # initialize the parser object:
    parser = argparse.ArgumentParser(
            description="Retrieve information from TVDB and IMDB to add "\
                    "TiVo metadatada to all media files in the current "\
                    "directory."
                    )

    # optional positional list of directories:
    parser.add_argument(
            "dir", nargs="*", default=['.'],
            help="Specific directory(-ies) to process. (Default is current directory.)"
            )

    # switches/options:
    parser.add_argument(
            "-d", "--debug", action="count", dest="debug", default=0,
            help="Turn on debugging. More -d's increase debug level."
            )
    parser.add_argument(
            "-f", "--force", action="store_true", dest="clobber",
            help="Force overwrite of existing metadata"
            )
    parser.add_argument(
            "-t", "--tidy", action="store_true", dest="metadir",
            help="Save metadata to the .meta directory in video directory. "\
                    "Compatible with tlc's patch "\
                    "(http://pytivo.krkeegan.com/viewtopic.php?t=153)"
            )
    parser.add_argument(
            "-r", "--recursive", action="store_true", dest="recursive",
            help="Generate metadata for all files in sub dirs too."
            )
    parser.add_argument(
            "-g", "--genre", dest="genre",
            help="Specify a directory in which to place symlinks to shows, "\
                    "organized by genre."
            )
    parser.add_argument(
            "-w", "--wait", dest="timeout", type=int, default=5,
            help="How many seconds to wait for a connection to theTVdb.com "\
                    "before giving up. (Default: 5s)"
            )

    args = parser.parse_args(argv)

    return args

def main():
    global OPTIONS
    args = process_command_line(sys.argv)
    OPTIONS = args

    OPTIONS.interactive = check_interactive()

    debug(2, "\nConsole Input encoding: %s" % in_encoding)
    debug(2, "Console Output encoding: %s" % out_encoding)
    debug(2, "Metadata File Output encoding: %s\n" % file_encoding)

    # Initalize things we'll need for looking up data
    mirror_url = get_mirror_url()

    if OPTIONS.genre:
        # Python doesn't support making symlinks on Windows.
        if sys.platform in ['win32', 'cygwin']:
            debug(0, "The genre feature doesn't work on Windows as symlinks " +\
                    "aren't well supported."
                    )
            OPTIONS.genre = ''
        else:
            if not os.path.exists(OPTIONS.genre):
                os.makedirs(OPTIONS.genre, 0o755)
            elif not os.path.isdir(OPTIONS.genre):
                raise OSError(
                        'Can\'t create "' + OPTIONS.genre + '" as a dir, a ' + \
                                'file already exists with that name.'
                        )
            else:
                debug(0, "Note: If you've removed videos, there may be old " +\
                        "symlinks in '" + OPTIONS.genre + "'.  If there's " +\
                        "nothing else in there, you can just remove the " +\
                        "whole thing first, then run this again (e.g. " +\
                        "rm -rf '" + OPTIONS.genre + "'), but be careful."
                        )

    for search_dir in OPTIONS.dir:
        process_dir(search_dir, mirror_url)

if __name__ == "__main__":
    main()
