#!/usr/bin/env python3

import imdb


imdb_access = imdb.IMDb()

title = "3:10 to Yuma (1957)"
results = imdb_access.search_movie(title)
imdb_movie_info = results[0]

print(imdb_movie_info.movieID)
imdb_access.update(imdb_movie_info)

print("AKAs:")
print(imdb_movie_info.get('akas', ''))
print("")

