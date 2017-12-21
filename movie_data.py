#!/usr/bin/env python3

import os
import os.path
import re
import sys
import textwrap

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

# debug level for messages of entire file
DEBUG_LEVEL = 0


# should be in common py file, duplicate for now ------------------------------
def debug(level, text):
    if level <= DEBUG_LEVEL:
        print(text)

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

# MOVIE DATA ------------------------------------------------------------------
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

def get_movie_info(title, interactive=False, is_trailer=False):
    debug(1, "Searching IMDb for: " + title)
    # IMDB access object
    imdb_access = imdb.IMDb()
    try:
        # Do the search, and get the results (a list of Movie objects).
        results = imdb_access.search_movie(title)
    except imdb.IMDbError as error:
        debug(0, "IMDb lookup error: " + str(error))
        sys.exit(3)

    if not results:
        debug(0, title + ": No IMDB matches found.")
        return

    if len(results) > 1 and interactive:
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
        except Exception:
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
            except Exception:
                debug(1, "Warning: unable to get release date.")

    return movie_info

def format_movie_data(movie_info, dir_, file_name, metadata_file_name, tags,
        genre_dir=None):
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

    #vProgramGenre and vSeriesGenre
    for genre in movie_info.get('genres', []):
        line += "vProgramGenre : %s\n" % genre
    for genre in movie_info.get('genres', []):
        line += "vSeriesGenre : %s\n" % genre

    # genre directory linking
    if "genres" in list(movie_info.keys()) and genre_dir:
        link_genres(dir_, genre_dir, file_name, metadata_file_name,
                movie_info['genres']
                )

    # vDirector
    # go through list, omitting duplicates
    director_names = []
    for director in movie_info.get('director', []):
        if director['name'] not in director_names:
            director_names.append(director['name'])
            line += "vDirector : %s|\n" % director['name']
            debug(3, "vDirector : " + director['name'])
    # vWriter
    # go through list, omitting duplicates
    writer_names = []
    for writer in movie_info.get('writer', []):
        if writer['name'] not in writer_names:
            writer_names.append(writer['name'])
            line += "vWriter : %s|\n" % writer['name']
            debug(3, "vWriter : " + writer['name'])
    # vActor
    # go through list, omitting duplicates
    actor_names = []
    for actor in movie_info.get('cast', []):
        if actor['name'] not in actor_names:
            actor_names.append(actor['name'])
            line += "vActor : %s|\n" % actor['name']
            debug(3, "vActor : " + actor['name'])

    debug(2, "Writing to %s" % metadata_file_name)

    # only when we are about to write file make metadata dir (e.g. .meta) if
    #   we need to
    mkdir_if_needed(os.path.dirname(metadata_file_name))
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

def fix_spaces(title):
    placeholders = ['[-._]', '  +']
    for place_holder in placeholders:
        title = re.sub(place_holder, ' ', title)
    # Remove leftover spaces before/after the year
    title = re.sub(r'\( ', '(', title)
    title = re.sub(r' \)', ')', title)
    title = re.sub(r'\(\)', '', title)
    return title

def parse_movie(search_dir, filename, metadata_file_name,
        interactive=False, is_trailer=False, genre_dir=None):
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

    movie_info = get_movie_info(
            title, interactive=interactive, is_trailer=is_trailer
            )

    if movie_info is not None:
        format_movie_data(movie_info, search_dir, filename, metadata_file_name,
                tags, genre_dir=genre_dir
                )

