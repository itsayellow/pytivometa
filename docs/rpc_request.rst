RPC Requests
============

Main Parts
----------

type
~~~~
one of ['offerSearch', 'contentSearch', 'collectionSearch', 'categorySearch']

contentSearch
    Search for a TV epsidoe.  Episode of a TV series is content.  Independent
    of unit.
collectionSearch
    Search for a TV series. Series is represented by a collection.  Independent
    of unit.
offerSearch
    How to obtain content, search the actual unit for information
categorySearch
    Search for category ids
lineupSearch
    Search for TV lineups from various providers

orderBy
~~~~~~~
    Specifies the sort order for the returned objects. Can be
    the name of one of the fields in the returned objects. If more than one
    value is specified, the first is the primary sort order, the second
    specifies the order for objects that match in the first field, etc.
    Putting a hyphen ahead of value reverses order

* 'title'
* '-title'
* 'relevance'
* 'strippedTitle'
* ['seasonNumber', 'episodeNum'],

groupBy
~~~~~~~
will return a list of group objects

* 'collectionId'

Specifying the Search Results Window
------------------------------------
count
    (int) desired number of items, maximum of 50
offset
    (int) an offset from the beginning of the results list, default 0

Filters
-------
keyword
    compares value to title, subtitle, description fields
titleKeyword
    compares value to title field
subtitleKeyword
    compares value to subtitle field
descriptionKeyword
    compares value to description field
titlePrefix
    matches from beginning of title
subtitlePrefix
    matches from beginning of subtitle
parentCategoryId
    only matches in this category (see categorySearch)
objectIdAndType
    list of objectIdAndType values
descriptionLanguage
    seems to only accept one value or gives error.  Beware, difference between
    'English', 'English GB'.  Not sure if 'English US' exists?
collectionType
    one of

* 'series'
* 'movie'
* 'special'
* 'playlist'
* 'song'
* 'webVideo'

Specifying the search results details
-------------------------------------
responseTemplate - set of fields that should be returned::

    "responseTemplate": [
        {
            "type": "responseTemplate",
            "fieldName": ["collection"],
            "typeName": "collectionList"
        },
        {
            "type": "responseTemplate",
            "fieldName": ["collectionId", "title", "movieYear"],
            "fieldInfo": [
                {
                    "type": "responseTemplateFieldInfo",
                    "fieldName": "credit",
                    "maxArity": 2
                }
            ],
            "typeName": "collection"
        },
        {
            "type": "responseTemplate",
            "fieldName": ["first", "last"],
            "typeName": "credit"
        }
    ]

levelOfDetail
    general level of detail

* low - minimal text info, IDs and text
* medium - adds most non-chunky fields
* high - adds the rest of the fields

Annotations
-----------
Include notes in data for follow-up requests

Return values
-------------
isTop
    True if window includes first item in results list (or list is empty)
isBottom
    True if no more results, False if more results than returned

Built-in Types
--------------
int
    "((-?[0-9]+)|(0x[0-9A-Fa-f]+))"
string
    Any UTF-8 character(s).
boolean
    "(true|false)"
date
    "[0-9]{4}-[0-9]{2}-[0-9]{2}"
time
    "([01][0-9]|2[0123]):[0-5][0-9]:[0-5][0-9]"
dateTime
    "[0-9]{4}-[0-9]{2}-[0-9]{2}" + " " + "([01][0-9]|2[0123]):[0-5][0-9]:[0-5][0-9]"
channelNumber
    "[0-9]+(-[0-9]+)?"

Objects
-------
Collection
    Group of related digital media content, e.g TV series (all episodes or 
    selected ones), music album, photo stream.  Members are Content objects.
    Separate collection for each language of a TV series.
Content
    One piece of digital media, e.g. TV show (one episode), movie, song, image.
    Includes all fields of a collection object.
Offer
    How to obtain content, e.g. TV, cable, VOD, download sites like bittorrent,
    etc.  E.g. channel, time, or URL.  Includes content type, provider, cost,
    access rights.  Content has zero or more offers associated.  Includes
    all the fields of a content object.
Recording
    Contains actual bits of media on unit specified by offer object. Includes
    all the fields of an offer object.
Category
    Classification of content, e.g. "Movies", "Comedy", part of read-only
    hierarchy.

ObjectIDs
---------
'objectId' field.  Globally unique identifier: bodyId, contentId, collectionId.

Format
~~~~~~
tivo:<type>[.<namespace>].<id>

e.g. tivo:cl.351131803 - collectionId of series 'Friends and Enemeies'
e.g. tivo:ct.22345 - contentId of
e.g. epgProvider:cl.SH0351131803 - collectionId of series 'Friends and Enemies
e.g. tivo:ca.349301 - categoryId

All rpc_request fiels seen in the wild
--------------------------------------
::

    req = rpc_request('collectionSearch',
        keyword=keywords,
        orderBy='strippedTitle',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        levelOfDetail='medium',
        count=count,
        mergeOverridingCollections='true',
        filterUnavailable='false',
        collectionType='series'
    )

    req = rpc_request('collectionSearch',
        keyword=keywords,
        orderBy='strippedTitle',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        levelOfDetail='medium',
        count=count,
        mergeOverridingCollections='true',
        filterUnavailable='false'
    )

    req = rpc_request('contentSearch',
        offset=offset,
        #filterUnavailable = 'false',
        count=25,
        orderBy=['seasonNumber', 'episodeNum'],
        levelOfDetail='medium',
        collectionId=collection_id
    )

    req = rpc_request('contentSearch',
        collectionId=collection_id,
        title=title,
        seasonNumber=season,
        episodeNum=episode,
        count=1,
    )

    req = rpc_request('contentSearch',
        collectionId=collection_id,
        title=title,
        seasonNumber=season,
        episodeNum=str(episode_num),
        count=1,
    )

    req = rpc_request('offerSearch',
        offset=offset,
        count=25,
        namespace='trioserver',
        levelOfDetail='medium',
        collectionId=collection_id
    )

    req = rpc_request('offerSearch',
        count=25,
        bodyId=body_id,
        title=title,
        subtitle=subtitle
    )

    req = rpc_request('offerSearch',
        count=25,
        bodyId=body_id,
        title=title
    )
