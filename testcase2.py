#!/usr/bin/env python3

import imdb


imdb_access = imdb.IMDb()

title = "3:10 to Yuma (1957)"
title = "Volver"
title = "Stray Dog"
title = "Seven Samurai"
title = "A Man Called Ove"
title = "Caramel"
title = "The Seventh Seal"
results = imdb_access.search_movie(title)
imdb_movie_info = results[0]

print(imdb_movie_info.movieID)
imdb_access.update(imdb_movie_info)

for key in imdb_movie_info.keys():
    print(key + ": ", end="")
    print(imdb_movie_info[key])
