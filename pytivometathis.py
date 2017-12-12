#!/usr/bin/env python3
# Copyright (c) 2008, Graham Dunn <gmd@kurai.org>
# Copyright (c) 2009-2011, Josh Harding <theamigo@gmail.com>
# Copyright (c) 2017, Matthew Clapp <itsayellow+dev@gmail.com>
#
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

# Version : 0.3

import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
import sys
import re
import string
import os
import errno
import sqlite3
import gzip
import io

from optparse import OptionParser
from xml.etree.ElementTree import parse, Element, SubElement
from time import gmtime, strftime, strptime
from datetime import datetime
from functools import reduce

# Import the IMDbPY package.
IMDB = 1
try:
    import imdb
except ImportError:
    print('IMDB module could not be loaded. Movie Lookups will be disabled. See http://imdbpy.sourceforge.net')
    IMDB = 0

# Which country's release date do we want to see:
COUNTRY = 'USA'

parser = OptionParser()
parser.add_option("-d", "--debug", action="count", dest="debug", help="Turn on debugging. More -d's increase debug level.")
parser.add_option("-f", "--force", action="store_true", dest="clobber", help="Force overwrite of existing metadata")
parser.add_option("-t", "--tidy", action="store_true", dest="metadir", help="Save metadata to the .meta directory in video directory. Compatible with tlc's patch (http://pytivo.krkeegan.com/viewtopic.php?t=153)")
parser.add_option("-r", "--recursive", action="store_true", dest="recursive", help="Generate metadata for all files in sub dirs too.")
parser.add_option("-g", "--genre", dest="genre", help="Specify a directory in which to place symlinks to shows, organized by genre.")
parser.add_option("-w", "--wait", dest="timeout", help="How many seconds to wait for a connection to theTVdb.com before giving up. (Default: 5s)")

# Options below here are all deprecated... most have been automated.
parser.add_option("-a", "--alternate", action="store_true", dest="isAltOutput", help="Deprecated.  Use templates instead: http://pytivo.krkeegan.com/pytivo-video-templates-t618.html")
parser.add_option("-i", "--interactive", action="store_true", dest="interactive", help="Deprecated.  Interactive prompts are automatically supressed when run via cron or as a scheduled task.")
parser.add_option("-m", "--movie", action="store_true", dest="isMovie", help="Deprecated.  Silently ignored to prevent errors.")
parser.add_option("-p", "--path", action="count", dest="ignore", help="Deprecated.  Directories may be listed without a -p, default is '.'")

(options, args) = parser.parse_args()

# Flag to track if TV lookups are enabled.
TVDB = 1
APIKEY="0403764A0DA51955"

GETSERIESID_URL = '/api/GetSeries.php?'
GETEPISODEID_URL = '/GetEpisodes.php?'
GETEPISODEINFO_URL = '/EpisodeUpdates.php?'

# Cache for series info.
SINFOCACHE = {}

# When using a subdir for metadata files, what should it be called
METADIR = '.meta'

# Regexes that match TV shows.
tvres = [r'(.+)[Ss](\d\d?)[Ee](\d+)', r'(.+?)(?: -)? ?(\d+)[Xx](\d+)', r'(.*).(\d\d\d\d).(\d+).(\d+).*', r'(.*).(\d+).(\d+).(\d\d\d\d).*', r'(?i)(.+)(\d?\d)(\d\d).*sitv']
# Types of files we want to get metadata for
fileExtList = [".mpg", ".avi", ".ogm", ".mkv", ".mp4", ".mov", ".wmv", ".vob", ".m4v", ".flv"]
# string encoding for input from console
in_encoding = sys.stdin.encoding or sys.getdefaultencoding()
# string encoding for output to console
out_encoding = sys.stdout.encoding or sys.getdefaultencoding()
# string encoding for output to metadata files.  Tivo is UTF8 compatible so use that for file output
file_encoding = 'UTF-8'

# We do a couple things differently if we're running python 2.6+ so check the version
PY26 = 0
(major, minor) = sys.version_info[0:2]
if major > 2 or (major == 2 and minor >= 6):
    PY26 = 1

def debug(level, text):
    if level<= options.debug:
        try:
            # Failes to print non-ASCII chars with the high bit set
            print(text.encode(out_encoding, 'replace'))
        except UnicodeDecodeError as e:
            try:
                # This can fail on unicode chars
                print(text)
            except UnicodeDecodeError as e:
                try:
                    # If sys.stdout.encoding is ascii (or 'ANSI_X3.4-1968') then the
                    # previous two attempts were the same thing, try something else
                    print(text.encode('latin-1', 'replace'))
                except UnicodeDecodeError as e:
                    print("Unable to display debug message, error is: " + str(e))

def alarmHandler():
    raise Exception('TimeOut')

def getMirrorURL():
    global TVDB
    # Query tvdb for a list of mirrors
    mirrorsURL = "http://www.thetvdb.com/api/%s/mirrors.xml" % APIKEY
    mirrorURL = ''
    # If we don't hear back after timeout seconds, give up and move on
    timeout = options.timeout or 5
    try:
        if PY26:
            mirrorsXML = parse(urllib.request.urlopen(mirrorsURL, None, timeout))
        else:
            # Before python 2.6, there's no timeout value:
            signal.signal(signal.SIGALRM, alarmHandler)
            try:
                signal.alarm(timeout)
                mirrorsXML = parse(urllib.request.urlopen(mirrorsURL))
            except 'TimeOut':
                debug(0, "Timeout looking up mirrors for thetvdb.com, site down?  No metadata will be retrieved for TV shows.")
                TVDB = 0
            signal.alarm(0)

        mirrors = [Item for Item in mirrorsXML.findall('Mirror')]
        mirrorURL = mirrors[0].findtext('mirrorpath')
    except:
        debug(0, "Error looking information from thetvdb, no metadata will be retrieved for TV shows.")
        TVDB = 0
    return mirrorURL

def findSeriesByYear(series, year):
    matchingSeries = []
    for show in series:
        firstAired = show.findtext('FirstAired')
        if firstAired:
            match = re.search(r'(\d\d\d\d)-\d\d-\d\d', firstAired)
            if match and year == match.group(1):
                matchingSeries.append(show)
    # Return all that matched the year (which may be an empty list)
    return matchingSeries

# patched function to allow hex
def toHex(s):
    lst = []
    for ch in s:
        hv = hex(ord(ch)).replace('0x', '')
        if len(hv) == 1:
            hv = '0'+hv
        lst.append(hv)

    return reduce(lambda x,y:x+y, lst)

# patched function to allow parsing gzipped data
def getXML(url):
    debug(3,"getXML: Using URL " + url)
    try:
        rawXML = urllib.request.urlopen(url).read()
    except Exception as e:
        debug(0, "\n Exception = " + str(e))
        return None
    
    xml = None
    if ( toHex(rawXML[0:2]) !=  "1f8b" ): #check for gzip compressed data
        filestream = io.StringIO(rawXML)
        debug(0,"Not gzip compressed data " +  toHex(rawXML[0:2]))
    else:
        filestream = gzip.GzipFile(fileobj=io.StringIO(rawXML))
        debug(0, "gzip compressed data")
    try:
        xml = parse(filestream).getroot()
    except Exception as e:
        debug(0, "\n Exception = " + str(e))
        debug(3,"\nrawXML = " + rawXML + "\n\nhexXML = " + toHex(rawXML))

    return xml

def getSeriesId(MirrorURL, show_name, showDir):
    seriesid = ''
    sidfiles = [os.path.join(showDir, show_name + ".seriesID")]
    if options.metadir or os.path.isdir(os.path.join(showDir, METADIR)):
        sidfiles.append(os.path.join(showDir, METADIR, show_name + ".seriesID"))

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
        debug(2,"Looking for .seriesID file in " + seriesidpath)
        # Get seriesid
        if os.path.exists(seriesidpath):
            debug(2,'Reading seriesID from file: ' + seriesidpath)
            seriesidfile = open(seriesidpath, 'r')
            seriesid = seriesidfile.read()
            seriesidfile.close()
            debug(1,'Using stored seriesID: ' + seriesid)

    if not options.clobber and len(seriesid) > 0:
        seriesid = re.sub("\n", "", seriesid)
    else:
        debug(1,'Searching for: ' + bare_title)
        url = MirrorURL + GETSERIESID_URL + urllib.parse.urlencode({"seriesname" : bare_title})
        debug(3,'seriesXML: Using URL ' + url)
        # patch new
        seriesXML = getXML(url)
        if ( seriesXML is None):
            debug(3,"Error getting Series Info")
            return None, None
        #seriesXML = parse(urllib.urlopen(url)).getroot()
        series = [Item for Item in seriesXML.findall('Series')]

        if year and len(series) > 1:
            debug(2, 'There are %d matching series, but we know what year to search for (%s).' % (len(series), year))
            series = findSeriesByYear(series, year)
            debug(2, 'Series that match by year: %d.' % len(series))

        if len(series) == 1:
            debug(1,"Found exact match")
            seriesid = series[0].findtext('id')
        elif options.interactive:
            # Display all the shows found
            if len(series) >= 2:
                print("####################################\n")
                print("Multiple TV Shows found:\n")
                print("Found %s shows for Series Title %s" % (len(series), show_name.encode(out_encoding, 'replace')))
                print("------------------------------------")
                for e in series:
                    eSeriesName = e.findtext('SeriesName')
                    eId = e.findtext('id')
                    eOverview = e.findtext('Overview')
                    firstAired = e.findtext('FirstAired')
                    # eOverview may not exist, so default them to something so print doesn't fail
                    if eOverview is None:
                        eOverview = "<None>"
                    if len(eOverview) > 240:
                        eOverview = eOverview[0:239]
                    print("Series Name:\t%s" % eSeriesName.encode(out_encoding, 'replace'))
                    print("Series ID:\t%s" % eId.encode(out_encoding, 'replace'))
                    if firstAired:
                        print("1st Aired:\t%s" % firstAired.encode(out_encoding, 'replace'))
                    print("Description:\t%s\n------------------------------------" % eOverview.encode(out_encoding, 'replace'))
                print("####################################\n\n")
                try:
                    seriesid = input('Please choose the correct seriesid: ')
                except KeyboardInterrupt:
                    print("\nCaught interrupt, exiting.")
                    sys.exit(1)

        elif len(series) > 1:
            debug(1,"Using best match: " + series[0].findtext('SeriesName'))
            seriesid = series[0].findtext('id')

        # Did we find any matches
        if len(series) and len(seriesid):
            debug(1,'Found seriesID: ' + seriesid)
            debug(2,'Writing seriesID to file: ' + seriesidpath)
            seriesidfile = open(seriesidpath, 'w')
            seriesidfile.write(seriesid)
            seriesidfile.close()
        else:
            debug(1,"Unable to find seriesid.")

    seriesURLXML = None
    if seriesid:
        seriesURL = MirrorURL + "/api/" + APIKEY + "/series/" + seriesid + "/en.xml"
        debug(3,"getSeriesInfoXML: Using URL " + seriesURL)
        # patch new
        seriesURLXML = getXML(seriesURL)
        if ( seriesURLXML is None ):
            debug(0,"!! Error parsing series info, skipping.")
        #try:
        #    seriesURLXML = parse(urllib.urlopen(seriesURL)).getroot()
        #except Exception, e:
        #    debug(0,"!! Error parsing series info, skipping.")
        #    debug(0,"!! Error description is: " + str(e))
        #    debug(3,"!! XML content is:\n" + str(urllib.urlopen(seriesURL).read()))
    return seriesURLXML, seriesid

def getEpisodeInfoXML(MirrorURL, seriesid, season, episode):
    # Takes a seriesid, season number, episode number and return xml data`
    url = MirrorURL + "/api/" + APIKEY + "/series/" + seriesid + "/default/" + season + "/" + episode + "/en.xml"
    debug(3,"getEpisodeInfoXML: Using URL " + url)
    # patch new
    episodeInfoXML = getXML(url)
    
    if ( episodeInfoXML is None):
        debug(0,"!! Error looking up data for this episode, skipping.")
    #try:
    #    episodeInfoXML = parse(urllib.urlopen(url)).getroot()
    #except Exception, e:
    #    debug(0,"!! Error looking up data for this episode, skipping.")
    #    print "exception is:"
    #    print e
    #    episodeInfoXML = None

    return episodeInfoXML

def getEpisodeInfoXMLByAirDate(MirrorURL, seriesid, year, month, day):
    # Takes a seriesid, year number, month number, day number, and return xml data`
    url = MirrorURL + "/api/GetEpisodeByAirDate.php?apikey=" + APIKEY + "&seriesid=" + seriesid + "&airdate=" + year + "-" + month + "-" + day
    debug(3, "getEpisodeInfoXMLByAirDate: Using URL " + url)
    # patch new
    episodeInfoXML = getXML(url)
    if ( episodeInfoXML is None):
        debug(0,"!! Error looking up data for this episode, skipping.")
    #try:
    #    episodeInfoXML = parse(urllib.urlopen(url)).getroot()
    #except Exception, e:
    #    debug(0,"!! Error looking up data for this episode, skipping.")
    #    episodeInfoXML = None

    return episodeInfoXML

def formatEpisodeData(e, metaDir, f):
    # Takes a dict e of XML elements, the series title, the Zap2It ID (aka the Tivo groupID), and a filename f
    # TODO : Split up multiple guest stars / writers / etc. Split on '|'. (http://trac.kurai.org/trac.cgi/ticket/2)
    # This is weak. Should just detect if EpisodeNumber exists.
    metadataText = ''
    isE = "true"
    e["isEpisode"] = isE

    # The following is a dictionary of pyTivo metadata attributes and how they map to thetvdb xml elements.
    pyTivoMetadata = {
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

    #for pyTivoTag in pyTivoMetadata.keys():
    #    print "%s : %s" % (pyTivoTag, pyTivoMetadata[pyTivoTag])

    # pyTivo Metadata tag order
    pyTivoMetadataOrder = [
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
    MetadataNameFields = [
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

    for tvTag in pyTivoMetadataOrder:

        debug(3,'Working on ' + tvTag)
        if tvTag in pyTivoMetadata and (pyTivoMetadata[tvTag]) and pyTivoMetadata[tvTag] in e and e[pyTivoMetadata[tvTag]]:
            # got data to work with
            line = term = ""
            text = str(e[pyTivoMetadata[tvTag]]).translate(transtable)

            # for debugging character translations
            #if tvTag == 'description':
            #    print "ord -> %s" % ord(text[370])

            debug(3,"%s : %s" % (tvTag, text))

            if tvTag == 'originalAirDate':
                text = datetime(*strptime(text, "%Y-%m-%d")[0:6]).strftime("%Y-%m-%dT%H:%M:%SZ")

            if tvTag == 'seriesId':
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

            # Only check to see if Season is > 0, allow EpNum to be 0 for things like "1x00 - Bonus content"
            if tvTag == 'episodeNumber' and e['EpisodeNumber'] and int(e['SeasonNumber']):
                text = "%d%02d" % (int(e['SeasonNumber']), int(e['EpisodeNumber']))

            if tvTag in MetadataNameFields:
                term = "|"

            if text is not None:
                if '|' in text:
                    people = text.strip('|').split('|')
                    for person in people:
                        debug(3,'Splitting ' + person.strip())
                        line += "%s : %s\n" % (tvTag, re.sub('\n', ' ', person.strip()+term))
                else:
                    line = "%s : %s\n" %(tvTag, re.sub('\n', ' ', text+term))
                    debug(3,'Completed -> ' + line)
                metadataText += line
        else:
            debug(3,'No data for ' + tvTag)

    if metadataText:
        mkdirIfNeeded(metaDir)
        outFile = open(os.path.join(metaDir, f), 'w')
        outFile.write(metadataText.encode(file_encoding, 'replace'))
        outFile.close()

def formatMovieData(title, dir, fileName, metadataFileName, tags, isTrailer):
    line = ""

    debug(1,'Searching IMDb for: ' + title)
    objIA = imdb.IMDb() # create new object to access IMDB
    title = str(title, in_encoding, 'replace')
    try:
        # Do the search, and get the results (a list of Movie objects).
        results = objIA.search_movie(title)
    except imdb.IMDbError as e:
        debug(0,'IMDb lookup error: ' + str(e))
        sys.exit(3)

    if not results:
        debug(1,'No matches found.')
        return

    if options.interactive:
        # Get number of movies found
        num_titles = len(results)

        # If only one found, select and go on
        if num_titles == 1:
            movie = results[0]
            reportMatch(movie, len(results))
        else:
            debug(2,'Found ' + str(num_titles) + ' matches.')
            # Show max 5 titles
            num_titles = min(num_titles, 5)

            #print "Found %s matches for /'%s/'\n" % (len(results), title.encode(out_encoding, 'replace'))
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
        reportMatch(movie, len(results))

    # So far the Movie object only contains basic information like the
    # title and the year; retrieve main information:
    try:
        objIA.update(movie)
        #debug(3,movie.summary())
    except Exception as e:
        debug(0,'Warning: unable to get extended details from IMDb for: ' + str(movie))
        debug(0,'         You may need to update your imdbpy module.')

    # title
    line = "title : %s %s\n" % (movie['title'], tags)

    # movieYear
    line += "movieYear : %s\n" % movie['year']

    reldate = ''
    if isTrailer:
        try:
            # This slows down the process, so only do it for trailers
            objIA.update(movie, 'release dates')
        except Exception as e:
            debug(1,'Warning: unable to get release date.')
        if 'release dates' in list(movie.keys()) and len(movie['release dates']):
            reldate += relDate(movie['release dates']) + '. '
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
    # mpaaRating
    # kind of a hack for now...
    # maybe parsing certificates would work better?
    if "mpaa" in list(movie.keys()):
        mpaaStr = movie['mpaa']
        mpaaRating = ""
        if "Rated G " in mpaaStr:
            mpaaRating = "G1"
        elif "Rated PG " in mpaaStr:
            mpaaRating = "P2"
        elif "Rated PG-13 " in mpaaStr:
            mpaaRating = "P3"
        elif "Rated R " in mpaaStr:
            mpaaRating = "R4"
        elif "Rated X " in mpaaStr:
            mpaaRating = "X5"
        elif "Rated NC-17 " in mpaaStr:
            mpaaRating = "N6"

        if mpaaRating:
            line += "mpaaRating : %s\n" % mpaaRating

    #vProgramGenre and vSeriesGenre
    if "genres" in list(movie.keys()):
        for i in movie['genres']:
            line += "vProgramGenre : %s\n" % i
        for i in movie['genres']:
            line += "vSeriesGenre : %s\n" % i
        if options.genre:
            linkGenres(dir, fileName, metadataFileName, movie['genres'])

    try:
        pass
        #don't enable the next line unless you want the full cast, actors + everyone else who worked on the movie
        #objIA.update(movie, 'full credits')
    except:
        debug(1, "Warning: unable to retrieve full credits.")

    # vDirector (suppress repeated names)
    if "director" in list(movie.keys()):
        directors = {}
        for i in movie['director']:
            if i['name'] not in directors:
                directors[i['name']] = 1
                line += "vDirector : %s|\n" % i['name']
                debug(3,'vDirector : ' + i['name'])
    # vWriter (suppress repeated names)
    if "writer" in list(movie.keys()):
        writers = {}
        for i in movie['writer']:
            if i['name'] not in writers:
                writers[i['name']] = 1
                line += "vWriter : %s|\n" % i['name']
                debug(3,'vWriter : ' + i['name'])
    # vActor (suppress repeated names)
    if "cast" in list(movie.keys()):
        actors = {}
        for i in movie['cast']:
            if i['name'] not in actors:
                actors[i['name']] = 1
                line += "vActor : %s|\n" % i['name']
                debug(3,'vActor : ' + i['name'])

    debug(2,"Writing to %s" % metadataFileName)
    outFile = open(metadataFileName, 'w')
    outFile.writelines(line.encode(file_encoding, 'replace'))
    outFile.close()

def linkGenres(dir, fileName, metadataPath, genres):
    for genre in genres:
        genrepath = os.path.join(options.genre, genre)
        mkdirIfNeeded(genrepath)
        # Create a symlink to the video
        link = os.path.join(genrepath, fileName)
        filePath = os.path.join(dir, fileName)
        mkLink(link, filePath)
        # Create a symlink to the metadata
        metadataDir = os.path.basename(metadataPath)
        link = os.path.join(genrepath, metadataDir)
        mkLink(link, metadataPath)

def mkLink(linkName, filePath):
    if PY26:
        # Needs python 2.6+ for relpath()
        target = os.path.relpath(filePath, os.path.dirname(linkName))
    else:
        # Older pythons will have to point links to absolute paths
        target = os.path.realpath(filePath)
    debug(2, "Linking " + linkName + " -> " + target)
    if os.path.islink(linkName):
        os.unlink(linkName)
        os.symlink(target, linkName)
    elif os.path.exists(linkName):
        debug(0,"Unable to create link '" + linkName + "', a file already exists with that name.")
    else:
        os.symlink(target, linkName)

def reportMatch(movie, numResults):
    matchtype = 'Using best match: '
    if numResults == 1:
        matchtype = 'Found exact match: '
    if 'long imdb title' in list(movie.keys()):
        debug(1,matchtype + movie['long imdb title'])
    else:
        debug(1,matchtype + str(movie))

def relDate(reldates):
    for rd in reldates:
        if rd.encode(file_encoding,'replace').lower().startswith(COUNTRY.lower() + '::'):
            return rd[len(COUNTRY)+2:]
    # Didn't find the country we want, so return the first one, but leave the country name in there.
    return reldates[0]

def getfiles(directory):
    "Get list of file info objects for files of particular extensions"
    entries = os.listdir(directory)
    fileList = [f for f in entries if os.path.splitext(f)[1].lower() in fileExtList and len(os.path.splitext(f)[0]) and os.path.isfile(os.path.join(directory, f))]
    fileList.sort()
    debug(2,"fileList after cull: %s" % str(fileList))
    dirList = []
    if options.recursive:
        # Get a list of all sub dirs
        dirList = [d for d in entries if os.path.isdir(os.path.join(directory, d)) and not d[0] == '.']
        dirList.sort()
        debug(2,"dirList after cull: %s" % str(dirList))
    return (fileList, dirList)

def parseMovie(dir, filename, metadataFileName, isTrailer):
    if not IMDB:
        print("No IMDB module, skipping movie: " + filename)
        return

    title = os.path.splitext(filename)[0]

    # Most tags and group names come after the year (which is often in parens or brackets)
    # Using the year when searching IMDb will help, so try to find it.
    m = re.match(r'(.*?\w+.*?)(?:([[(])|(\W))(.*?)((?:19|20)\d\d)(?(2)[])]|(\3|$))(.*?)$', title)
    if m:
        (tags, junk) = extractTags(title)
        (title, year, soup1, soup2) = m.group(1,5,4,7)
        soup = "%s %s" % (soup1, soup2)
        debug(2,"    Title: %s\n    Year: %s" % (title, year))
        title += ' (' + year + ')'
    else:
        # 2nd pass at finding the year.  Look for a series of tags in parens which may include the year.
        m = re.match(r'(.*?\w+.*?)\(.*((?:19|20)\d\d)\).*\)', title)
        if m:
            (title, year) = m.group([1,2])
            debug(2,"    Title: %s\n    Year: %s" % (title, year))
            title += ' (' + year + ')'
        else:
            debug(2,"Cleaning up title the hard way.")
            title = cleanTitle(title)
            debug(2,"    Title: %s" % title)
        # Note: this also removes the tags from the title
        (tags, title) = extractTags(title)
    debug(3, "Before fixing spaces, title is: " + title)
    title = fixSpaces(title)
    debug(3, "After fixing spaces, title is: " + title)
    formatMovieData(title, dir, filename, metadataFileName, tags, isTrailer)

def extractTags(title):
    # Look for tags that we want to show on the tivo, but not include in IMDb searches.
    tags = ""
    taglist = {
        # Strip these out      : return these instead
        '(\d{3,4})([IiPp])'    : r'\1\2', #720p,1080p,1080i,720P,etc
        '(?i)Telecine'         : 'TC',    #Telecine,telecine
        'TC'                   : 'TC',
        '(?i)Telesync'         : 'TS',    #Telesync,telesync
        'TS'                   : 'TS',
        'CAM'                  : 'CAM',
        '(?i)CD ?(\d)'         : r'CD\1', #CD1,CD2,cd1,cd3,etc
        '(?i)\(?Disc ?(\d)\)?' : r'CD\1', #Disc 1,Disc 2,disc 1,etc
        }
    for tag in list(taglist.keys()):
        match = re.search(tag, title)
        if match:
            tags += match.expand(taglist[tag]) + ' '
            title = re.sub(tag, '', title)
    debug(2,'    Tags: ' + tags)
    return (tags, title)

def cleanTitle(title):
    # strip a variety of common junk from torrented avi filenames
    striplist = ('crowbone','joox-dot-net','DOMiNiON','LiMiTED','aXXo','DoNE','ViTE','BaLD','COCAiNE','NoGRP','leetay','AC3','BluRay','DVD','VHS','Screener','(?i)DVD SCR','\[.*\]','(?i)swesub','(?i)dvdrip','(?i)dvdscr','(?i)xvid','(?i)divx')
    for strip in striplist:
        title = re.sub(strip, '', title)
    debug(3,"After stripping keywords, title is: " + title)
    return title

def fixSpaces(title):
    placeholders = ['[-._]','  +']
    for ph in placeholders:
        title = re.sub(ph, ' ', title)
    # Remove leftover spaces before/after the year
    title = re.sub('\( ', '(', title)
    title = re.sub(' \)', ')', title)
    title = re.sub('\(\)', '', title)
    return title

def parseTV(MirrorURL, match, metaDir, metaFile, showDir):
    series = re.sub('[._]', ' ', match.group(1)).strip()
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
    debug(2,"    Series: %s\n    Season: %s\n    Episode: %s\n    Year: %s\n    Month: %s\n    Day: %s" % (series, season, episode, year, month, day))

    episodeInfo = {}
    if series not in SINFOCACHE:
        SINFOCACHE[series] = getSeriesId(MirrorURL, series, showDir)
    (seriesInfoXML, seriesid) = SINFOCACHE[series]
    if seriesid is not None and seriesInfoXML is not None:
        for node in seriesInfoXML.getiterator():
            episodeInfo[node.tag] = node.text
        if year == 0:
            episodeInfoXML = getEpisodeInfoXML(MirrorURL, seriesid, season, episode)
        else:
            episodeInfoXML = getEpisodeInfoXMLByAirDate(MirrorURL, seriesid, year, month, day)
        if episodeInfoXML is not None:
            for node in episodeInfoXML.getiterator():
                episodeInfo[node.tag] = node.text
            formatEpisodeData(episodeInfo, metaDir, metaFile)

def mkdirIfNeeded(dirname):
    if not os.path.exists(dirname):
        # Don't use os.makedirs() because that would only matter if -p named a non-existant dir (which we don't want to create)
        os.mkdir(dirname, 0o755)
    elif not os.path.isdir(dirname):
        raise OSError('Can\'t create "' + dirname + '" as a dir, a file already exists with that name.')

def processDir(dir, MirrorURL):
    debug(1,'\n## Looking for videos in: ' + dir)
    (fileList, dirList) = getfiles(dir)

    isTrailer = 0
    # See if we're in a "Trailer" folder.
    if 'trailer' in os.path.abspath(dir).lower():
        isTrailer = 1

    metaDir = dir
    if options.metadir or os.path.isdir(os.path.join(dir, METADIR)):
        metaDir = os.path.join(dir, METADIR)
        mkdirIfNeeded(metaDir)
    for filename in fileList:
        metaFile = filename + '.txt'
        debug(1,"\n--->working on: %s" % filename)
        debug(2,"Metadir is: " + metaDir)
        if os.path.exists(os.path.join(metaDir, metaFile)) and not options.clobber:
            debug(1,"Metadata file already exists, skipping.")
        else:
            ismovie = 1;
            for tvre in tvres:
                match = re.search(tvre, filename)
                if match: # Looks like a TV show
                    if not TVDB:
                        debug(1,"Metadata service for TV shows is unavailable, skipping this show.")
                    else:
                        parseTV(MirrorURL, match, metaDir, metaFile, dir)
                    ismovie = 0
                    break
            if ismovie:
                parseMovie(dir, filename, os.path.join(metaDir, metaFile), isTrailer)
    for subdir in dirList:
        processDir(os.path.join(dir, subdir), MirrorURL)

def checkInteractive():
    if sys.platform not in ['win32', 'cygwin']:
        # On unix-like platforms, set interactive mode when running from a terminal
        if os.isatty(sys.stdin.fileno()):
            options.interactive = 1
    # On windows systems set interactive when running from a console
    elif 'PROMPT' in list(os.environ.keys()):
        options.interactive = 1

def main():
    global args
    checkInteractive()

    debug(2,"\nConsole Input encoding: %s" % in_encoding)
    debug(2,"Console Output encoding: %s" % out_encoding)
    debug(2,"Metadata File Output encoding: %s\n" % file_encoding)

    # Initalize things we'll need for looking up data
    MirrorURL = getMirrorURL()

    if options.isAltOutput:
        debug(0,"Option -a is deprecated, ignoring.  Use templates instead: http://pytivo.krkeegan.com/pytivo-video-templates-t618.html")

    if options.genre:
        # Python doesn't support making symlinks on Windows.
        if sys.platform in ['win32', 'cygwin']:
            debug(0,"The genre feature doesn't work on Windows as symlinks aren't well supported.")
            options.genre = ''
        else:
            if not os.path.exists(options.genre):
                os.makedirs(options.genre, 0o755)
            elif not os.path.isdir(options.genre):
                raise OSError('Can\'t create "' + options.genre + '" as a dir, a file already exists with that name.')
            else:
                debug(0,"Note: If you've removed videos, there may be old symlinks in '" + options.genre + "'.  If there's nothing else in there, you can just remove the whole thing first, then run this again (e.g. rm -rf '" + options.genre + "'), but be careful.")

    # As of Python 2.6, setting default=['.'] doesn't work with action="append"... instead of
    # using the default when no dirs are specified, it always includes the default too.
    if not args:
        args = ['.']
    for dir in args:
        processDir(dir, MirrorURL)

if __name__ == "__main__":
    main()
