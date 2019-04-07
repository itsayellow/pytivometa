#!/usr/bin/env python3

import imdb

imdb_access = imdb.IMDb()

title = "The Seventh Seal"
results = imdb_access.search_movie(title)
imdb_movie_info = results[0]

print(imdb_movie_info.movieID)
imdb_access.update(imdb_movie_info)

for key in imdb_movie_info.keys():
    try:
        _ = imdb_movie_info[key]
    except KeyError:
        print(key + " is in list of keys(), but cannot be accessed.")
