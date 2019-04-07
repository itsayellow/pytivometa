#!/usr/bin/env python3

import imdb
import textwrap


def indent(text):
    return textwrap.indent(
            "\n".join(textwrap.wrap(str(text), 75)),
            "    "
            )


imdb_access = imdb.IMDb()

title = "3:10 to Yuma (1957)"
results = imdb_access.search_movie(title)
searched_movie = results[0]
print(searched_movie.movieID)
base_keys = set(searched_movie.keys())
print(base_keys)
for infoset in imdb_access.get_movie_infoset():
    imdb_movie_info = imdb_access.get_movie(searched_movie.movieID)
    base_keys = set(imdb_movie_info.keys())
    imdb_access.update(imdb_movie_info, info=infoset)
    new_keys = set(imdb_movie_info.keys()) - base_keys
    print("Infoset: " + infoset)
    print("Keys: " + str(new_keys))
    print("")

print("Year:")
print(indent(imdb_movie_info['year']))
print("")
print("Director:")
print(indent(imdb_movie_info['director']))
print("")
print("Outline:")
print(indent(imdb_movie_info['plot outline']))
print("")
print("Rating:")
print(indent(imdb_movie_info['rating']))
print("")
print("MPAA:")
print(indent(imdb_movie_info.get('mpaa', '')))
print("")
print("Genres:")
print(indent(imdb_movie_info['genres']))
print("")
print("Director:")
print(indent(imdb_movie_info['director']))
print("")
print("Writer:")
print(indent(imdb_movie_info['writer']))
print("")
print("Cast:")
print(indent(imdb_movie_info['cast']))
print("")
print("AKAs:")
print(indent(imdb_movie_info.get('akas', '')))
print("")

movie_info = {}
print(type(imdb_movie_info))
print(dir(imdb_movie_info))
print(imdb_movie_info.keys())
for key in imdb_movie_info.keys():
    print(key + ": ", end="")
    print(imdb_movie_info[key])
    movie_info[key] = imdb_movie_info[key]
