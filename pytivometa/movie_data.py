#!/usr/bin/env python3

#    movie_data.py, module to access movie data for pytivometa
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

import logging
import os
import os.path
import re
import sys


# imdbpy
import imdb


import common
import rpc_search


# Set up logger
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


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
    LOGGER.debug("3,After stripping keywords, title is: %s", title)
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
    LOGGER.debug("2,    Tags: %s", tags)
    return (tags, title)

def fix_spaces(title):
    placeholders = ['[-._]', '  +']
    for place_holder in placeholders:
        title = re.sub(place_holder, ' ', title)
    # Remove leftover spaces before/after the year
    title = re.sub(r'\( ', '(', title)
    title = re.sub(r' \)', ')', title)
    title = re.sub(r'\(\)', '', title)
    return title

def mk_link(link_name, file_path):
    target = os.path.relpath(file_path, os.path.dirname(link_name))
    LOGGER.debug("2,Linking " + link_name + " -> " + target)
    if os.path.islink(link_name):
        os.unlink(link_name)
        os.symlink(target, link_name)
    elif os.path.exists(link_name):
        print("Unable to create link '" + link_name + "', a file already "
                "exists with that name.")
    else:
        os.symlink(target, link_name)

def report_match(movie_info, num_results):
    matchtype = 'Using best match: '
    if num_results == 1:
        matchtype = 'Found exact match: '
    if 'long imdb title' in list(movie_info.keys()):
        LOGGER.debug(matchtype + movie_info['long imdb title'])
    else:
        LOGGER.debug(matchtype + str(movie_info))


class MovieData():
    def __init__(self, rpc_remote=None, interactive=False, genre_dir=None,
            country='USA', lang='English'):
        self.interactive = interactive

        self.genre_dir = genre_dir

        # Which country's release date do we want to see:
        #   Also as another way to search for an "Also Known As" title
        self.country = country

        # What language to use for "Also Known As" title?
        self.lang = lang

        # RPC access
        self.rpc_remote = rpc_remote

    def get_movie_info(self, title, is_trailer=False):
        # minimal movie listing:
        #
        # category: [
        #   {'categoryId': 'tivo:ca.413902', 'displayRank': 0,
        #       'label': 'Movies', 'topLevel': True, 'type': 'category'
        #   }
        # ]
        # collectionId: tivo:cl.ts.114928751
        # description: When Dr. Indiana Jones, the tweed-suited professor who
        #       just happens to be a celebrated archaeologist-- is hired by the
        #       government to locate the legendary Ark of the Covenant he finds
        #       himself up against the entire Nazi regime.  In HD.
        # movieYear: 1981
        # mpaaRating: pg
        # rating: [{'type': 'typedMpaaRating', 'value': 'pg'}]
        # title: Indiana Jones/Raiders of the Lost Ark
        # type: collection
        # -------------------
        # category: [
        #   {'categoryId': 'tivo:ca.121999524', 'displayRank': 0,
        #   'label': 'Action', 'topLevel': False, 'type': 'category'
        #   },
        #   {'categoryId': 'tivo:ca.121999525', 'displayRank': 1,
        #   'label': 'Adventure', #   'topLevel': False, 'type': 'category'
        #   }
        # ]
        # collectionId: tivo:cl.ts.93034831
        # description: Get ready for edge-of-your-seat thrills in Indiana Jones
        #       and the Raiders of the Lost Ark. Indy (Harrison Ford) and his feisty
        #       ex-flame Marion Ravenwood (Karen Allen) dodge booby-traps, fight
        #       Nazis and stare down snakes in their incredible worldwide quest for
        #       the mystical Ark of the Covenant. Experience one exciting cliffhanger
        #       after another when you discover adventure with the one and only
        #       Indiana Jones.
        # movieYear: 1981
        # mpaaRating: pg
        # partnerCollectionId: ZINC-VUDU#16966B1861503A2B287BFD393FE90E3ED1671AA2
        # rating: [{'type': 'typedMpaaRating', 'value': 'pg'}]
        # title: Indiana Jones and the Raiders of the Lost Ark
        # type: collection
        LOGGER.debug("Searching IMDb for: %s", title)
        # IMDB access object
        imdb_access = imdb.IMDb()
        try:
            # Do the search, and get the results (a list of Movie objects).
            results = imdb_access.search_movie(title)
        except imdb.IMDbError as error:
            print("IMDb lookup error: " + str(error))
            # TODO: raise Exception
            sys.exit(3)

        if not results:
            print(title + ": No IMDB matches found.")
            return None

        if len(results) > 1 and self.interactive:
            print("\nMatches for movie title '%s'"%title)
            print("------------------------------------")
            options_text = []
            for result in results:
                options_text.append(result['long imdb title'])
            imdb_movie_info = common.ask_user(options_text, results, max_options=5)
            print("------------------------------------")
        else:
            # automatically pick first match
            imdb_movie_info = results[0]
            report_match(imdb_movie_info, len(results))

        # get more info from RPC
        if self.rpc_remote is not None:
            rpc_movie_info = {}
            LOGGER.debug("2,from imdb: %s", imdb_movie_info['title'])

            tries_left = 3
            rpc_info = {}
            while tries_left > 0:
                try:
                    rpc_info = self.rpc_remote.search_movie(
                            imdb_movie_info['title'],
                            year=imdb_movie_info.get('year', None)
                            )
                except rpc_search.MindTimeoutError:
                    print("RPC Timeout, trying again...")
                    tries_left -= 1
                else:
                    tries_left = 0
            if rpc_info.get('partnerCollectionId', '') and rpc_info.get('partnerContentId', ''):
                partnerCollectionId = re.sub(
                        r'epgProvider:cl\.', '',
                        rpc_info['partnerCollectionId']
                        )
                partnerContentId = re.sub(
                        r'epgProvider:ct\.', '',
                        rpc_info['partnerContentId']
                        )
                rpc_movie_info['tivoSeriesId'] = partnerCollectionId
                rpc_movie_info['tivoProgramId'] = partnerContentId

            # DEBUG DELETEME
            for key in sorted(rpc_info):
                LOGGER.debug(key + ": " + str(rpc_info[key]))

        if imdb_movie_info is not None:
            # So far the imdb_movie_info object only contains basic information like the
            # title and the year; retrieve main information:
            try:
                imdb_access.update(imdb_movie_info)
                #LOGGER.debug("3," + imdb_movie_info.summary())
            except Exception:
                print("Warning: unable to get extended details from "
                        "IMDb for: " + str(imdb_movie_info))
                print("         You may need to update your imdbpy module.")

            try:
                pass
                #don't enable the next line unless you want the full cast,
                #   actors + everyone else who worked on the movie
                #imdb_access.update(imdb_movie_info, 'full credits')
            except:
                LOGGER.debug("Warning: unable to retrieve full credits.")

            if is_trailer:
                try:
                    # This slows down the process, so only do it for trailers
                    imdb_access.update(imdb_movie_info, 'release dates')
                except Exception:
                    LOGGER.debug("Warning: unable to get release date.")

        # copy from imdb_movie_info object into real dict
        movie_info = {}
        for key in imdb_movie_info.keys():
            movie_info[key] = imdb_movie_info[key]

        # add RPC info to movie info
        movie_info.update(rpc_movie_info)

        return movie_info

    def format_movie_data(self, movie_info, dir_, file_name, metadata_file_name, tags):
        """
        All imdbpy tags seen in a long list of movies:
        -------------------------------------------------------------------------
        ['akas', 'animation department', 'art department', 'art direction', 'aspect
        ratio', 'assistant director', 'camera and electrical department',
        'canonical title', 'cast', 'casting department', 'casting director',
        'certificates', 'cinematographer', 'color info', 'costume department',
        'costume designer', 'countries', 'country codes', 'cover url', 'director',
        'distributors', 'editor', 'editorial department', 'full-size cover url',
        'genres', 'imdbIndex', 'kind', 'language codes', 'languages', 'location
        management', 'long imdb canonical title', 'long imdb title', 'make up',
        'miscellaneous companies', 'miscellaneous crew', 'mpaa', 'music
        department', 'original music', 'plot', 'plot outline', 'producer',
        'production companies', 'production design', 'production manager',
        'rating', 'runtimes', 'set decoration', 'smart canonical title', 'smart
        long imdb canonical title', 'sound crew', 'sound mix', 'special effects
        companies', 'special effects department', 'stunt performer', 'thanks',
        'title', 'top 250 rank', 'transportation department', 'visual effects',
        'votes', 'writer', 'year']


        Description of movie tags from imbdpy
        https://github.com/alberanid/imdbpy/blob/master/docs/README.package.txt
        -------------------------------------------------------------------------
        title; string; the "usual" title of the movie, like "The Untouchables".
        long imdb title; string; "Uncommon Valor (1983/II) (TV)"
        canonical title; string; the title in the canonical format,
                                 like "Untouchables, The".
        long imdb canonical title; string; "Patriot, The (2000)".
        year; string; the year of release or '????' if unknown.
        kind; string; one in ('movie', 'tv series', 'tv mini series', 'video game',
                              'video movie', 'tv movie', 'episode')
        imdbIndex; string; the roman number for movies with the same title/year.
        director; Person list; a list of director's name (e.g.: ['Brian De Palma'])
        cast; Person list; list of actor/actress, with the currentRole instance
                           variable set to a Character object which describe his
                           role/duty.
        cover url; string; the link to the image of the poster.
        writer; Person list; list of writers ['Oscar Fraley (novel)']
        plot; list; list of plots and authors of the plot.
        rating; string; user rating on IMDb from 1 to 10 (e.g. '7.8')
        votes; string; number of votes (e.g. '24,101')
        runtimes; string list; in minutes ['119'] or something like ['USA:118',
                  'UK:116']
        number of episodes; int; number or episodes for a series.
        color info; string list; ["Color (Technicolor)"]
        countries; string list; production's country ['USA', 'Italy']
        genres; string list; one or more in (Action, Adventure, Adult, Animation,
                        Comedy, Crime, Documentary, Drama, Family, Fantasy, Film-Noir,
                        Horror, Musical, Mystery, Romance, Sci-Fi, Short, Thriller,
                        War, Western) and other genres defined by IMDb.
        akas; string list; list of aka for this movie
        languages; string list; list of languages
        certificates; string list; ['UK:15', 'USA:R']
        mpaa; string; the mpaa rating
        episodes (series only); dictionary of dictionary; one key for every season,
                                one key for every episode in the season.
        number of episodes (series only); int; total number of episodes.
        number of seasons (series only); int; total number of seasons.
        series years (series only); string; range of years when the series was produced.
        episode of (episode only); Movie object; the parent series for an episode.
        season (episode only); int; the season number.
        episode (episode only); int; the number of the episode in the season.
        long imdb episode title (episode only); string; episode and series title.
        series title; string.
        canonical series title; string.
        """
        line = ""

        # search for user language or country version of title if present
        title_aka = ''
        for aka in movie_info.get('akas', []):
            (title_aka, info_aka) = aka.split('::')
            # Note: maybe safer to search for '(imdb display title)' ?
            #   see: Volver, which finds "To Return" with USA, English?
            if self.country in info_aka or '(' + self.lang + ' title)' in info_aka:
                LOGGER.debug("3,AKA: " + title_aka + "::" + info_aka)
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

        # description
        line += 'description : '
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

        # TiVo Series ID and Program ID from RPC
        if 'tivoSeriesId' in movie_info:
            line += "seriesId : %s\n"%movie_info['tivoSeriesId']
        if 'tivoProgramId' in movie_info:
            line += "programId : %s\n"%movie_info['tivoProgramId']

        #vProgramGenre and vSeriesGenre
        for genre in movie_info.get('genres', []):
            line += "vProgramGenre : %s\n" % genre
        for genre in movie_info.get('genres', []):
            line += "vSeriesGenre : %s\n" % genre

        # genre directory linking
        if "genres" in list(movie_info.keys()) and self.genre_dir:
            self.link_genres(dir_, file_name, metadata_file_name,
                    movie_info['genres']
                    )

        # vDirector
        # go through list, omitting duplicates
        director_names = []
        for director in movie_info.get('director', []):
            if director['name'] not in director_names:
                director_names.append(director['name'])
                line += "vDirector : %s|\n" % director['name']
                LOGGER.debug("3,vDirector : %s", director['name'])
        # vWriter
        # go through list, omitting duplicates
        writer_names = []
        for writer in movie_info.get('writer', []):
            if writer['name'] not in writer_names:
                writer_names.append(writer['name'])
                line += "vWriter : %s|\n" % writer['name']
                LOGGER.debug("3,vWriter : %s", writer['name'])
        # vActor
        # go through list, omitting duplicates
        actor_names = []
        for actor in movie_info.get('cast', []):
            if actor['name'] not in actor_names:
                actor_names.append(actor['name'])
                line += "vActor : %s|\n" % actor['name']
                LOGGER.debug("3,vActor : %s", actor['name'])

        LOGGER.debug("2,Writing to %s", metadata_file_name)

        # only when we are about to write file make metadata dir (e.g. .meta) if
        #   we need to
        common.mkdir_if_needed(os.path.dirname(metadata_file_name))
        with open(metadata_file_name, 'w') as out_file:
            out_file.writelines(line)

    def link_genres(self, work_dir, file_name, metadata_path, genres):
        for this_genre in genres:
            genrepath = os.path.join(self.genre_dir, this_genre)
            common.mkdir_if_needed(genrepath)
            # Create a symlink to the video
            link = os.path.join(genrepath, file_name)
            file_path = os.path.join(work_dir, file_name)
            mk_link(link, file_path)
            # Create a symlink to the metadata
            metadata_dir = os.path.basename(metadata_path)
            link = os.path.join(genrepath, metadata_dir)
            mk_link(link, metadata_path)

    def parse_movie(self, search_dir, filename, metadata_file_name,
            is_trailer=False):
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
            LOGGER.debug("2,    Title: %s\n    Year: %s", title, year)
            title += ' (' + year + ')'
        else:
            # 2nd pass at finding the year.  Look for a series of tags in parens
            #   which may include the year.
            year_match2 = re.match(r'(.*?\w+.*?)\(.*((?:19|20)\d\d)\).*\)', title)
            if year_match2:
                (title, year) = year_match2.group([1, 2])
                LOGGER.debug("2,    Title: %s\n    Year: %s", title, year)
                title += ' (' + year + ')'
            else:
                LOGGER.debug("2,Cleaning up title the hard way.")
                title = clean_title(title)
                LOGGER.debug("2,    Title: %s", title)
            # Note: this also removes the tags from the title
            (tags, title) = extract_tags(title)
        LOGGER.debug("3,Before fixing spaces, title is: %s", title)
        title = fix_spaces(title)
        LOGGER.debug("3,After fixing spaces, title is: %s", title)

        movie_info = self.get_movie_info(title, is_trailer=is_trailer)

        if movie_info is not None:
            self.format_movie_data(movie_info, search_dir, filename, metadata_file_name, tags)
